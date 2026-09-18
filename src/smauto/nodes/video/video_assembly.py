"""
VIDEO ASSEMBLY — concat the good clips in scene order.

Skips any clip marked "fallback".  If fewer than 2 clips remain, we bail
without producing an assembly and let QA flag it.
"""
from __future__ import annotations

from pathlib import Path

from ...infra.logging import get_logger
from ...infra.tracing import span
from ...services.media import concat
from ...state.schema import GraphState
from ...storage.paths import ensure_run_dirs

log = get_logger("node.video_assembly")


async def video_assembly_node(state: GraphState) -> dict:
    vs = dict(state.get("video_state") or {})
    run_id = state.get("run_id")
    if not run_id:
        return {"video_state": vs}

    clips = sorted(vs.get("clips") or [], key=lambda c: int(c.get("scene_id", 0)))
    good = [Path(c["path"]) for c in clips
            if c.get("status") == "ok" and c.get("path")]

    if len(good) < 2:
        log.warning("assembly skipped: only %d usable clips", len(good))
        vs["_assembled"] = None
        return {"video_state": vs}

    paths = ensure_run_dirs(run_id)
    out = paths["render"] / "assembled.mp4"

    with span("node.video_assembly", n=len(good)):
        await concat(good, out)

    vs["_assembled"] = str(out)
    log.info("assembly done n=%d -> %s", len(good), out)
    return {"video_state": vs}