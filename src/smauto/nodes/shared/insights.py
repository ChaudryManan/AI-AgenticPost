"""
INSIGHTS — write a feedback blob for the next run's planner.

Each run drops a JSON file under runs/_feedback/<run_id>.json.  The planner
could (optionally) read recent blobs and feed them in as few-shot examples.
We don't wire that into the planner yet — just collect the data so it's
ready when you want it.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from ...config.settings import get_settings
from ...infra.logging import get_logger
from ...state.schema import GraphState

log = get_logger("node.insights")


async def insights_node(state: GraphState) -> dict:
    s = get_settings()
    store = s.artifact_root / "_feedback"
    store.mkdir(parents=True, exist_ok=True)

    strategy = state.get("strategy") or {}
    plan = state.get("plan") or {}

    blob = {
        "run_id": state.get("run_id"),
        "at": datetime.now(timezone.utc).isoformat(),
        "content_type": state.get("content_type"),
        "platforms": state.get("platforms", []),
        "hook": strategy.get("hook"),
        "tone": strategy.get("tone"),
        "qa_passed": (state.get("qa") or {}).get("passed"),
        "revision_count": state.get("revision_count", 0),
        "publish_results": state.get("publish_results", []),
        "analytics": plan.get("_analytics", []),
    }

    run_id = state.get("run_id") or "unknown"
    out = store / f"{run_id}.json"
    try:
        out.write_text(json.dumps(blob, indent=2, default=str), encoding="utf-8")
        log.info("insights written -> %s", out)
    except Exception as e:  # noqa: BLE001
        log.warning("insights write failed: %s", e)

    return {}