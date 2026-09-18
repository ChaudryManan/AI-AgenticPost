"""
X (Twitter) publisher — API v2.

Notes:
  • v2 basic tier allows ~500 posts/month — check your quota.
  • Threads are not implemented here; the platform formatter splits long
    copy into 1/n chunks but this adapter posts a single tweet.  Add a
    thread loop when you need it.
  • Media upload requires the v1.1 media endpoint + OAuth 1.0a — we only
    post text.  Add media handling when your app is approved for it.
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

log = get_logger("publisher.x")

_TWEETS_URL = "https://api.twitter.com/2/tweets"
_MAX_CHARS = 280


def _token() -> str:
    t = os.getenv("X_BEARER_TOKEN")
    if not t:
        raise AuthFailed("X_BEARER_TOKEN is not set")
    return t


@register("x")
class XPublisher:
    name = "x"

    async def publish(
        self,
        *,
        body: str,
        media: list[Path] | None = None,       # noqa: ARG002
        hashtags: list[str] | None = None,     # noqa: ARG002
    ) -> PublishResult:
        text = body.strip()
        if len(text) > _MAX_CHARS:
            # trim to 277 + ellipsis so we never hit the API with an overlong
            # payload — the formatter should have handled this, but belt+braces
            text = text[: _MAX_CHARS - 3].rstrip() + "..."

        headers = {
            "Authorization": f"Bearer {_token()}",
            "Content-Type": "application/json",
        }

        with span("publish.x", chars=len(text)):
            async with httpx.AsyncClient(timeout=45.0) as c:
                r = await c.post(_TWEETS_URL, headers=headers, json={"text": text})

        if r.status_code == 429:
            raise RateLimited(f"x 429: {r.text[:200]}")
        if r.status_code in (401, 403):
            raise AuthFailed(f"x {r.status_code}: {r.text[:200]}")
        if r.status_code >= 400:
            raise PublishError(f"x {r.status_code}: {r.text[:200]}")

        data = (r.json() or {}).get("data", {})
        tweet_id = data.get("id")
        if not tweet_id:
            raise PublishError(f"x 2xx but no tweet id: {r.text[:200]}")

        url = f"https://x.com/i/web/status/{tweet_id}"
        log.info("x published id=%s", tweet_id)
        return PublishResult(platform="x", status="ok", post_id=tweet_id, url=url)

    async def fetch_metrics(self, post_id: str) -> dict[str, Any]:
        url = f"https://api.twitter.com/2/tweets/{post_id}"
        params = {"tweet.fields": "public_metrics"}
        headers = {"Authorization": f"Bearer {_token()}"}
        async with httpx.AsyncClient(timeout=30.0) as c:
            r = await c.get(url, params=params, headers=headers)
        if r.status_code >= 400:
            return {"error": f"http {r.status_code}"}
        return ((r.json() or {}).get("data") or {}).get("public_metrics", {})