"""
Publisher protocol + result type.

Every platform adapter is a class with:
    name: str
    async publish(*, body, media, hashtags) -> PublishResult
    async fetch_metrics(post_id) -> dict

The publish node calls these through services/publishers/registry.get_publisher()
and catches typed errors (RateLimited / AuthFailed / FormatRejected / PublishError)
to decide whether to retry, re-auth, or dead-letter.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@dataclass
class PublishResult:
    platform: str
    status: str                        # "ok" | "error"
    post_id: str | None = None
    url: str | None = None
    error: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == "ok"


@runtime_checkable
class Publisher(Protocol):
    name: str

    async def publish(
        self,
        *,
        body: str,
        media: list[Path] | None = None,
        hashtags: list[str] | None = None,
    ) -> PublishResult: ...

    async def fetch_metrics(self, post_id: str) -> dict[str, Any]: ...