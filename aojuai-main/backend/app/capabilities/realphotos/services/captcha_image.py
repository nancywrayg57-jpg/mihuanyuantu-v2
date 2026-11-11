"""Render a simple numeric captcha PNG (FR-001 / ND-001)."""

from __future__ import annotations

import base64
import io
import random
import secrets

from PIL import Image, ImageDraw, ImageFont


def render_captcha_data_url(code: str, *, width: int = 160, height: int = 52) -> str:
    """Return ``data:image/png;base64,...`` for the given challenge code."""
    digits = str(code or "").strip()
    if not digits:
        raise ValueError("captcha code required")

    bg = (248, 249, 252)
    img = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(img)
    rng = random.Random(secrets.randbits(32))

    # Noise lines
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

    # Noise dots
    for _ in range(40):
        draw.point(
            (rng.randint(0, width - 1), rng.randint(0, height - 1)),
            fill=tuple(rng.randint(120, 200) for _ in range(3)),
        )

    try:
        font = ImageFont.load_default()
    except Exception:  # pragma: no cover
        font = None

    # Spread digits across the canvas (default bitmap font is small; scale via spacing).
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
