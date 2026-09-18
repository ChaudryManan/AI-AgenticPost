"""
SCENE GENERATE — parallel generation of all clips.

Fans out over scene_prompts with a semaphore so we don't hammer Replicate.
Failures are captured per-clip; scene_check handles retry + fallback.
"""
from __future__ import annotations

import asyncio

from ...infra.logging import get_logger
from ...infra.tracing import span
from ...services.media import generate_clip
from ...state.schema import GraphState
from ...storage.paths import ensure_run_dirs

log = get_logger("node.scene_generate")

_CONCURRENCY = 3


async def scene_generate_node(state: GraphState) -> dict:
    vs = dict(state.get("video_state") or {})
    prompts = vs.get("scene_prompts") or []
    bible = vs.get("style_bible") or {}
    seed = bible.get("seed")

    if not prompts:
        log.warning("scene_generate called with no prompts")
        vs["clips"] = []
        return {"video_state": vs}

    run_id = state.get("run_id")
    if not run_id:
        # without a run_id we can't lay down files anywhere sane
        vs["clips"] = []
        return {"video_state": vs, "errors": [{
            "node": "scene_generate", "type": "missing_run_id",
        }]}

    paths = ensure_run_dirs(run_id)
    sem = asyncio.Semaphore(_CONCURRENCY)

    async def one(p: dict) -> dict:
        sid = int(p.get("scene_id", 0))
        out = paths["scenes"] / f"scene_{sid:02d}.mp4"
        async with sem:
            try:
                with span("scene_generate.clip", scene=sid):
                    await generate_clip(
                        prompt=p.get("prompt", ""),
                        out_path=out,
                        duration=6.0,
                        seed=seed,
                    )
                return {"scene_id": sid, "path": str(out),
                        "status": "ok", "attempts": 1}
            except Exception as e:  # noqa: BLE001
                log.warning("scene %d generation failed: %s", sid, e)
                return {"scene_id": sid, "path": "",
                        "status": f"error:{type(e).__name__}",
                        "attempts": 1,
                        "fallback_reason": str(e)[:200]}

    with span("node.scene_generate", n=len(prompts)):
        clips = list(await asyncio.gather(*(one(p) for p in prompts)))

    vs["clips"] = clips
    ok = sum(1 for c in clips if c["status"] == "ok")
    log.info("scene_generate done ok=%d/%d", ok, len(clips))
    return {"video_state": vs}