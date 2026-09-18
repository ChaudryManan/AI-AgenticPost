"""
SCHEDULER — stamp the run with a target posting time.

The plan already contains `posting_time_utc` from the planner.  This node
just promotes it to a first-class field so downstream workers can read it
without drilling into plan.
"""
from __future__ import annotations

from datetime import datetime, timezone

from ...infra.logging import get_logger
from ...state.schema import GraphState

log = get_logger("node.scheduler")


async def scheduler_node(state: GraphState) -> dict:
    plan = dict(state.get("plan") or {})
    scheduled_at = plan.get("posting_time_utc")

    if not scheduled_at:
        scheduled_at = datetime.now(timezone.utc).isoformat()

    plan["scheduled_at"] = scheduled_at
    log.info("scheduler scheduled_at=%s", scheduled_at)
    return {"plan": plan}