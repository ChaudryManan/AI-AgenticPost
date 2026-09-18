"""
Instagram publisher — interface stub.

Why this is a stub:
  • IG Graph API requires media (image or video) to be hosted at a PUBLIC url
    first — you can't upload raw bytes.  This means we need an S3/CDN step
    that produces a public URL before calling /media.
  • Then: POST /{ig-user-id}/media  → returns a container id
  • Then: POST /{ig-user-id}/media_publish  → publishes the container
  • Rate limit: 25 posts / 24h per IG user.

Implement `_upload_to_public_url(local_path)` using your S3 bucket
(config.settings.s3_bucket) and then the two-step publish below will work
as written — the rest of the flow is already correct.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx

from ...infra.errors import AuthFailed, PublishError, RateLimited
from ...infra.logging import get_logger
from .base import PublishResult
from .registry import register

log = get_logger("publisher.instagram")

_GRAPH = "https://graph.facebook.com/v20.0"


def _creds() -> tuple[str, str]:
    token = os.getenv("IG_ACCESS_TOKEN")
    user_id = os.getenv("IG_USER_ID")
    if not token:
        raise AuthFailed("IG_ACCESS_TOKEN is not set")
    if not user_id:
        raise AuthFailed("IG_USER_ID is not set")
    return token, user_id


@register("instagram")
class InstagramPublisher:
    name = "instagram"

    async def publish(
        self,
        *,
        body: str,
        media: list[Path] | None = None,
        hashtags: list[str] | None = None,     # noqa: ARG002
    ) -> PublishResult:
        token, user_id = _creds()

        if not media:
            raise PublishError(
                "Instagram requires at least one media file (image or video). "
                "Configure S3 storage and wire _upload_to_public_url()."
            )

        # ── Step 1: get a public URL for the first media file ─────────
        public_url = await self._upload_to_public_url(media[0])

        # ── Step 2: create the media container ────────────────────────
        is_video = media[0].suffix.lower() in {".mp4", ".mov", ".m4v"}
        container_endpoint = f"{_GRAPH}/{user_id}/media"
        container_params: dict[str, Any] = {
            "access_token": token,
            "caption": body,
            "media_type": "REELS" if is_video else "IMAGE",
        }
        if is_video:
            container_params["video_url"] = public_url
        else:
            container_params["image_url"] = public_url

        async with httpx.AsyncClient(timeout=90.0) as c:
            r1 = await c.post(container_endpoint, params=container_params)
            if r1.status_code == 429:
                raise RateLimited(f"ig container 429: {r1.text[:200]}")
            if r1.status_code in (401, 403):
                raise AuthFailed(f"ig container {r1.status_code}: {r1.text[:200]}")
            if r1.status_code >= 400:
                raise PublishError(f"ig container {r1.status_code}: {r1.text[:200]}")

            container_id = (r1.json() or {}).get("id")
            if not container_id:
                raise PublishError("ig container 2xx but no id")

            # ── Step 3: publish the container ─────────────────────────
            r2 = await c.post(
                f"{_GRAPH}/{user_id}/media_publish",
                params={"access_token": token, "creation_id": container_id},
            )

        if r2.status_code == 429:
            raise RateLimited(f"ig publish 429: {r2.text[:200]}")
        if r2.status_code in (401, 403):
            raise AuthFailed(f"ig publish {r2.status_code}: {r2.text[:200]}")
        if r2.status_code >= 400:
            raise PublishError(f"ig publish {r2.status_code}: {r2.text[:200]}")

        post_id = (r2.json() or {}).get("id")
        if not post_id:
            raise PublishError("ig publish 2xx but no id")

        log.info("instagram published id=%s", post_id)
        return PublishResult(
            platform="instagram", status="ok", post_id=post_id,
            url=f"https://www.instagram.com/p/{post_id}",
            meta={"container_id": container_id, "media_url": public_url},
        )

    async def _upload_to_public_url(self, local_path: Path) -> str:
        """
        Upload media somewhere publicly reachable and return the URL.

        Default implementation calls services.storage.artifacts.put_artifact
        which handles S3 if S3_BUCKET is configured.  If you don't have a
        public bucket, replace this with a signed-URL uploader.
        """
        from ...storage.artifacts import put_artifact, public_url
        uri = put_artifact(Path(local_path))
        url = public_url(uri)
        if not url.startswith(("http://", "https://")):
            raise PublishError(
                f"Instagram needs a public HTTPS URL, got {url!r}. "
                f"Configure S3_BUCKET and make objects publicly readable."
            )
        return url

    async def fetch_metrics(self, post_id: str) -> dict[str, Any]:
        token, _ = _creds()
        url = f"{_GRAPH}/{post_id}/insights"
        params = {
            "access_token": token,
            "metric": "impressions,reach,likes,comments,saved",
        }
        async with httpx.AsyncClient(timeout=30.0) as c:
            r = await c.get(url, params=params)
        if r.status_code >= 400:
            return {"error": f"http {r.status_code}"}
        return {"data": (r.json() or {}).get("data", [])}