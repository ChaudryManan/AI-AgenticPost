"""
SQLAlchemy 2.0 declarative models.

Five tables:
    runs          — one row per pipeline run
    posts         — one row per (run, platform) published post
    metrics       — metric snapshots at 1h / 24h / 7d horizons
    approvals     — human approval decisions (audit trail)
    dead_letters  — permanently failed operations
"""
from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    request: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(String(16))          # video|text|both
    platforms: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    state_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    posts: Mapped[list["Post"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", lazy="selectin")


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    variant: Mapped[str | None] = mapped_column(String(64), nullable=True)
    url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    posted_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow)

    run: Mapped[Run] = relationship(back_populates="posts")
    metrics: Mapped[list["Metric"]] = relationship(
        back_populates="post", cascade="all, delete-orphan", lazy="selectin")


class Metric(Base):
    __tablename__ = "metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id"), index=True)
    horizon: Mapped[str] = mapped_column(String(8))                # "1h" | "24h" | "7d"
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    pulled_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow)

    post: Mapped[Post] = relationship(back_populates="metrics")


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    status: Mapped[str] = mapped_column(String(16))                # approved|rejected|edited
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    editor: Mapped[str | None] = mapped_column(String(128), nullable=True)
    at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow)


class DeadLetter(Base):
    __tablename__ = "dead_letters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    node: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow)