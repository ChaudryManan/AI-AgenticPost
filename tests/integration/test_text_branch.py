"""Text branch end-to-end (LLM mocked, no network)."""
from __future__ import annotations

from smauto.nodes.text.copywriter import copywriter_node
from smauto.nodes.text.fact_check import fact_check_node
from smauto.nodes.text.hashtags import hashtags_node
from smauto.nodes.text.image_assembly import image_assembly_node
from smauto.nodes.text.platform_formatter import platform_formatter_node
from smauto.nodes.text.seo_readability import seo_readability_node
from smauto.nodes.text.slide_splitter import slide_splitter_node
from smauto.nodes.text.variant_scorer import variant_scorer_node


async def test_text_branch_chain(mock_llm, clean_run_dirs):
    state: dict = {
        "run_id": "pytest_run",
        "content_type": "text",
        "platforms": ["linkedin"],
        "strategy": {"hook": "h", "angle": "a", "tone": "professional",
                     "structure": [], "cta": "c"},
        "research": {
            "facts": ["RAG grounds answers."],
            "sources": [{"title": "t", "url": "u", "content": "RAG grounds answers."}],
        },
    }

    # chain: copywriter → scorer → formatter → hashtags → slide_splitter
    state.update(await copywriter_node(state))
    state.update(await variant_scorer_node(state))
    state.update(await platform_formatter_node(state))
    state.update(await hashtags_node(state))
    state.update(await slide_splitter_node(state))
    state.update(await image_assembly_node(state))
    state.update(await fact_check_node(state))
    state.update(await seo_readability_node(state))

    ts = state["text_state"]
    assert len(ts["variants"]) == 4
    assert ts["draft"]["hook"]  # best variant has a hook
    assert "linkedin" in ts["platform_bodies"]
    assert len(ts["hashtags"]) > 0
    assert ts["visual_type"] in ("none", "quote", "carousel")
    # image_paths may be empty (visual_type=none) — but the key must exist
    assert "image_paths" in ts
    assert "seo" in ts
    assert "fact_check" in ts