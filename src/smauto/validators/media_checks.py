"""
Media QC for the video branch.

These are pure functions — no ffprobe here.  The caller (video/scene_check.py
or nodes/shared/qa.py) does the ffprobe and passes numbers in.
"""
from __future__ import annotations


def check_duration(actual: float,
                   target: float,
                   tolerance: float = 1.5) -> bool:
    """
    True if `actual` is within `tolerance` seconds of `target`.
    Used to verify the script's sum matches ~30s.
    """
    return abs(float(actual) - float(target)) <= float(tolerance)


def check_drift(vo_timestamps: list[dict],
                clip_durations: list[float],
                tolerance: float = 1.5) -> bool:
    """
    Compare per-scene VO duration vs the matching clip duration.

    vo_timestamps: [{"start": 0.0, "end": 6.2, "text": "..."}, ...]
    clip_durations: [6.0, 6.1, 5.9, ...]  (one per scene, in order)

    Returns True if every scene is within `tolerance` seconds.
    """
    if len(vo_timestamps) != len(clip_durations):
        return False

    for seg, clip_dur in zip(vo_timestamps, clip_durations):
        vo_dur = float(seg.get("end", 0)) - float(seg.get("start", 0))
        if abs(vo_dur - float(clip_dur)) > float(tolerance):
            return False
    return True


def check_loudness(lufs: float, target: float = -14.0,
                   tolerance: float = 2.0) -> bool:
    """True if integrated loudness is within `tolerance` LUFS of target."""
    return abs(float(lufs) - float(target)) <= float(tolerance)


def check_aspect(width: int, height: int, expected: str) -> bool:
    """
    Verify an image/video matches an aspect-ratio string like "9:16", "1:1".
    Tolerant of ±1 pixel rounding.
    """
    try:
        ew, eh = (int(x) for x in expected.split(":"))
    except (ValueError, AttributeError):
        return False
    expected_ratio = ew / eh
    actual_ratio = width / height
    return abs(actual_ratio - expected_ratio) < 0.02