"""
Video branch — the LLM-only part of the chain (script → scene_prompts).

Skipping the media-generation nodes because they need API keys; the point
here is that the LLM-driven planning chain produces correct shapes.
"""
from __future__ import annotations

from smauto.nodes.video.characters import characters_node
from smauto.nodes.video.scene_prompts import scene_prompts_node
from smauto.nodes.video.script import script_node
from smauto.nodes.video.storyboard import storyboard_node


async def test_video_planning_chain(mock_llm):
    state: dict = {
        "run_id": "pytest_run",
        "content_type": "video",
        "platforms": ["youtube"],
        "strategy": {"hook": "h", "angle": "a", "tone": "professional",
                     "structure": [], "cta": "c"},
        "research": {"facts": ["f"]},
    }

    state.update(await script_node(state))
    state.update(await storyboard_node(state))
    state.update(await characters_node(state))
    state.update(await scene_prompts_node(state))

    vs = state["video_state"]
    assert len(vs["script"]) == 5
    assert len(vs["storyboard"]) == 5
    assert vs["style_bible"]["seed"] is not None
    assert len(vs["scene_prompts"]) == 5

    # every prompt has the right scene_id
    for i, p in enumerate(vs["scene_prompts"], start=1):
        assert p["scene_id"] == i


async def test_video_assembly_skips_with_no_clips(clean_run_dirs, mock_llm):
    """With zero usable clips, assembly should not crash — it just skips."""
    from smauto.nodes.video.scene_generate import scene_generate_node
    from smauto.nodes.video.video_assembly import video_assembly_node

    state: dict = {
        "run_id": "pytest_run",
        "content_type": "video",
        "video_state": {"scene_prompts": []},
    }

    state.update(await scene_generate_node(state))
    assert state["video_state"]["clips"] == []

    state.update(await video_assembly_node(state))
    assert state["video_state"].get("_assembled") is None