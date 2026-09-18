"""
SUBTITLES — SRT from the audio timestamps.

Delegates to services/media/align.forced_align_to_srt.
"""
from __future__ import annotations

from ...infra.logging import get_logger
from ...services.media import forced_align_to_srt
from ...state.schema import GraphState
from ...storage.paths import ensure_run_dirs

log = get_logger("node.subtitles")


async def subtitles_node(state: GraphState) -> dict:
    vs = dict(state.get("video_state") or {})
    run_id = state.get("run_id")
    stamps = vs.get("audio_timestamps") or []

    if not run_id or not stamps:
        vs["subtitles_path"] = None
        return {"video_state": vs}

    paths = ensure_run_dirs(run_id)
    out = paths["subtitles"] / "captions.srt"

    forced_align_to_srt(stamps, out)
    vs["subtitles_path"] = str(out)
    log.info("subtitles done -> %s", out)
    return {"video_state": vs}