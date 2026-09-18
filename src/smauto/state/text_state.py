from __future__ import annotations

from typing import Any, TypedDict


class Variant(TypedDict, total=False):
    hook: str
    body: str
    cta: str
    score: float
    # populated by variant_scorer — kept so callers can inspect sub-scores
    scores: dict[str, float]


class TextState(TypedDict, total=False):
    # copywriter → scorer
    variants: list[Variant]
    draft: Variant                        # the chosen best variant

    # formatter
    platform_bodies: dict[str, str]       # {platform: formatted_body}

    # hashtags + visual
    hashtags: list[str]
    visual_type: str                      # "none" | "quote" | "carousel"
    slides: list[dict[str, Any]]          # [{index, title, body}]
    image_paths: list[str]

    # QA
    fact_check: dict[str, Any]            # {"failures": [...]}
    seo: dict[str, Any]                   # {"grade": float, "hook_ok": bool}