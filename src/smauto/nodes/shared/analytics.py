"""
ANALYTICS — pull metrics for each successful post.

This runs synchronously as part of the graph so the run record captures
whatever the platforms return immediately.  Deeper pulls (t+1h, t+24h,
t+7d) are handled by the metrics worker on a schedule.
"""
from __future__ import annotations

from ...infra.logging import get_logger
from ...services.publishers import get_publisher
from ...state.schema import GraphState
from ...storage.db.repositories import MetricRepo

log = get_logger("node.analytics")


async def analytics_node(state: GraphState) -> dict:
    pulls: list[dict] = []
    results = state.get("publish_results") or []

    for r in results:
        if r.get("status") != "ok" or not r.get("post_id"):
            continue

        platform = r.get("platform") or ""
        post_id = r.get("post_id") or ""

        try:
            pub = get_publisher(platform)
            metrics = await pub.fetch_metrics(post_id)
            pulls.append({"platform": platform, "post_id": post_id,
                          "metrics": metrics})
            try:
                MetricRepo.add(post_id, "immediate", metrics)
            except Exception as e:  # noqa: BLE001
                log.warning("metric persist failed for %s: %s", post_id, e)
        except Exception as e:  # noqa: BLE001
            log.warning("metric pull failed for %s/%s: %s", platform, post_id, e)
            pulls.append({"platform": platform, "post_id": post_id,
                          "error": str(e)[:200]})

    log.info("analytics done pulls=%d", len(pulls))

    plan = dict(state.get("plan") or {})
    plan["_analytics"] = pulls
    return {"plan": plan}