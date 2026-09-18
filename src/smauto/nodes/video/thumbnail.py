"""
THUMBNAIL — two or three quote cards using the strategy hook.

Deliberately cheap: no LLM call, no image-gen.  Just typography on a colored
background.  Extend with flux-schnell when you want photographic covers.
"""
from __future__ import annotations

from ...infra.logging import get_logger
from ...services.media import render_quote_card
from ...state.schema import GraphState
from ...storage.paths import ensure_run_dirs

log = get_logger("node.thumbnail")

_VARIANTS = [
    {"bg": "#0F172A", "fg": "#FFFFFF", "accent": "#22D3EE"},
    {"bg": "#FFFFFF", "fg": "#0B1220", "accent": "#0F172A"},
]


async def thumbnail_node(state: GraphState) -> dict:
    vs = dict(state.get("video_state") or {})
    run_id = state.get("run_id")
    if not run_id:
        vs["thumbnail_paths"] = []
        return {"video_state": vs}

    hook = (state.get("strategy") or {}).get("hook") or state.get("topic") or "Watch this"

    paths = ensure_run_dirs(run_id)
    outs: list[str] = []

    for i, variant in enumerate(_VARIANTS):
        out = paths["images"] / f"thumb_{i:02d}.png"
        try:
            render_quote_card(
                text=hook,
                out_path=out,
                bg=variant["bg"],
                fg=variant["fg"],
                accent=variant["accent"],
            )
            outs.append(str(out))
        except Exception as e:  # noqa: BLE001
            log.warning("thumbnail %d failed: %s", i, e)

    vs["thumbnail_paths"] = outs
    log.info("thumbnail done n=%d", len(outs))
    return {"video_state": vs}