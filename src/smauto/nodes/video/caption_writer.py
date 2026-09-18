"""
CAPTION WRITER — the social post that accompanies the finished video.

Produces state.video_state.caption and state.video_state.hashtags.
"""
from __future__ import annotations

from jinja2 import Template

from ...config.settings import get_settings
from ...infra.logging import get_logger
from ...infra.tracing import span
from ...services.llm import get_llm
from ...state.schema import GraphState

log = get_logger("node.caption_writer")


async def caption_writer_node(state: GraphState) -> dict:
    s = get_settings()
    vs = dict(state.get("video_state") or {})

    prompt = Template((s.prompts_dir / "caption_writer.j2").read_text(encoding="utf-8")).render(
        strategy=state.get("strategy") or {},
        platforms=state.get("platforms", []),
    )

    with span("node.caption_writer"):
        data = await get_llm().json(
            node="caption_writer",
            system="You write social captions. Output strict JSON.",
            user=prompt,
        )

    vs["caption"] = (data.get("caption") or "").strip()
    vs["hashtags"] = [h for h in (data.get("hashtags") or []) if isinstance(h, str)]

    log.info("caption_writer done caption_chars=%d hashtags=%d",
             len(vs["caption"]), len(vs["hashtags"]))
    return {"video_state": vs}