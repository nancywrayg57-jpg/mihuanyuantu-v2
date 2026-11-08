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
    """Legacy: fixed without coords skips GPS write; mode stays fixed; submit allowed."""
    import io

    from PIL import Image

    from app.capabilities.realphotos.services.five_layer import run_five_layer
    from app.capabilities.realphotos.services.gps_write import (
        assert_preset_gps_ready,
        gps_writability,
        resolve_gps,
    )
    from app.capabilities.realphotos.services.s1_catalog import S1_ENABLED_PRESETS

    plan = resolve_gps(preset={"gpsMode": "fixed", "gpsConfig": {}}, seed=1)
    assert plan["action"] == "skip"
    assert plan["mode"] == "fixed"
    assert "跳过" in str(plan.get("reason") or "")
    assert "缺少可用的纬度/经度" not in str(plan.get("reason") or "")
    writable = gps_writability(gps_mode="fixed", gps_config={})
    assert writable["gpsWritable"] is True
    assert writable["gpsWillSkip"] is True
    assert "跳过" in str(writable.get("gpsWritableReason") or "")
    assert writable["gpsMode"] == "fixed"
    assert_preset_gps_ready({"gpsMode": "fixed", "gpsConfig": {}})

    buf = io.BytesIO()
    Image.new("RGB", (640, 480), (20, 40, 60)).save(buf, format="JPEG", quality=85)
    preset = dict(S1_ENABLED_PRESETS[0])
    preset["gpsMode"] = "fixed"
    preset["gpsConfig"] = {}
    out = run_five_layer(source=buf.getvalue(), preset=preset, seed=8)
    gps_field = next(f for f in out.fields if f["tag"] == "GPSLatitude")
    assert gps_field["verification_status"] == "skipped"


def test_random_by_scene_missing_scene_skips_gps_not_fail() -> None:
    """Merchant legacy presets often lack sceneRule; must not hard-fail EXIF."""
    import io

    from PIL import Image

    from app.capabilities.realphotos.services.five_layer import run_five_layer
    from app.capabilities.realphotos.services.gps_write import (
        assert_preset_gps_ready,
        gps_writability,
        resolve_gps,
    )
    from app.capabilities.realphotos.services.s1_catalog import S1_ENABLED_PRESETS

    plan = resolve_gps(preset={"gpsMode": "random_by_scene", "gpsConfig": {}}, seed=7)
    assert plan["action"] == "skip"
    assert "不伪造" in str(plan.get("reason") or "")
    writable = gps_writability(gps_mode="random_by_scene", gps_config={})
    assert writable["gpsWritable"] is True
    assert writable["gpsWillSkip"] is True
    assert "跳过" in str(writable.get("gpsWritableReason") or "")
    assert_preset_gps_ready({"gpsMode": "random_by_scene", "gpsConfig": {}})

    buf = io.BytesIO()
    Image.new("RGB", (1024, 768), (40, 60, 80)).save(buf, format="JPEG", quality=85)
    preset = dict(S1_ENABLED_PRESETS[0])
    preset["gpsMode"] = "random_by_scene"
    preset["gpsConfig"] = {}
    out = run_five_layer(source=buf.getvalue(), preset=preset, seed=7)
    gps_field = next(f for f in out.fields if f["tag"] == "GPSLatitude")
    assert gps_field["verification_status"] == "skipped"
    assert out.jpeg.startswith(b"\xff\xd8\xff")

    # Legacy scene_type fallback writes GPS (old random_by_scene path).
    with_scene = dict(S1_ENABLED_PRESETS[0])
    with_scene["gpsMode"] = "random_by_scene"
    with_scene["gpsConfig"] = {}
    with_scene["legacyParameters"] = {"scene_type": "urban"}
    plan_scene = resolve_gps(preset=with_scene, seed=11)
    assert plan_scene["action"] == "write"
    assert plan_scene.get("sceneRule") == "urban"
    out_scene = run_five_layer(source=buf.getvalue(), preset=with_scene, seed=11)
    gps_ok = next(f for f in out_scene.fields if f["tag"] == "GPSLatitude")
    assert gps_ok["verification_status"] == "verified"
