"""
Minimal span-based tracing.

If LangSmith is enabled (`LANGCHAIN_TRACING_V2=true`) LangGraph/LangChain
report automatically — this module is the app-level fallback so you always
get timing logs, and a place to plug OpenTelemetry later.

Usage:
    async with span("node.script", run_id=rid):
        ...
"""
from __future__ import annotations

import contextlib
import os
import time
from typing import Any

from .logging import get_logger

log = get_logger("tracing")


@contextlib.contextmanager
def span(name: str, **attrs: Any):
    t0 = time.perf_counter()
    try:
        yield
    except Exception as e:  # noqa: BLE001
        dt = (time.perf_counter() - t0) * 1000.0
        log.error("span.fail %s %.1fms err=%s attrs=%s", name, dt, e, attrs)
        raise
    else:
        dt = (time.perf_counter() - t0) * 1000.0
        log.info("span.ok %s %.1fms attrs=%s", name, dt, attrs)


def langsmith_enabled() -> bool:
    return os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"


def current_run_context(run_id: str) -> dict[str, str]:
    """Mergeable context used by loggers that support structured bindings."""
    return {"run_id": run_id}