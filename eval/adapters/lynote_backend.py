"""Generic adapter for lynote-ai/ai-image-detector backends."""

from __future__ import annotations

import hashlib
import time
from pathlib import Path

from eval.schema import DetectResult, map_probability

DEFAULT_THRESHOLD = 0.5
UNCERTAIN_BAND = 0.0

_cache: dict[str, object] = {}
_errors: dict[str, str] = {}


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load(backend: str):
    if backend in _cache or backend in _errors:
        return
    try:
        from aidetector import create_detector

        _cache[backend] = create_detector(backend, device="cpu")
    except Exception as e:  # noqa: BLE001
        _errors[backend] = f"lynote:{backend} load failed: {e}"


def _predict(detector, image_path: str):
    if hasattr(detector, "predict_path"):
        return detector.predict_path(image_path)
    if hasattr(detector, "predict_image"):
        from PIL import Image

        return detector.predict_image(Image.open(image_path).convert("RGB"))
    raise RuntimeError(f"detector has no predict_path/predict_image: {type(detector)}")


def make_detect(backend: str, detector_id: str | None = None):
    det_id = detector_id or f"lynote_{backend.replace('-', '_')}"

    def detect(image_path: str, threshold: float = DEFAULT_THRESHOLD) -> DetectResult:
        t0 = time.perf_counter()
        sha = _sha256(image_path) if Path(image_path).is_file() else ""
        _load(backend)
        if backend in _errors:
            return DetectResult(
                detector_id=det_id,
                image_path=image_path,
                sha256=sha,
                verdict="tech_fail",
                threshold=threshold,
                error=_errors[backend],
                latency_ms=(time.perf_counter() - t0) * 1000,
            )
        try:
            result = _predict(_cache[backend], image_path)
            raw = result.as_dict() if hasattr(result, "as_dict") else dict(result)
            ai_p = None
            for key in ("probability_ai", "fake_probability", "ai_probability", "probability", "score"):
                if key in raw and raw[key] is not None:
                    ai_p = float(raw[key])
                    break
            if ai_p is None:
                raise RuntimeError(f"cannot parse {raw!r}")
            verdict = map_probability(ai_p, threshold=threshold, uncertain_band=UNCERTAIN_BAND)
            return DetectResult(
                detector_id=det_id,
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
                detector_id=det_id,
                image_path=image_path,
                sha256=sha,
                verdict="tech_fail",
                threshold=threshold,
                error=str(e),
                latency_ms=(time.perf_counter() - t0) * 1000,
            )

    return detect
