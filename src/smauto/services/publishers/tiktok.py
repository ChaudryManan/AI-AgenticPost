"""
TikTok publisher — interface stub.

Why this is a stub:
  • TikTok's Content Posting API requires the "Direct Post" feature to be
    approved on your developer app (a manual review process, usually 2-4
    weeks).  Without approval, only draft uploads are permitted.
  • Flow (once approved):
      1. POST /v2/post/publish/video/init/  → upload_url + publish_id
      2. PUT the file to upload_url
      3. POST /v2/post/publish/video/publish/ with publish_id
  • Rate limit: 6 posts / 24h per user with basic approval.

Wire up the flow once your app is approved — the code below leaves a clear
insertion point and raises a helpful error until then.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ...infra.errors import AuthFailed, PublishError
from ...infra.logging import get_logger
from .base import PublishResult
from .registry import register

log = get_logger("publisher.tiktok")


@register("tiktok")
class TikTokPublisher:
    name = "tiktok"

    async def publish(
        self,
        *,
        body: str,                             # noqa: ARG002
        media: list[Path] | None = None,       # noqa: ARG002
        hashtags: list[str] | None = None,     # noqa: ARG002
    ) -> PublishResult:
        if not os.getenv("TIKTOK_ACCESS_TOKEN"):
            raise AuthFailed("TIKTOK_ACCESS_TOKEN is not set")

        raise PublishError(
            "TikTok Content Posting API requires approved 'Direct Post' access. "
            "Apply at https://developers.tiktok.com/ and then implement the "
            "3-step flow (init / upload / publish) in this file."
        )

    async def fetch_metrics(self, post_id: str) -> dict[str, Any]:
        return {"post_id": post_id, "note": "TikTok metrics API not implemented"}