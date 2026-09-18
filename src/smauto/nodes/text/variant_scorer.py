"""
VARIANT SCORER — score each variant, pick the best as state.text_state.draft.

Keeps all variants (sorted by score) so an A/B test layer could use the
alternatives later.
"""
from __future__ import annotations

from jinja2 import Template

from ...config.settings import get_settings
from ...infra.logging import get_logger
from ...infra.tracing import span
from ...services.llm import get_llm
from ...state.schema import GraphState

log = get_logger("node.variant_scorer")

_AXES = ("hook_strength", "clarity", "on_brand", "novelty")


async def variant_scorer_node(state: GraphState) -> dict:
    s = get_settings()
    ts = dict(state.get("text_state") or {})
    variants = list(ts.get("variants") or [])

    if not variants:
        log.warning("variant_scorer called with no variants")
        ts["draft"] = {}
        return {"text_state": ts}

    # single-variant fast path — no LLM call
    if len(variants) == 1:
        variants[0]["score"] = 100.0
        ts["variants"] = variants
        ts["draft"] = variants[0]
        return {"text_state": ts}

    prompt = Template((s.prompts_dir / "variant_scorer.j2").read_text(encoding="utf-8")).render(
        variants=variants,
    )

    with span("node.variant_scorer", n=len(variants)):
        data = await get_llm().json(
            node="scorer",
            system="You score copy objectively. Output strict JSON.",
            user=prompt,
        )

    scored = data.get("scored") or []
    by_idx = {int(x.get("index", -1)): x for x in scored if "index" in x}

    for i, v in enumerate(variants):
        row = by_idx.get(i)
        if not row:
            v["score"] = 0.0
            v["scores"] = {}
            continue
        total = sum(float(row.get(ax, 0)) for ax in _AXES)
        v["score"] = round(total, 2)
        v["scores"] = {ax: float(row.get(ax, 0)) for ax in _AXES}

    variants.sort(key=lambda v: v.get("score", 0), reverse=True)
    ts["variants"] = variants
    ts["draft"] = variants[0]

    log.info(
        "variant_scorer done best=%r score=%.2f",
        (variants[0].get("hook") or "")[:40], variants[0].get("score", 0),
    )
    return {"text_state": ts}