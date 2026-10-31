"""Adapter for e3ntity/nonescape (prefer official Python API; ONNX fallback).

ASSUMPTION N-H1: If `nonescape` package is unavailable, ONNX path uses ImageNet
normalization @224 — this may NOT match training preprocess. Official package path
is preferred for scoring; ONNX fallback results must be marked in raw.mode.
"""

from __future__ import annotations

import hashlib
import time
import urllib.request
from pathlib import Path

from eval.schema import DetectResult, map_probability

DETECTOR_ID = "nonescape_onnx"
DEFAULT_THRESHOLD = 0.5
UNCERTAIN_BAND = 0.0
WEIGHT_URL_FULL = "https://nonescape.sfo2.cdn.digitaloceanspaces.com/nonescape-mini-v0.safetensors"
WEIGHT_URL_ONNX = "https://nonescape.sfo2.cdn.digitaloceanspaces.com/nonescape-mini-v0.onnx"
WEIGHT_DIR = Path(__file__).resolve().parents[2] / "weights"
WEIGHT_ST = WEIGHT_DIR / "nonescape-mini-v0.safetensors"
WEIGHT_ONNX = WEIGHT_DIR / "nonescape-mini-v0.onnx"

_classifier = None
_session = None
_input_name = None
_mode: str | None = None
_load_error: str | None = None


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _download(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and dest.stat().st_size > 1000:
        return dest
    urllib.request.urlretrieve(url, dest)
    return dest


def _load():
    global _classifier, _session, _input_name, _mode, _load_error
    if _mode is not None or _load_error is not None:
        return
    # Prefer official package
    try:
        from nonescape import NonescapeClassifierMini  # type: ignore

        path = _download(WEIGHT_URL_FULL, WEIGHT_ST)
        _classifier = NonescapeClassifierMini(str(path))
        _mode = "official_mini"
        return
    except Exception:
        pass
    try:
        import onnxruntime as ort  # type: ignore

        path = _download(WEIGHT_URL_ONNX, WEIGHT_ONNX)
        _session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        _input_name = _session.get_inputs()[0].name
        _mode = "onnx_fallback_ASSUMPTION_N-H1"
    except Exception as e:  # noqa: BLE001
        _load_error = f"nonescape load failed (official+onnx): {e}"


def _preprocess_onnx(image_path: str):
    import numpy as np
    from PIL import Image

    img = Image.open(image_path).convert("RGB").resize((224, 224))
    arr = np.asarray(img).astype("float32") / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype="float32")
    std = np.array([0.229, 0.224, 0.225], dtype="float32")
    arr = (arr - mean) / std
    arr = np.transpose(arr, (2, 0, 1))[None, ...]
    return arr


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
        if _mode == "official_mini":
            result = _classifier.predict(image_path)
            # result.is_synthetic / confidence
            is_syn = bool(getattr(result, "is_synthetic", False))
            conf = float(getattr(result, "confidence", 0.5))
            ai_p = conf if is_syn else (1.0 - conf)
            raw = {
                "mode": _mode,
                "is_synthetic": is_syn,
                "confidence": conf,
            }
        else:
            import numpy as np

            inp = _preprocess_onnx(image_path)
            outs = _session.run(None, {_input_name: inp})
            logits = np.asarray(outs[0]).reshape(-1)
            if logits.size == 1:
                ai_p = float(1 / (1 + np.exp(-logits[0])))
            else:
                e = np.exp(logits - logits.max())
                prob = e / e.sum()
                ai_p = float(prob[-1])
            raw = {"mode": _mode, "logits": logits.tolist()}
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
