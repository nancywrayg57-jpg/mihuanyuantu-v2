from __future__ import annotations

from typing import Callable

from eval.schema import DetectResult

DetectorFn = Callable[[str], DetectResult]


def get_adapter(detector_id: str) -> DetectorFn:
    if detector_id == "lynote_univfd":
        from eval.adapters.lynote_univfd import detect

        return detect
    if detector_id == "nonescape_onnx":
        from eval.adapters.nonescape_onnx import detect

        return detect
    if detector_id == "community_forensics":
        from eval.adapters.community_forensics import detect

        return detect
    if detector_id == "heuristic_stub":
        from eval.adapters.heuristic_stub import detect

        return detect
    raise KeyError(f"unknown detector_id={detector_id}")


AVAILABLE = [
    "lynote_univfd",
    "nonescape_onnx",
    "community_forensics",
    "heuristic_stub",
]
