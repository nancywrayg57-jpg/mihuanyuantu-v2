"""Adapter for CommunityForensics ViT (HF: buildborderless/...)."""

from __future__ import annotations

import hashlib
import time
from pathlib import Path

from eval.schema import DetectResult, map_probability

DETECTOR_ID = "community_forensics"
DEFAULT_THRESHOLD = 0.5
UNCERTAIN_BAND = 0.0
MODEL_ID = "buildborderless/CommunityForensics-DeepfakeDet-ViT"

_pipe = None
_load_error: str | None = None


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load():
    global _pipe, _load_error
    if _pipe is not None or _load_error is not None:
        return
    try:
        from PIL import Image
        from transformers import pipeline  # type: ignore

        _pipe = pipeline(
            "image-classification",
            model=MODEL_ID,
            device=-1,  # CPU
        )
        _ = Image  # noqa: F841 — ensure Pillow available at load time
    except Exception as e:  # noqa: BLE001
        _load_error = f"community_forensics load failed: {e}"


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
        from PIL import Image

        img = Image.open(image_path).convert("RGB")
        preds = _pipe(img)
        raw = {"predictions": preds}
        ai_p = None
        real_p = None
        for item in preds:
            label = str(item.get("label", "")).lower()
            score = float(item.get("score", 0.0))
            if any(k in label for k in ("fake", "ai", "generated", "synthetic", "deepfake")):
                ai_p = score if ai_p is None else max(ai_p, score)
            if any(k in label for k in ("real", "human", "authentic", "organic")):
                real_p = score if real_p is None else max(real_p, score)
        if ai_p is None and real_p is not None:
            ai_p = 1.0 - real_p
        if ai_p is None:
            # take top label heuristic
            top = max(preds, key=lambda x: float(x["score"]))
            lab = str(top["label"]).lower()
            ai_p = float(top["score"]) if any(k in lab for k in ("fake", "ai", "generated")) else 1.0 - float(top["score"])
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
