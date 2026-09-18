"""Script node — mocked LLM + duration validation."""
from __future__ import annotations

from smauto.nodes.video.script import script_node


async def test_script_sets_scenes(mock_llm):
    out = await script_node({
        "strategy": {"hook": "h"},
        "research": {"facts": []},
    })
    scenes = out["video_state"]["script"]
    assert len(scenes) == 5
    # mock returns 5 × 6s = 30s, so no rescale should fire
    assert sum(s["duration"] for s in scenes) == 30


async def test_script_caps_scene_count():
    """If the LLM returns >5 scenes, the node should trim to 5."""
    from unittest.mock import patch

    async def too_many(self, node, system, user, override=None, meter=None):
        return {"scenes": [
            {"id": i, "vo_text": "x", "duration": 6,
             "on_screen_text": "y", "beat": "z"}
            for i in range(1, 11)
        ]}

    with patch("smauto.services.llm.client.LLMClient.json", too_many):
        out = await script_node({"strategy": {}, "research": {}})
    assert len(out["video_state"]["script"]) == 5