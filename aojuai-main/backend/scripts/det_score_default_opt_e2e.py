#!/usr/bin/env python3
"""FIVE-LAYER-DEFAULT-OPT e2e: freeze H0 then single-variable arms A1–A5 (A6 PG optional).

Env:
  DEFAULT_OPT_ARM=H0|A1|A2|A3|A4|A5|A6|ALL
  ALIGN_SAMPLE_N=12
  score_fn always None for ablation (documented in evidence header).

Does NOT change module default constants. True Gemini required.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parents[1]
LOG = Path("/tmp/det-score-default-opt-e2e.log")
EVIDENCE_DIR = REPO / "docs" / "mihuanyuantu-v2" / "input"
SAMPLE_DIR = REPO / "测试用" / "图片"
SEED = 20261113
DEFAULT_N = 12
FOCAL = "26mm"

# Measurement grids (H0 values are module defaults; not written as new defaults here).
A1_LEVELS = ("0", "0.16", "0.24")  # vs H0 optical 0.32
A2_LEVELS = ("0.85", "1.0")  # vs H0 noise 1.55


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
        "code": "det-default-opt-phone",
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


_MEASURE_KEYS = (
    "ALIGN_LAYER0_OPTICAL_STRENGTH",
    "ALIGN_NOISE_INTENSITY",
    "ALIGN_FIXED_MODE_SCALE",
    "ALIGN_SHARPEN",
    "ALIGN_VIGNETTE_SCALE",
    "ALIGN_JPEG_MILD_SWEEP",
    "ALIGN_JPEG_QUALITIES",
    "ALIGN_BAYER_ROUNDTRIP",
    "ALIGN_BAYER_STRENGTH",
    "ALIGN_PG_NOISE",
    "ALIGN_PG_SCALE",
    "ALIGN_PG_FLAT_THR",
)


def _clear_measure(settings) -> None:
    settings.ALIGN_LAYER0_IMG2IMG = "0"
    for key in _MEASURE_KEYS:
        setattr(settings, key, "")
        os.environ.pop(key, None)


def _apply(settings, **kwargs: str) -> None:
    _clear_measure(settings)
    for key, value in kwargs.items():
        setattr(settings, key, value)
        os.environ[key] = value


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


def _score_arm(files: list[Path], *, label: str) -> dict:
    totals: list[float] = []
    dims = {k: [] for k in ("noise", "depthOfField", "lighting", "colorRealism", "overallRealism")}
    pass75 = 0
    for path in files:
        source = path.read_bytes()
        note(f"--- arm={label} sample={path.name} ---")
        jpeg = _run_v3(source)
        report = _gemini(jpeg)
        total = float(report.get("total_score") or 0)
        totals.append(total)
        if total >= 75 or report.get("passed") is True:
            pass75 += 1
        for key in dims:
            dims[key].append(float(report.get(key) or 0))
        note(
            f"gemini_{label} total={total} passed={report.get('passed')} "
            f"noise={report.get('noise')} dof={report.get('depthOfField')} "
            f"light={report.get('lighting')} color={report.get('colorRealism')} "
            f"overall={report.get('overallRealism')}"
        )
    mean_total = sum(totals) / len(totals)
    mean_dims = {k: round(sum(v) / len(v), 2) for k, v in dims.items()}
    out = {
        "label": label,
        "n": len(totals),
        "mean_total": round(mean_total, 2),
        "pass75": pass75,
        "mean_dims": mean_dims,
        "totals": totals,
    }
    note(f"ARM_SUMMARY {json.dumps(out, ensure_ascii=False)}")
    return out


def _write_evidence(name: str) -> Path:
    path = EVIDENCE_DIR / name
    path.write_text(LOG.read_text(encoding="utf-8"), encoding="utf-8")
    note(f"evidence_copy={path}")
    return path


def main() -> int:
    for key in list(os.environ):
        if "proxy" in key.lower():
            os.environ.pop(key, None)
    os.environ["NO_PROXY"] = "*"
    os.environ["no_proxy"] = "*"
    os.environ["ALIGN_LAYER0_IMG2IMG"] = "0"

    arm = str(os.environ.get("DEFAULT_OPT_ARM") or "H0").strip().upper()
    LOG.write_text("", encoding="utf-8")
    note("=== FIVE-LAYER-DEFAULT-OPT e2e ===")
    note(f"ts={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
    note(f"arm={arm} focal={FOCAL} seed={SEED} score_fn=None layer0_img2img=0 ca=0")
    note("PASS_SCORE=75 unchanged; module defaults NOT permanently changed")
    note("gates: DEFAULT_OPT_MEAN_GAIN Δ>=+3 OR PASS75_LIFT +2 vs H0")

    sys.path.insert(0, str(BACKEND))
    from dotenv import load_dotenv

    load_dotenv(BACKEND / ".env")
    from app.capabilities.realphotos.services.five_layer import (
        _CA_INTENSITY,
        _LAYER0_OPTICAL_STRENGTH,
        _NOISE_INTENSITY,
        _VIGNETTE_LEGACY_SCALE,
    )
    from app.core.config import settings

    must(float(_CA_INTENSITY) == 0.0, "ca_hemo")
    must(float(_LAYER0_OPTICAL_STRENGTH) == 0.24, "optical_module_default")
    must(float(_NOISE_INTENSITY) == 1.55, "noise_module_default")
    must(float(_VIGNETTE_LEGACY_SCALE) == 0.85, "vignette_module_default")
    must(str(settings.ALIGN_LAYER0_IMG2IMG or "0") == "0", "layer0_img2img_off")

    limit = int(os.environ.get("ALIGN_SAMPLE_N") or DEFAULT_N)
    files = sorted(SAMPLE_DIR.glob("product_*.jpg"))[:limit]
    must(len(files) >= 1, f"samples n={len(files)}")

    results: list[dict] = []

    def run_h0() -> dict:
        _clear_measure(settings)
        return _score_arm(files, label="H0")

    if arm in {"H0", "ALL"}:
        results.append(run_h0())
        if arm == "H0":
            _write_evidence("FIVE-LAYER-DEFAULT-OPT-e2e-h0-2026-11-14.txt")
            note("DEFAULT_OPT_H0_DONE")
            return 0

    if arm in {"A1", "ALL"}:
        for level in A1_LEVELS:
            _apply(settings, ALIGN_LAYER0_OPTICAL_STRENGTH=level)
            results.append(_score_arm(files, label=f"A1_optical_{level}"))
        if arm == "A1":
            _write_evidence("FIVE-LAYER-DEFAULT-OPT-e2e-a1-2026-11-14.txt")
            note("DEFAULT_OPT_A1_DONE")
            return 0

    if arm in {"A2", "ALL"}:
        for level in A2_LEVELS:
            _apply(settings, ALIGN_NOISE_INTENSITY=level)
            results.append(_score_arm(files, label=f"A2_noise_{level}"))
        if arm == "A2":
            _write_evidence("FIVE-LAYER-DEFAULT-OPT-e2e-a2-2026-11-14.txt")
            note("DEFAULT_OPT_A2_DONE")
            return 0

    if arm in {"A3", "ALL"}:
        _apply(settings, ALIGN_SHARPEN="0")
        results.append(_score_arm(files, label="A3_sharpen_off"))
        if arm == "A3":
            _write_evidence("FIVE-LAYER-DEFAULT-OPT-e2e-a3-2026-11-14.txt")
            note("DEFAULT_OPT_A3_DONE")
            return 0

    if arm in {"A4", "ALL"}:
        _apply(settings, ALIGN_VIGNETTE_SCALE="0.50")
        results.append(_score_arm(files, label="A4_vignette_0.50"))
        if arm == "A4":
            _write_evidence("FIVE-LAYER-DEFAULT-OPT-e2e-a4-2026-11-14.txt")
            note("DEFAULT_OPT_A4_DONE")
            return 0

    if arm in {"A5", "ALL"}:
        _apply(settings, ALIGN_JPEG_MILD_SWEEP="1", ALIGN_JPEG_QUALITIES="90,93,96")
        results.append(_score_arm(files, label="A5_jpeg_mild_90_93_96"))
        if arm == "A5":
            _write_evidence("FIVE-LAYER-DEFAULT-OPT-e2e-a5-2026-11-14.txt")
            note("DEFAULT_OPT_A5_DONE")
            return 0

    if arm in {"A6", "ALL"}:
        _apply(settings, ALIGN_PG_NOISE="1", ALIGN_PG_SCALE="0.40")
        results.append(_score_arm(files, label="A6_pg_0.40"))
        if arm == "A6":
            _write_evidence("FIVE-LAYER-DEFAULT-OPT-e2e-a6-2026-11-14.txt")
            note("DEFAULT_OPT_A6_DONE")
            return 0

    if arm != "ALL":
        note(f"FAIL unknown_arm={arm}")
        return 2

    # ALL: need H0 in results[0]
    h0 = results[0]
    note("--- SUMMARY DEFAULT_OPT ALL ---")
    for row in results[1:]:
        d_mean = row["mean_total"] - h0["mean_total"]
        d_pass = row["pass75"] - h0["pass75"]
        dim_ok = True
        for key, val in row["mean_dims"].items():
            if val - h0["mean_dims"][key] <= -5.0:
                dim_ok = False
        gain = d_mean >= 3.0 and dim_ok
        lift = d_pass >= 2
        note(
            json.dumps(
                {
                    "vs_H0": row["label"],
                    "delta_mean": round(d_mean, 2),
                    "delta_pass75": d_pass,
                    "DEFAULT_OPT_MEAN_GAIN": gain,
                    "DEFAULT_OPT_PASS75_LIFT": lift,
                    "dim_ok": dim_ok,
                },
                ensure_ascii=False,
            )
        )
    _write_evidence("FIVE-LAYER-DEFAULT-OPT-e2e-all-2026-11-14.txt")
    note("DEFAULT_OPT_ALL_DONE")
    note("STOP: do not promote defaults without §2.4 + admin; do not claim old Q1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
