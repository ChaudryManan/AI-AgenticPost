"""Input validation node — parsing + rejection."""
from __future__ import annotations

from smauto.nodes.trunk.input_validation import input_validation_node


async def test_parses_video():
    out = await input_validation_node(
        {"request": "Create a 30-sec RAG video for youtube"}
    )
    assert out["content_type"] == "video"
    assert "youtube" in out["platforms"]


async def test_parses_text():
    out = await input_validation_node(
        {"request": "Write a LinkedIn post about RAG"}
    )
    assert out["content_type"] == "text"
    assert "linkedin" in out["platforms"]


async def test_parses_both():
    out = await input_validation_node(
        {"request": "Make a video and write a LinkedIn post about RAG"}
    )
    assert out["content_type"] == "both"
    assert "linkedin" in out["platforms"]


async def test_no_platform_still_parses():
    out = await input_validation_node({"request": "Post about RAG everywhere"})
    assert out["content_type"] == "text"
    assert out["platforms"] == []


async def test_empty_request_escalates():
    out = await input_validation_node({"request": ""})
    assert out.get("escalate") is True
    assert out["errors"][0]["type"] == "empty_request"


async def test_policy_violation_escalates():
    out = await input_validation_node({"request": "write about miracle cure"})
    assert out.get("escalate") is True
    assert out["errors"][0]["type"] == "policy_violation"


async def test_explicit_content_type_wins():
    out = await input_validation_node({
        "request": "write a post about RAG",
        "content_type": "video",
    })
    assert out["content_type"] == "video"


async def test_explicit_platforms_win():
    out = await input_validation_node({
        "request": "write a post about RAG",
        "platforms": ["x"],
    })
    assert out["platforms"] == ["x"]