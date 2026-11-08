"""R2: preset EXIF completeness gate (no silent defaults)."""

from __future__ import annotations

import pytest

from app.capabilities.realphotos.services.five_layer import (
    assert_preset_exif_ready,
    missing_exif_fields,
)
from app.core.exceptions import BusinessError


def test_missing_exif_fields_lists_chinese_labels() -> None:
    missing = missing_exif_fields({"brand": "A", "model": "", "iso": "", "shutter": "1/100"})
    assert "型号" in missing
    assert "ISO" in missing
    assert "光圈" in missing
    assert "焦距" in missing
    assert "品牌" not in missing


def test_assert_preset_exif_ready_raises_incomplete() -> None:
    with pytest.raises(BusinessError) as exc:
        assert_preset_exif_ready({"brand": "A", "model": "B"})
    assert exc.value.code == "PRESET_EXIF_INCOMPLETE"
    assert "ISO" in exc.value.message
    assert "快门" in exc.value.message


def test_assert_preset_exif_ready_ok() -> None:
    assert_preset_exif_ready(
        {
            "brand": "A",
            "model": "B",
            "iso": "100",
            "shutter": "1/120",
            "aperture": "f/1.8",
            "focalLength": "26mm",
        }
    )
