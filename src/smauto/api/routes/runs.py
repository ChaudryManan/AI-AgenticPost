"""
Run lifecycle endpoints.

    POST /runs            create a run, invoke the graph up to the first
                          interrupt (or completion)
    GET  /runs/{id}       fetch current status + state + interrupt info
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException

from ...graph.interrupts import (
    APPROVAL_INTERRUPT,
    CLARIFY_INTERRUPT,
    approval_payload,
    clarify_payload,
)
from ...infra.logging import get_logger
from ...storage.db.repositories import RunRepo
from ..deps import get_graph
from ..schemas.requests import CreateRun
from ..schemas.responses import RunCreated, RunStatus

router = APIRouter(prefix="/runs", tags=["runs"])
log = get_logger("api.runs")


def _detect_interrupt(state: dict) -> dict | None:
    """
    Figure out whether the graph stopped at an interrupt point.

    LangGraph surfaces interrupts in state["__interrupt__"], but the exact
    shape varies.  We construct a friendly payload based on the state's own
    flags instead of relying on the internal representation.
    """
    # if the graph is paused before `clarify`, the state has
    # clarification_needed=True and hasn't yet run planner
    if state.get("clarification_needed") and not state.get("plan"):
        return clarify_payload(state)
    # if the graph is paused before `approval`, QA has passed and no
    # publish_results exist yet
    if (state.get("qa") or {}).get("passed") and not state.get("publish_results"):
        return approval_payload(state)
    return None


@router.post("", response_model=RunCreated)
async def create_run(body: CreateRun,
                     graph=Depends(get_graph)) -> RunCreated:
    run_id = uuid.uuid4().hex[:12]

    init: dict = {
        "run_id": run_id,
        "request": body.request,
        "content_type": body.content_type or "text",
        "platforms": body.platforms or [],
    }

    try:
        RunRepo.upsert(run_id, body.request, init["content_type"],
                       init["platforms"], status="running", state=init)
    except Exception as e:  # noqa: BLE001
        log.warning("RunRepo.upsert failed: %s", e)

    config = {"configurable": {"thread_id": run_id}}

    try:
        final_state = await graph.ainvoke(init, config)
    except Exception as e:  # noqa: BLE001
        log.exception("graph failed for run %s", run_id)
        try:
            RunRepo.upsert(run_id, body.request, init["content_type"],
                           init["platforms"], status="error",
                           state={"error": str(e)})
        except Exception:  # noqa: BLE001
            pass
        raise HTTPException(status_code=500, detail=f"graph failed: {e}") from e

    interrupt = _detect_interrupt(final_state)
    status = "awaiting_approval" if interrupt else "done"

    try:
        RunRepo.upsert(run_id, body.request,
                       final_state.get("content_type", init["content_type"]),
                       final_state.get("platforms", init["platforms"]),
                       status=status, state=final_state)
    except Exception as e:  # noqa: BLE001
        log.warning("RunRepo.upsert(final) failed: %s", e)

    log.info("run %s finished status=%s interrupt=%s",
             run_id, status, (interrupt or {}).get("kind"))

    return RunCreated(run_id=run_id, status=status, interrupt=interrupt)


@router.get("/{run_id}", response_model=RunStatus)
async def get_run(run_id: str,
                  graph=Depends(get_graph)) -> RunStatus:
    config = {"configurable": {"thread_id": run_id}}

    # prefer the live graph state if the thread exists in the checkpointer
    try:
        snapshot = await graph.aget_state(config)
        state = dict(snapshot.values or {})
        if state:
            interrupt = _detect_interrupt(state)
            status = "awaiting_approval" if interrupt else (
                "escalated" if state.get("escalate") else "done")
            return RunStatus(run_id=run_id, status=status, state=state,
                             interrupt=interrupt)
    except Exception as e:  # noqa: BLE001
        log.warning("graph.aget_state failed for %s: %s", run_id, e)

    # fall back to the DB record
    r = RunRepo.get(run_id)
    if not r:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")

    return RunStatus(run_id=run_id, status=r["status"], state=r["state"],
                     interrupt=None)