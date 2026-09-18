"""
Per-platform format constraints.

Reads config/platforms.yaml once per call (cheap — the file is tiny and yaml
caching is fine at this scale).  Raises PlatformViolation on the FIRST hard
violation; the caller decides whether to revise or dead-letter.

Soft issues (near-limit warnings) are returned as strings by
`validate_platform_soft()` so QA can list them without failing the run.
"""
from __future__ import annotations

from typing import Any

import yaml

from ..config.settings import get_settings


class PlatformViolation(Exception):
    """A hard format violation that must be fixed before publishing."""


def _rules() -> dict[str, Any]:
    return yaml.safe_load(get_settings().platforms_path.read_text(encoding="utf-8"))


def _rules_for(platform: str) -> dict[str, Any]:
    rules = _rules().get(platform)
    if not rules:
        known = sorted(_rules().keys())
        raise PlatformViolation(
            f"Unknown platform '{platform}'. Known platforms: {known}"
        )
    return rules


def validate_platform(
    platform: str,
    body: str,
    hashtags: list[str] | None = None,
) -> None:
    """
    Raise PlatformViolation if `body` (with optional `hashtags`) breaks any
    hard rule for `platform`.  Returns None on success.
    """
    rules = _rules_for(platform)

    # content type gate — e.g. YouTube is video-only
    body_len = len(body or "")

    # char limit
    max_chars = rules.get("max_chars")
    if max_chars and body_len > max_chars:
        raise PlatformViolation(
            f"{platform}: body is {body_len} chars, exceeds limit of {max_chars}"
        )

    # hashtag count
    if hashtags:
        max_tags = rules.get("hashtag_max", 0)
        if max_tags and len(hashtags) > max_tags:
            raise PlatformViolation(
                f"{platform}: {len(hashtags)} hashtags, limit is {max_tags}"
            )

    # links in body
    if not rules.get("links_in_body", True):
        low = (body or "").lower()
        if "http://" in low or "https://" in low or "www." in low:
            raise PlatformViolation(
                f"{platform}: links are not allowed in the body "
                f"(move them to the first comment or bio)"
            )


def validate_platform_soft(
    platform: str,
    body: str,
    hashtags: list[str] | None = None,
) -> list[str]:
    """
    Return a list of soft warnings (near-limit, hashtag suggestions, etc.).
    Never raises.  Useful for QA output that shouldn't fail the run.
    """
    warnings: list[str] = []
    try:
        rules = _rules_for(platform)
    except PlatformViolation as e:
        return [str(e)]

    max_chars = rules.get("max_chars", 0)
    if max_chars and body:
        used = len(body) / max_chars
        if used >= 0.95:
            warnings.append(
                f"{platform}: body is at {used:.0%} of the {max_chars}-char limit"
            )

    max_tags = rules.get("hashtag_max", 0)
    if max_tags and hashtags:
        if len(hashtags) > max_tags - 1:
            warnings.append(
                f"{platform}: near hashtag cap ({len(hashtags)}/{max_tags})"
            )

    return warnings