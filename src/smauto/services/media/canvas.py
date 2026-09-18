"""
Pillow-based renderers for quote cards and carousel slides.

Font resolution order:
    1. A font explicitly bundled at  assets/brand/<name>.ttf
    2. Common system font paths (Windows / macOS / Linux)
    3. PIL's default bitmap font (ugly but never fails)

If you want to ship your own typography, drop the .ttf into assets/brand/
and pass `font_path=` to either function.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from ...infra.logging import get_logger

log = get_logger("canvas")

# Order matters — first existing file wins.
_SYSTEM_FONT_CANDIDATES = [
    # Windows
    r"C:\Windows\Fonts\segoeuib.ttf",     # Segoe UI Bold
    r"C:\Windows\Fonts\arialbd.ttf",      # Arial Bold
    r"C:\Windows\Fonts\arial.ttf",
    # macOS
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    # Linux
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


def _resolve_font(font_path: str | Path | None, size: int) -> ImageFont.FreeTypeFont:
    candidates: list[str] = []
    if font_path:
        candidates.append(str(font_path))
    candidates.extend(_SYSTEM_FONT_CANDIDATES)

    for c in candidates:
        try:
            return ImageFont.truetype(c, size)
        except (OSError, ValueError):
            continue

    log.warning("no truetype font found — falling back to PIL default")
    # type: ignore[return-value] — load_default returns a Font, acceptable here
    return ImageFont.load_default()


def _hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    h = hex_str.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def render_quote_card(
    text: str,
    out_path: Path,
    size: tuple[int, int] = (1080, 1080),
    bg: str = "#0F172A",
    fg: str = "#FFFFFF",
    accent: str | None = "#22D3EE",
    font_path: str | Path | None = None,
) -> Path:
    """Square quote card — big centered text, optional accent bar on top."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    img = Image.new("RGB", size, _hex_to_rgb(bg))
    draw = ImageDraw.Draw(img)

    # accent bar
    if accent:
        draw.rectangle([0, 0, size[0], 12], fill=_hex_to_rgb(accent))

    font = _resolve_font(font_path, size=64)

    # wrap text at ~22 chars for 1080px width with a 64pt font
    wrapped = "\n".join(textwrap.wrap(text or "", width=22)) or (text or "")
    bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, align="center", spacing=12)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    xy = ((size[0] - w) / 2 - bbox[0], (size[1] - h) / 2 - bbox[1])

    draw.multiline_text(xy, wrapped, font=font, fill=_hex_to_rgb(fg),
                        align="center", spacing=12)

    img.save(out_path, "PNG")
    log.info("quote card -> %s", out_path)
    return out_path


def render_slide(
    title: str,
    body: str,
    out_path: Path,
    size: tuple[int, int] = (1080, 1080),
    bg: str = "#FFFFFF",
    fg: str = "#0B1220",
    accent: str = "#22D3EE",
    font_path: str | Path | None = None,
    slide_index: int | None = None,
    slide_total: int | None = None,
) -> Path:
    """Carousel slide — title top, body below, accent bar + optional page number."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    img = Image.new("RGB", size, _hex_to_rgb(bg))
    draw = ImageDraw.Draw(img)

    # accent bar top
    draw.rectangle([0, 0, size[0], 14], fill=_hex_to_rgb(accent))

    title_font = _resolve_font(font_path, size=72)
    body_font = _resolve_font(font_path, size=44)
    meta_font = _resolve_font(font_path, size=28)

    # title (wrap at ~20 chars to fit 72pt in 1080px with 80px margins)
    title_wrapped = "\n".join(textwrap.wrap(title or "", width=20))
    draw.multiline_text((80, 140), title_wrapped, font=title_font,
                        fill=_hex_to_rgb(fg), spacing=8)

    # body — measured off the actual title height
    title_bbox = draw.multiline_textbbox((80, 140), title_wrapped,
                                         font=title_font, spacing=8)
    body_y = title_bbox[3] + 60
    body_wrapped = "\n".join(textwrap.wrap(body or "", width=34))
    draw.multiline_text((80, body_y), body_wrapped, font=body_font,
                        fill=_hex_to_rgb(fg), spacing=14)

    # page number bottom-right
    if slide_index is not None and slide_total is not None:
        label = f"{slide_index + 1}/{slide_total}"
        bbox = draw.textbbox((0, 0), label, font=meta_font)
        w = bbox[2] - bbox[0]
        draw.text((size[0] - 80 - w, size[1] - 90), label,
                  font=meta_font, fill=_hex_to_rgb(fg))

    img.save(out_path, "PNG")
    log.info("slide -> %s", out_path)
    return out_path