"""Revision-loop control flow — routers + revision node."""
from __future__ import annotations

from smauto.config.settings import get_settings
from smauto.graph.routers import qa_router, revision_router
from smauto.nodes.shared.revision import revision_node


async def test_revision_node_bumps_counter():
    out = await revision_node({"revision_count": 0})
    assert out["revision_count"] == 1
    assert out["qa"]["failures"] == []
    assert out["qa"]["passed"] is False


async def test_revision_node_escalates_past_max():
    max_rev = get_settings().max_revisions
    out = await revision_node({"revision_count": max_rev})
    assert out.get("escalate") is True
    assert out["errors"][0]["type"] == "max_revisions_exceeded"


def test_qa_loop_progresses_through_revisions():
    """Simulate the router's decision at each revision count."""
    max_rev = get_settings().max_revisions

    # failing QA → revise until we hit the max
    for count in range(max_rev):
        state = {"qa": {"passed": False}, "revision_count": count}
        assert qa_router(state) == "revise", f"count={count}"

    # at max → escalate
    state = {"qa": {"passed": False}, "revision_count": max_rev}
    assert qa_router(state) == "escalate"


def test_qa_pass_routes_to_approval_regardless_of_count():
    for count in range(5):
        state = {"qa": {"passed": True}, "revision_count": count}
        assert qa_router(state) == "approve"


def test_revision_routes_back_to_correct_branch():
    assert revision_router({"content_type": "video"}) == "video"
    assert revision_router({"content_type": "text"}) == "text"
    assert revision_router({"content_type": "both"}) == "both"