"""
COPYWRITER — generate N distinct post variants.

Output: state.text_state.variants = [{hook, body, cta}, ...]
"""
from __future__ import annotations

from jinja2 import Template

from ...config.settings import get_settings
from ...infra.logging import get_logger
from ...infra.tracing import span
from ...services.llm import get_llm
from ...state.schema import GraphState

log = get_logger("node.copywriter")

_N_VARIANTS = 4


async def copywriter_node(state: GraphState) -> dict:
    s = get_settings()
    ts = dict(state.get("text_state") or {})
    research = state.get("research") or {}

    prompt = Template((s.prompts_dir / "copywriter.j2").read_text(encoding="utf-8")).render(
        n=_N_VARIANTS,
        strategy=state.get("strategy") or {},
        facts=(research.get("facts") or [])[:10],
        platforms=state.get("platforms", []),
    )

    with span("node.copywriter", n=_N_VARIANTS):
        data = await get_llm().json(
            node="copywriter",
            system="You write on-brand social copy. Output strict JSON.",
            user=prompt,
        )

    variants = list(data.get("variants") or [])
    # normalize each variant — ensure all three keys exist
    normalized = []
    for v in variants:
        if not isinstance(v, dict):
            continue
        normalized.append({
            "hook": (v.get("hook") or "").strip(),
            "body": (v.get("body") or "").strip(),
            "cta": (v.get("cta") or "").strip(),
        })
    normalized = [v for v in normalized if v["hook"] or v["body"]]
    normalized = normalized[:_N_VARIANTS]

    ts["variants"] = normalized
    log.info("copywriter done variants=%d", len(normalized))
    return {"text_state": ts}