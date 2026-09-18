"""
PLANNER — turn the raw request into an objective, audience, key messages,
KPI, and preferred posting time.

Feeds off:
    state["request"], state["content_type"], state["platforms"]

Produces:
    state["plan"]  = {objective, audience, key_messages, kpi, posting_time_utc, notes}
    state["goal"]  = mirror of plan["objective"] for convenience
"""
from __future__ import annotations

from jinja2 import Template

from ...config.settings import get_settings
from ...infra.logging import get_logger
from ...infra.tracing import span
from ...services.llm import get_llm
from ...state.schema import GraphState

log = get_logger("node.planner")


def _render(template_path, **kw) -> str:
    tpl = Template(template_path.read_text(encoding="utf-8"))
    return tpl.render(**kw)


async def planner_node(state: GraphState) -> dict:
    s = get_settings()
    prompt = _render(
        s.prompts_dir / "planner.j2",
        request=state.get("request", ""),
        content_type=state.get("content_type", "text"),
        platforms=state.get("platforms", []),
    )

    with span("node.planner"):
        plan = await get_llm().json(
            node="planner",
            system="You are a precise social media planner. Output strict JSON.",
            user=prompt,
        )

    # defensive defaults — planner LLM occasionally omits keys
    plan.setdefault("objective", state.get("topic", ""))
    plan.setdefault("audience", "general audience")
    plan.setdefault("key_messages", [])
    plan.setdefault("kpi", "engagement")
    plan.setdefault("posting_time_utc", None)
    plan.setdefault("notes", "")

    log.info(
        "planner done objective=%r kpis=%s",
        plan["objective"][:60], plan["kpi"],
    )
    return {"plan": plan, "goal": plan["objective"]}