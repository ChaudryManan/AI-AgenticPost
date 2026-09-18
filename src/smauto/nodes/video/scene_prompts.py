"""
SCENE PROMPTS — one generation prompt + negative prompt per scene.

Merges storyboard framing with style-bible look for consistency.
"""
from __future__ import annotations

from jinja2 import Template

from ...config.settings import get_settings
from ...infra.logging import get_logger
from ...infra.tracing import span
from ...services.llm import get_llm
from ...state.schema import GraphState

log = get_logger("node.scene_prompts")


async def scene_prompts_node(state: GraphState) -> dict:
    s = get_settings()
    vs = dict(state.get("video_state") or {})
    shots = vs.get("storyboard") or []
    bible = vs.get("style_bible") or {}

    if not shots:
        log.warning("scene_prompts called with empty storyboard")
        vs["scene_prompts"] = []
        return {"video_state": vs}

    prompt = Template((s.prompts_dir / "scene_prompt.j2").read_text(encoding="utf-8")).render(
        shots=shots,
        style_bible=bible,
    )

    with span("node.scene_prompts", n=len(shots)):
        data = await get_llm().json(
            node="scene_prompts",
            system="You write image/video generation prompts. Output strict JSON.",
            user=prompt,
        )

    prompts = data.get("prompts") or []
    # normalize: one entry per scene, aligned by scene_id
    by_id = {int(p.get("scene_id", -1)): p for p in prompts if "scene_id" in p}
    normalized = []
    for sh in shots:
        sid = int(sh.get("scene_id", -1))
        p = by_id.get(sid)
        if p is None:
            p = {
                "scene_id": sid,
                "prompt": f"Cinematic shot: {sh.get('composition', 'wide shot')}",
                "negative_prompt": "text, watermark, blurry",
            }
        normalized.append(p)

    vs["scene_prompts"] = normalized
    log.info("scene_prompts done n=%d", len(normalized))
    return {"video_state": vs}