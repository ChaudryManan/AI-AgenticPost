"""
STRATEGY — the creative brief.

Produces the hook, angle, tone, structure, and CTA that all downstream
content nodes (script, copywriter, caption_writer) build from.
"""
from __future__ import annotations

from jinja2 import Template

from ...config.settings import get_settings
from ...infra.logging import get_logger
from ...infra.tracing import span
from ...services.llm import get_llm
from ...state.schema import GraphState

log = get_logger("node.strategy")


def _render(template_path, **kw) -> str:
    tpl = Template(template_path.read_text(encoding="utf-8"))
    return tpl.render(**kw)


async def strategy_node(state: GraphState) -> dict:
    s = get_settings()
    research = state.get("research") or {}
    facts = (research.get("facts") or [])[:10]  # cap context size

    prompt = _render(
        s.prompts_dir / "strategy.j2",
        request=state.get("request", ""),
        plan=state.get("plan") or {},
        facts=facts,
        platforms=state.get("platforms", []),
    )

    with span("node.strategy"):
        strat = await get_llm().json(
            node="strategy",
            system="You are a senior content strategist. Output strict JSON.",
            user=prompt,
        )

    # defensive defaults
    strat.setdefault("hook", "")
    strat.setdefault("angle", "")
    strat.setdefault("tone", "professional")
    strat.setdefault("structure", [])
    strat.setdefault("cta", "")

    log.info(
        "strategy done hook=%r tone=%s",
        (strat["hook"] or "")[:60], strat["tone"],
    )
    return {"strategy": strat}