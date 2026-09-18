from __future__ import annotations

from typing import Literal, TypedDict

Severity = Literal["soft", "hard"]


class QAFailure(TypedDict, total=False):
    stage: str        # node name that produced the failure
    reason: str       # human-readable explanation
    severity: Severity
    detail: dict      # optional structured context


class QAState(TypedDict, total=False):
    passed: bool
    failures: list[QAFailure]
    checked_at: str | None    # ISO-8601 UTC