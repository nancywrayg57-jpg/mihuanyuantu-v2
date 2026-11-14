"""S2 five-layer byte floor and EXIF read-back. Detection stays a fixture."""

from __future__ import annotations

import asyncio
import gc
import io
import json
import logging
import math
import subprocess
import warnings

import numpy as np
import pytest
from PIL import Image

from app.capabilities.realphotos.services.camera_specs import lookup_camera_spec
from app.capabilities.realphotos.services.five_layer import (
    _LAYER0_OPTICAL_STRENGTH,
    FIDELITY_MAD_HARD_MAX,
    FIDELITY_MAD_MAX,
    PIPELINE_VERSION,
    _apply_chromatic_aberration,
    _flag_setting_on,
    _l1_l3,
    _maybe_layer0_img2img,
    _verified_optional,
    _weak_bayer_roundtrip,
    _write_and_read,
    focal_length_to_ca_strength,
    l1_noise_sigma,
    mean_abs_delta,
    optional_exif_assignments,
    run_five_layer,
)
from app.capabilities.realphotos.services.s1_catalog import S1_ENABLED_PRESETS
from app.core.config import Settings, settings
from app.core.exceptions import BusinessError


def _source(*, quality: int, width: int = 320, height: int = 240, kind: str = "noise") -> bytes:
    if kind == "gradient":
        # Smooth photo-like content so JPEG re-encode does not dominate MAD.
        yy, xx = np.mgrid[0:height, 0:width]
        pixels = np.stack(
            [
                (xx * 255 / max(width - 1, 1)).astype(np.uint8),
                (yy * 255 / max(height - 1, 1)).astype(np.uint8),
                np.full((height, width), 128, dtype=np.uint8),
            ],
            axis=-1,
        )
    else:
        rng = np.random.default_rng(7)
        pixels = rng.integers(0, 255, size=(height, width, 3), dtype=np.uint8)
    buf = io.BytesIO()
    Image.fromarray(pixels, mode="RGB").save(buf, format="JPEG", quality=quality, subsampling=0)
    return buf.getvalue()


def test_pipeline_version_is_s2_five_layer_3() -> None:
    assert PIPELINE_VERSION == "s2-five-layer-3"


def test_focal_length_ca_strength_legacy_table() -> None:
    assert focal_length_to_ca_strength("26mm") == 1.0
    assert focal_length_to_ca_strength(14) == 2.0
    assert focal_length_to_ca_strength(100) == 0.4


def test_l1_sigma_iso_stronger_than_v2_and_capped() -> None:
    # ISO100 uses process floor 400 × intensity 1.55 → ~1.55; capped ≤2.20.
    assert 1.20 <= l1_noise_sigma(100) <= 1.90
    assert l1_noise_sigma(100) > 1.10
    assert l1_noise_sigma(1600) <= 2.20
    assert l1_noise_sigma(51200) <= 2.20


def test_camera_spec_lookup_iphone() -> None:
    spec = lookup_camera_spec("Apple", "iPhone 15 Pro")
    assert spec is not None
    assert float(spec["focal_plane_x_res"]) > 0


def test_five_layer_keeps_size_writes_preset_and_meets_byte_floor() -> None:
    source = _source(quality=40)
    preset = dict(S1_ENABLED_PRESETS[0])
    output = run_five_layer(source=source, preset=preset, seed=11).jpeg
    assert output.startswith(b"\xff\xd8\xff")
    assert len(output) >= len(source)
    with Image.open(io.BytesIO(source)) as before, Image.open(io.BytesIO(output)) as after:
        assert after.size == before.size
        assert after.mode == "RGB"
    raw = subprocess.run(
        ["exiftool", "-json", "-Make", "-Model", "-GPSLatitude", "-MakerNote", "-"],
        input=output,
        check=True,
        capture_output=True,
    )
    row = json.loads(raw.stdout.decode())[0]
    assert row["Make"] == "Apple"
    assert row["Model"] == "iPhone 15 Pro"
    assert "GPSLatitude" not in row
    assert "MakerNote" not in row


def test_five_layer_fidelity_mad_is_finite_observe_only() -> None:
    """Q11 复裁：MAD 仅观测；单测只要求有限值与常量次序，不否决。"""
    source = _source(quality=92, kind="gradient")
    preset = dict(S1_ENABLED_PRESETS[0])
    output = run_five_layer(source=source, preset=preset, seed=11).jpeg
    with Image.open(io.BytesIO(source)) as before, Image.open(io.BytesIO(output)) as after:
        mad = mean_abs_delta(np.asarray(before, dtype=np.float32), np.asarray(after, dtype=np.float32))
    assert mad >= 0.0
    assert math.isfinite(mad)
    assert FIDELITY_MAD_MAX <= FIDELITY_MAD_HARD_MAX


def test_freq_modes_keep_dimensions() -> None:
    source = _source(quality=50)
    preset = dict(S1_ENABLED_PRESETS[0])
    for mode in ("2d", "1d", "hybrid", "auto"):
        out = run_five_layer(source=source, preset=preset, seed=5, freq_mode=mode).jpeg
        with Image.open(io.BytesIO(source)) as before, Image.open(io.BytesIO(out)) as after:
            assert after.size == before.size


def test_byte_floor_fails_without_padding() -> None:
    source = _source(quality=100, width=64, height=48) + (b"\x00" * 400_000)
    with pytest.raises(BusinessError) as exc:
        run_five_layer(source=source, preset=dict(S1_ENABLED_PRESETS[0]), seed=3)
    assert exc.value.code == "OUTPUT_CONSTRAINT_UNSATISFIED"


def test_optional_exif_assignments_skip_empty_and_placeholders() -> None:
    preset = {
        "brand": "Apple",
        "model": "iPhone",
        "legacyParameters": {
            "software": "Luminar AI",
            "author": "",
            "copyright": None,
            "lens_model": "-",
            "lens_make": "   ",
            "white_balance": "Auto",
            "metering_mode": "",
            "flash_mode": "Off",
            "scene_mode": None,
        },
    }
    tags = dict(optional_exif_assignments(preset))
    assert tags["Software"] == "Luminar AI"
    assert tags["WhiteBalance"] == "0"
    assert tags["Flash"] == "0"
    assert "Artist" not in tags
    assert "Copyright" not in tags
    assert "LensModel" not in tags
    assert "LensMake" not in tags
    assert "MeteringMode" not in tags
    assert "SceneCaptureType" not in tags


def test_five_layer_skips_empty_optional_exif_writes_filled() -> None:
    source = _source(quality=40)
    preset = dict(S1_ENABLED_PRESETS[0])
    preset["legacyParameters"] = {
        "software": "Luminar AI",
        "author": "",
        "copyright": None,
        "lens_model": "",
        "lens_make": "-",
        "white_balance": "Auto",
    }
    result = run_five_layer(source=source, preset=preset, seed=11)
    raw = subprocess.run(
        [
            "exiftool",
            "-json",
            "-Software",
            "-Artist",
            "-Copyright",
            "-LensModel",
            "-LensMake",
            "-WhiteBalance",
            "-",
        ],
        input=result.jpeg,
        check=True,
        capture_output=True,
    )
    row = json.loads(raw.stdout.decode())[0]
    assert row.get("Software") == "Luminar AI"
    assert "Artist" not in row
    assert "Copyright" not in row
    assert "LensModel" not in row
    assert "LensMake" not in row
    assert row.get("WhiteBalance") in {"Auto", "0", 0}
    ledger = {field["tag"]: field for field in result.fields}
    assert ledger["Software"]["verification_status"] == "verified"
    assert "Artist" not in ledger
    assert "LensModel" not in ledger


def test_optional_exif_enum_printconv_aliases() -> None:
    """PrintConv labels must not fail verification when requested value is the numeric code."""
    assert _verified_optional("MeteringMode", "3", "Spot")["verification_status"] == "verified"
    assert (
        _verified_optional("ExposureProgram", "3", "Aperture-priority AE")["verification_status"]
        == "verified"
    )
    assert _verified_optional("MeteringMode", "3", "3")["verification_status"] == "verified"
    assert _verified_optional("MeteringMode", "3", "Average")["verification_status"] == "failed"


def test_huawei_p60_art_optional_exif_enums_verify() -> None:
    """Regression: legacy Huawei Spot + Aperture Priority + f/1.4 must not raise EXIF_WRITE_FAILED."""
    source = _source(quality=40)
    preset = {
        "brand": "Huawei",
        "model": "Huawei P60 Art",
        "iso": "400",
        "shutter": "1/125",
        "aperture": "f/1.4",
        "focalLength": "8mm",
        "makerNote": "Huawei",
        "gpsMode": "none",
        "legacyParameters": {
            "metering_mode": "Spot",
            "white_balance": "Tungsten",
            "flash_mode": "Off",
            "exposure_mode": "Aperture Priority",
        },
    }
    jpeg, fields = _write_and_read(source, preset, seed=17)
    assert jpeg.startswith(b"\xff\xd8\xff")
    ledger = {field["tag"]: field for field in fields}
    assert ledger["MeteringMode"]["verification_status"] == "verified"
    assert ledger["ExposureProgram"]["verification_status"] == "verified"
    assert ledger["WhiteBalance"]["verification_status"] == "verified"
    assert ledger["Flash"]["verification_status"] == "verified"
    assert ledger["LightSource"]["verification_status"] == "verified"


def _solid_jpeg(*, width: int, height: int, color: tuple[int, int, int]) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buf, format="JPEG", quality=95, subsampling=0)
    return buf.getvalue()


def _enable_layer0(monkeypatch: pytest.MonkeyPatch, flag: str) -> None:
    monkeypatch.setenv("ALIGN_LAYER0_IMG2IMG", flag)
    monkeypatch.setattr(settings, "ALIGN_LAYER0_IMG2IMG", flag)


def test_align_layer0_img2img_default_is_off() -> None:
    assert Settings.model_fields["ALIGN_LAYER0_IMG2IMG"].default == "0"


def test_chromatic_aberration_8mm_and_26mm_match_input() -> None:
    """Default CA is identity at the preview focal length and the ALIGN preset."""
    rng = np.random.default_rng(3)
    src = rng.integers(0, 256, size=(40, 36, 3), dtype=np.uint8).astype(np.float32)
    for focal in ("8mm", "26mm"):
        out = _apply_chromatic_aberration(src, focal_length=focal, intensity=1.0)
        assert out.shape == src.shape
        assert np.array_equal(out, src)


def test_layer0_flag_0_jpeg_pixels_match_skip(monkeypatch: pytest.MonkeyPatch) -> None:
    """flag=0 must not call img2img and must match an explicit skip."""
    calls: list[object] = []

    async def poison(**kwargs):
        calls.append(kwargs)
        return {"images": [{"raw": _solid_jpeg(width=kwargs["width"], height=kwargs["height"], color=(255, 0, 0))}]}

    monkeypatch.setattr(
        "app.capabilities.realphotos.services.supplier_clients.generate_images",
        poison,
    )
    monkeypatch.setattr(
        "app.capabilities.realphotos.services.supplier_secrets.read_duty_secret",
        lambda duty: "unit-test-key",
    )
    _enable_layer0(monkeypatch, "0")
    source = _source(quality=90, width=64, height=48, kind="gradient")
    preset = dict(S1_ENABLED_PRESETS[0])
    flagged = run_five_layer(source=source, preset=preset, seed=11).jpeg

    def _skip(source: bytes, *, preset: dict) -> None:
        return None

    monkeypatch.setattr(
        "app.capabilities.realphotos.services.five_layer._maybe_layer0_img2img",
        _skip,
    )
    skipped = run_five_layer(source=source, preset=preset, seed=11).jpeg
    with Image.open(io.BytesIO(flagged)) as left, Image.open(io.BytesIO(skipped)) as right:
        assert np.array_equal(np.asarray(left), np.asarray(right))
    assert calls == []


async def test_layer0_running_loop_returns_image_without_never_awaited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A live loop must run generate_images on another thread, not drop the coroutine."""
    caller = asyncio.get_running_loop()
    state = {"n": 0, "other_loop": False}

    async def fake_generate_images(**kwargs):
        state["n"] += 1
        state["other_loop"] = asyncio.get_running_loop() is not caller
        return {
            "images": [
                {
                    "raw": _solid_jpeg(
                        width=int(kwargs["width"]),
                        height=int(kwargs["height"]),
                        color=(12, 34, 56),
                    )
                }
            ]
        }

    monkeypatch.setattr(
        "app.capabilities.realphotos.services.supplier_clients.generate_images",
        fake_generate_images,
    )
    monkeypatch.setattr(
        "app.capabilities.realphotos.services.supplier_secrets.read_duty_secret",
        lambda duty: "unit-test-key",
    )
    _enable_layer0(monkeypatch, "1")
    source = _source(quality=90, width=32, height=24)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", RuntimeWarning)
        result = _maybe_layer0_img2img(source, preset={"deviceType": "phone"})
        gc.collect()
    assert not any("never awaited" in str(item.message) for item in caught)
    assert state["n"] == 1
    assert state["other_loop"] is True
    assert result is not None
    assert result.startswith(b"\xff\xd8")


async def test_layer0_running_loop_failure_logs_error_type(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def boom(**kwargs):
        raise TimeoutError("stub-down")

    monkeypatch.setattr(
        "app.capabilities.realphotos.services.supplier_clients.generate_images",
        boom,
    )
    monkeypatch.setattr(
        "app.capabilities.realphotos.services.supplier_secrets.read_duty_secret",
        lambda duty: "unit-test-key",
    )
    _enable_layer0(monkeypatch, "1")
    source = _source(quality=90, width=32, height=24)
    with caplog.at_level(logging.ERROR), warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", RuntimeWarning)
        result = _maybe_layer0_img2img(source, preset={"deviceType": "phone"})
        gc.collect()
    assert result is None
    assert not any("never awaited" in str(item.message) for item in caught)
    assert any("error_type=TimeoutError" in record.getMessage() for record in caplog.records)


def test_nonlegacy_pilot_settings_default_off() -> None:
    for key in (
        "ALIGN_BAYER_ROUNDTRIP",
        "ALIGN_BAYER_STRENGTH",
        "ALIGN_PG_NOISE",
        "ALIGN_PG_SCALE",
        "ALIGN_PG_FLAT_THR",
    ):
        assert Settings.model_fields[key].default == ""


def test_default_opt_measure_settings_default_empty() -> None:
    for key in (
        "ALIGN_SHARPEN",
        "ALIGN_VIGNETTE_SCALE",
        "ALIGN_JPEG_MILD_SWEEP",
        "ALIGN_JPEG_QUALITIES",
    ):
        assert Settings.model_fields[key].default == ""


def test_layer0_optical_default_is_024_after_default_opt() -> None:
    assert float(_LAYER0_OPTICAL_STRENGTH) == 0.24


def test_weak_bayer_strength_zero_is_identity() -> None:
    rng = np.random.default_rng(9)
    src = rng.integers(0, 256, size=(32, 28, 3), dtype=np.uint8).astype(np.float32)
    out = _weak_bayer_roundtrip(src, strength=0.0)
    assert np.array_equal(out, src)


def test_nonlegacy_flags_off_leave_l1_l3_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty pilot flags must not change hemostasis pixels for the same seed."""
    for key in (
        "ALIGN_BAYER_ROUNDTRIP",
        "ALIGN_BAYER_STRENGTH",
        "ALIGN_PG_NOISE",
        "ALIGN_PG_SCALE",
        "ALIGN_PG_FLAT_THR",
    ):
        monkeypatch.setattr(settings, key, "")
        monkeypatch.setenv(key, "")
    assert _flag_setting_on("ALIGN_BAYER_ROUNDTRIP") is False
    assert _flag_setting_on("ALIGN_PG_NOISE") is False
    rng_src = np.random.default_rng(21)
    baseline = rng_src.integers(40, 220, size=(48, 40, 3), dtype=np.uint8).astype(np.float32)
    a = _l1_l3(baseline, seed=77, iso="400", aperture="f/1.8", focal_length="26mm")
    b = _l1_l3(baseline, seed=77, iso="400", aperture="f/1.8", focal_length="26mm")
    assert np.allclose(a, b)


def test_bayer_roundtrip_on_changes_pixels(monkeypatch: pytest.MonkeyPatch) -> None:
    rng_src = np.random.default_rng(22)
    baseline = rng_src.integers(40, 220, size=(48, 40, 3), dtype=np.uint8).astype(np.float32)
    monkeypatch.setattr(settings, "ALIGN_BAYER_ROUNDTRIP", "")
    monkeypatch.setattr(settings, "ALIGN_BAYER_STRENGTH", "")
    monkeypatch.setattr(settings, "ALIGN_PG_NOISE", "")
    base = _l1_l3(baseline, seed=88, iso="400", aperture="f/1.8", focal_length="26mm", layer0=False)
    monkeypatch.setattr(settings, "ALIGN_BAYER_ROUNDTRIP", "1")
    monkeypatch.setattr(settings, "ALIGN_BAYER_STRENGTH", "1.0")
    on = _l1_l3(baseline, seed=88, iso="400", aperture="f/1.8", focal_length="26mm", layer0=False)
    assert on.shape == base.shape
    assert not np.allclose(on, base)


def test_pg_noise_on_changes_flat_region(monkeypatch: pytest.MonkeyPatch) -> None:
    # Smooth plate → high flat-mask coverage so PG path is exercised.
    baseline = np.full((40, 36, 3), 120.0, dtype=np.float32)
    monkeypatch.setattr(settings, "ALIGN_BAYER_ROUNDTRIP", "")
    monkeypatch.setattr(settings, "ALIGN_PG_NOISE", "")
    monkeypatch.setattr(settings, "ALIGN_PG_SCALE", "")
    base = _l1_l3(baseline, seed=91, iso="400", aperture="f/1.8", focal_length="26mm", layer0=False)
    monkeypatch.setattr(settings, "ALIGN_PG_NOISE", "1")
    monkeypatch.setattr(settings, "ALIGN_PG_SCALE", "1.0")
    monkeypatch.setattr(settings, "ALIGN_PG_FLAT_THR", "9999")
    on = _l1_l3(baseline, seed=91, iso="400", aperture="f/1.8", focal_length="26mm", layer0=False)
    assert on.shape == base.shape
    assert not np.allclose(on, base)
