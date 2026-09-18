"""
Forced alignment → SRT.

This module currently produces SRT from *proportional* timestamps — i.e. it
trusts the durations the script node gave each scene rather than running an
actual forced aligner.  That's fine for short-form social video where the VO
is short and the scenes are roughly equal length.

To upgrade to real forced alignment:
    1. `pip install whisperx` (or use a hosted aligner)
    2. Replace `forced_align_to_srt` with a call to your aligner
    3. Feed it (audio_path, full_text) and use the returned word timestamps

The SRT output format is stable either way, so nothing downstream changes.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable


def _fmt_ts(seconds: float) -> str:
    """SRT timestamp: HH:MM:SS,mmm"""
    if seconds < 0:
        seconds = 0.0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    # format S with 3 decimal places, then swap . for , for SRT
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")


def forced_align_to_srt(
    segments: Iterable[dict],
    out_path: Path,
) -> Path:
    """
    segments: iterable of {"start": float, "end": float, "text": str}
              — typically state["video_state"]["audio_timestamps"]

    Writes an SRT file to `out_path` and returns the path.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    for i, seg in enumerate(segments, start=1):
        start = float(seg.get("start", 0.0))
        end = float(seg.get("end", start))
        text = (seg.get("text") or "").strip().replace("\n", " ")

        # skip empty cues — SRT viewers choke on them
        if not text or end <= start:
            continue

        lines.append(str(i))
        lines.append(f"{_fmt_ts(start)} --> {_fmt_ts(end)}")
        lines.append(text)
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path