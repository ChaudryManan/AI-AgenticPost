"""
Checkpointer factory.

The default is MemorySaver — it works with async graph execution out of the
box, which is what all our nodes use (async def).

For persistence across process restarts, call setup_async_checkpointer() at
app startup (API, CLI, worker) and pass the result to build_graph().  That
gives you an AsyncPostgresSaver or AsyncSqliteSaver as a long-lived object.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from ..config.settings import get_settings

log = logging.getLogger("checkpointer")


# ── sync default ──────────────────────────────────────────────────────

def build_checkpointer() -> Any:
    """
    Return an async-safe checkpointer for local dev.

    MemorySaver is the only sync-constructible checkpointer that works with
    async graph methods, so it's the default.
    """
    from langgraph.checkpoint.memory import MemorySaver
    log.info("checkpointer: memory (no persistence across restarts)")
    return MemorySaver()


# ── optional async persistent checkpointer ────────────────────────────

async def setup_async_checkpointer() -> Any:
    """
    Enter a persistent async checkpointer.  Caller must keep the returned
    object (and its context) alive for the lifetime of the process.

    Usage in FastAPI startup:
        from smauto.graph.checkpointer import setup_async_checkpointer
        app.state.checkpointer = await setup_async_checkpointer()

    Usage in the CLI/worker:
        checkpointer = await setup_async_checkpointer()
        graph = build_graph(checkpointer=checkpointer)
    """
    s = get_settings()
    url = s.database_url

    # 1. Postgres
    if url.startswith("postgresql"):
        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            cs = url.replace("postgresql+psycopg://", "postgresql://")
            ctx = AsyncPostgresSaver.from_conn_string(cs)
            saver = await ctx.__aenter__()
            await saver.setup()
            # hang the ctx off the saver so shutdown can close it if needed
            saver._smauto_ctx = ctx  # type: ignore[attr-defined]
            log.info("checkpointer: AsyncPostgresSaver")
            return saver
        except Exception as e:  # noqa: BLE001
            log.warning("postgres async checkpointer unavailable (%s)", e)

    # 2. SQLite
    try:
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        if url.startswith("sqlite"):
            path = url.replace("sqlite:///", "").replace("sqlite://", "")
        else:
            path = os.path.join(os.getcwd(), ".checkpoints.sqlite")
        ctx = AsyncSqliteSaver.from_conn_string(path)
        saver = await ctx.__aenter__()
        saver._smauto_ctx = ctx  # type: ignore[attr-defined]
        log.info("checkpointer: AsyncSqliteSaver at %s", path)
        return saver
    except Exception as e:  # noqa: BLE001
        log.warning("sqlite async checkpointer unavailable (%s)", e)

    # 3. Memory
    from langgraph.checkpoint.memory import MemorySaver
    log.warning("checkpointer: memory fallback")
    return MemorySaver()


async def teardown_async_checkpointer(saver: Any) -> None:
    """Close a checkpointer created by setup_async_checkpointer()."""
    ctx = getattr(saver, "_smauto_ctx", None)
    if ctx is not None:
        try:
            await ctx.__aexit__(None, None, None)
        except Exception:  # noqa: BLE001
            pass