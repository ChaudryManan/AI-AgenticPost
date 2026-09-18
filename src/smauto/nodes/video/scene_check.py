"""
SCENE CHECK — QC pass over generated clips.

For each clip:
  • verify file exists and is non-trivial (>10 KB)
  • if not, retry generation up to settings.scene_retry_max times
  • if still bad, mark `status: "fallback"` (assembly skips it, QA warns)
"""
from __future__ import annotations

from pathlib import Path

from ...config.settings import get_settings
from ...infra.logging import get_logger
from ...infra.tracing import span
from ...services.media import generate_clip
from ...state.schema import GraphState
from ...storage.paths import ensure_run_dirs

log = get_logger("node.scene_check")

_MIN_BYTES = 10_000


def _clip_ok(path: Path) -> bool:
    try:
        return path.exists() and path.stat().st_size >= _MIN_BYTES
    except OSError:
        return False


async def scene_check_node(state: GraphState) -> dict:
    s = get_settings()
    vs = dict(state.get("video_state") or {})
    clips = list(vs.get("clips") or [])
    prompts = {int(p.get("scene_id", -1)): p
               for p in (vs.get("scene_prompts") or [])}
    seed = (vs.get("style_bible") or {}).get("seed")

    run_id = state.get("run_id")
    if not run_id or not clips:
        return {"video_state": vs}

    paths = ensure_run_dirs(run_id)

    for c in clips:
        sid = int(c.get("scene_id", 0))
        path = Path(c.get("path") or paths["scenes"] / f"scene_{sid:02d}.mp4")

        if _clip_ok(path):
            c["path"] = str(path)
            c["status"] = "ok"
            continue

        attempts = int(c.get("attempts", 0))
        while attempts < s.scene_retry_max and not _clip_ok(path):
            attempts += 1
            p = prompts.get(sid)
            if not p:
                break
            try:
                with span("scene_check.retry", scene=sid, attempt=attempts):
                    await generate_clip(
                        prompt=p.get("prompt", ""),
                        out_path=path,
                        duration=6.0,
                        seed=seed,
                    )
            except Exception as e:  # noqa: BLE001
                log.warning("scene %d retry %d failed: %s", sid, attempts, e)

        c["attempts"] = attempts
        if _clip_ok(path):
            c["path"] = str(path)
            c["status"] = "ok"
        else:
            c["status"] = "fallback"
            c["path"] = ""
            c.setdefault("fallback_reason", "clip failed after retries")

    vs["clips"] = clips
    good = sum(1 for c in clips if c["status"] == "ok")
    log.info("scene_check done ok=%d/%d", good, len(clips))
    return {"video_state": vs}