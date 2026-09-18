"""
CLARIFY — pause point.

The graph is compiled with `interrupt_before=["clarify"]`, so when the input
router sends us here, LangGraph persists state and returns control to the
caller.  A human (or an upstream system) supplies the missing info via
POST /runs/{id}/approve, which resumes the graph at `input_validation`.

This node's job is minimal: clear the clarification flag so the re-entered
input_validation doesn't loop forever on the same ambiguity.
"""
from __future__ import annotations

from ...infra.logging import get_logger
from ...state.schema import GraphState

log = get_logger("node.clarify")


async def clarify_node(state: GraphState) -> dict:
    log.info(
        "clarify resume — request=%r platforms=%s",
        (state.get("request") or "")[:60],
        state.get("platforms", []),
    )
    return {"clarification_needed": False}