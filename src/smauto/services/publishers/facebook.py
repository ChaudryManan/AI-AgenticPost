"""
Facebook Page publisher — Graph API v20.

Posts to a Page feed.  Media (photo/video) requires a separate upload flow
and is not wired here — text-only for now.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx

from ...infra.errors import AuthFailed, PublishError, RateLimited
from ...infra.logging import get_logger
from ...infra.tracing import span
from .base import PublishResult
from .registry import register

log = get_logger("publisher.facebook")

_GRAPH = "https://graph.facebook.com/v20.0"


def _creds() -> tuple[str, str]:
    token = os.getenv("FB_PAGE_TOKEN")
    page_id = os.getenv("FB_PAGE_ID")
    if not token:
        raise AuthFailed("FB_PAGE_TOKEN is not set")
    if not page_id:
        raise AuthFailed("FB_PAGE_ID is not set")
    return token, page_id


@register("facebook")
class FacebookPublisher:
    name = "facebook"

    async def publish(
        self,
        *,
        body: str,
        media: list[Path] | None = None,       # noqa: ARG002
        hashtags: list[str] | None = None,     # noqa: ARG002
    ) -> PublishResult:
        token, page_id = _creds()
        url = f"{_GRAPH}/{page_id}/feed"

        with span("publish.facebook", chars=len(body)):
            async with httpx.AsyncClient(timeout=60.0) as c:
                r = await c.post(url, params={
                    "access_token": token,
                    "message": body,
                })

        if r.status_code == 429:
            raise RateLimited(f"facebook 429: {r.text[:200]}")
        if r.status_code in (401, 403):
            raise AuthFailed(f"facebook {r.status_code}: {r.text[:200]}")
        if r.status_code >= 400:
            raise PublishError(f"facebook {r.status_code}: {r.text[:200]}")

        post_id = (r.json() or {}).get("id")
        if not post_id:
            raise PublishError("facebook 2xx but no post id")

        url = f"https://www.facebook.com/{post_id}"
        log.info("facebook published id=%s", post_id)
        return PublishResult(platform="facebook", status="ok", post_id=post_id, url=url)

    async def fetch_metrics(self, post_id: str) -> dict[str, Any]:
        token, _ = _creds()
        url = f"{_GRAPH}/{post_id}"
        params = {
            "access_token": token,
            "fields": "shares,comments.summary(true),reactions.summary(true)",
        }
        async with httpx.AsyncClient(timeout=30.0) as c:
            r = await c.get(url, params=params)
        if r.status_code >= 400:
            return {"error": f"http {r.status_code}"}
        data = r.json()
        return {
            "shares": (data.get("shares") or {}).get("count", 0),
            "comments": ((data.get("comments") or {}).get("summary") or {}).get("total_count", 0),
            "reactions": ((data.get("reactions") or {}).get("summary") or {}).get("total_count", 0),
            "raw": data,
        }