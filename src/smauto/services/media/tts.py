"""
Text-to-speech via ElevenLabs.

Returns MP3 bytes written to `out_path`.  There is no word-level timestamp
data from this call — the voice node creates proportional timestamps from
the script durations.  If you want real forced alignment, see align.py.
"""
from __future__ import annotations

import os
from pathlib import Path

import httpx

from ...infra.errors import MediaError
from ...infra.logging import get_logger
from ...infra.rate_limit import bucket
from ...infra.tracing import span

log = get_logger("tts")

_ELEVEN_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"


def _token() -> str:
    t = os.getenv("ELEVENLABS_API_KEY")
    if not t:
        raise MediaError("ELEVENLABS_API_KEY is not set")
    return t


async def synthesize(
    text: str,
    out_path: Path,
    voice_id: str,
    model: str = "eleven_multilingual_v2",
    stability: float = 0.5,
    similarity_boost: float = 0.75,
    timeout: float = 180.0,
) -> Path:
    """Synthesize `text` to MP3 at `out_path`.  Returns the path."""
    if not text.strip():
        raise MediaError("cannot synthesize empty text")

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    await bucket("tts").acquire()

    url = _ELEVEN_URL.format(voice_id=voice_id)
    body = {
        "text": text,
        "model_id": model,
        "voice_settings": {
            "stability": stability,
            "similarity_boost": similarity_boost,
        },
    }
    headers = {
        "xi-api-key": _token(),
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }

    with span("tts", voice=voice_id, chars=len(text)):
        async with httpx.AsyncClient(timeout=timeout) as c:
            r = await c.post(url, headers=headers, json=body)

    if r.status_code >= 400:
        raise MediaError(f"elevenlabs {r.status_code}: {r.text[:500]}")

    out_path.write_bytes(r.content)
    log.info("tts ok path=%s bytes=%d chars=%d",
             out_path, out_path.stat().st_size, len(text))
    return out_path