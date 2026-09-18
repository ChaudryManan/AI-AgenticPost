"""
Structlog-lite: a stdlib logging wrapper with a consistent format.

If `structlog` is installed we use its JSON renderer in prod and a colorful
console renderer in dev.  Otherwise we fall back to stdlib — the rest of the
codebase only ever calls `get_logger(...)` and `.info/.warning/.error`.
"""
from __future__ import annotations

import logging
import os
import sys

from ..config.settings import get_settings

_CONFIGURED = False


def setup_logging() -> None:
    """Idempotent: safe to call from API startup, CLI, and workers."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    s = get_settings()
    level = getattr(logging, s.log_level.upper(), logging.INFO)

    # Try structlog first — graceful fallback if not installed.
    try:
        import structlog  # type: ignore

        json_logs = os.getenv("LOG_FORMAT", "console").lower() == "json"
        renderer = (structlog.processors.JSONRenderer()
                    if json_logs else structlog.dev.ConsoleRenderer())
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.processors.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                renderer,
            ],
            wrapper_class=structlog.make_filtering_bound_logger(level),
            logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
            cache_logger_on_first_use=True,
        )
        _CONFIGURED = True
        return
    except ImportError:
        pass

    # stdlib fallback
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
        stream=sys.stdout,
        force=True,
    )
    _CONFIGURED = True


def get_logger(name: str):
    """Return a logger.  Prefers structlog, falls back to stdlib."""
    setup_logging()
    try:
        import structlog  # type: ignore
        return structlog.get_logger(name)
    except ImportError:
        return logging.getLogger(name)