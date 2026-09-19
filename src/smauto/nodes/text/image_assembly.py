"""
IMAGE ASSEMBLY — render visuals for the text branch.

  visual_type="none"      → no images
  visual_type="quote"     → LLM writes a visual brief, HF renders it,
                             Pillow card is the fallback if anything fails
  visual_type="carousel"  → Pillow slides with page numbers
"""
from __future__ import annotations

from jinja2 import Template

from ...config.settings import get_settings
from ...infra.logging import get_logger
from ...infra.tracing import span
from ...services.llm import get_llm
from ...services.media import generate_image, render_quote_card, render_slide
from ...state.schema import GraphState
from ...storage.paths import ensure_run_dirs

log = get_logger("node.image_assembly")


# ── visual brief generation ──────────────────────────────────────────────

async def _generate_visual_brief(state: GraphState,
                                 draft: dict,
                                 topic: str) -> dict[str, str]:
    """
    Ask the LLM to write an image-generation prompt that supports the post.

    Returns {"prompt": ..., "negative": ..., "rationale": ...}.
    On any failure, returns a safe fallback built from the hook.
    """
    s = get_settings()

    # brand palette — pass through so the image matches your brand
    try:
        import yaml
        brand = yaml.safe_load(s.brand_path.read_text(encoding="utf-8")) or {}
        palette = brand.get("palette") or {}
    except Exception:  # noqa: BLE001
        palette = {}

    tpl = Template((s.prompts_dir / "image_prompt.j2").read_text(encoding="utf-8"))
    user_prompt = tpl.render(
        hook=(draft.get("hook") or "").strip(),
        body=(draft.get("body") or "").strip(),
        cta=(draft.get("cta") or "").strip(),
        topic=topic,
        palette=palette or {},
    )

    with span("node.image_assembly.brief"):
        try:
            data = await get_llm().json(
                node="image_prompt",
                system=(
                    "You write concise image-generation prompts. "
                    "Output strict JSON only."
                ),
                user=user_prompt,
            )
        except Exception as e:  # noqa: BLE001
            log.warning("image_prompt LLM failed (%s); using fallback", e)
            data = {}

    prompt = (data.get("prompt") or "").strip()
    if not prompt:
        # fallback: build a minimal prompt from the hook
        hook = (draft.get("hook") or topic or "an abstract editorial scene").strip()
        prompt = (
            f"Minimalist editorial illustration evoking the theme: {hook}. "
            "Dark background, one bold accent shape, subtle grain, "
            "no text, no words, no letters, no logos, no people."
        )

    negative = (data.get("negative") or
                "text, words, letters, watermark, logo, signature, "
                "low quality, blurry, distorted, ugly, cluttered")

    rationale = (data.get("rationale") or "").strip()

    log.info("visual brief written: %s", (rationale or prompt)[:120])
    return {"prompt": prompt, "negative": negative, "rationale": rationale}


# ── the node ────────────────────────────────────────────────────────────

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
        topic = state.get("topic") or ""

        # 1. LLM writes the visual brief
        brief = await _generate_visual_brief(state, draft, topic)
        ts["image_brief"] = brief

        # 2. HF renders it
        ai_out = paths["images"] / "quote_ai.png"
        try:
            await generate_image(
                brief["prompt"],
                ai_out,
                negative_prompt=brief["negative"],
            )
            outs.append(str(ai_out))
            log.info("image_assembly: AI image -> %s", ai_out)
        except Exception as e:  # noqa: BLE001
            log.warning("AI image gen failed (%s); falling back to Pillow", e)
            # 3. Pillow fallback
            fallback = paths["images"] / "quote.png"
            text = (draft.get("hook") or (draft.get("body") or ""))[:140]
            try:
                render_quote_card(text, fallback)
                outs.append(str(fallback))
            except Exception as e2:  # noqa: BLE001
                log.warning("Pillow fallback also failed: %s", e2)

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