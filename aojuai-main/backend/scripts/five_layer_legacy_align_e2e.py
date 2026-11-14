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
        "deviceType": "phone",
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
) -> tuple[bytes, float, int | None, dict | None]:
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
    return out.jpeg, float(mad), out.detector_score, out.detector_report


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
    import os

    # Meta/Clash Fake-IP: clear Cursor sandbox HTTP(S)_PROXY so aoju + Gemini both
    # egress via TUN (trust_env=False generation client + urllib Gemini).
    for key in list(os.environ):
        if "proxy" in key.lower():
            os.environ.pop(key, None)
    os.environ["NO_PROXY"] = "*"
    os.environ["no_proxy"] = "*"
    os.environ.setdefault("ALIGN_LAYER0_IMG2IMG", "1")
    # Gate 2026-11-14: α=1.0 matches legacy full-replace (strength never entered API).
    os.environ.setdefault("ALIGN_LAYER0_BLEND_ALPHA", "1.0")

    LOG.write_text("", encoding="utf-8")
    note("=== FIVE-LAYER-LEGACY-ALIGN e2e ===")
    note(f"ts={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
    note("production_billing=false")
    note(f"sample_dir={SAMPLE_DIR}")
    note(f"sample_inventory={SAMPLE_JSON}")
    note(
        "net=meta_fakeip_clear_proxy layer0_img2img=on "
        f"blend_alpha={os.environ.get('ALIGN_LAYER0_BLEND_ALPHA')} "
        "prompts=legacy_zh_c1 ca_sat_nudge=off"
    )

    sys.path.insert(0, str(BACKEND))
    from dotenv import load_dotenv

    load_dotenv(BACKEND / ".env")

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

        # Dual-path evidence on first sample: 2d vs 1d vs hybrid (no img2img on these modes).
        if idx == 0:
            j2d, mad2d, _, _ = _run_pipeline(raw, version="2d", freq_mode="2d", algorithm="v3")
            j1d, mad1d, _, _ = _run_pipeline(raw, version="1d", freq_mode="1d", algorithm="v3")
            jh, madh, _, _ = _run_pipeline(raw, version="hybrid", freq_mode="hybrid", algorithm="v3")
            note(
                "dual_path note=no_img2img multipliers_may_be_0.85_damped "
                f"mad_2d={mad2d:.3f} mad_1d={mad1d:.3f} mad_hybrid={madh:.3f}"
            )
            note(f"dual_path bytes_2d={len(j2d)} bytes_1d={len(j1d)} bytes_hybrid={len(jh)}")
            note(
                f"MAD_OBSERVE prefer={FIDELITY_MAD_MAX} hard_ref={FIDELITY_MAD_HARD_MAX} "
                f"(no veto)"
            )
            dual_path_ok = True
            note("ALIGN_W2_PIXEL_FFT dual_path_evidence_ok")

        base_jpeg, mad_b, _, _ = _run_pipeline(
            raw, version="baseline_v2", freq_mode="2d", algorithm="v2"
        )
        try:
            from app.capabilities.realphotos.services import five_layer as _fl

            if hasattr(_fl._maybe_layer0_img2img, "last_note"):
                delattr(_fl._maybe_layer0_img2img, "last_note")
            v3_jpeg, mad_v, picked, rep_pick = _run_pipeline(
                raw,
                version="v3",
                freq_mode="auto",
                algorithm="v3",
                score_fn=_gemini,
            )
            layer0_note = getattr(_fl._maybe_layer0_img2img, "last_note", None)
            note(f"layer0_note={layer0_note!r}")
        except Exception as exc:  # noqa: BLE001
            note(f"FAIL v3_pipeline err={exc}")
            raise SystemExit(3) from exc
        note(f"mad_baseline_v2={mad_b:.3f} mad_v3={mad_v:.3f}")
        if mad_v > FIDELITY_MAD_HARD_MAX:
            note(f"MAD_OBSERVE above_hard_ref path={path.name} mad={mad_v:.3f}")
        elif mad_v > FIDELITY_MAD_MAX:
            note(f"MAD_OBSERVE above_prefer path={path.name} mad={mad_v:.3f}")
        else:
            note(f"MAD_OBSERVE within_prefer path={path.name} mad={mad_v:.3f}")

        try:
            rep_b = _gemini(base_jpeg)
        except Exception as exc:  # noqa: BLE001
            note(f"FAIL gemini_call err={exc}")
            raise SystemExit(3) from exc

        sb = float(rep_b["total_score"])
        # C9: prefer full detector_report from rerank; never invent empty five-dim shell.
        if isinstance(rep_pick, dict) and "total_score" in rep_pick:
            rep_v = rep_pick
            sv = float(rep_v["total_score"])
        elif picked is not None:
            try:
                rep_v = _gemini(v3_jpeg)
            except Exception as exc:  # noqa: BLE001
                note(f"FAIL gemini_call err={exc}")
                raise SystemExit(3) from exc
            sv = float(rep_v["total_score"])
            note(f"rerank_score_only={picked} refreshed_full_report=true")
        else:
            try:
                rep_v = _gemini(v3_jpeg)
            except Exception as exc:  # noqa: BLE001
                note(f"FAIL gemini_call err={exc}")
                raise SystemExit(3) from exc
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
    note("ALIGN_RELAX Q4_ca=on Q8_layer0=on Q11_mad=observe_only")
    note("ALIGN_GATE_2026_11_14 C1_zh_prompts C4_no_ca_sat C9_keep_five_dim")

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
