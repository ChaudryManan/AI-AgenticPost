"""
FastAPI application.

Lifespan:
  • on startup  → enter a persistent async checkpointer, compile the graph,
                  stash both on app.state
  • on shutdown → close the checkpointer cleanly

Routes:
  • /runs, /analytics, /webhooks   → API
  • /runs/{id}/images/{filename}   → serve generated PNGs
  • /                              → testing frontend (index.html)
  • /static/*                      → frontend assets (css, js)
"""
from __future__ import annotations

import contextlib
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ..config.settings import PROJECT_ROOT, get_settings
from ..graph.builder import build_graph
from ..graph.checkpointer import (
    setup_async_checkpointer,
    teardown_async_checkpointer,
)
from ..infra.logging import get_logger, setup_logging
from ..storage.db.session import init_db
from .routes import analytics, approvals, posts, runs, webhooks

log = get_logger("api.main")

_FRONTEND_DIR = PROJECT_ROOT / "frontend"


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    setup_logging()
    s = get_settings()
    log.info("smauto starting | artifact_root=%s", s.artifact_root)

    try:
        init_db()
    except Exception as e:  # noqa: BLE001
        log.warning("init_db failed: %s", e)

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

    if _FRONTEND_DIR.exists():
        log.info("frontend mounted from %s", _FRONTEND_DIR)
    else:
        log.warning("frontend/ not found at %s — UI will not be served",
                    _FRONTEND_DIR)

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API routers (registered first — nothing shadows them) ───────────────
app.include_router(runs.router)
app.include_router(approvals.router)
app.include_router(posts.router)
app.include_router(analytics.router)
app.include_router(webhooks.router)


# ── meta ────────────────────────────────────────────────────────────────
@app.get("/health", tags=["meta"])
async def health() -> dict[str, Any]:
    return {"ok": True, "version": app.version}


# ── generated image serving ─────────────────────────────────────────────
@app.get("/runs/{run_id}/images/{filename}", tags=["runs"])
async def serve_run_image(run_id: str, filename: str) -> FileResponse:
    for part in (run_id, filename):
        if ".." in part or "/" in part or "\\" in part:
            raise HTTPException(status_code=400, detail="bad path")

    base = get_settings().artifact_root / run_id / "images"
    path = base / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="image not found")
    return FileResponse(path, media_type="image/png")


# ── frontend ────────────────────────────────────────────────────────────
# Static assets (css, js) live under /static/... — a subpath mount, so it
# never shadows /runs, /analytics, /webhooks.
if _FRONTEND_DIR.exists():
    app.mount(
        "/static",
        StaticFiles(directory=str(_FRONTEND_DIR)),
        name="frontend-assets",
    )

    @app.get("/", include_in_schema=False)
    async def frontend_index() -> FileResponse:
        return FileResponse(_FRONTEND_DIR / "index.html")