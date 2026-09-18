"""
SLIDE SPLITTER — decide the visual type and (if carousel) split into slides.

Decision rules (deterministic, no LLM for the type decision):
  • carousel  — target includes LinkedIn or Instagram AND body > 400 chars
  • quote     — hook < 120 chars (a quote card renders nicely)
  • none      — otherwise (X threads, short posts)
"""
from __future__ import annotations

from jinja2 import Template

from ...config.settings import get_settings
from ...infra.logging import get_logger
from ...infra.tracing import span
from ...services.llm import get_llm
from ...state.schema import GraphState

log = get_logger("node.slide_splitter")

_CAROUSEL_PLATFORMS = {"linkedin", "instagram"}


def _pick_visual_type(state: GraphState, draft: dict, platform_bodies: dict) -> str:
    platforms = {p.lower() for p in (state.get("platforms") or [])}
    if platforms & _CAROUSEL_PLATFORMS:
        # check the longest body across the target platforms
        longest = max((len(b) for b in platform_bodies.values()), default=0)
        if longest > 400:
            return "carousel"
    hook = (draft.get("hook") or "").strip()
    if 0 < len(hook) < 120:
        return "quote"
    return "none"


async def slide_splitter_node(state: GraphState) -> dict:
    s = get_settings()
    ts = dict(state.get("text_state") or {})
    draft = ts.get("draft") or {}
    bodies = ts.get("platform_bodies") or {}

    visual_type = _pick_visual_type(state, draft, bodies)
    ts["visual_type"] = visual_type

    if visual_type != "carousel":
        ts["slides"] = []
        log.info("slide_splitter done visual_type=%s", visual_type)
        return {"text_state": ts}

    # use the longest body for splitting — it has the most content
    body = max(bodies.values(), key=len) if bodies else (draft.get("body") or "")

    prompt = Template((s.prompts_dir / "slide_splitter.j2").read_text(encoding="utf-8")).render(
        body=body[:3000],
    )

    with span("node.slide_splitter"):
        data = await get_llm().json(
            node="slide_splitter",
            system="Split the post into carousel slides. Output strict JSON.",
            user=prompt,
        )

    slides = data.get("slides") or []
    # normalize
    normalized = []
    for i, sl in enumerate(slides):
        normalized.append({
            "index": int(sl.get("index", i)),
            "title": (sl.get("title") or "").strip(),
            "body": (sl.get("body") or "").strip(),
        })
    ts["slides"] = normalized

    log.info("slide_splitter done visual_type=carousel slides=%d", len(normalized))
    return {"text_state": ts}