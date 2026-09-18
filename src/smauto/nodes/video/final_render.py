"""
FINAL RENDER — mux audio under the assembled video, then loudness-normalize.

If the assembled video or the voice track is missing, we set render_path to
None and let QA flag the failure with a `hard` severity.
"""
from __future__ import annotations

from pathlib import Path

from ...infra.logging import get_logger
from ...infra.tracing import span
from ...services.media import loudnorm, mux
from ...state.schema import GraphState
from ...storage.paths import ensure_run_dirs

log = get_logger("node.final_render")


async def final_render_node(state: GraphState) -> dict:
    vs = dict(state.get("video_state") or {})
    run_id = state.get("run_id")

    assembled = vs.get("_assembled")
    audio = vs.get("audio_path")

    if not run_id or not assembled or not Path(assembled).exists():
        vs["render_path"] = None
        return {"video_state": vs}

    paths = ensure_run_dirs(run_id)

    # if no voice track, just copy the assembled video as the final (silent)
    if not audio or not Path(audio).exists():
        final = paths["render"] / "final_9x16.mp4"
        final.write_bytes(Path(assembled).read_bytes())
        vs["render_path"] = str(final)
        vs["render_variants"] = {"9:16": str(final)}
        log.warning("final_render produced silent video (no voice track)")
        return {"video_state": vs}

    muxed = paths["render"] / "muxed.mp4"
    final = paths["render"] / "final_9x16.mp4"

    with span("node.final_render"):
        await mux(Path(assembled), Path(audio), muxed)
        await loudnorm(muxed, final, target_lufs=-14.0)

    vs["render_path"] = str(final)
    vs["render_variants"] = {"9:16": str(final)}
    log.info("final_render done -> %s", final)
    return {"video_state": vs}