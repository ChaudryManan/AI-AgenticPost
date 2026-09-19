"""
RESEARCH — ask the LLM for search queries, then hit the web, collect facts
and sources, and produce a confidence score.

The router (research_router) can send us back here for up to
settings.research_requery_max extra passes if confidence is low.
"""
from __future__ import annotations

from jinja2 import Template

from ...config.settings import get_settings
from ...infra.logging import get_logger
from ...infra.tracing import span
from ...services.llm import get_llm
from ...services.search import web_search
from ...state.schema import GraphState

log = get_logger("node.research")


def _render(template_path, **kw) -> str:
    tpl = Template(template_path.read_text(encoding="utf-8"))
    return tpl.render(**kw)


# a source's `content` gets truncated to this many chars before it's stored —
# keeps state size down and stays under the LLM's context budget
_MAX_SOURCE_CHARS = 800
_MAX_FACT_CHARS = 400


async def research_node(state: GraphState) -> dict:
    s = get_settings()
    plan = state.get("plan") or {}

    # 1. ask the LLM for search queries
    query_prompt = _render(
        s.prompts_dir / "research_query.j2",
        topic=state.get("topic", ""),
        audience=plan.get("audience", ""),
        key_messages=plan.get("key_messages", []),
    )

    with span("node.research.queries"):
        q_out = await get_llm().json(
            node="research",
            system="Return strict JSON with a 'queries' array.",
            user=query_prompt,
        )

    queries = [q for q in (q_out.get("queries") or []) if isinstance(q, str)]
    queries = queries[:5]
    if not queries:
        queries = [state.get("topic", "")]

    # 2. run the searches
    facts: list[str] = []
    sources: list[dict] = []

    with span("node.research.search", n=len(queries)):
        for q in queries:
            hits = await web_search(q, max_results=4)
            for h in hits:
                content = (h.get("content") or "")[:_MAX_SOURCE_CHARS]
                sources.append({
                    "title": (h.get("title") or "")[:200],
                    "url": h.get("url") or "",
                    "content": content,
                    "score": h.get("score", 0.0),
                })
                if content:
                    facts.append(content[:_MAX_FACT_CHARS])

    
        # 3. confidence heuristic + requery counter
    prev = state.get("research") or {}
    requery_count = int(prev.get("requery_count", 0))

    import os
    search_enabled = bool(os.getenv("TAVILY_API_KEY"))

    # confidence scales with how many sources we found, saturating at ~1.0
    confidence = min(1.0, len(sources) / 8.0)

    # If search is disabled, don't requery — there's nothing to find.
    # Also don't requery if we already have enough sources.
    if not search_enabled:
        requery_count = 999  # force the router to stop looping
    elif confidence < 0.5 and state.get("research"):
        requery_count += 1
        
    log.info(
        "research done sources=%d facts=%d confidence=%.2f requery=%d",
        len(sources), len(facts), confidence, requery_count,
    )

    return {"research": {
        "facts": facts,
        "sources": sources,
        "confidence": confidence,
        "requery_count": requery_count,
    }}