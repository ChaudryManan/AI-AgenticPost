"""
Everything the video branch produces.

Kept as a TypedDict so it's cheap, JSON-serializable, and plays nicely with
LangGraph's checkpointer (which needs plain data, not pydantic models).
"""
from __future__ import annotations

from typing import Any, TypedDict


class Scene(TypedDict, total=False):
    id: int
    vo_text: str            # voiceover line
    duration: float         # seconds
    on_screen_text: str     # text overlay
    beat: str               # narrative purpose of the scene


class Shot(TypedDict, total=False):
    scene_id: int
    shot_type: str          # wide | medium | close-up | ...
    camera_move: str        # static | push-in | pan-left | ...
    composition: str        # framing notes
    transition: str         # cut | dissolve | whip-pan | match-cut


class ScenePrompt(TypedDict, total=False):
    scene_id: int
    prompt: str
    negative_prompt: str


class Clip(TypedDict, total=False):
    scene_id: int
    path: str               # local file path
    status: str             # "ok" | "fallback" | "error:<Type>"
    attempts: int
    fallback_reason: str


class VideoState(TypedDict, total=False):
    # writing
    script: list[Scene]
    storyboard: list[Shot]
    style_bible: dict[str, Any]
    scene_prompts: list[ScenePrompt]

    # generation
    clips: list[Clip]

    # audio + post
    audio_path: str | None
    audio_timestamps: list[dict[str, Any]]   # [{start, end, text}]
    subtitles_path: str | None
    music_path: str | None

    # render
    render_path: str | None
    render_variants: dict[str, str]          # {"9:16": path, "1:1": path, ...}
    thumbnail_paths: list[str]

    # social
    caption: str
    hashtags: list[str]

    # internal scratch (prefixed with _ so it's obviously not user-facing)
    _assembled: str | None
    _duration_total: float