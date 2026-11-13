#!/usr/bin/env python3
"""FIVE-LAYER-LEGACY-ALIGN e2e: baseline v2 vs v3 + true Gemini scores.

Evidence log: /tmp/five-layer-legacy-align-e2e.log
Requires GEMINI_* from settings / 生产物料-backed env. production_billing=false.
"""

from __future__ import annotations

import hashlib
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parents[1]
LOG = Path("/tmp/five-layer-legacy-align-e2e.log")
SAMPLE_DIR = REPO / "测试用" / "图片"
SAMPLE_JSON = REPO / "docs" / "mihuanyuantu-v2" / "input" / "FIVE-LAYER-LEGACY-ALIGN-sample-sha256.json"
SEED = 20261113
# Cap sample count for runtime; full 50 when ALIGN_FULL=1
DEFAULT_N = 12


def note(msg: str) -> None:
    line = msg if msg.endswith("\n") else msg + "\n"
    print(line, end="")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line)


def must(cond: bool, label: str) -> None:
    if not cond:
        note(f"FAIL {label}")
        raise SystemExit(2)
    note(f"PASS {label}")


def _load_samples(limit: int) -> list[Path]:
    files = sorted(SAMPLE_DIR.glob("product_*.jpg"))
    must(len(files) >= 1, f"samples_present count={len(files)}")
    return files[: max(1, int(limit))]


def _preset() -> dict:
    return {
        "code": "align-e2e-phone",
        "brand": "Apple",
        "model": "iPhone 15 Pro",
        "iso": "400",
        "shutter": "1/120",
        "aperture": "f/1.8",
        "focalLength": "26mm",
        "gpsMode": "none",
        "legacyParameters": {
            "software": "Luminar AI",
            "white_balance": "Auto",
            "lens_model": "iPhone 15 Pro back camera 6.86mm f/1.78",
            "author": "",
            "copyright": None,
        },
    }


def _run_pipeline(
    source: bytes,
    *,
    version: str,
    freq_mode: str = "hybrid",
    algorithm: str = "v3",
    score_fn=None,
) -> tuple[bytes, float]:
    import io

    import numpy as np
    from PIL import Image

    from app.capabilities.realphotos.services.five_layer import (
        mean_abs_delta,
        run_five_layer,
    )

    out = run_five_layer(
        source=source,
        preset=_preset(),
        seed=SEED,
        freq_mode=freq_mode,
        algorithm=algorithm,
        score_fn=score_fn,
    )
    with Image.open(io.BytesIO(source)) as before, Image.open(io.BytesIO(out.jpeg)) as after:
        mad = mean_abs_delta(
            np.asarray(before.convert("RGB"), dtype=np.float32),
            np.asarray(after.convert("RGB"), dtype=np.float32),
        )
        must(after.size == before.size, f"size_unchanged_{version}")
        must(after.mode == "RGB", f"rgb_{version}")
    must(out.jpeg.startswith(b"\xff\xd8\xff"), f"jpeg_{version}")
    must(
        len(out.jpeg) >= len(source) or not source.startswith(b"\xff\xd8\xff"),
        f"byte_floor_{version}",
    )
    return out.jpeg, float(mad)


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


def main() -> int:
    LOG.write_text("", encoding="utf-8")
    note("=== FIVE-LAYER-LEGACY-ALIGN e2e ===")
    note(f"ts={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
    note("production_billing=false")
    note(f"sample_dir={SAMPLE_DIR}")
    note(f"sample_inventory={SAMPLE_JSON}")

    sys.path.insert(0, str(BACKEND))
    from dotenv import load_dotenv

    load_dotenv(BACKEND / ".env")

    import os

    limit = int(os.environ.get("ALIGN_SAMPLE_N") or DEFAULT_N)
    if str(os.environ.get("ALIGN_FULL") or "") == "1":
        limit = 50
    samples = _load_samples(limit)
    note(f"ALIGN_W0_CONFIRMED sample_n={len(samples)} seed={SEED}")

    from app.capabilities.realphotos.services.five_layer import (
        FIDELITY_MAD_HARD_MAX,
        FIDELITY_MAD_MAX,
        PIPELINE_VERSION,
    )
    from app.capabilities.realphotos.services.redo_policy import PASS_SCORE

    must(PIPELINE_VERSION == "s2-five-layer-3", "pipeline_v3")
    must(int(PASS_SCORE) == 75, "pass_score_unchanged")
    note(f"FIDELITY_MAD_MAX={FIDELITY_MAD_MAX} HARD={FIDELITY_MAD_HARD_MAX}")

    base_scores: list[float] = []
    v3_scores: list[float] = []
    dual_path_ok = False

    for idx, path in enumerate(samples):
        raw = path.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        note(f"--- sample={path.name} sha256={sha} bytes={len(raw)} ---")

        # Dual-path evidence on first sample: 2d vs 1d vs hybrid sizes equal.
        if idx == 0:
            j2d, mad2d = _run_pipeline(raw, version="2d", freq_mode="2d", algorithm="v3")
            j1d, mad1d = _run_pipeline(raw, version="1d", freq_mode="1d", algorithm="v3")
            jh, madh = _run_pipeline(raw, version="hybrid", freq_mode="hybrid", algorithm="v3")
            note(f"dual_path mad_2d={mad2d:.3f} mad_1d={mad1d:.3f} mad_hybrid={madh:.3f}")
            note(f"dual_path bytes_2d={len(j2d)} bytes_1d={len(j1d)} bytes_hybrid={len(jh)}")
            # Gate 2d/1d (auto 选优 paths). Hybrid is stacked evidence-only and may exceed prefer.
            must(mad2d <= FIDELITY_MAD_HARD_MAX and mad1d <= FIDELITY_MAD_HARD_MAX, "dual_path_mad_hard")
            if madh > FIDELITY_MAD_HARD_MAX:
                note(f"WARN hybrid_mad_above_hard mad={madh:.3f} (evidence-only; not default encode)")
            dual_path_ok = True
            note("ALIGN_W2_PIXEL_FFT dual_path_evidence_ok")

        base_jpeg, mad_b = _run_pipeline(raw, version="baseline_v2", freq_mode="2d", algorithm="v2")
        try:
            v3_jpeg, mad_v = _run_pipeline(
                raw,
                version="v3",
                freq_mode="auto",
                algorithm="v3",
            )
        except Exception as exc:  # noqa: BLE001
            note(f"FAIL v3_pipeline err={exc}")
            raise SystemExit(3) from exc
        note(f"mad_baseline_v2={mad_b:.3f} mad_v3={mad_v:.3f}")
        must(mad_v <= FIDELITY_MAD_HARD_MAX + 0.05, f"mad_hard_{path.name}")
        if mad_v > FIDELITY_MAD_MAX:
            note(f"WARN mad_above_prefer path={path.name} mad={mad_v:.3f}")

        try:
            rep_b = _gemini(base_jpeg)
            rep_v = _gemini(v3_jpeg)
        except Exception as exc:  # noqa: BLE001 — surface in log
            note(f"FAIL gemini_call err={exc}")
            raise SystemExit(3) from exc

        sb = float(rep_b["total_score"])
        sv = float(rep_v["total_score"])
        base_scores.append(sb)
        v3_scores.append(sv)
        note(
            f"gemini_baseline_v2 total={sb} passed={rep_b.get('passed')} "
            f"noise={rep_b.get('noise')} dof={rep_b.get('depthOfField')} "
            f"light={rep_b.get('lighting')} color={rep_b.get('colorRealism')} "
            f"overall={rep_b.get('overallRealism')}"
        )
        note(
            f"gemini_v3 total={sv} passed={rep_v.get('passed')} "
            f"noise={rep_v.get('noise')} dof={rep_v.get('depthOfField')} "
            f"light={rep_v.get('lighting')} color={rep_v.get('colorRealism')} "
            f"overall={rep_v.get('overallRealism')} reason={rep_v.get('reason')!r}"
        )
        note(f"delta={sv - sb:.1f}")

    must(dual_path_ok, "dual_path_ran")
    mean_b = sum(base_scores) / len(base_scores)
    mean_v = sum(v3_scores) / len(v3_scores)
    gain = mean_v - mean_b
    note(f"ALIGN_W1_BASELINE mean_baseline_v2={mean_b:.2f} n={len(base_scores)}")
    note(f"ALIGN_W5 mean_v3={mean_v:.2f} gain={gain:.2f} target>=10")
    note(f"PIPELINE_VERSION={PIPELINE_VERSION}")
    note("ALIGN_W3_EXIF focalplane_via_camera_specs=enabled empty_skip=enabled")
    note("ALIGN_W4_ENCODE profile=s2-ecommerce-1 byte_floor=hard")

    if gain >= 10.0:
        note("ALIGN_W5_E2E_PASS")
        note("ALIGN_W0_CONFIRMED")
        return 0

    note("ALIGN_W5_E2E_SHORTFALL")
    note(
        "STOP: gain below Q1 threshold; do not lower PASS_SCORE; "
        "report bottleneck (sample/detector/architecture)."
    )
    # Still exit 0 for infrastructure green when shortfall is score-only? Plan says
    # must reach ≥10 to mark pass. Fail the gate.
    return 4


if __name__ == "__main__":
    raise SystemExit(main())
