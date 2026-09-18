"""
VOICE — TTS the full script, then build proportional timestamps.

We concatenate all vo_text into one string (single TTS call = more natural
prosody) and derive per-scene timestamps from the script durations.
"""
from __future__ import annotations

import yaml

from ...config.settings import get_settings
from ...infra.logging import get_logger
from ...infra.tracing import span
from ...services.media import synthesize
from ...state.schema import GraphState
from ...storage.paths import ensure_run_dirs

log = get_logger("node.voice")


async def voice_node(state: GraphState) -> dict:
    s = get_settings()
    vs = dict(state.get("video_state") or {})
    script = vs.get("script") or []
    run_id = state.get("run_id")

    if not script or not run_id:
        vs["audio_path"] = None
        vs["audio_timestamps"] = []
        return {"video_state": vs}

    full_text = " ".join((sc.get("vo_text") or "").strip() for sc in script).strip()
    if not full_text:
        vs["audio_path"] = None
        vs["audio_timestamps"] = []
        return {"video_state": vs}

    try:
        tts_cfg = yaml.safe_load(s.models_path.read_text(encoding="utf-8"))["tts"]["default"]
    except Exception:  # noqa: BLE001
        tts_cfg = {"voice_id": "21m00Tcm4TlvDq8ikWAM",
                   "model": "eleven_multilingual_v2"}

    paths = ensure_run_dirs(run_id)
    out = paths["audio"] / "voice.mp3"

    with span("node.voice", chars=len(full_text)):
        try:
            await synthesize(
                full_text, out,
                voice_id=tts_cfg["voice_id"],
                model=tts_cfg.get("model", "eleven_multilingual_v2"),
            )
            vs["audio_path"] = str(out)
        except Exception as e:  # noqa: BLE001
            log.warning("tts failed: %s", e)
            vs["audio_path"] = None

    # proportional timestamps from script durations
    t = 0.0
    stamps = []
    for sc in script:
        d = float(sc.get("duration", 6.0))
        stamps.append({
            "start": round(t, 3),
            "end": round(t + d, 3),
            "text": (sc.get("vo_text") or "").strip(),
        })
        t += d

    vs["audio_timestamps"] = stamps
    vs["_duration_total"] = round(t, 3)
    log.info("voice done audio=%s stamps=%d total=%.1fs",
             bool(vs["audio_path"]), len(stamps), t)
    return {"video_state": vs}