"""
Engine + session factory.

Strategy:
  1. Try to connect to DATABASE_URL (Postgres by default).
  2. If that fails, fall back to a local SQLite file ./.smauto.sqlite.

This means the graph runs out of the box without Postgres, and silently
upgrades when you bring Postgres up.
"""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ...config.settings import get_settings
from .models import Base

log = logging.getLogger("db")

_SQLITE_FALLBACK_FILE = ".smauto.sqlite"


def _try_engine(url: str) -> Engine | None:
    try:
        e = create_engine(url, pool_pre_ping=True, future=True)
        with e.connect() as c:
            c.execute(text("SELECT 1"))
        return e
    except Exception as e:  # noqa: BLE001
        log.warning("could not connect to %s (%s)", url, e)
        return None


def _build_engine() -> tuple[Engine, bool]:
    """Returns (engine, using_sqlite_fallback)."""
    s = get_settings()
    url = s.database_url

    # explicit sqlite url → just use it
    if url.startswith("sqlite"):
        return create_engine(url, future=True), False

    primary = _try_engine(url)
    if primary is not None:
        return primary, False

    fallback_path = os.path.join(os.getcwd(), _SQLITE_FALLBACK_FILE)
    log.warning("falling back to sqlite at %s", fallback_path)
    return create_engine(f"sqlite:///{fallback_path}", future=True), True


engine, _USING_FALLBACK = _build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False,
                            expire_on_commit=False, future=True)


def is_sqlite_fallback() -> bool:
    return _USING_FALLBACK


def init_db() -> None:
    """Create all tables.  Safe to call repeatedly."""
    Base.metadata.create_all(engine)


@contextmanager
def get_session() -> Iterator[Session]:
    """Context-managed session — commits on clean exit, rolls back on error."""
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()