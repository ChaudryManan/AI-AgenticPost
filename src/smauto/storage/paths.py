"""
Run-scoped path conventions.

Every run gets its own directory under artifact_root:

    runs/<run_id>/
        scenes/      generated clip .mp4 files
        audio/       TTS .mp3, mixed audio
        images/      thumbnails, quote cards, carousel slides
        subtitles/   .srt files
        music/       picked bed (symlink or copy)
        render/      assembled / muxed / final videos
        state.json   (optional checkpoint dump)

Never hardcode these paths anywhere else — always call ensure_run_dirs()
or run_dir() so the layout stays changeable in one place.
"""
from __future__ import annotations

from pathlib import Path

from ..config.settings import get_settings

# subdirectories every run gets
_SUBDIRS = ("scenes", "audio", "images", "subtitles", "music", "render")


def run_dir(run_id: str) -> Path:
    """Return the root directory for a run (does not create it)."""
    if not run_id or "/" in run_id or "\\" in run_id:
        raise ValueError(f"invalid run_id: {run_id!r}")
    return get_settings().artifact_root / run_id


def ensure_run_dirs(run_id: str) -> dict[str, Path]:
    """
    Create (if needed) and return every per-run subdirectory.

    Returns a dict so callers can do:
        paths = ensure_run_dirs(state["run_id"])
        out = paths["scenes"] / "scene_1.mp4"
    """
    base = run_dir(run_id)
    base.mkdir(parents=True, exist_ok=True)

    out: dict[str, Path] = {"root": base}
    for name in _SUBDIRS:
        p = base / name
        p.mkdir(parents=True, exist_ok=True)
        out[name] = p
    return out


def state_path(run_id: str) -> Path:
    """Path to the optional state.json dump for a run."""
    return run_dir(run_id) / "state.json"