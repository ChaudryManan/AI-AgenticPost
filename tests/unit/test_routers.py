"""Router logic — pure functions over state dicts."""
from __future__ import annotations

from smauto.graph.routers import (
    approval_router,
    content_router,
    input_router,
    qa_router,
    research_router,
    revision_router,
)


# ── input_router ──────────────────────────────────────────────────────

def test_input_router_escalate():
    assert input_router({"escalate": True}) == "end"


def test_input_router_clarify():
    assert input_router({"clarification_needed": True}) == "clarify"


def test_input_router_plan():
    assert input_router({}) == "plan"


# ── research_router ───────────────────────────────────────────────────

def test_research_router_low_confidence_requeries():
    state = {"research": {"confidence": 0.2, "requery_count": 0}}
    assert research_router(state) == "requery"


def test_research_router_requery_budget_exhausted():
    state = {"research": {"confidence": 0.2, "requery_count": 5}}
    assert research_router(state) == "continue"


def test_research_router_high_confidence_continues():
    state = {"research": {"confidence": 0.9, "requery_count": 0}}
    assert research_router(state) == "continue"


# ── content_router ────────────────────────────────────────────────────

def test_content_router_video():
    assert content_router({"content_type": "video"}) == "video"


def test_content_router_text():
    assert content_router({"content_type": "text"}) == "text"


def test_content_router_both():
    assert content_router({"content_type": "both"}) == "both"


# ── qa_router ─────────────────────────────────────────────────────────

def test_qa_router_pass():
    assert qa_router({"qa": {"passed": True}}) == "approve"


def test_qa_router_revise_when_under_budget():
    state = {"qa": {"passed": False}, "revision_count": 1}
    assert qa_router(state) == "revise"


def test_qa_router_escalate_at_max_revisions():
    from smauto.config.settings import get_settings
    max_rev = get_settings().max_revisions
    state = {"qa": {"passed": False}, "revision_count": max_rev}
    assert qa_router(state) == "escalate"


# ── revision_router ───────────────────────────────────────────────────

def test_revision_router_video():
    assert revision_router({"content_type": "video"}) == "video"


def test_revision_router_text():
    assert revision_router({"content_type": "text"}) == "text"


def test_revision_router_both():
    assert revision_router({"content_type": "both"}) == "both"


# ── approval_router ───────────────────────────────────────────────────

def test_approval_router_approved():
    assert approval_router({"approval": {"status": "approved"}}) == "publish"


def test_approval_router_rejected():
    assert approval_router({"approval": {"status": "rejected"}}) == "revise"


def test_approval_router_pending():
    assert approval_router({"approval": {}}) == "pause"


def test_approval_router_missing():
    assert approval_router({}) == "pause"