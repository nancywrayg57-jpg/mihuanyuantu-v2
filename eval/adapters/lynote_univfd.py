"""Adapter for lynote-ai/ai-image-detector (UnivFD default)."""

from __future__ import annotations

import hashlib
import time
from pathlib import Path

from eval.schema import DetectResult, map_probability

DETECTOR_ID = "lynote_univfd"
DEFAULT_THRESHOLD = 0.5
# Default: no uncertain band for primary scoring; set via env if needed
UNCERTAIN_BAND = 0.0

_detector = None
_load_error: str | None = None


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load():
    global _detector, _load_error
    if _detector is not None or _load_error is not None:
        return
    try:
        from aidetector import create_detector  # type: ignore

        _detector = create_detector("univfd", device="auto")
    except Exception as e:  # noqa: BLE001 — surface as tech_fail
        _load_error = f"lynote_univfd load failed: {e}"


def detect(image_path: str, threshold: float = DEFAULT_THRESHOLD) -> DetectResult:
    t0 = time.perf_counter()
    sha = _sha256(image_path) if Path(image_path).is_file() else ""
    _load()
    if _load_error:
        return DetectResult(
            detector_id=DETECTOR_ID,
            image_path=image_path,
            sha256=sha,
            verdict="tech_fail",
            threshold=threshold,
            error=_load_error,
            latency_ms=(time.perf_counter() - t0) * 1000,
        )
    try:
        result = _detector.predict_path(image_path)
        raw = result.as_dict() if hasattr(result, "as_dict") else dict(result)
        # lynote DetectionResult.as_dict uses probability_ai / probability_real
        ai_p = None
        for key in (
            "probability_ai",
            "fake_probability",
            "ai_probability",
            "probability",
            "score",
        ):
            if key in raw and raw[key] is not None:
                ai_p = float(raw[key])
                break
        if ai_p is None and "label" in raw:
            label = str(raw["label"]).lower()
            ai_p = 1.0 if label in {"fake", "ai", "ai_generated", "synthetic"} else 0.0
        if ai_p is None:
            raise RuntimeError(f"cannot parse probability from {raw!r}")
        verdict = map_probability(ai_p, threshold=threshold, uncertain_band=UNCERTAIN_BAND)
        return DetectResult(
            detector_id=DETECTOR_ID,
            image_path=image_path,
            sha256=sha,
            verdict=verdict,
            ai_probability=ai_p,
            confidence=abs(ai_p - 0.5) * 2,
            threshold=threshold,
            raw=raw,
            latency_ms=(time.perf_counter() - t0) * 1000,
        )
    except Exception as e:  # noqa: BLE001
        return DetectResult(
            detector_id=DETECTOR_ID,
            image_path=image_path,
            sha256=sha,
            verdict="tech_fail",
            threshold=threshold,
            error=str(e),
            latency_ms=(time.perf_counter() - t0) * 1000,
        )
