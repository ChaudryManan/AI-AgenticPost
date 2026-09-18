"""
STORYBOARD — turn each scene into a shot (camera move, framing, transition).
"""
from __future__ import annotations

from jinja2 import Template

from ...config.settings import get_settings
from ...infra.logging import get_logger
from ...infra.tracing import span
from ...services.llm import get_llm
from ...state.schema import GraphState

log = get_logger("node.storyboard")


async def storyboard_node(state: GraphState) -> dict:
    s = get_settings()
    vs = dict(state.get("video_state") or {})
    script = vs.get("script") or []

    if not script:
        log.warning("storyboard called with empty script")
        vs["storyboard"] = []
        return {"video_state": vs}

    prompt = Template((s.prompts_dir / "storyboard.j2").read_text(encoding="utf-8")).render(
        script=script,
    )

    with span("node.storyboard", n_scenes=len(script)):
        data = await get_llm().json(
            node="storyboard",
            system="You are a director. Output strict JSON.",
            user=prompt,
        )

    shots = data.get("shots") or []
    # normalize: make sure every scene has a shot, even if the LLM dropped one
    by_id = {int(x.get("scene_id", -1)): x for x in shots if "scene_id" in x}
    normalized = []
    for sc in script:
        sid = int(sc.get("id", len(normalized) + 1))
        normalized.append(by_id.get(sid, {
            "scene_id": sid,
            "shot_type": "medium",
            "camera_move": "static",
            "composition": "rule-of-thirds",
            "transition": "cut",
        }))

    vs["storyboard"] = normalized
    log.info("storyboard done shots=%d", len(normalized))
    return {"video_state": vs}