"""
YouTube Shorts publisher — interface stub.

Why this is a stub:
  • YouTube uploads use a resumable upload protocol:
      1. POST /upload/youtube/v3/videos?uploadType=resumable  → session URL
      2. PUT chunks to the session URL, tracking Content-Range
      3. The final response contains the video id.
  • You also need an OAuth 2.0 access token with the youtube.upload scope.
  • Shorts are just regular uploads with vertical aspect + #Shorts in the
    title/description — no special endpoint.

Full resumable upload is ~40 lines; leaving it stubbed so you can drop in
your google-auth flow (service account or installed-app) when ready.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ...infra.errors import AuthFailed, PublishError
from ...infra.logging import get_logger
from .base import PublishResult
from .registry import register

log = get_logger("publisher.youtube")


@register("youtube")
class YouTubePublisher:
    name = "youtube"

    async def publish(
        self,
        *,
        body: str,
        media: list[Path] | None = None,
        hashtags: list[str] | None = None,     # noqa: ARG002
    ) -> PublishResult:
        if not os.getenv("YT_ACCESS_TOKEN"):
            raise AuthFailed("YT_ACCESS_TOKEN is not set")

        if not media:
            raise PublishError("YouTube requires a video file")

        raise PublishError(
            "YouTube requires a resumable upload flow with OAuth 2.0. "
            "Implement it in this file using google-auth + the "
            "/upload/youtube/v3/videos endpoint. "
            f"(Title from body: {body[:60]!r}, media: {media[0].name})"
        )

    async def fetch_metrics(self, post_id: str) -> dict[str, Any]:
        return {"post_id": post_id, "note": "YouTube metrics API not implemented"}