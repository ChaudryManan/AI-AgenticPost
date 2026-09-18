"""
QA — the gate.

Runs after both branches complete (or after `both` runs sequentially).
Reads state from video_state and text_state, applies every validator we
have, and produces state.qa = {passed, failures, checked_at}.

Rules:
  • Any "hard" failure flips passed to False
  • "soft" failures are recorded but don't fail the run
  • If the branches produced nothing at all, that's a hard failure
"""
from __future__ import annotations

from datetime import datetime, timezone

import yaml

from ...config.settings import get_settings
from ...infra.logging import get_logger
from ...state.schema import GraphState
from ...validators import (
    PlatformViolation,
    check_brand,
    check_policy,
    validate_platform,
)

log = get_logger("node.qa")


def _fail(stage: str, reason: str, severity: str = "hard",
          detail: dict | None = None) -> dict:
    f: dict = {"stage": stage, "reason": reason, "severity": severity}
    if detail:
        f["detail"] = detail
    return f


async def qa_node(state: GraphState) -> dict:
    s = get_settings()
    failures: list[dict] = []

    try:
        platforms_rules = yaml.safe_load(s.platforms_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        platforms_rules = {}

    # ── text branch checks ────────────────────────────────────────────
    ts = state.get("text_state") or {}
    bodies: dict[str, str] = ts.get("platform_bodies") or {}
    hashtags: list[str] = ts.get("hashtags") or []

    if bodies:
        for platform, body in bodies.items():
            # hard: platform rules
            try:
                validate_platform(platform, body, hashtags)
            except PlatformViolation as e:
                failures.append(_fail("qa.platform", str(e), "hard"))

            # hard: policy scan
            for v in check_policy(body):
                failures.append(_fail("qa.policy", v, "hard"))

            # soft: brand tone
            for v in check_brand(body):
                failures.append(_fail("qa.brand", v, "soft"))

    # ── video branch checks ───────────────────────────────────────────
    vs = state.get("video_state") or {}
    if state.get("content_type") in ("video", "both"):
        if not vs.get("script"):
            failures.append(_fail("qa.video", "no script generated", "hard"))
        elif not vs.get("render_path"):
            failures.append(_fail("qa.video", "no final render", "hard"))

        clips = vs.get("clips") or []
        if clips:
            bad = [c for c in clips if c.get("status") != "ok"]
            if bad:
                failures.append(_fail(
                    "qa.video",
                    f"{len(bad)}/{len(clips)} clips fell back to placeholder",
                    "soft",
                    detail={"bad_scene_ids": [c.get("scene_id") for c in bad]},
                ))

        if not vs.get("caption"):
            failures.append(_fail("qa.video", "no caption generated", "soft"))

    # ── fact_check escalations ────────────────────────────────────────
    # fact_check may have already pushed hard failures into state.qa
    incoming = state.get("qa") or {}
    for f in (incoming.get("failures") or []):
        if f not in failures:
            failures.append(f)

    passed = not any(f.get("severity") == "hard" for f in failures)

    log.info("qa done passed=%s failures=%d hard=%d",
             passed, len(failures),
             sum(1 for f in failures if f.get("severity") == "hard"))

    return {"qa": {
        "passed": passed,
        "failures": failures,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }}