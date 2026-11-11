"""Render a simple numeric captcha image (FR-001 / ND-001).

Prefer SVG data-URL (no font/Pillow quirks). PNG remains available as a
fallback renderer for environments that expect raster images.
"""

from __future__ import annotations

import base64
import html
import io
import random
import secrets
from urllib.parse import quote


def render_captcha_svg_data_url(code: str, *, width: int = 160, height: int = 52) -> str:
    """Return ``data:image/svg+xml,...`` for the given challenge code."""
    digits = str(code or "").strip()
    if not digits:
        raise ValueError("captcha code required")

    rng = random.Random(secrets.randbits(32))
    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f8f9fc"/>',
    ]
    for _ in range(6):
        x1, y1 = rng.randint(0, width), rng.randint(0, height)
        x2, y2 = rng.randint(0, width), rng.randint(0, height)
        stroke = f"rgb({rng.randint(160, 210)},{rng.randint(160, 210)},{rng.randint(160, 210)})"
        parts.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-width="1"/>'
        )
    margin_x = 14
    usable = max(width - margin_x * 2, len(digits) * 18)
    step = usable / max(len(digits), 1)
    for i, ch in enumerate(digits):
        x = int(margin_x + i * step + rng.randint(-2, 2))
        y = int(height / 2 + 6 + rng.randint(-8, 8))
        rot = rng.randint(-18, 18)
        fill = f"rgb({rng.randint(20, 60)},{rng.randint(20, 60)},{rng.randint(40, 90)})"
        safe = html.escape(ch)
        parts.append(
            f'<text x="{x}" y="{y}" fill="{fill}" font-size="22" '
            f'font-family="ui-monospace, Menlo, Consolas, monospace" '
            f'transform="rotate({rot} {x} {y})">{safe}</text>'
        )
    parts.append("</svg>")
    svg = "".join(parts)
    return "data:image/svg+xml;charset=utf-8," + quote(svg)


def render_captcha_png_data_url(code: str, *, width: int = 160, height: int = 52) -> str:
    """Return ``data:image/png;base64,...`` (Pillow)."""
    from PIL import Image, ImageDraw, ImageFont

    digits = str(code or "").strip()
    if not digits:
        raise ValueError("captcha code required")

    bg = (248, 249, 252)
    img = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(img)
    rng = random.Random(secrets.randbits(32))

    for _ in range(6):
        color = tuple(rng.randint(160, 210) for _ in range(3))
        draw.line(
            (
                rng.randint(0, width),
                rng.randint(0, height),
                rng.randint(0, width),
                rng.randint(0, height),
            ),
            fill=color,
            width=1,
        )
    for _ in range(40):
        draw.point(
            (rng.randint(0, width - 1), rng.randint(0, height - 1)),
            fill=tuple(rng.randint(120, 200) for _ in range(3)),
        )
    try:
        font = ImageFont.load_default()
    except Exception:  # pragma: no cover
        font = None

    margin_x = 14
    usable = max(width - margin_x * 2, len(digits) * 12)
    step = usable / max(len(digits), 1)
    for i, ch in enumerate(digits):
        x = int(margin_x + i * step + rng.randint(-2, 2))
        y = int(height / 2 - 6 + rng.randint(-6, 6))
        color = (rng.randint(20, 60), rng.randint(20, 60), rng.randint(40, 90))
        draw.text((x, y), ch, fill=color, font=font)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def render_captcha_data_url(code: str, *, width: int = 160, height: int = 52) -> str:
    """Preferred captcha data-URL (SVG first, PNG fallback)."""
    try:
        return render_captcha_svg_data_url(code, width=width, height=height)
    except Exception:
        return render_captcha_png_data_url(code, width=width, height=height)
