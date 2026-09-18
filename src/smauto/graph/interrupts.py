"""
Payload helpers for the two human-in-the-loop pause points.

The graph compiles with interrupt_before=["clarify", "approval"].  When the
graph stops at one of those nodes, the API surfaces these payloads to the
caller so the human knows what they're being asked.
"""
from __future__ import annotations

from typing import Any

CLARIFY_INTERRUPT = "clarify"
APPROVAL_INTERRUPT = "approval"


def clarify_payload(state: dict[str, Any]) -> dict[str, Any]:
    """What to show the caller when paused for clarification."""
    return {
        "kind": CLARIFY_INTERRUPT,
        "run_id": state.get("run_id"),
        "question": state.get("clarification_question")
        or "Could you clarify your request?",
        "current": {
            "request": state.get("request"),
            "content_type": state.get("content_type"),
            "platforms": state.get("platforms", []),
        },
    }


def approval_payload(state: dict[str, Any]) -> dict[str, Any]:
    """What to show the caller when paused for approval."""
    strategy = state.get("strategy") or {}
    qa = state.get("qa") or {}
    return {
        "kind": APPROVAL_INTERRUPT,
        "run_id": state.get("run_id"),
        "hook": strategy.get("hook"),
        "tone": strategy.get("tone"),
        "platforms": state.get("platforms", []),
        "content_type": state.get("content_type"),
        "qa_passed": qa.get("passed"),
        "qa_failures": qa.get("failures", []),
    }