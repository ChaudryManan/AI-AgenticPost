"""
PUBLISH — send the approved artifacts to every target platform.

This is where the typed-error taxonomy pays off:
    RateLimited    → dead-letter, keep going
    AuthFailed     → dead-letter, keep going (needs human re-auth)
    PublishError   → dead-letter, keep going
    Unexpected     → dead-letter, keep going

We never abort the whole run because one platform rejected us — the other
platforms still deserve their post.  Failures are surfaced in
publish_results and errors, and dead-lettered for ops.
"""
from __future__ import annotations

from pathlib import Path

from ...infra.dead_letter import dead_letter
from ...infra.errors import AuthFailed, PublishError, RateLimited
from ...infra.logging import get_logger
from ...infra.retry import async_retry
from ...services.publishers import get_publisher
from ...services.publishers.base import PublishResult
from ...state.schema import GraphState
from ...storage.db.repositories import PostRepo

log = get_logger("node.publish")


async def _publish_one(platform: str,
                       body: str,
                       media: list[Path] | None,
                       hashtags: list[str],
                       run_id: str | None) -> dict:
    """Publish to a single platform with retry + error classification."""

    try:
        pub = get_publisher(platform)
    except KeyError as e:
        log.error("unknown publisher %s: %s", platform, e)
        dead_letter("publish", {"run_id": run_id, "platform": platform,
                                "error": f"unknown publisher: {e}"})
        return {"platform": platform, "status": "error",
                "post_id": None, "url": None,
                "error": f"unknown publisher: {e}"}

    # rate-limit-aware retry wrapper
    @async_retry(times=3, base=1.0)
    async def _go() -> PublishResult:
        return await pub.publish(body=body, media=media, hashtags=hashtags)

    try:
        result = await _go()
        log.info("publish ok %s id=%s", platform, result.post_id)
        return {
            "platform": result.platform,
            "post_id": result.post_id,
            "url": result.url,
            "status": result.status,
            "error": result.error,
        }
    except RateLimited as e:
        log.warning("publish rate-limited on %s: %s", platform, e)
        dead_letter("rate_limit", {"run_id": run_id, "platform": platform,
                                   "detail": str(e)[:500]})
        return {"platform": platform, "status": "error", "post_id": None,
                "url": None, "error": "rate_limit"}

    except AuthFailed as e:
        log.warning("publish auth failed on %s: %s", platform, e)
        dead_letter("auth", {"run_id": run_id, "platform": platform,
                             "detail": str(e)[:500]})
        return {"platform": platform, "status": "error", "post_id": None,
                "url": None, "error": "auth"}

    except PublishError as e:
        log.warning("publish format/reject on %s: %s", platform, e)
        dead_letter("publish", {"run_id": run_id, "platform": platform,
                                "detail": str(e)[:500]})
        return {"platform": platform, "status": "error", "post_id": None,
                "url": None, "error": str(e)[:200]}

    except Exception as e:  # noqa: BLE001
        log.exception("publish unexpected error on %s", platform)
        dead_letter("publish", {"run_id": run_id, "platform": platform,
                                "detail": f"{type(e).__name__}: {e}"})
        return {"platform": platform, "status": "error", "post_id": None,
                "url": None, "error": f"{type(e).__name__}: {e}"[:200]}


async def publish_node(state: GraphState) -> dict:
    ts = state.get("text_state") or {}
    vs = state.get("video_state") or {}
    run_id = state.get("run_id")

    # hashtags: prefer text branch, fall back to video branch
    hashtags = list(ts.get("hashtags") or vs.get("hashtags") or [])

    # media: attach the final video (if any) + any images
    media: list[Path] = []
    if vs.get("render_path"):
        p = Path(vs["render_path"])
        if p.exists():
            media.append(p)
    for img in ts.get("image_paths", []) or []:
        p = Path(img)
        if p.exists():
            media.append(p)

    platforms = state.get("platforms") or []
    if not platforms:
        log.warning("publish called with no platforms")
        return {"publish_results": []}

    results: list[dict] = []
    for platform in platforms:
        # body: platform_formatter output wins, else video caption, else request
        body = (
            (ts.get("platform_bodies") or {}).get(platform)
            or vs.get("caption")
            or state.get("request", "")
        )

        r = await _publish_one(platform, body, media or None, hashtags, run_id)
        results.append(r)

        # persist successes to the registry
        if r["status"] == "ok" and r.get("post_id") and run_id:
            try:
                PostRepo.add(r["post_id"], run_id, platform, r.get("url"))
            except Exception as e:  # noqa: BLE001
                log.warning("failed to persist post %s: %s", r["post_id"], e)

    log.info("publish done results=%d ok=%d",
             len(results), sum(1 for r in results if r["status"] == "ok"))

    return {"publish_results": results}