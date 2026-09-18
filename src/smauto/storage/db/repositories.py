"""
Repository functions.

Every method opens its own short-lived session — no long-lived DB handles
leaking into the async graph.  Calls are idempotent where it matters (upsert
on runs) and appends otherwise.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select

from . import models
from .session import get_session

log = logging.getLogger("repos")


# ─────────────────────────────────────────────────────────────────────
class RunRepo:
    @staticmethod
    def upsert(
        run_id: str,
        request: str,
        content_type: str,
        platforms: list[str],
        status: str = "running",
        state: dict[str, Any] | None = None,
    ) -> None:
        with get_session() as s:
            obj = s.get(models.Run, run_id)
            if obj is None:
                s.add(models.Run(
                    id=run_id,
                    request=request,
                    content_type=content_type,
                    platforms=list(platforms or []),
                    status=status,
                    state_json=state or {},
                ))
            else:
                obj.status = status
                obj.content_type = content_type
                obj.platforms = list(platforms or [])
                if state is not None:
                    obj.state_json = state

    @staticmethod
    def get(run_id: str) -> dict[str, Any] | None:
        with get_session() as s:
            o = s.get(models.Run, run_id)
            if o is None:
                return None
            return {
                "id": o.id,
                "status": o.status,
                "state": o.state_json,
                "content_type": o.content_type,
                "platforms": o.platforms,
                "created_at": o.created_at.isoformat() if o.created_at else None,
                "updated_at": o.updated_at.isoformat() if o.updated_at else None,
            }

    @staticmethod
    def list_recent(limit: int = 50) -> list[dict[str, Any]]:
        with get_session() as s:
            rows = s.execute(
                select(models.Run).order_by(models.Run.created_at.desc()).limit(limit)
            ).scalars().all()
            return [
                {"id": r.id, "status": r.status, "content_type": r.content_type,
                 "created_at": r.created_at.isoformat() if r.created_at else None}
                for r in rows
            ]


# ─────────────────────────────────────────────────────────────────────
class PostRepo:
    @staticmethod
    def add(post_id: str, run_id: str, platform: str,
            url: str | None = None, variant: str | None = None) -> None:
        with get_session() as s:
            if s.get(models.Post, post_id) is not None:
                log.info("post %s already exists — skipping", post_id)
                return
            s.add(models.Post(
                id=post_id, run_id=run_id, platform=platform,
                url=url, variant=variant,
            ))

    @staticmethod
    def list_for_run(run_id: str) -> list[dict[str, Any]]:
        with get_session() as s:
            rows = s.execute(
                select(models.Post).where(models.Post.run_id == run_id)
            ).scalars().all()
            return [
                {"id": r.id, "platform": r.platform, "url": r.url,
                 "variant": r.variant,
                 "posted_at": r.posted_at.isoformat() if r.posted_at else None}
                for r in rows
            ]


# ─────────────────────────────────────────────────────────────────────
class MetricRepo:
    @staticmethod
    def add(post_id: str, horizon: str, data: dict[str, Any]) -> None:
        with get_session() as s:
            s.add(models.Metric(post_id=post_id, horizon=horizon, data=data))

    @staticmethod
    def list_for_post(post_id: str) -> list[dict[str, Any]]:
        with get_session() as s:
            rows = s.execute(
                select(models.Metric)
                .where(models.Metric.post_id == post_id)
                .order_by(models.Metric.pulled_at.asc())
            ).scalars().all()
            return [
                {"horizon": r.horizon, "data": r.data,
                 "pulled_at": r.pulled_at.isoformat() if r.pulled_at else None}
                for r in rows
            ]


# ─────────────────────────────────────────────────────────────────────
class ApprovalRepo:
    @staticmethod
    def add(run_id: str, status: str,
            notes: str | None = None, editor: str | None = None) -> None:
        with get_session() as s:
            s.add(models.Approval(
                run_id=run_id, status=status, notes=notes, editor=editor,
            ))

    @staticmethod
    def list_for_run(run_id: str) -> list[dict[str, Any]]:
        with get_session() as s:
            rows = s.execute(
                select(models.Approval)
                .where(models.Approval.run_id == run_id)
                .order_by(models.Approval.at.asc())
            ).scalars().all()
            return [
                {"status": r.status, "notes": r.notes, "editor": r.editor,
                 "at": r.at.isoformat() if r.at else None}
                for r in rows
            ]


# ─────────────────────────────────────────────────────────────────────
class DeadLetterRepo:
    @staticmethod
    def add(run_id: str | None, node: str,
            kind: str, payload: dict[str, Any]) -> None:
        with get_session() as s:
            s.add(models.DeadLetter(
                run_id=run_id, node=node, kind=kind, payload=payload,
            ))

    @staticmethod
    def list_recent(limit: int = 100) -> list[dict[str, Any]]:
        with get_session() as s:
            rows = s.execute(
                select(models.DeadLetter)
                .order_by(models.DeadLetter.at.desc())
                .limit(limit)
            ).scalars().all()
            return [
                {"id": r.id, "run_id": r.run_id, "node": r.node,
                 "kind": r.kind, "payload": r.payload,
                 "at": r.at.isoformat() if r.at else None}
                for r in rows
            ]