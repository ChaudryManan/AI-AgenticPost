"""
REVISION — bump the counter, clear hard failures, let the router send
control back to the appropriate branch.

Two modes:
  • automated — QA failed, loop back to regenerate, count against budget
  • manual   — user clicked "Edit" on the frontend, same loop but no budget
"""
from __future__ import annotations

from ...config.settings import get_settings
from ...infra.logging import get_logger
from ...state.schema import GraphState

log = get_logger("node.revision")


async def revision_node(state: GraphState) -> dict:
    # ── user-driven edit ──────────────────────────────────────────────
    if state.get("manual_edit"):
        log.info("user-driven edit — resetting revision count")
        return {
            "revision_count": 0,
            "qa": {"passed": False, "failures": [], "checked_at": None},
            "needs_revision": True,
            "manual_edit": False,   # clear the flag
        }

    # ── automated revision ────────────────────────────────────────────
    s = get_settings()
    n = int(state.get("revision_count", 0)) + 1

    if n > s.max_revisions:
        log.warning("revision_count=%d exceeds max=%d — escalating",
                    n, s.max_revisions)
        return {
            "revision_count": n,
            "escalate": True,
            "errors": [{
                "node": "revision",
                "type": "max_revisions_exceeded",
                "detail": f"reached {n} revisions",
            }],
        }

    log.info("revision #%d — clearing failures, routing back to branch", n)
    return {
        "revision_count": n,
        "qa": {"passed": False, "failures": [], "checked_at": None},
        "needs_revision": True,
    }