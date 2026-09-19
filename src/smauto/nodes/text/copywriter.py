"""
COPYWRITER — generate N distinct post variants.

Two modes:
  • fresh    — write from strategy + research
  • revision — user asked for a specific change; pass the previous draft
               and the feedback so the LLM edits rather than rewrites
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

    feedback = (state.get("revision_feedback") or "").strip()
    previous = ts.get("draft") or {}

    # If this is a user-driven revision, ask for a single tight rewrite
    # focused on the feedback. Otherwise generate the usual batch.
    is_revision = bool(feedback)

    prompt = Template((s.prompts_dir / "copywriter.j2").read_text(encoding="utf-8")).render(
        n=1 if is_revision else _N_VARIANTS,
        strategy=state.get("strategy") or {},
        facts=(research.get("facts") or [])[:10],
        platforms=state.get("platforms", []),
        feedback=feedback,
        previous=previous,
        is_revision=is_revision,
    )

    with span("node.copywriter", n=1 if is_revision else _N_VARIANTS,
              revision=is_revision):
        data = await get_llm().json(
            node="copywriter",
            system="You write on-brand social copy. Output strict JSON.",
            user=prompt,
        )

    raw = list(data.get("variants") or [])
    normalized = []
    for v in raw:
        if not isinstance(v, dict):
            continue
        normalized.append({
            "hook": (v.get("hook") or "").strip(),
            "body": (v.get("body") or "").strip(),
            "cta":  (v.get("cta") or "").strip(),
        })
    normalized = [v for v in normalized if v["hook"] or v["body"]]

    # On a user revision, force the result to be the only variant.
    if is_revision and normalized:
        normalized = normalized[:1]

    ts["variants"] = normalized
    log.info("copywriter done variants=%d revision=%s",
             len(normalized), is_revision)

    # clear the feedback once consumed so it isn't reused on the next loop
    out: dict = {"text_state": ts}
    if is_revision:
        out["revision_feedback"] = ""
    return out