"""
Facebook Page publisher — Graph API v20.

Two modes:
  • text-only   → POST /{page_id}/feed   with `message`
  • with image  → POST /{page_id}/photos with `source` (file upload) + `caption`

The `/photos` endpoint creates a photo post that appears in the Page feed
with the caption as its text. It gets significantly more reach than a
text-only post.
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

# image extensions we know how to upload to /photos
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def _creds() -> tuple[str, str]:
    token = os.getenv("FB_PAGE_TOKEN")
    page_id = os.getenv("FB_PAGE_ID")
    if not token:
        raise AuthFailed("FB_PAGE_TOKEN is not set")
    if not page_id:
        raise AuthFailed("FB_PAGE_ID is not set")
    return token, page_id


def _first_image(media: list[Path] | None) -> Path | None:
    """Return the first media file that looks like an image."""
    for p in media or []:
        if p and Path(p).suffix.lower() in _IMAGE_EXTS and Path(p).exists():
            return Path(p)
    return None


@register("facebook")
class FacebookPublisher:
    name = "facebook"

    async def publish(
        self,
        *,
        body: str,
        media: list[Path] | None = None,
        hashtags: list[str] | None = None,     # noqa: ARG002
    ) -> PublishResult:
        token, page_id = _creds()
        image = _first_image(media)

        if image is not None:
            return await self._publish_photo(token, page_id, image, body)
        return await self._publish_text(token, page_id, body)

    # ── text-only post ────────────────────────────────────────────────
    async def _publish_text(self, token: str, page_id: str, body: str) -> PublishResult:
        url = f"{_GRAPH}/{page_id}/feed"

        with span("publish.facebook.text", chars=len(body)):
            async with httpx.AsyncClient(timeout=60.0) as c:
                r = await c.post(url, params={"access_token": token, "message": body})

        self._raise_for_status(r, "text")
        post_id = (r.json() or {}).get("id")
        if not post_id:
            raise PublishError("facebook text 2xx but no post id")

        log.info("facebook text post id=%s", post_id)
        return PublishResult(
            platform="facebook", status="ok", post_id=post_id,
            url=f"https://www.facebook.com/{post_id}",
        )

    # ── photo post ────────────────────────────────────────────────────
    async def _publish_photo(self, token: str, page_id: str,
                             image: Path, caption: str) -> PublishResult:
        """
        Upload a photo to /{page_id}/photos as a multipart form.

        Facebook returns 2xx with `{id, post_id}`. We use `post_id` (the
        feed story id) for the permalink, falling back to `id` (the photo
        object id) if post_id is missing.
        """
        url = f"{_GRAPH}/{page_id}/photos"
        img_bytes = image.read_bytes()

        # multipart: everything except the file goes in `data`, the file
        # itself goes in `files`.
        data = {
            "access_token": token,
            "caption": caption,
            "published": "true",
        }
        files = {
            "source": (image.name, img_bytes, _mime_for(image)),
        }

        with span("publish.facebook.photo", bytes=len(img_bytes)):
            async with httpx.AsyncClient(timeout=120.0) as c:
                r = await c.post(url, data=data, files=files)

        self._raise_for_status(r, "photo")
        payload = r.json() or {}
        post_id = payload.get("post_id") or payload.get("id")
        if not post_id:
            raise PublishError(f"facebook photo 2xx but no id: {payload}")

        log.info("facebook photo post id=%s photo_id=%s", post_id, payload.get("id"))
        return PublishResult(
            platform="facebook", status="ok", post_id=str(post_id),
            url=f"https://www.facebook.com/{post_id}",
            meta={"photo_id": payload.get("id")},
        )

    # ── shared ────────────────────────────────────────────────────────
    @staticmethod
    def _raise_for_status(r: httpx.Response, kind: str) -> None:
        if r.status_code == 429:
            raise RateLimited(f"facebook {kind} 429: {r.text[:200]}")
        if r.status_code in (401, 403):
            raise AuthFailed(f"facebook {kind} {r.status_code}: {r.text[:200]}")
        if r.status_code >= 400:
            raise PublishError(f"facebook {kind} {r.status_code}: {r.text[:200]}")

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


def _mime_for(p: Path) -> str:
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(p.suffix.lower(), "application/octet-stream")