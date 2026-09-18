"""Metrics / analytics read endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from ...storage.db.repositories import MetricRepo

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/post/{post_id}")
async def metrics_for_post(post_id: str) -> list[dict]:
    return MetricRepo.list_for_post(post_id)