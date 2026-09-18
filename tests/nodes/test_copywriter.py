"""Copywriter node — mocked LLM."""
from __future__ import annotations

from smauto.nodes.text.copywriter import copywriter_node


async def test_copywriter_returns_variants(mock_llm):
    state = {
        "run_id": "pytest_run",
        "strategy": {"hook": "h", "angle": "a", "tone": "professional",
                     "structure": [], "cta": "c"},
        "research": {"facts": ["f1"]},
        "platforms": ["linkedin"],
    }
    out = await copywriter_node(state)
    variants = out["text_state"]["variants"]
    assert len(variants) == 4
    assert all("hook" in v and "body" in v and "cta" in v for v in variants)


async def test_copywriter_handles_empty_response():
    """If the LLM returns no variants, the node should still produce a valid state."""
    from unittest.mock import patch

    async def empty_json(self, node, system, user, override=None, meter=None):
        return {"variants": []}

    with patch("smauto.services.llm.client.LLMClient.json", empty_json):
        out = await copywriter_node({
            "strategy": {}, "research": {}, "platforms": ["linkedin"],
        })
    assert out["text_state"]["variants"] == []