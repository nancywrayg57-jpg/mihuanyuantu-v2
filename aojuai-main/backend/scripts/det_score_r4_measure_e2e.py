#!/usr/bin/env python3
"""R4 measurement e2e (protocol W, 8mm only).

Compares R0 (v2) vs R4 (v3 + optical 0.16 + noise 1.0 + fixed_scale 1.0).
CA stays 0; Layer0 img2img stays 0. Does NOT change module defaults permanently.
Evidence: /tmp/det-score-r4-e2e.log → docs/.../DET-SCORE-OPTIMIZE-ablation-r4-2026-11-14.txt
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parents[1]
LOG = Path("/tmp/det-score-r4-e2e.log")
EVIDENCE = REPO / "docs" / "mihuanyuantu-v2" / "input" / "DET-SCORE-OPTIMIZE-ablation-r4-2026-11-14.txt"
SAMPLE_DIR = REPO / "测试用" / "图片"
SEED = 20261113
DEFAULT_N = 12
FOCAL = "8mm"


def note(msg: str) -> None:
    line = msg if msg.endswith("\n") else msg + "\n"
    print(line, end="", flush=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line)


def must(cond: bool, label: str) -> None:
    if not cond:
        note(f"FAIL {label}")
        raise SystemExit(2)
    note(f"PASS {label}")


def _preset() -> dict:
    return {
        "code": "det-r4-phone",
        "deviceType": "phone",
        "brand": "Apple",
        "model": "iPhone 15 Pro",
        "iso": "400",
        "shutter": "1/120",
        "aperture": "f/1.8",
        "focalLength": FOCAL,
        "gpsMode": "none",
        "legacyParameters": {"software": "Luminar AI", "white_balance": "Auto"},
    }


def _gemini(jpeg: bytes) -> dict:
    from app.capabilities.realphotos.services.gemini_detector import detect_jpeg
    from app.core.config import settings
    from app.core.exceptions import BusinessError

    must(bool(str(settings.GEMINI_API_KEY or "").strip()), "gemini_key_configured")
    last: Exception | None = None
    for attempt in range(4):
        try:
            return detect_jpeg(jpeg)
        except BusinessError as exc:
            last = exc
            time.sleep(2.0 * (attempt + 1))
    assert last is not None
    raise last


def _run(source: bytes, *, algorithm: str) -> bytes:
    from app.capabilities.realphotos.services.five_layer import run_five_layer

    out = run_five_layer(
        source=source,
        preset=_preset(),
        seed=SEED,
        freq_mode="auto",
        algorithm=algorithm,
        score_fn=None,
    )
    return out.jpeg


def main() -> int:
    for key in list(os.environ):
        if "proxy" in key.lower():
            os.environ.pop(key, None)
    os.environ["NO_PROXY"] = "*"
    os.environ["no_proxy"] = "*"
    os.environ["ALIGN_LAYER0_IMG2IMG"] = "0"
    os.environ["ALIGN_LAYER0_OPTICAL_STRENGTH"] = "0.16"
    os.environ["ALIGN_NOISE_INTENSITY"] = "1.0"
    os.environ["ALIGN_FIXED_MODE_SCALE"] = "1.0"

    LOG.write_text("", encoding="utf-8")
    note("=== DET-SCORE R4 measurement protocol W 8mm ===")
    note(f"ts={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
    note("optical=0.16 noise_intensity=1.0 fixed_mode_scale=1.0 layer0_img2img=0 ca=0")
    note("PASS_SCORE=75 unchanged; defaults NOT permanently changed")

    sys.path.insert(0, str(BACKEND))
    from dotenv import load_dotenv

    load_dotenv(BACKEND / ".env")

    from app.core.config import settings

    settings.ALIGN_LAYER0_IMG2IMG = "0"
    settings.ALIGN_LAYER0_OPTICAL_STRENGTH = "0.16"
    settings.ALIGN_NOISE_INTENSITY = "1.0"
    settings.ALIGN_FIXED_MODE_SCALE = "1.0"

    from app.capabilities.realphotos.services.five_layer import (
        _LAYER0_OPTICAL_STRENGTH,
        _NOISE_INTENSITY,
        _float_setting_override,
        l1_noise_sigma,
    )

    must(float(_LAYER0_OPTICAL_STRENGTH) == 0.32, "module_default_optical_unchanged")
    must(float(_NOISE_INTENSITY) == 1.55, "module_default_noise_unchanged")
    must(abs(_float_setting_override("ALIGN_LAYER0_OPTICAL_STRENGTH", 0.32) - 0.16) < 1e-9, "override_optical")
    must(abs(_float_setting_override("ALIGN_NOISE_INTENSITY", 1.55) - 1.0) < 1e-9, "override_noise")
    must(abs(l1_noise_sigma("400") - 1.0) < 1e-6, "sigma_iso400_with_override")

    limit = int(os.environ.get("ALIGN_SAMPLE_N") or DEFAULT_N)
    files = sorted(SAMPLE_DIR.glob("product_*.jpg"))[:limit]
    must(len(files) >= 1, f"samples n={len(files)}")

    rows: list[dict] = []
    for path in files:
        source = path.read_bytes()
        note(f"--- sample={path.name} ---")
        j2 = _run(source, algorithm="v2")
        d2 = _gemini(j2)
        j4 = _run(source, algorithm="v3")
        d4 = _gemini(j4)
        t2 = float(d2.get("total_score") or 0)
        t4 = float(d4.get("total_score") or 0)
        rows.append(
            {
                "sample": path.name,
                "v2": t2,
                "r4": t4,
                "delta": t4 - t2,
                "r4_reason": str(d4.get("reason") or "")[:160],
            }
        )
        note(f"v2={t2} r4={t4} delta={t4 - t2:+.1f} reason={rows[-1]['r4_reason']}")

    n = len(rows)
    mean_v2 = sum(r["v2"] for r in rows) / n
    mean_r4 = sum(r["r4"] for r in rows) / n
    summary = {
        "n": n,
        "focal": FOCAL,
        "mean_v2": round(mean_v2, 2),
        "mean_r4": round(mean_r4, 2),
        "gain_vs_v2": round(mean_r4 - mean_v2, 2),
        "prior_w_post_mean_v3_8mm": 62.17,
        "delta_vs_prior_post": round(mean_r4 - 62.17, 2),
        "pass_rate": sum(1 for r in rows if r["r4"] >= 75) / n,
    }
    note("--- SUMMARY R4 ---")
    note(json.dumps(summary, ensure_ascii=False))
    # Hypothesis bandwidth: |mean_r4 - prior_post| < 3 → do not confirm overdrive as dominant
    if abs(mean_r4 - 62.17) < 3.0:
        note("P-V3-OVERDRIVE: NOT_CONFIRMED (|R4-prior_post|<3)")
    elif mean_r4 > 62.17 + 3.0:
        note("P-V3-OVERDRIVE: SUPPORTED_DIRECTION (R4 raised vs prior post)")
    else:
        note("P-V3-OVERDRIVE: R4_LOWER_THAN_PRIOR (unexpected)")
    note("DET_SCORE_R4_DONE")
    EVIDENCE.write_text(LOG.read_text(encoding="utf-8"), encoding="utf-8")
    note(f"evidence_copy={EVIDENCE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
