"""
CHARACTERS / STYLE BIBLE — a consistent look for the generated visuals.

Outputs a fixed `seed` so Replicate calls are reproducible.
"""
from __future__ import annotations

import random

import yaml
from jinja2 import Template

from ...config.settings import get_settings
from ...infra.logging import get_logger
from ...infra.tracing import span
from ...services.llm import get_llm
from ...state.schema import GraphState

log = get_logger("node.characters")


async def characters_node(state: GraphState) -> dict:
    s = get_settings()
    vs = dict(state.get("video_state") or {})

    try:
        brand = yaml.safe_load(s.brand_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        brand = {}

    prompt = Template((s.prompts_dir / "character_bible.j2").read_text(encoding="utf-8")).render(
        brand=brand,
        script=vs.get("script") or [],
    )

    with span("node.characters"):
        bible = await get_llm().json(
            node="characters",
            system="Output strict JSON describing a coherent visual style.",
            user=prompt,
        )

    # make sure a seed exists so downstream generation is reproducible
    if "seed" not in bible or bible["seed"] is None:
        bible["seed"] = random.randint(1, 2**31 - 1)

    bible.setdefault("appearance", "modern, clean, professional")
    bible.setdefault("wardrobe", "smart casual")
    bible.setdefault("palette", ["#0F172A", "#22D3EE", "#FFFFFF"])
    bible.setdefault("lighting", "soft key from the left, gentle fill")

    vs["style_bible"] = bible
    log.info("characters done seed=%s", bible["seed"])
    return {"video_state": vs}