"""
Reducers — merge functions for LangGraph state channels.

Every field in GraphState that can be written by more than one node (or by a
node running in parallel) needs a reducer.  Without one, LangGraph's default
is "last write wins" and parallel updates raise an error.

The reducer signature is always:
    (existing_value, incoming_value) -> new_value
"""
from __future__ import annotations

from typing import Any


def merge_dict(a: dict[str, Any] | None,
               b: dict[str, Any] | None) -> dict[str, Any]:
    """
    Recursive shallow-ish merge — b wins on scalar collisions.

    Nested dicts merge recursively.  Lists and scalars from b REPLACE those
    from a (they don't concatenate).  This is what we want for sub-states like
    video_state / text_state where each node returns the full sub-state.
    """
    a = a or {}
    b = b or {}
    out = dict(a)
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = merge_dict(out[k], v)
        else:
            out[k] = v
    return out


def merge_list(a: list[Any] | None, b: list[Any] | None) -> list[Any]:
    """Concatenate — order preserved, a first."""
    return (a or []) + (b or [])


def take_last(_a: Any, b: Any) -> Any:
    """Explicit last-write-wins — use for counters, status flags."""
    return b


def or_bool(a: bool | None, b: bool | None) -> bool:
    """OR two booleans — once True, stays True for the run."""
    return bool(a) or bool(b)