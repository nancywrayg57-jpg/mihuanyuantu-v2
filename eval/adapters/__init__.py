from __future__ import annotations

from typing import Callable

from eval.schema import DetectResult

DetectorFn = Callable[[str], DetectResult]


def get_adapter(detector_id: str) -> DetectorFn:
    from eval.adapters.lynote_backend import make_detect

    mapping = {
        "lynote_univfd": ("univfd", "lynote_univfd"),
        "nonescape_onnx": ("nonescape-mini", "nonescape_onnx"),  # via lynote; id kept for continuity
        "nonescape_mini": ("nonescape-mini", "nonescape_mini"),
        "lynote_hybrid": ("hybrid", "lynote_hybrid"),
        # legacy alias: broken HF pack retained only for explicit debug
        "community_forensics": None,
    }
    if detector_id == "community_forensics":
        from eval.adapters.community_forensics import detect

        return detect
    if detector_id in mapping and mapping[detector_id] is not None:
        backend, did = mapping[detector_id]
        return make_detect(backend, did)
    raise KeyError(f"unknown detector_id={detector_id}")


AVAILABLE = [
    "lynote_univfd",
    "nonescape_mini",
    "nonescape_onnx",  # alias → nonescape-mini
    "lynote_hybrid",
    "community_forensics",  # HF pack broken; not for main gate
]

# Official Top3 for this run (CF HF pack failed verification 2026-10-31)
TOP3 = ["lynote_univfd", "nonescape_mini", "lynote_hybrid"]
