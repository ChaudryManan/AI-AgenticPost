"""
FastAPI application.

Lifespan:
  • on startup  → enter a persistent async checkpointer, compile the graph,
                  stash both on app.state
  • on shutdown → close the checkpointer cleanly

Routes are mounted under /runs, /analytics, /webhooks.  Health at /health.
"""
from __future__ import annotations

import contextlib
from typing import Any, AsyncIterator

from fastapi import FastAPI

from ..config.settings import get_settings
from ..graph.builder import build_graph
from ..graph.checkpointer import setup_async_checkpointer, teardown_async_checkpointer
from ..infra.logging import get_logger, setup_logging
from ..storage.db.session import init_db
from .routes import analytics, approvals, posts, runs, webhooks

log = get_logger("api.main")


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    setup_logging()
    s = get_settings()
    log.info("smauto starting | artifact_root=%s", s.artifact_root)

    # 1. DB tables — best-effort
    try:
        init_db()
    except Exception as e:  # noqa: BLE001
        log.warning("init_db failed: %s", e)

    # 2. checkpointer + graph
    checkpointer: Any = None
    try:
        checkpointer = await setup_async_checkpointer()
    except Exception as e:  # noqa: BLE001
        log.warning("checkpointer setup failed (%s); using in-memory", e)
        from langgraph.checkpoint.memory import MemorySaver
        checkpointer = MemorySaver()

    app.state.checkpointer = checkpointer
    app.state.graph = build_graph(checkpointer=checkpointer)
    log.info("graph compiled")

    try:
        yield
    finally:
        log.info("smauto shutting down")
        try:
            await teardown_async_checkpointer(checkpointer)
        except Exception:  # noqa: BLE001
            pass


app = FastAPI(
    title="smauto",
    version="0.1.0",
    description="Social media automation graph (video + text).",
    lifespan=lifespan,
)

app.include_router(runs.router)
app.include_router(approvals.router)
app.include_router(posts.router)
app.include_router(analytics.router)
app.include_router(webhooks.router)


@app.get("/health", tags=["meta"])
async def health() -> dict[str, Any]:
    return {"ok": True, "version": app.version}