"""
The graph.

  input_validation ─┬─► END                (escalate: empty / policy / max revisions)
                    ├─► clarify ──► input_validation
                    └─► planner ─► research ─┬─► research       (requery loop)
                                             └─► strategy
                                                  │
                                                  ▼
                                              content_router
                                             ┌────┴─────┐
                                             ▼          ▼
                                        video chain   text chain
                                             │          │
                                (caption_writer →)      │
                                             ▼          │
                                            (both) ─────┤
                                                        ▼
                                                       qa ─┬─► approval ─┬─► scheduler ─► publish ─► analytics ─► insights ─► END
                                                           │             ├─► revision ──► branch
                                                           │             └─► END     (pause)
                                                           ├─► revision ──► branch
                                                           └─► escalate ──► END

"both" content type: the video chain runs first (content_router → script → …
→ caption_writer), then the caption_writer conditional edge sends control
into the text chain when content_type == "both".  The text chain ends at
seo_readability → qa.  Sequential rather than parallel because it keeps
checkpointing simple and the branches don't share heavy state.
"""
from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

# ── trunk ─────────────────────────────────────────────────────────────
from ..nodes.trunk.clarify import clarify_node
from ..nodes.trunk.input_validation import input_validation_node
from ..nodes.trunk.planner import planner_node
from ..nodes.trunk.research import research_node
from ..nodes.trunk.strategy import strategy_node

# ── video ─────────────────────────────────────────────────────────────
from ..nodes.video.caption_writer import caption_writer_node
from ..nodes.video.characters import characters_node
from ..nodes.video.final_render import final_render_node
from ..nodes.video.music import music_node
from ..nodes.video.scene_check import scene_check_node
from ..nodes.video.scene_generate import scene_generate_node
from ..nodes.video.scene_prompts import scene_prompts_node
from ..nodes.video.script import script_node
from ..nodes.video.storyboard import storyboard_node
from ..nodes.video.subtitles import subtitles_node
from ..nodes.video.thumbnail import thumbnail_node
from ..nodes.video.video_assembly import video_assembly_node
from ..nodes.video.voice import voice_node

# ── text ──────────────────────────────────────────────────────────────
from ..nodes.text.copywriter import copywriter_node
from ..nodes.text.fact_check import fact_check_node
from ..nodes.text.hashtags import hashtags_node
from ..nodes.text.image_assembly import image_assembly_node
from ..nodes.text.platform_formatter import platform_formatter_node
from ..nodes.text.seo_readability import seo_readability_node
from ..nodes.text.slide_splitter import slide_splitter_node
from ..nodes.text.variant_scorer import variant_scorer_node

# ── shared ────────────────────────────────────────────────────────────
from ..nodes.shared.analytics import analytics_node
from ..nodes.shared.approval import approval_node
from ..nodes.shared.insights import insights_node
from ..nodes.shared.publish import publish_node
from ..nodes.shared.qa import qa_node
from ..nodes.shared.revision import revision_node
from ..nodes.shared.scheduler import scheduler_node

# ── state ─────────────────────────────────────────────────────────────
from ..state.schema import GraphState

# ── local ─────────────────────────────────────────────────────────────
from .checkpointer import build_checkpointer
from .routers import (
    approval_router,
    content_router,
    input_router,
    qa_router,
    research_router,
    revision_router,
)


# ── tiny internal nodes ──────────────────────────────────────────────

async def _escalate_node(state: GraphState) -> dict:
    """Terminal node for escalated runs."""
    return {"escalate": True}


async def _noop_node(state: GraphState) -> dict:
    """Placeholder — used where the graph needs a named node but no work."""
    return {}


# ── branch wiring ────────────────────────────────────────────────────

def _wire_video(g: StateGraph) -> None:
    g.add_node("script", script_node)
    g.add_node("storyboard", storyboard_node)
    g.add_node("characters", characters_node)
    g.add_node("scene_prompts", scene_prompts_node)
    g.add_node("scene_generate", scene_generate_node)
    g.add_node("scene_check", scene_check_node)
    g.add_node("video_assembly", video_assembly_node)
    g.add_node("voice", voice_node)
    g.add_node("subtitles", subtitles_node)
    g.add_node("music", music_node)
    g.add_node("final_render", final_render_node)
    g.add_node("thumbnail", thumbnail_node)
    g.add_node("caption_writer", caption_writer_node)

    g.add_edge("script", "storyboard")
    g.add_edge("storyboard", "characters")
    g.add_edge("characters", "scene_prompts")
    g.add_edge("scene_prompts", "scene_generate")
    g.add_edge("scene_generate", "scene_check")
    g.add_edge("scene_check", "video_assembly")
    g.add_edge("video_assembly", "voice")
    g.add_edge("voice", "subtitles")
    g.add_edge("subtitles", "music")
    g.add_edge("music", "final_render")
    g.add_edge("final_render", "thumbnail")
    g.add_edge("thumbnail", "caption_writer")


def _wire_text(g: StateGraph) -> None:
    g.add_node("copywriter", copywriter_node)
    g.add_node("variant_scorer", variant_scorer_node)
    g.add_node("platform_formatter", platform_formatter_node)
    g.add_node("hashtags", hashtags_node)
    g.add_node("slide_splitter", slide_splitter_node)
    g.add_node("image_assembly", image_assembly_node)
    g.add_node("fact_check", fact_check_node)
    g.add_node("seo_readability", seo_readability_node)

    g.add_edge("copywriter", "variant_scorer")
    g.add_edge("variant_scorer", "platform_formatter")
    g.add_edge("platform_formatter", "hashtags")
    g.add_edge("hashtags", "slide_splitter")
    g.add_edge("slide_splitter", "image_assembly")
    g.add_edge("image_assembly", "fact_check")
    g.add_edge("fact_check", "seo_readability")
    g.add_edge("seo_readability", "qa")


def _wire_shared(g: StateGraph) -> None:
    g.add_node("qa", qa_node)
    g.add_node("revision", revision_node)
    g.add_node("approval", approval_node)
    g.add_node("scheduler", scheduler_node)
    g.add_node("publish", publish_node)
    g.add_node("analytics", analytics_node)
    g.add_node("insights", insights_node)
    g.add_node("escalate", _escalate_node)

    # qa → approve | revise | escalate
    g.add_conditional_edges("qa", qa_router, {
        "approve": "approval",
        "revise": "revision",
        "escalate": "escalate",
    })

    # revision → back into a branch
    g.add_conditional_edges("revision", revision_router, {
        "video": "script",
        "text": "copywriter",
        "both": "script",
    })

    # approval → publish | revise | end
    g.add_conditional_edges("approval", approval_router, {
        "publish": "scheduler",
        "revise": "revision",
        "pause": END,
    })

    g.add_edge("scheduler", "publish")
    g.add_edge("publish", "analytics")
    g.add_edge("analytics", "insights")
    g.add_edge("insights", END)
    g.add_edge("escalate", END)


# ── builder ──────────────────────────────────────────────────────────

def build_graph(checkpointer: Any | None = None):
    """
    Compile the StateGraph.

    checkpointer: optional async checkpointer.  If None, uses an in-memory
                  MemorySaver (state won't survive process restarts).
                  For persistence, pass the result of
                  setup_async_checkpointer().
    """
    g = StateGraph(GraphState)

    # trunk
    g.add_node("input_validation", input_validation_node)
    g.add_node("clarify", clarify_node)
    g.add_node("planner", planner_node)
    g.add_node("research", research_node)
    g.add_node("strategy", strategy_node)
    g.add_node("content_router", _noop_node)

    # branches
    _wire_video(g)
    _wire_text(g)

    # shared tail
    _wire_shared(g)

    # entry
    g.set_entry_point("input_validation")

    # input_validation → clarify | planner | END
    g.add_conditional_edges("input_validation", input_router, {
        "clarify": "clarify",
        "plan": "planner",
        "end": END,
    })

    # clarify loops back into input_validation
    g.add_edge("clarify", "input_validation")

    # planner → research
    g.add_edge("planner", "research")

    # research → requery (loop) or continue
    g.add_conditional_edges("research", research_router, {
        "requery": "research",
        "continue": "strategy",
    })

    # strategy → content_router → video | text | both
    g.add_edge("strategy", "content_router")
    g.add_conditional_edges("content_router", content_router, {
        "video": "script",
        "text": "copywriter",
        "both": "script",
    })

    # end-of-video-chain → text chain (both) or QA
    g.add_conditional_edges(
        "caption_writer",
        lambda s: "text" if s.get("content_type") == "both" else "qa",
        {"text": "copywriter", "qa": "qa"},
    )

    if checkpointer is None:
        checkpointer = build_checkpointer()

    return g.compile(
        checkpointer=checkpointer,
        interrupt_before=["clarify", "approval"],
    )


def get_compiled_graph(checkpointer: Any | None = None):
    """
    Non-cached accessor.  Call sites that build repeatedly should cache the
    graph themselves.
    """
    return build_graph(checkpointer=checkpointer)