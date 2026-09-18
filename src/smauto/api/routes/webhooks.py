"""
Platform webhook receiver.

Real platforms POST events here (post published, metrics ready, token
revoked, etc.).  We log them for now — wire real handlers when you need
reactive behavior.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from ...infra.logging import get_logger

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
log = get_logger("api.webhooks")


@router.post("/{platform}")
async def receive(platform: str, request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        raw = await request.body()
        payload = {"_raw": raw.decode("utf-8", errors="replace")[:2000]}

    log.info("webhook platform=%s keys=%s", platform, list(payload.keys()))
    return {"ok": True, "platform": platform, "received_keys": list(payload.keys())}