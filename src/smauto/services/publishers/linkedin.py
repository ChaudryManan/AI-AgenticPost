"""
LinkedIn publisher — UGC Posts API (v2).

Notes:
  • Author URN:  urn:li:person:{sub}  for personal, urn:li:organization:{id} for org.
    This stub reads LINKEDIN_AUTHOR_URN from env so you can configure either
    without editing code.
  • Links inside the post body are penalized by LinkedIn's feed algorithm —
    the platform rules already enforce links_in_body: false for LinkedIn.
  • Rate limits: 100 posts/day per member, 20/day per org as of 2024.
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

log = get_logger("publisher.linkedin")

_UGC_URL = "https://api.linkedin.com/v2/ugcPosts"
_ME_URL = "https://api.linkedin.com/v2/userinfo"


def _token() -> str:
    t = os.getenv("LINKEDIN_ACCESS_TOKEN")
    if not t:
        raise AuthFailed("LINKEDIN_ACCESS_TOKEN is not set")
    return t


def _author_urn() -> str:
    # explicit override wins
    urn = os.getenv("LINKEDIN_AUTHOR_URN")
    if urn:
        return urn
    # fallback: we'd need to call /v2/me to resolve — do it lazily in publish
    return ""


@register("linkedin")
class LinkedInPublisher:
    name = "linkedin"

    async def _resolve_author(self, client: httpx.AsyncClient) -> str:
        urn = _author_urn()
        if urn:
            return urn
        r = await client.get(
            _ME_URL,
            headers={"Authorization": f"Bearer {_token()}"},
        )
        if r.status_code in (401, 403):
            raise AuthFailed(f"LinkedIn /userinfo {r.status_code}: {r.text[:200]}")
        if r.status_code >= 400:
            raise PublishError(f"LinkedIn /userinfo {r.status_code}: {r.text[:200]}")
        sub = r.json().get("sub")
        if not sub:
            raise PublishError("LinkedIn /userinfo missing 'sub'")
        return f"urn:li:person:{sub}"

    async def publish(
        self,
        *,
        body: str,
        media: list[Path] | None = None,       # noqa: ARG002 — video/photo not wired yet
        hashtags: list[str] | None = None,     # noqa: ARG002
    ) -> PublishResult:
        headers = {
            "Authorization": f"Bearer {_token()}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        }

        with span("publish.linkedin", chars=len(body)):
            async with httpx.AsyncClient(timeout=60.0) as c:
                author = await self._resolve_author(c)

                payload = {
                    "author": author,
                    "lifecycleState": "PUBLISHED",
                    "specificContent": {
                        "com.linkedin.ugc.ShareContent": {
                            "shareCommentary": {"text": body},
                            "shareMediaCategory": "NONE",
                        }
                    },
                    "visibility": {
                        "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                    },
                }

                r = await c.post(_UGC_URL, headers=headers, json=payload)

        if r.status_code == 429:
            raise RateLimited(f"linkedin 429: {r.text[:200]}")
        if r.status_code in (401, 403):
            raise AuthFailed(f"linkedin {r.status_code}: {r.text[:200]}")
        if r.status_code >= 400:
            raise PublishError(f"linkedin {r.status_code}: {r.text[:200]}")

        # LinkedIn returns the post URN in a header, not the body.
        post_urn = r.headers.get("x-restli-id") or (r.json() or {}).get("id")
        if not post_urn:
            raise PublishError("linkedin 2xx but no post URN in response")

        url = f"https://www.linkedin.com/feed/update/{post_urn}"
        log.info("linkedin published id=%s", post_urn)

        return PublishResult(
            platform="linkedin",
            status="ok",
            post_id=post_urn,
            url=url,
            meta={"author": author},
        )

    async def fetch_metrics(self, post_id: str) -> dict[str, Any]:
        # LinkedIn's socialActions endpoint reports likes/comments/shares.
        # Kept minimal — expand when you need impressions/CTR.
        url = f"https://api.linkedin.com/v2/socialActions/{post_id}"
        headers = {"Authorization": f"Bearer {_token()}"}
        async with httpx.AsyncClient(timeout=30.0) as c:
            r = await c.get(url, headers=headers)
        if r.status_code >= 400:
            log.warning("linkedin metrics failed %s: %s", r.status_code, r.text[:200])
            return {"error": f"http {r.status_code}"}
        data = r.json()
        return {
            "likes": (data.get("likesSummary") or {}).get("totalLikes", 0),
            "comments": (data.get("commentsSummary") or {}).get("totalFirstLevelComments", 0),
            "raw": data,
        }