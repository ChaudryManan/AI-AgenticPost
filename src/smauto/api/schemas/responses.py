"""Pydantic response models for the API."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class RunCreated(BaseModel):
    run_id: str
    status: str
    interrupt: dict[str, Any] | None = None


class RunStatus(BaseModel):
    run_id: str
    status: str
    state: dict[str, Any]
    interrupt: dict[str, Any] | None = None


class ApprovalResponse(BaseModel):
    run_id: str
    status: str
    next_step: str


class PostList(BaseModel):
    run_id: str
    posts: list[dict[str, Any]]


class HealthResponse(BaseModel):
    ok: bool
    version: str


class ErrorResponse(BaseModel):
    detail: str