"""Unified detector output schema (baseline contract mapping)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Optional

Verdict = Literal["physical_device", "ai_generated", "uncertain", "tech_fail"]


@dataclass
class DetectResult:
    detector_id: str
    image_path: str
    sha256: str
    verdict: Verdict
    ai_probability: Optional[float] = None
    confidence: Optional[float] = None
    threshold: Optional[float] = None
    raw: dict[str, Any] = field(default_factory=dict)
    latency_ms: Optional[float] = None
    error: Optional[str] = None
    cached: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def map_probability(
    ai_probability: float,
    threshold: float = 0.5,
    uncertain_band: float = 0.05,
) -> Verdict:
    """Map P(AI) to unified verdict. Band around threshold → uncertain (optional)."""
    if uncertain_band > 0 and abs(ai_probability - threshold) < uncertain_band:
        return "uncertain"
    if ai_probability >= threshold:
        return "ai_generated"
    return "physical_device"
