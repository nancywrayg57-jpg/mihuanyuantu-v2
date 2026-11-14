#!/usr/bin/env python3
"""DET-SCORE OPEN_PARTIAL ablation e2e (protocol W).

Arms after whitelist A+D+B:
  R0  = algorithm=v2 (frozen), Layer0 N/A
  R_post = algorithm=v3, ALIGN_LAYER0_IMG2IMG=0, _CA_INTENSITY=0 (identity)

Protocol W: no score_fn (matches worker). PASS_SCORE stays 75.
Evidence: /tmp/det-score-ablation-e2e.log (+ copy under docs/.../input/)
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parents[1]
LOG = Path("/tmp/det-score-ablation-e2e.log")
EVIDENCE = REPO / "docs" / "mihuanyuantu-v2" / "input" / "DET-SCORE-OPTIMIZE-ablation-w-2026-11-14.txt"
SAMPLE_DIR = REPO / "测试用" / "图片"
SEED = 20261113
DEFAULT_N = 12


def note(msg: str) -> None:
    line = msg if msg.endswith("\n") else msg + "\n"
    print(line, end="", flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line)


def must(cond: bool, label: str) -> None:
    if not cond:
        note(f"FAIL {label}")
        raise SystemExit(2)
    note(f"PASS {label}")


def _preset(focal: str) -> dict:
    return {
        "code": "det-ablation-phone",
        "deviceType": "phone",
        "brand": "Apple",
        "model": "iPhone 15 Pro",
        "iso": "400",
        "shutter": "1/120",
        "aperture": "f/1.8",
        "focalLength": focal,
        "gpsMode": "none",
        "legacyParameters": {
            "software": "Luminar AI",
            "white_balance": "Auto",
            "lens_model": "iPhone 15 Pro back camera 6.86mm f/1.78",
        },
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


def _run(source: bytes, *, algorithm: str, focal: str) -> tuple[bytes, float]:
    import io

    import numpy as np
    from PIL import Image

    from app.capabilities.realphotos.services.five_layer import mean_abs_delta, run_five_layer

    out = run_five_layer(
        source=source,
        preset=_preset(focal),
        seed=SEED,
        freq_mode="auto",
        algorithm=algorithm,
        score_fn=None,
    )
    with Image.open(io.BytesIO(source)) as before, Image.open(io.BytesIO(out.jpeg)) as after:
        mad = mean_abs_delta(
            np.asarray(before.convert("RGB"), dtype=np.float32),
            np.asarray(after.convert("RGB"), dtype=np.float32),
        )
        must(after.size == before.size, f"size_{algorithm}_{focal}")
    return out.jpeg, float(mad)


def main() -> int:
    for key in list(os.environ):
        if "proxy" in key.lower():
            os.environ.pop(key, None)
    os.environ["NO_PROXY"] = "*"
    os.environ["no_proxy"] = "*"
    # Protocol W: Layer0 off (matches post-whitelist default / worker).
    os.environ["ALIGN_LAYER0_IMG2IMG"] = "0"

    LOG.write_text("", encoding="utf-8")
    note("=== DET-SCORE-OPTIMIZE ablation protocol W ===")
    note(f"ts={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
    note("production_billing=false")
    note("protocol=W score_fn=none layer0=0 ca_intensity=0(post-whitelist)")
    note("arms=R0_v2 vs R_post_v3 ; focals=8mm,26mm ; R1≡R2 after B")
    note(f"sample_dir={SAMPLE_DIR}")
    note("PASS_SCORE=75 unchanged")

    sys.path.insert(0, str(BACKEND))
    from dotenv import load_dotenv

    load_dotenv(BACKEND / ".env")

    # Refresh settings after env poke.
    from app.core.config import settings

    settings.ALIGN_LAYER0_IMG2IMG = "0"

    import numpy as np

    from app.capabilities.realphotos.services.five_layer import (
        _CA_INTENSITY,
        PIPELINE_VERSION,
        _apply_chromatic_aberration,
    )

    must(PIPELINE_VERSION == "s2-five-layer-3", "pipeline_v3")
    must(float(_CA_INTENSITY) == 0.0, "ca_intensity_zero")
    probe = np.random.default_rng(0).integers(0, 256, size=(16, 16, 3), dtype=np.uint8).astype(np.float32)
    for focal in ("8mm", "26mm"):
        out = _apply_chromatic_aberration(probe, focal_length=focal, intensity=1.0)
        must(np.array_equal(out, probe), f"ca_identity_{focal}")

    limit = int(os.environ.get("ALIGN_SAMPLE_N") or DEFAULT_N)
    files = sorted(SAMPLE_DIR.glob("product_*.jpg"))[:limit]
    must(len(files) >= 1, f"samples n={len(files)}")
    note(f"ALIGN_W0 sample_n={len(files)} seed={SEED}")

    rows: list[dict] = []
    for path in files:
        source = path.read_bytes()
        note(f"--- sample={path.name} bytes={len(source)} ---")
        for focal in ("8mm", "26mm"):
            jpeg_v2, mad_v2 = _run(source, algorithm="v2", focal=focal)
            det_v2 = _gemini(jpeg_v2)
            jpeg_v3, mad_v3 = _run(source, algorithm="v3", focal=focal)
            det_v3 = _gemini(jpeg_v3)
            t2 = float(det_v2.get("total_score") or 0)
            t3 = float(det_v3.get("total_score") or 0)
            row = {
                "sample": path.name,
                "focal": focal,
                "v2_total": t2,
                "v3_total": t3,
                "delta": t3 - t2,
                "v2_passed": bool(det_v2.get("passed")),
                "v3_passed": bool(det_v3.get("passed")),
                "v2_color": det_v2.get("color_realism"),
                "v3_color": det_v3.get("color_realism"),
                "v2_overall": det_v2.get("overall_realism"),
                "v3_overall": det_v3.get("overall_realism"),
                "mad_v2": mad_v2,
                "mad_v3": mad_v3,
                "v2_reason": str(det_v2.get("reason") or "")[:160],
                "v3_reason": str(det_v3.get("reason") or "")[:160],
            }
            rows.append(row)
            note(
                f"focal={focal} v2={t2} v3={t3} delta={t3 - t2:+.1f} "
                f"color={det_v2.get('color_realism')}->{det_v3.get('color_realism')} "
                f"overall={det_v2.get('overall_realism')}->{det_v3.get('overall_realism')}"
            )
            note(f"  v3_reason={row['v3_reason']}")

    def _summary(focal: str) -> dict:
        subset = [r for r in rows if r["focal"] == focal]
        n = len(subset)
        mean_v2 = sum(r["v2_total"] for r in subset) / n
        mean_v3 = sum(r["v3_total"] for r in subset) / n
        gain = mean_v3 - mean_v2
        ca_words = ("色差", "红蓝", "伪影", "chromatic", "aberration", "fringing")
        ca_hits = sum(1 for r in subset if any(w.lower() in r["v3_reason"].lower() for w in ca_words))
        return {
            "focal": focal,
            "n": n,
            "mean_v2": round(mean_v2, 2),
            "mean_v3": round(mean_v3, 2),
            "gain_vs_v2": round(gain, 2),
            "v3_pass_rate": sum(1 for r in subset if r["v3_passed"]) / n,
            "v3_ca_reason_hits": ca_hits,
        }

    s8 = _summary("8mm")
    s26 = _summary("26mm")
    note("--- SUMMARY protocol W (Layer0=0, CA=0) ---")
    note(json.dumps(s8, ensure_ascii=False))
    note(json.dumps(s26, ensure_ascii=False))
    note(
        "NOTE: gain_vs_v2 is NOT Q1 (Q1 needs protocol C + score_fn + contract preset). "
        "Historical preview v3 mean≈49 with CA on; compare mean_v3 here for recovery."
    )
    # Gate B: CA reason count should drop vs historical; we only have post-fix reasons.
    note(
        f"P-CA-PHONE observe: 8mm ca_reason_hits={s8['v3_ca_reason_hits']}/{s8['n']} "
        f"mean_v3={s8['mean_v3']} (hist≈49 with CA); gain_vs_v2={s8['gain_vs_v2']}"
    )
    note(
        f"26mm mean_v3={s26['mean_v3']} gain_vs_v2={s26['gain_vs_v2']} "
        f"(C1 was +1.00 with Layer0 on; this arm Layer0 off)"
    )
    note("DET_SCORE_ABLATION_W_DONE")

    EVIDENCE.write_text(LOG.read_text(encoding="utf-8"), encoding="utf-8")
    note(f"evidence_copy={EVIDENCE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
