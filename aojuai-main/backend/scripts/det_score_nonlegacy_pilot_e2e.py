#!/usr/bin/env python3
"""NONLEGACY OPEN_PILOT e2e: H0 hemostasis vs P1 Bayer vs P2 PG (one variable each).

Contract sample n=12, seed=20261113, 26mm, Layer0=0, CA=0, score_fn off for fair H0.
True Gemini required. Does not change module defaults.
Evidence → docs/.../DET-SCORE-NONLEGACY-e2e-pilot-2026-11-14.txt
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parents[1]
LOG = Path("/tmp/det-score-nonlegacy-pilot-e2e.log")
EVIDENCE = (
    REPO / "docs" / "mihuanyuantu-v2" / "input" / "DET-SCORE-NONLEGACY-e2e-pilot-2026-11-14.txt"
)
SAMPLE_DIR = REPO / "测试用" / "图片"
SEED = 20261113
DEFAULT_N = 12
FOCAL = "26mm"


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
        "code": "det-nonlegacy-phone",
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


def _clear_pilot(settings) -> None:
    settings.ALIGN_BAYER_ROUNDTRIP = ""
    settings.ALIGN_BAYER_STRENGTH = ""
    settings.ALIGN_PG_NOISE = ""
    settings.ALIGN_PG_SCALE = ""
    settings.ALIGN_PG_FLAT_THR = ""
    for key in (
        "ALIGN_BAYER_ROUNDTRIP",
        "ALIGN_BAYER_STRENGTH",
        "ALIGN_PG_NOISE",
        "ALIGN_PG_SCALE",
        "ALIGN_PG_FLAT_THR",
    ):
        os.environ.pop(key, None)


def _run_v3(source: bytes) -> bytes:
    from app.capabilities.realphotos.services.five_layer import run_five_layer

    return run_five_layer(
        source=source,
        preset=_preset(),
        seed=SEED,
        freq_mode="auto",
        algorithm="v3",
        score_fn=None,
    ).jpeg


def _arm_scores(files: list[Path], *, label: str) -> list[float]:
    scores: list[float] = []
    for path in files:
        source = path.read_bytes()
        note(f"--- arm={label} sample={path.name} ---")
        jpeg = _run_v3(source)
        report = _gemini(jpeg)
        total = float(report.get("total_score") or 0)
        scores.append(total)
        note(
            f"gemini_{label} total={total} passed={report.get('passed')} "
            f"noise={report.get('noise')} dof={report.get('depthOfField')} "
            f"light={report.get('lighting')} color={report.get('colorRealism')} "
            f"overall={report.get('overallRealism')}"
        )
    return scores


def main() -> int:
    for key in list(os.environ):
        if "proxy" in key.lower():
            os.environ.pop(key, None)
    os.environ["NO_PROXY"] = "*"
    os.environ["no_proxy"] = "*"
    os.environ["ALIGN_LAYER0_IMG2IMG"] = "0"

    LOG.write_text("", encoding="utf-8")
    note("=== DET-SCORE NONLEGACY OPEN_PILOT e2e ===")
    note(f"ts={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
    note("H0=hemostasis P1=bayer P2=pg; one variable each; PASS_SCORE=75; defaults unchanged")

    sys.path.insert(0, str(BACKEND))
    from dotenv import load_dotenv

    load_dotenv(BACKEND / ".env")

    from app.core.config import settings

    settings.ALIGN_LAYER0_IMG2IMG = "0"
    _clear_pilot(settings)

    from app.capabilities.realphotos.services.five_layer import _CA_INTENSITY

    must(float(_CA_INTENSITY) == 0.0, "ca_intensity_hemo")
    must(str(settings.ALIGN_LAYER0_IMG2IMG) == "0", "layer0_default_hemo")

    limit = int(os.environ.get("ALIGN_SAMPLE_N") or DEFAULT_N)
    files = sorted(SAMPLE_DIR.glob("product_*.jpg"))[:limit]
    must(len(files) >= 1, f"samples n={len(files)}")

    h0 = _arm_scores(files, label="H0")
    settings.ALIGN_BAYER_ROUNDTRIP = "1"
    settings.ALIGN_BAYER_STRENGTH = "0.35"
    os.environ["ALIGN_BAYER_ROUNDTRIP"] = "1"
    os.environ["ALIGN_BAYER_STRENGTH"] = "0.35"
    p1 = _arm_scores(files, label="P1_bayer")
    _clear_pilot(settings)
    settings.ALIGN_PG_NOISE = "1"
    settings.ALIGN_PG_SCALE = "0.40"
    os.environ["ALIGN_PG_NOISE"] = "1"
    os.environ["ALIGN_PG_SCALE"] = "0.40"
    p2 = _arm_scores(files, label="P2_pg")
    _clear_pilot(settings)

    mean_h0 = sum(h0) / len(h0)
    mean_p1 = sum(p1) / len(p1)
    mean_p2 = sum(p2) / len(p2)
    d1 = mean_p1 - mean_h0
    d2 = mean_p2 - mean_h0
    note("--- SUMMARY NONLEGACY PILOT ---")
    note(
        json.dumps(
            {
                "n": len(files),
                "focal": FOCAL,
                "mean_H0": round(mean_h0, 2),
                "mean_P1_bayer": round(mean_p1, 2),
                "delta_P1": round(d1, 2),
                "mean_P2_pg": round(mean_p2, 2),
                "delta_P2": round(d2, 2),
                "hemo_baseline_frozen": 66.92,
            },
            ensure_ascii=False,
        )
    )
    if d1 > 0 or d2 > 0:
        note("NONLEGACY_PILOT_E2E_GAIN partial_or_full")
    else:
        note("NONLEGACY_PILOT_E2E_SHORTFALL no_positive_delta")
    note("STOP: do not claim product PASS; do not promote pilots to defaults without admin")
    note("DET_SCORE_NONLEGACY_PILOT_DONE")
    EVIDENCE.write_text(LOG.read_text(encoding="utf-8"), encoding="utf-8")
    note(f"evidence_copy={EVIDENCE}")
    return 0 if (d1 > 0 or d2 > 0) else 4


if __name__ == "__main__":
    raise SystemExit(main())
