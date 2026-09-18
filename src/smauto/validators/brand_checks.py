"""
Brand voice checks.

Uses config/brand.yaml.  Currently a simple forbidden-phrase scan; extend
with tone heuristics (e.g. "we as opener") when you need them.
"""
from __future__ import annotations

import re

import yaml

from ..config.settings import get_settings


def _brand() -> dict:
    return yaml.safe_load(get_settings().brand_path.read_text(encoding="utf-8"))


def check_brand(body: str) -> list[str]:
    """
    Return a list of brand violations.  Empty list = clean.

    Severity: all current checks are "soft" — they should be surfaced to QA
    but shouldn't fail a run on their own.
    """
    issues: list[str] = []
    if not body:
        return issues

    low = body.lower()
    cfg = _brand()

    # 1. forbidden phrases
    for phrase in cfg.get("forbidden_phrases", []):
        if not phrase:
            continue
        if phrase.lower() in low:
            issues.append(f"forbidden phrase used: '{phrase}'")

    # 2. 'we' as sentence opener (brand rule for some brands)
    for rule in cfg.get("tone_rules", []):
        if "avoid 'we' as opener" in rule.lower():
            if re.search(r"(^|[.!?]\s+)we\b", body, flags=re.IGNORECASE):
                issues.append("opens a sentence with 'we'")
            break

    return issues