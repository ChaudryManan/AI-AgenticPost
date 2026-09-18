"""
IMAGE ASSEMBLY — render the visuals decided by slide_splitter.

  visual_type="none"      → no images
  visual_type="quote"     → 1 quote card
  visual_type="carousel"  → N slides with page numbers
"""
from __future__ import annotations

from ...infra.logging import get_logger
from ...services.media import render_quote_card, render_slide
from ...state.schema import GraphState
from ...storage.paths import ensure_run_dirs

log = get_logger("node.image_assembly")


async def image_assembly_node(state: GraphState) -> dict:
    ts = dict(state.get("text_state") or {})
    run_id = state.get("run_id")
    visual_type = ts.get("visual_type", "none")

    if visual_type == "none" or not run_id:
        ts["image_paths"] = []
        return {"text_state": ts}

    paths = ensure_run_dirs(run_id)
    outs: list[str] = []

    if visual_type == "quote":
        draft = ts.get("draft") or {}
        text = (draft.get("hook") or "").strip() or (draft.get("body") or "")[:140]
        out = paths["images"] / "quote.png"
        try:
            render_quote_card(text, out)
            outs.append(str(out))
        except Exception as e:  # noqa: BLE001
            log.warning("quote card render failed: %s", e)

    elif visual_type == "carousel":
        slides = ts.get("slides") or []
        total = len(slides)
        for i, sl in enumerate(slides):
            out = paths["images"] / f"slide_{i:02d}.png"
            try:
                render_slide(
                    title=sl.get("title", ""),
                    body=sl.get("body", ""),
                    out_path=out,
                    slide_index=i,
                    slide_total=total,
                )
                outs.append(str(out))
            except Exception as e:  # noqa: BLE001
                log.warning("slide %d render failed: %s", i, e)

    ts["image_paths"] = outs
    log.info("image_assembly done visual=%s n=%d", visual_type, len(outs))
    return {"text_state": ts}