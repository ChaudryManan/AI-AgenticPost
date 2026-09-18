"""
Async ffmpeg wrapper.

Every call shells out to the `ffmpeg` binary; if it's not on PATH we raise
MediaError early instead of producing a confusing subprocess failure.

Windows note: ffmpeg's concat demuxer requires forward slashes OR escaped
backslashes in the list file.  We normalize paths with `.as_posix()` which
ffmpeg on Windows accepts.
"""
from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

from ...infra.errors import MediaError
from ...infra.logging import get_logger
from ...infra.tracing import span

log = get_logger("ffmpeg")


def _require_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        raise MediaError(
            "ffmpeg not found on PATH. Install it:\n"
            "  Windows : winget install Gyan.FFmpeg\n"
            "  macOS   : brew install ffmpeg\n"
            "  Linux   : sudo apt install ffmpeg"
        )


async def _run(args: list[str], timeout: float = 900.0) -> tuple[str, str]:
    """Run ffmpeg with `-y -hide_banner -loglevel error` prefixed."""
    _require_ffmpeg()
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError as e:
        proc.kill()
        raise MediaError(f"ffmpeg timed out after {timeout}s") from e

    if proc.returncode != 0:
        tail = (err or b"").decode("utf-8", errors="replace")[-2000:]
        raise MediaError(f"ffmpeg failed (rc={proc.returncode}): {tail}")

    return (out or b"").decode("utf-8", errors="replace"), \
           (err or b"").decode("utf-8", errors="replace")


# ── public ops ────────────────────────────────────────────────────────

async def concat(clips: list[Path], out_path: Path) -> Path:
    """Concatenate a list of video files (same codec/resolution required)."""
    if not clips:
        raise MediaError("concat called with no clips")

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    list_file = out_path.with_suffix(".concat.txt")
    # ffmpeg's concat demuxer wants paths in single quotes, with forward slashes
    list_file.write_text(
        "\n".join(f"file '{Path(c).resolve().as_posix()}'" for c in clips),
        encoding="utf-8",
    )

    with span("ffmpeg.concat", n=len(clips), out=str(out_path)):
        await _run([
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_file),
            "-c", "copy",
            str(out_path),
        ])

    log.info("concat ok %d clips -> %s", len(clips), out_path)
    return out_path


async def mux(video: Path, audio: Path, out_path: Path) -> Path:
    """Attach an audio track to a video (video stream is copied, not re-encoded)."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with span("ffmpeg.mux", out=str(out_path)):
        await _run([
            "-i", str(video),
            "-i", str(audio),
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(out_path),
        ])

    log.info("mux ok -> %s", out_path)
    return out_path


async def trim(src: Path, out_path: Path,
               start: float, duration: float) -> Path:
    """Cut a segment out of a clip, copy codecs."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with span("ffmpeg.trim", start=start, dur=duration):
        await _run([
            "-ss", f"{start:.3f}",
            "-i", str(src),
            "-t", f"{duration:.3f}",
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            str(out_path),
        ])
    return out_path


async def loudnorm(src: Path, out_path: Path,
                   target_lufs: float = -14.0,
                   true_peak: float = -1.5,
                   lra: float = 11.0) -> Path:
    """
    Loudness-normalize to broadcast-ish levels.  -14 LUFS is the standard for
    social platforms (YouTube, TikTok, IG all normalize toward this).
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with span("ffmpeg.loudnorm", target=target_lufs):
        await _run([
            "-i", str(src),
            "-af", f"loudnorm=I={target_lufs}:TP={true_peak}:LRA={lra}",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            str(out_path),
        ])
    return out_path


async def probe_duration(path: Path) -> float:
    """Return the duration of a media file in seconds (via ffprobe)."""
    if shutil.which("ffprobe") is None:
        raise MediaError("ffprobe not found on PATH")

    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "json",
        str(path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    if proc.returncode != 0:
        raise MediaError(f"ffprobe failed: {err.decode(errors='replace')[-500:]}")

    data = json.loads(out.decode("utf-8"))
    return float(data["format"]["duration"])