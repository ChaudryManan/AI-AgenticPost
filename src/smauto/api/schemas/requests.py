"""Pydantic request models for the API."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CreateRun(BaseModel):
    request: str = Field(..., min_length=4, max_length=2000,
                         description="Raw prompt describing what to create.")
    content_type: Literal["video", "text", "both"] | None = Field(
        default=None,
        description="Force content type; if omitted, parsed from the request.",
    )
    platforms: list[str] | None = Field(
        default=None,
        description="Target platforms; if omitted, parsed from the request.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "request": "Write a LinkedIn post about RAG for customer support",
                "content_type": "text",
                "platforms": ["linkedin"],
            }
        }
    }


class ApprovalDecision(BaseModel):
    status: Literal["approved", "rejected", "edited"]
    notes: str | None = Field(default=None, max_length=2000)
    editor: str | None = Field(default=None, max_length=128)


class ClarifyAnswer(BaseModel):
    """The user's reply to a clarification question."""
    answer: str = Field(..., min_length=1, max_length=2000)