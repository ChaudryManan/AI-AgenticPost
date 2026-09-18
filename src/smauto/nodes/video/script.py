"""
SCRIPT — write a ~30s video script, 5 scenes of ~6s each.

Validates Σ durations ≈ 30s; if off by more than tolerance, asks the LLM
once to rescale.  Hard-caps the script list to 5 scenes.
"""
from __future__ import annotations

from jinja2 import Template

from ...config.settings import get_settings
from ...infra.logging import get_logger
from ...infra.tracing import span
from ...services.llm import get_llm
from ...state.schema import GraphState

log = get_logger("node.script")

_TARGET_TOTAL = 30.0
_TOLERANCE = 3.0
_MAX_SCENES = 5


async def script_node(state: GraphState) -> dict:
    s = get_settings()
    vs = dict(state.get("video_state") or {})
    research = state.get("research") or {}

    prompt = Template((s.prompts_dir / "script.j2").read_text(encoding="utf-8")).render(
        strategy=state.get("strategy") or {},
        facts=(research.get("facts") or [])[:10],
    )

    with span("node.script"):
        data = await get_llm().json(
            node="script",
            system="You write tight short-form scripts. Output strict JSON.",
            user=prompt,
        )

    scenes = list(data.get("scenes") or [])[:_MAX_SCENES]

    # rescale if sum is off
    total = sum(float(sc.get("duration", 0)) for sc in scenes)
    if scenes and abs(total - _TARGET_TOTAL) > _TOLERANCE:
        log.info("script duration %.1fs off-target, asking LLM to rescale", total)
        repair_prompt = (
            f"Rescale the following scenes so durations sum to ~30 seconds. "
            f"Keep the exact same vo_text, on_screen_text, and beat. Only "
            f"change the `duration` field. Return JSON {{\"scenes\": [...]}}.\n\n"
            f"{scenes}"
        )
        with span("node.script.rescale"):
            data2 = await get_llm().json(
                node="script",
                system="Return only JSON.",
                user=repair_prompt,
            )
        scenes = list(data2.get("scenes") or scenes)[:_MAX_SCENES]

    vs["script"] = scenes
    log.info("script done scenes=%d total_dur=%.1fs",
             len(scenes), sum(float(x.get("duration", 0)) for x in scenes))
    return {"video_state": vs}