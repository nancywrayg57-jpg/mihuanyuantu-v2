"""Geocoder adapter boundary (ALIGN-GAP G4 / architecture adapters/geocoder).

FR-008 GPS is resolved only from device presets (none / fixed / random_by_scene).
First version does not enable external geocoding; callers that ask for it get a
clear NotConfigured error. Processing must not depend on this adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.core.exceptions import BusinessError

GEOCODER_MODE = "reserved"


@dataclass(frozen=True, slots=True)
class GeocodeResult:
    latitude: float
    longitude: float
    altitude: float | None = None
    label: str = ""


class GeocoderAdapter(Protocol):
    def geocode(self, query: str) -> GeocodeResult: ...


class NotConfiguredGeocoder:
    """Scheme A: reserved slot; never opens HTTP."""

    mode = GEOCODER_MODE

    def geocode(self, query: str) -> GeocodeResult:
        del query
        raise BusinessError(
            message="地理编码适配器未启用；首版 GPS 仅走设备预设",
            code="SERVICE_NOT_CONFIGURED",
        )


def get_geocoder_adapter() -> NotConfiguredGeocoder:
    return NotConfiguredGeocoder()
