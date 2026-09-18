"""
Conditional edge functions.

Each router takes the current GraphState and returns a string — the name
of the next node (or one of the keys in the conditional-edges mapping).
Keep these pure and side-effect free.
"""
from __future__ import annotations

from ..config.settings import get_settings
from ..state.schema import GraphState


def input_router(state: GraphState) -> str:
    """After INPUT_VALIDATION: escalate, clarify, or continue."""
    if state.get("escalate"):
        return "end"
    if state.get("clarification_needed"):
        return "clarify"
    return "plan"


def research_router(state: GraphState) -> str:
    """
    After RESEARCH: re-query if confidence is low and we haven't exceeded
    the requery budget.  Otherwise continue to STRATEGY.
    """
    r = state.get("research") or {}
    conf = float(r.get("confidence", 1.0))
    requery_count = int(r.get("requery_count", 0))
    max_requeries = get_settings().research_requery_max

    if conf < 0.5 and requery_count < max_requeries:
        return "requery"
    return "continue"


def content_router(state: GraphState) -> str:
    """
    After STRATEGY: which branch(es) to run.
    Keys must match the conditional-edges mapping in builder.py.
    """
    ct = state.get("content_type", "text")
    if ct == "video":
        return "video"
    if ct == "text":
        return "text"
    return "both"


def qa_router(state: GraphState) -> str:
    """
    After QA: approve, revise, or escalate.

    Escalation happens when we've hit the max revision budget AND QA is
    still failing.  Otherwise, a failed QA loops back through revision.
    """
    qa = state.get("qa") or {}
    if qa.get("passed"):
        return "approve"

    s = get_settings()
    if int(state.get("revision_count", 0)) >= s.max_revisions:
        return "escalate"

    return "revise"


def revision_router(state: GraphState) -> str:
    """After REVISION: send control back to the appropriate branch."""
    ct = state.get("content_type", "text")
    if ct == "video":
        return "video"
    if ct == "text":
        return "text"
    return "both"


def approval_router(state: GraphState) -> str:
    """After APPROVAL: publish, revise, or pause."""
    a = state.get("approval") or {}
    status = a.get("status")
    if status == "approved":
        return "publish"
    if status == "rejected":
        return "revise"
    return "pause"