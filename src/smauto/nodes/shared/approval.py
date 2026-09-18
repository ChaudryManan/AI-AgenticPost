"""
APPROVAL — human-in-the-loop gate.

The graph compiles with `interrupt_before=["approval"]`, so we never enter
this node until a human has resumed the run via POST /runs/{id}/approve.

By the time we get here, the API has already set state["approval"] =
{status, notes, editor}.  Our job is just to persist an audit trail.
"""
from __future__ import annotations

from ...infra.logging import get_logger
from ...state.schema import GraphState
from ...storage.db.repositories import ApprovalRepo

log = get_logger("node.approval")


async def approval_node(state: GraphState) -> dict:
    a = dict(state.get("approval") or {})
    status = a.get("status") or "pending"

    run_id = state.get("run_id")
    if run_id:
        try:
            ApprovalRepo.add(
                run_id=run_id,
                status=status,
                notes=a.get("notes"),
                editor=a.get("editor"),
            )
        except Exception as e:  # noqa: BLE001
            log.warning("failed to persist approval: %s", e)

    log.info("approval status=%s editor=%s", status, a.get("editor"))

    # clear needs_revision if approved — the router uses approval.status, but
    # this keeps state tidy for anything that inspects it downstream
    if status == "approved":
        return {"needs_revision": False}

    return {}