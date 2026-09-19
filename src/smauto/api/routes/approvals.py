"""
Approval and clarification resume endpoints.

    POST /runs/{id}/approve      approve / reject / edit — resume the graph
    POST /runs/{id}/clarify      answer the clarification question and resume
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from ..schemas.requests import ApprovalDecision, ClarifyAnswer, EditRequest
from ...infra.logging import get_logger
from ...storage.db.repositories import ApprovalRepo, RunRepo
from ..deps import get_graph
from ..schemas.requests import ApprovalDecision, ClarifyAnswer
from ..schemas.responses import ApprovalResponse

router = APIRouter(prefix="/runs", tags=["approvals"])
log = get_logger("api.approvals")


@router.post("/{run_id}/approve", response_model=ApprovalResponse)
async def approve_run(run_id: str,
                      body: ApprovalDecision,
                      graph=Depends(get_graph)) -> ApprovalResponse:
    config = {"configurable": {"thread_id": run_id}}

    # write the decision into the graph state before resuming
    try:
        await graph.aupdate_state(config, {
            "approval": {
                "status": body.status,
                "notes": body.notes,
                "editor": body.editor,
            },
        })
    except Exception as e:  # noqa: BLE001
        log.exception("aupdate_state failed for %s", run_id)
        raise HTTPException(status_code=500,
                            detail=f"failed to update state: {e}") from e

    # persist the decision
    try:
        ApprovalRepo.add(run_id, body.status, body.notes, body.editor)
    except Exception as e:  # noqa: BLE001
        log.warning("ApprovalRepo.add failed: %s", e)

    # resume
    try:
        final_state = await graph.ainvoke(None, config)
    except Exception as e:  # noqa: BLE001
        log.exception("resume failed for %s", run_id)
        raise HTTPException(status_code=500,
                            detail=f"resume failed: {e}") from e

    try:
        RunRepo.upsert(run_id,
                       final_state.get("request", ""),
                       final_state.get("content_type", "text"),
                       final_state.get("platforms", []),
                       status="done", state=final_state)
    except Exception as e:  # noqa: BLE001
        log.warning("RunRepo.upsert after resume failed: %s", e)

    next_step = {
        "approved": "publishing",
        "rejected": "revising",
        "edited": "pausing",
    }.get(body.status, "unknown")

    log.info("run %s approved status=%s next=%s", run_id, body.status, next_step)
    return ApprovalResponse(run_id=run_id, status=body.status,
                            next_step=next_step)


@router.post("/{run_id}/clarify", response_model=ApprovalResponse)
async def clarify_run(run_id: str,
                      body: ClarifyAnswer,
                      graph=Depends(get_graph)) -> ApprovalResponse:
    """
    Answer a clarification question.  We append the answer to the request
    and clear the clarification flag so input_validation re-runs cleanly.
    """
    config = {"configurable": {"thread_id": run_id}}

    try:
        snapshot = await graph.aget_state(config)
        current = dict(snapshot.values or {})
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=404,
                            detail=f"run {run_id} not found: {e}") from e

    if not current:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")

    original = current.get("request", "")
    updated_request = f"{original} — additional info: {body.answer}"

    try:
        await graph.aupdate_state(config, {
            "request": updated_request,
            "clarification_needed": False,
        })
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500,
                            detail=f"failed to update state: {e}") from e

    try:
        final_state = await graph.ainvoke(None, config)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500,
                            detail=f"resume failed: {e}") from e

    try:
        RunRepo.upsert(run_id, updated_request,
                       final_state.get("content_type", "text"),
                       final_state.get("platforms", []),
                       status="running", state=final_state)
    except Exception as e:  # noqa: BLE001
        log.warning("RunRepo.upsert after clarify failed: %s", e)

    return ApprovalResponse(run_id=run_id, status="clarified",
                            next_step="resumed")


@router.post("/{run_id}/edit", response_model=ApprovalResponse)
async def edit_run(run_id: str,
                   body: EditRequest,
                   graph=Depends(get_graph)) -> ApprovalResponse:
    """
    Apply user feedback to the current draft and resume the graph.

    Sets `revision_feedback` + `manual_edit` + a rejected approval so the
    graph loops through revision → copywriter → QA → approval again, this
    time with the feedback visible to the copywriter.
    """
    config = {"configurable": {"thread_id": run_id}}

    try:
        await graph.aupdate_state(config, {
            "revision_feedback": body.feedback,
            "manual_edit": True,
            "approval": {
                "status": "rejected",
                "notes": body.feedback,
                "editor": body.editor or "edit-ui",
            },
        })
    except Exception as e:  # noqa: BLE001
        log.exception("aupdate_state failed for %s", run_id)
        raise HTTPException(status_code=500,
                            detail=f"failed to update state: {e}") from e

    try:
        final_state = await graph.ainvoke(None, config)
    except Exception as e:  # noqa: BLE001
        log.exception("edit resume failed for %s", run_id)
        raise HTTPException(status_code=500,
                            detail=f"resume failed: {e}") from e

    # save the audit trail
    try:
        ApprovalRepo.add(run_id, "edited", body.feedback, body.editor)
    except Exception as e:  # noqa: BLE001
        log.warning("ApprovalRepo.add failed: %s", e)

    # figure out what the graph did
    qa_passed = (final_state.get("qa") or {}).get("passed", False)
    next_step = "awaiting_approval" if qa_passed else "revising"

    log.info("run %s edited — next=%s", run_id, next_step)
    return ApprovalResponse(run_id=run_id, status="edited", next_step=next_step)