"""
GraphState — the single source of truth for one run.

Every node reads from this and returns a partial dict that LangGraph merges
back in.  Fields with `Annotated[..., reducer]` are the ones that can be
written by more than one node, or in parallel.
"""
from __future__ import annotations

from typing import Annotated, Any, Literal, TypedDict

from .qa_state import QAState
from .reducers import merge_dict, merge_list, or_bool, take_last
from .text_state import TextState
from .video_state import VideoState

ContentType = Literal["video", "text", "both"]


class PublishResult(TypedDict, total=False):
    platform: str
    post_id: str | None
    url: str | None
    status: str        # "ok" | "error"
    error: str | None


class ErrorEntry(TypedDict, total=False):
    node: str
    type: str
    retry_count: int
    detail: str


class GraphState(TypedDict, total=False):
    # ── identity ──────────────────────────────────────────────────────
    run_id: str

    # ── raw request + parsed fields ───────────────────────────────────
    request: str
    content_type: ContentType
    topic: str
    goal: str
    platforms: list[str]

    # ── trunk outputs ─────────────────────────────────────────────────
    plan: dict[str, Any]                    # planner
    research: dict[str, Any]                # {facts, sources, confidence, requery_count}
    strategy: dict[str, Any]                # {hook, angle, tone, structure, cta}

    # ── branches (parallel-safe: merged, not replaced) ────────────────
    video_state: Annotated[VideoState, merge_dict]
    text_state: Annotated[TextState, merge_dict]

    # ── QA / revision / approval ──────────────────────────────────────
    qa: Annotated[QAState, merge_dict]
    revision_count: Annotated[int, take_last]
    approval: Annotated[dict[str, Any], merge_dict]

    # ── publish / feedback ────────────────────────────────────────────
    publish_results: Annotated[list[PublishResult], merge_list]
    errors: Annotated[list[ErrorEntry], merge_list]

    # ── routing flags ─────────────────────────────────────────────────
    clarification_needed: Annotated[bool, or_bool]
    clarification_question: str
    needs_revision: Annotated[bool, or_bool]
    escalate: Annotated[bool, or_bool]