"""
REVISION — bump the counter, clear hard failures, let the router send
control back to the appropriate branch.

This node deliberately does NOT try to fix content itself.  When the router
sends us back to `script` or `copywriter`, those nodes re-read state
(including the failures we just cleared) and regenerate.  If you want them
to *see* the failures as context, extend their .j2 templates to accept
`state.qa.failures`.
"""
from __future__ import annotations

from ...config.settings import get_settings
from ...infra.logging import get_logger
from ...state.schema import GraphState

log = get_logger("node.revision")


async def revision_node(state: GraphState) -> dict:
    s = get_settings()
    n = int(state.get("revision_count", 0)) + 1

    if n > s.max_revisions:
        log.warning("revision_count=%d exceeds max=%d — escalating", n, s.max_revisions)
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

    # clear QA failures so the branch regenerates cleanly.  `passed=False`
    # forces the router to loop; the branch nodes will overwrite content.
    return {
        "revision_count": n,
        "qa": {"passed": False, "failures": [], "checked_at": None},
        "needs_revision": True,
    }