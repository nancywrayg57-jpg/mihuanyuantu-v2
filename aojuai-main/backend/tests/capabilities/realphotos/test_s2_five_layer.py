"""S2 five-layer byte floor and EXIF read-back. Detection stays a fixture."""

from __future__ import annotations

import io
import json
import subprocess

import numpy as np
import pytest
from PIL import Image

from app.capabilities.realphotos.services.five_layer import run_five_layer
from app.capabilities.realphotos.services.s1_catalog import S1_ENABLED_PRESETS
from app.core.exceptions import BusinessError


def _source(*, quality: int, width: int = 320, height: int = 240) -> bytes:
    rng = np.random.default_rng(7)
    pixels = rng.integers(0, 255, size=(height, width, 3), dtype=np.uint8)
    buf = io.BytesIO()
    Image.fromarray(pixels, mode="RGB").save(buf, format="JPEG", quality=quality, subsampling=0)
    return buf.getvalue()


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
    assert row["Make"] == "Honeybadger"
    assert row["Model"] == "HB-Phone-1"
    assert "GPSLatitude" not in row
    assert "MakerNote" not in row


def test_byte_floor_fails_without_padding() -> None:
    source = _source(quality=100, width=64, height=48) + (b"\x00" * 400_000)
    with pytest.raises(BusinessError) as exc:
        run_five_layer(source=source, preset=dict(S1_ENABLED_PRESETS[0]), seed=3)
    assert exc.value.code == "OUTPUT_CONSTRAINT_UNSATISFIED"
