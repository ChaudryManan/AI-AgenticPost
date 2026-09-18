"""
HASHTAGS — pick per-platform hashtags, respecting the platform cap and the
banned-terms policy.
"""
from __future__ import annotations

import yaml
from jinja2 import Template

from ...config.settings import get_settings
from ...infra.logging import get_logger
from ...infra.tracing import span
from ...services.llm import get_llm
from ...state.schema import GraphState

log = get_logger("node.hashtags")


def _banned() -> set[str]:
    p = get_settings().policies_dir / "banned_terms.txt"
    if not p.exists():
        return set()
    return {ln.strip().lower() for ln in p.read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.startswith("#")}


def _is_banned(tag: str, banned: set[str]) -> bool:
    low = tag.lower().lstrip("#")
    return any(b in low for b in banned)


async def hashtags_node(state: GraphState) -> dict:
    s = get_settings()
    ts = dict(state.get("text_state") or {})
    bodies = ts.get("platform_bodies") or {}
    if not bodies:
        ts["hashtags"] = []
        return {"text_state": ts}

    try:
        rules = yaml.safe_load(s.platforms_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        rules = {}

    banned = _banned()
    prompt_tpl = Template((s.prompts_dir / "hashtags.j2").read_text(encoding="utf-8"))

    all_tags: list[str] = []
    for platform, body in bodies.items():
        max_tags = rules.get(platform, {}).get("hashtag_max", 5)
        prompt = prompt_tpl.render(
            platform=platform,
            max=max_tags,
            body=body[:1500],   # cap context
            banned=sorted(banned),
        )

        with span("node.hashtags.one", platform=platform):
            data = await get_llm().json(
                node="hashtags",
                system="Return strict JSON with a hashtags array.",
                user=prompt,
            )

        tags = [
            t if t.startswith("#") else f"#{t}"
            for t in (data.get("hashtags") or [])
            if isinstance(t, str) and t.strip()
        ]
        tags = [t for t in tags if not _is_banned(t, banned)][:max_tags]
        all_tags.extend(tags)

    # dedupe while preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for t in all_tags:
        if t.lower() not in seen:
            seen.add(t.lower())
            deduped.append(t)

    ts["hashtags"] = deduped
    log.info("hashtags done n=%d", len(deduped))
    return {"text_state": ts}