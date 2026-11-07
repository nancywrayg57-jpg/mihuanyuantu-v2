"""G4: geocoder reserved adapter never opens HTTP."""

from __future__ import annotations

import pytest

from app.capabilities.realphotos.adapters.geocoder import (
    GEOCODER_MODE,
    NotConfiguredGeocoder,
    get_geocoder_adapter,
)
from app.core.exceptions import BusinessError


def test_geocoder_not_configured_raises() -> None:
    adapter = get_geocoder_adapter()
    assert isinstance(adapter, NotConfiguredGeocoder)
    assert adapter.mode == GEOCODER_MODE == "reserved"
    with pytest.raises(BusinessError) as exc:
        adapter.geocode("上海市")
    assert exc.value.code == "SERVICE_NOT_CONFIGURED"


def test_gps_writability_fixed_missing_coords() -> None:
    from app.capabilities.realphotos.services.gps_write import gps_writability, resolve_gps

    plan = resolve_gps(preset={"gpsMode": "fixed", "gpsConfig": {}}, seed=1)
    assert plan["action"] == "fail"
    assert plan["mode"] == "fixed"
    writable = gps_writability(gps_mode="fixed", gps_config={})
    assert writable["gpsWritable"] is False
    assert writable["gpsMode"] == "fixed"
