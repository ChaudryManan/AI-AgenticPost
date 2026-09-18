"""QA node — pass/fail gate."""
from __future__ import annotations

from smauto.nodes.shared.qa import qa_node


async def test_qa_passes_empty():
    out = await qa_node({"content_type": "text", "platforms": []})
    assert out["qa"]["passed"] is True
    assert out["qa"]["failures"] == []


async def test_qa_passes_clean_text():
    state = {
        "content_type": "text",
        "platforms": ["linkedin"],
        "text_state": {
            "platform_bodies": {"linkedin": "Short, clean post."},
            "hashtags": ["#ai"],
        },
    }
    out = await qa_node(state)
    assert out["qa"]["passed"] is True


async def test_qa_fails_on_policy_violation():
    state = {
        "content_type": "text",
        "platforms": ["linkedin"],
        "text_state": {
            "platform_bodies": {"linkedin": "A miracle cure for your team."},
            "hashtags": [],
        },
    }
    out = await qa_node(state)
    assert out["qa"]["passed"] is False
    assert any(f["severity"] == "hard" for f in out["qa"]["failures"])


async def test_qa_fails_on_brand_violation_soft():
    state = {
        "content_type": "text",
        "platforms": ["linkedin"],
        "text_state": {
            "platform_bodies": {"linkedin": "Our revolutionary new tool."},
            "hashtags": [],
        },
    }
    out = await qa_node(state)
    # brand issues are soft — should NOT flip passed to False
    assert out["qa"]["passed"] is True
    assert any(f["severity"] == "soft" for f in out["qa"]["failures"])


async def test_qa_video_missing_render_hard_fails():
    state = {
        "content_type": "video",
        "platforms": ["youtube"],
        "video_state": {
            "script": [{"id": 1, "vo_text": "x", "duration": 6}],
            "render_path": None,
        },
    }
    out = await qa_node(state)
    assert out["qa"]["passed"] is False


async def test_qa_video_complete_passes():
    state = {
        "content_type": "video",
        "platforms": ["youtube"],
        "video_state": {
            "script": [{"id": i, "vo_text": "x", "duration": 6} for i in range(5)],
            "render_path": "/fake/path/final.mp4",
            "clips": [{"scene_id": i, "status": "ok", "path": "x"} for i in range(5)],
            "caption": "Sample caption.",
        },
    }
    out = await qa_node(state)
    assert out["qa"]["passed"] is True