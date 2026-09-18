"""
FACT CHECK — LLM check on semantic claims + local numeric heuristic.

Runs two passes:
  1. validators.grounding.check_grounding — cheap numeric heuristic
  2. LLM fact_check prompt — semantic check

Any hard failure flips QA's `passed` to False and adds an entry.
The revision loop routes back to COPYWRITER, which will see the failures in
state.qa and can regenerate with them in context (extend copywriter.j2 later
to accept `qa.failures` as input).
"""
from __future__ import annotations

from jinja2 import Template

from ...config.settings import get_settings
from ...infra.logging import get_logger
from ...infra.tracing import span
from ...services.llm import get_llm
from ...state.schema import GraphState
from ...validators import check_grounding

log = get_logger("node.fact_check")


def _extract_claims(text: str) -> list[str]:
    # naive: split on sentence boundaries, keep anything with a digit or a
    # comparison word — the LLM will re-check them
    sentences = [s.strip() for s in
                 text.replace("!", ".").replace("?", ".").split(".") if s.strip()]
    return sentences


async def fact_check_node(state: GraphState) -> dict:
    s = get_settings()
    ts = dict(state.get("text_state") or {})
    draft = ts.get("draft") or {}
    research = state.get("research") or {}

    full_text = "\n\n".join(filter(None, [
        draft.get("hook") or "",
        draft.get("body") or "",
        draft.get("cta") or "",
    ]))

    # 1. local numeric heuristic
    claims = _extract_claims(full_text)
    heuristic_fails = check_grounding(
        claims=claims,
        sources=research.get("sources", []),
        facts=research.get("facts", []),
    )

    # 2. LLM semantic check (only if we have sources to check against)
    llm_fails: list[dict] = []
    if research.get("sources"):
        prompt = Template((s.prompts_dir / "fact_check.j2").read_text(encoding="utf-8")).render(
            claims=claims[:15],
            sources=research.get("sources", [])[:10],
        )
        with span("node.fact_check.llm"):
            try:
                data = await get_llm().json(
                    node="fact_check",
                    system="You are a strict fact-checker. Output strict JSON.",
                    user=prompt,
                )
                llm_fails = data.get("failures") or []
            except Exception as e:  # noqa: BLE001
                log.warning("LLM fact check failed: %s", e)

    all_fails = heuristic_fails + llm_fails
    ts["fact_check"] = {"failures": all_fails}

    hard = [f for f in all_fails if f.get("severity") == "hard"]
    log.info("fact_check done fails=%d hard=%d", len(all_fails), len(hard))

    if hard:
        # escalate to QA via the shared qa channel
        qa = dict(state.get("qa") or {})
        qa["passed"] = False
        existing = list(qa.get("failures") or [])
        for f in hard:
            existing.append({
                "stage": "fact_check",
                "reason": f.get("reason") or "unsupported claim",
                "severity": "hard",
                "detail": {"claim": f.get("claim")},
            })
        qa["failures"] = existing
        return {"text_state": ts, "qa": qa}

    return {"text_state": ts}