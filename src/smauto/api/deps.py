"""
FastAPI dependency accessors.

The graph and checkpointer live on `app.state` (set during lifespan
startup).  These helpers give route handlers a clean way to reach them
without importing the app module directly.
"""
from __future__ import annotations

from typing import Any

from fastapi import Request


def get_graph(request: Request) -> Any:
    """Return the compiled graph instance from app.state."""
    g = getattr(request.app.state, "graph", None)
    if g is None:
        raise RuntimeError(
            "graph not initialized — did the app's lifespan startup run?"
        )
    return g


def get_checkpointer(request: Request) -> Any:
    return getattr(request.app.state, "checkpointer", None)