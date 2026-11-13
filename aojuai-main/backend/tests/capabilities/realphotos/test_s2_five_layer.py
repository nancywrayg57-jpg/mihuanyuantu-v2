"""S2 five-layer byte floor and EXIF read-back. Detection stays a fixture."""

from __future__ import annotations

import io
import json
import subprocess

import numpy as np
import pytest
from PIL import Image

from app.capabilities.realphotos.services.five_layer import (
    FIDELITY_MAD_MAX,
    PIPELINE_VERSION,
    l1_noise_sigma,
    mean_abs_delta,
    optional_exif_assignments,
    run_five_layer,
)
from app.capabilities.realphotos.services.s1_catalog import S1_ENABLED_PRESETS
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


def test_pipeline_version_is_s2_five_layer_2() -> None:
    assert PIPELINE_VERSION == "s2-five-layer-2"


def test_l1_sigma_iso_weak_and_capped() -> None:
    assert 1.05 <= l1_noise_sigma(100) <= 1.25
    assert l1_noise_sigma(100) > 0.8
    assert l1_noise_sigma(1600) <= 1.85
    assert l1_noise_sigma(51200) <= 1.85


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


def test_five_layer_fidelity_mad_within_fine_limit() -> None:
    """ND-020 proxy: MAD on smooth source stays under FIDELITY_MAD_MAX (logged in e2e)."""
    source = _source(quality=92, kind="gradient")
    preset = dict(S1_ENABLED_PRESETS[0])
    output = run_five_layer(source=source, preset=preset, seed=11).jpeg
    with Image.open(io.BytesIO(source)) as before, Image.open(io.BytesIO(output)) as after:
        mad = mean_abs_delta(np.asarray(before, dtype=np.float32), np.asarray(after, dtype=np.float32))
    assert mad <= FIDELITY_MAD_MAX


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
