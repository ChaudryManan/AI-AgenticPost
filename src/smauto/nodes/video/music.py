"""
MUSIC — pick a bed from assets/music.

Deterministic pick based on run_id so re-runs are stable.  If the folder
is empty, leaves music_path unset — final_render copes without music.
"""
from __future__ import annotations

import hashlib

from ...config.settings import get_settings
from ...infra.logging import get_logger
from ...state.schema import GraphState

log = get_logger("node.music")

_ALLOWED = {".mp3", ".m4a", ".wav", ".aac", ".ogg"}


async def music_node(state: GraphState) -> dict:
    vs = dict(state.get("video_state") or {})
    s = get_settings()

    music_dir = s.assets_dir / "music"
    if not music_dir.exists():
        vs["music_path"] = None
        return {"video_state": vs}

    tracks = sorted(p for p in music_dir.iterdir()
                    if p.is_file() and p.suffix.lower() in _ALLOWED)

    if not tracks:
        vs["music_path"] = None
        return {"video_state": vs}

    # deterministic pick from run_id
    seed_str = str(state.get("run_id") or "default")
    idx = int(hashlib.sha256(seed_str.encode()).hexdigest(), 16) % len(tracks)
    chosen = tracks[idx]

    vs["music_path"] = str(chosen)
    log.info("music picked %s", chosen.name)
    return {"video_state": vs}