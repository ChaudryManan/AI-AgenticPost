"""
Trend signals per platform.

This is a *stub* on purpose — real trend APIs (Google Trends, TikTok Creative
Center, X trends) each need their own auth.  The interface is the shape the
planner and research nodes expect, so plugging in a real source later is a
drop-in replacement.
"""
from __future__ import annotations

from typing import Any

from ...infra.logging import get_logger

log = get_logger("trends")


async def fetch_trends(topic: str, platform: str,
                       limit: int = 5) -> list[dict[str, Any]]:
    """
    Returns a list of trend signals:
        [{"topic": str, "platform": str, "signal": str, "score": float}, ...]

    Stub returns [] so callers degrade gracefully.
    """
    log.info("fetch_trends stub called topic=%s platform=%s", topic, platform)
    return []