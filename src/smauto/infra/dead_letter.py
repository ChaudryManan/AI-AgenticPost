"""
Dead-letter queue for permanently-failed operations.

Written both to disk (always) and to the DB (if configured).  On any failure
that retries can't fix — bad auth, format rejection, exhausted retries — the
publish node calls `dead_letter(...)` and moves on.  An ops alert can tail
the directory or the `dead_letters` table.
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from ..config.settings import get_settings
from .logging import get_logger

log = get_logger("dead_letter")


def dead_letter(bucket: str, payload: dict[str, Any]) -> Path:
    """
    Persist a failed payload.

    bucket  — a short tag: "publish" | "auth" | "rate_limit" | "media" | ...
    payload — whatever context helps ops debug (run_id, platform, error, ...).
    """
    s = get_settings()
    d = s.artifact_root / "_dead_letter"
    d.mkdir(parents=True, exist_ok=True)

    ts = int(time.time() * 1000)
    fname = f"{bucket}-{ts}-{uuid.uuid4().hex[:6]}.json"
    path = d / fname

    entry = {"bucket": bucket, "at": ts, **payload}
    try:
        path.write_text(json.dumps(entry, indent=2, default=str), encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        log.error("dead_letter.write_failed bucket=%s err=%s", bucket, e)
        return path

    log.error("dead_letter bucket=%s path=%s payload_keys=%s",
              bucket, path, list(payload.keys()))

    # Best-effort DB mirror — never let DB failure mask the primary error.
    try:
        from ..storage.db.repositories import DeadLetterRepo
        DeadLetterRepo.add(
            run_id=payload.get("run_id"),
            node=payload.get("node", bucket),
            kind=bucket,
            payload=entry,
        )
    except Exception:  # noqa: BLE001
        pass

    return path