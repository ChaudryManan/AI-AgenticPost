"""
PLATFORM FORMATTER — adapt the draft per platform.

Produces state.text_state.platform_bodies = {platform: formatted_body}.
Enforces the char cap from config/platforms.yaml locally (in case the LLM
overshoots).
"""
from __future__ import annotations

import yaml
from jinja2 import Template

from ...config.settings import get_settings
from ...infra.logging import get_logger
from ...infra.tracing import span
from ...services.llm import get_llm
from ...state.schema import GraphState

log = get_logger("node.platform_formatter")


def _draft_text(draft: dict) -> str:
    parts = [draft.get("hook") or "", draft.get("body") or "", draft.get("cta") or ""]
    return "\n\n".join(p for p in parts if p).strip()


async def platform_formatter_node(state: GraphState) -> dict:
    s = get_settings()
    ts = dict(state.get("text_state") or {})
    draft = ts.get("draft") or {}
    platforms = state.get("platforms") or []

    if not draft or not platforms:
        ts["platform_bodies"] = {}
        return {"text_state": ts}

    try:
        rules = yaml.safe_load(s.platforms_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        rules = {}

    draft_text = _draft_text(draft)
    prompt_tpl = Template((s.prompts_dir / "platform_format.j2").read_text(encoding="utf-8"))

    bodies: dict[str, str] = {}

    for platform in platforms:
        r = rules.get(platform, {})
        prompt = prompt_tpl.render(platform=platform, rules=r, draft=draft_text)

        with span("node.platform_formatter.one", platform=platform):
            data = await get_llm().json(
                node="platform_format",
                system=f"Adapt the copy for {platform}. Output strict JSON.",
                user=prompt,
            )

        body = (data.get("body") or draft_text).strip()

        # enforce char cap defensively
        cap = r.get("max_chars")
        if cap and len(body) > cap:
            log.warning("formatter overshot %s (%d > %d), truncating",
                        platform, len(body), cap)
            body = body[: cap - 1].rstrip() + "…"

        # hard rule: no links in body
        if not r.get("links_in_body", True):
            for marker in ("http://", "https://", "www."):
                if marker in body.lower():
                    log.warning("formatter left a link in %s body — stripping", platform)
                    # crude but effective: cut everything from the first URL on
                    idx = min((body.lower().find(m) for m in
                               ("http://", "https://", "www.")
                               if m in body.lower()), default=-1)
                    if idx >= 0:
                        body = body[:idx].rstrip()
                    break

        bodies[platform] = body

    ts["platform_bodies"] = bodies
    log.info("platform_formatter done n=%d", len(bodies))
    return {"text_state": ts}