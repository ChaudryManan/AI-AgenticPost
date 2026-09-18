"""
Alias module — some callers expect the `*_edges` naming convention.
Everything delegates to graph.routers; there is exactly one implementation
of each routing decision.
"""
from __future__ import annotations

from .routers import (
    approval_router as approval_edges,
    content_router as content_edges,
    input_router as input_edges,
    qa_router as qa_edges,
    research_router as research_edges,
    revision_router as revision_edges,
)

__all__ = [
    "input_edges",
    "research_edges",
    "content_edges",
    "qa_edges",
    "revision_edges",
    "approval_edges",
]