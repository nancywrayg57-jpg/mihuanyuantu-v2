"""S2 five-layer pipeline.

Order follows architecture §8.2: L1 → L2 → L3 → L4 EXIF → L5 encode.
If L5 strips the snapshot, the final package restores it and reads it back.
The byte floor is measured only after that last encode and write.
"""

from __future__ import annotations

import io
import json
import math
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from app.core.exceptions import BusinessError

PIPELINE_VERSION = "s2-five-layer-1"
ENCODE_PROFILE = "s2-ecommerce-1"
_QUALITIES = (90, 93, 96, 98, 100)


@dataclass(frozen=True)
class FiveLayerOutput:
    jpeg: bytes
    fields: list[dict]
    width: int
    height: int


def run_five_layer(*, source: bytes, preset: dict, seed: int) -> FiveLayerOutput:
    """Run L1–L5 and return the final JPEG plus the EXIF field ledger."""
    baseline = _decode_baseline(source)
    height, width = int(baseline.shape[0]), int(baseline.shape[1])
    pixels = _l1_l3(baseline, seed=int(seed))
    if pixels.shape[0] != height or pixels.shape[1] != width:
        raise BusinessError(message="五层改变了宽高", code="OUTPUT_CONSTRAINT_UNSATISFIED")
    image = Image.fromarray(pixels.astype(np.uint8), mode="RGB")
    # L4 is written onto an intermediate JPEG. That size is not the byte floor.
    intermediate = _encode(image, quality=90)
    _write_and_read(intermediate, preset)
    last_fields: list[dict] = []
    for quality in _QUALITIES:
        # L5 re-encodes pixels and drops metadata. Restore the approved snapshot after it.
        encoded = _encode(image, quality=int(quality))
        final, last_fields = _write_and_read(encoded, preset)
        if len(final) >= len(source) and _same_size(final, width=width, height=height):
            return FiveLayerOutput(jpeg=final, fields=last_fields, width=width, height=height)
    raise BusinessError(
        message="无法同时满足 JPEG 与字节下限",
        code="OUTPUT_CONSTRAINT_UNSATISFIED",
    )


def shutter_seconds(value: str) -> float:
    text = str(value).strip()
    if "/" in text:
        numerator, denominator = text.split("/", 1)
        return float(numerator) / float(denominator)
    return float(text)


def apex_shutter_value(seconds: float) -> float:
    """APEX TimeValue = -log2(exposure seconds)."""
    return -math.log2(float(seconds))


def apex_aperture_value(f_number: float) -> float:
    """APEX ApertureValue = 2 * log2(FNumber)."""
    return 2.0 * math.log2(float(f_number))


def _decode_baseline(source: bytes) -> np.ndarray:
    with Image.open(io.BytesIO(source)) as image:
        rgb = image.convert("RGB")
        return np.asarray(rgb, dtype=np.float32)


def _l1_l3(baseline: np.ndarray, *, seed: int) -> np.ndarray:
    rng = np.random.default_rng(int(seed))
    arr = np.array(baseline, copy=True)
    # L1 细微像素噪声。不旋转、不裁切、不缩放。
    arr += rng.normal(0.0, 0.8, size=arr.shape)
    # L2 高频幅度的小幅扰动。
    for channel in range(3):
        freq = np.fft.rfft2(arr[:, :, channel])
        height, width = freq.shape
        yy, xx = np.ogrid[:height, :width]
        radius = np.sqrt((yy / max(height, 1)) ** 2 + (xx / max(width, 1)) ** 2)
        mask = radius > 0.35
        delta = rng.normal(0.0, 0.02, size=freq.shape)
        freq = freq * (1.0 + mask * delta)
        arr[:, :, channel] = np.fft.irfft2(freq, s=arr.shape[:2])
    # L3 稀疏一档像素扰动，宽高保持基线。
    count = min(512, arr.shape[0] * arr.shape[1])
    ys = rng.integers(0, arr.shape[0], size=count)
    xs = rng.integers(0, arr.shape[1], size=count)
    arr[ys, xs, :] += rng.choice(np.array([-1.0, 1.0]), size=(count, 1))
    return np.clip(arr, 0, 255)


def _encode(image: Image.Image, *, quality: int) -> bytes:
    buf = io.BytesIO()
    image.save(
        buf,
        format="JPEG",
        quality=int(quality),
        subsampling=0,
        optimize=False,
    )
    return buf.getvalue()


def _same_size(jpeg: bytes, *, width: int, height: int) -> bool:
    with Image.open(io.BytesIO(jpeg)) as image:
        return image.size == (int(width), int(height)) and image.mode == "RGB"


def _f_number(aperture: str) -> float:
    return float(str(aperture).strip().removeprefix("f/").removeprefix("F/"))


def _write_and_read(jpeg: bytes, preset: dict) -> tuple[bytes, list[dict]]:
    brand = str(preset.get("brand") or "")
    model = str(preset.get("model") or "")
    if not brand or not model:
        raise BusinessError(message="预设缺少品牌或型号", code="EXIF_WRITE_FAILED")
    gps_mode = str(preset.get("gpsMode") or "none")
    if gps_mode in {"fixed", "random_by_scene"}:
        raise BusinessError(message="S2 预设未提供可写入的 GPS 坐标", code="EXIF_WRITE_FAILED")
    if gps_mode != "none":
        raise BusinessError(message="未知 gpsMode", code="EXIF_WRITE_FAILED")
    iso = str(preset.get("iso") or "")
    shutter = str(preset.get("shutter") or "")
    aperture = str(preset.get("aperture") or "")
    focal = str(preset.get("focalLength") or "")
    if not iso or not shutter or not aperture or not focal:
        raise BusinessError(message="预设缺少曝光字段", code="EXIF_WRITE_FAILED")
    tv = apex_shutter_value(shutter_seconds(shutter))
    av = apex_aperture_value(_f_number(aperture))
    requested = {
        "Make": brand,
        "Model": model,
        "ISO": iso,
        "ExposureTime": shutter,
        "FNumber": f"{_f_number(aperture):.1f}",
        "FocalLength": focal,
        "ColorSpace": "sRGB",
        "ShutterSpeedValue": f"{tv:.6f}",
        "ApertureValue": f"{av:.6f}",
    }
    with tempfile.TemporaryDirectory(prefix="rp-s2-") as folder:
        path = Path(folder) / "result.jpg"
        path.write_bytes(jpeg)
        command = [
            "exiftool",
            "-overwrite_original",
            f"-Make={requested['Make']}",
            f"-Model={requested['Model']}",
            f"-ISO={requested['ISO']}",
            f"-ExposureTime={requested['ExposureTime']}",
            f"-FNumber={_f_number(aperture)}",
            f"-FocalLength={requested['FocalLength']}",
            "-ColorSpace=sRGB",
            f"-ShutterSpeedValue={tv:.6f}",
            f"-ApertureValue={av:.6f}",
            "-GPS:all=",
            str(path),
        ]
        try:
            written = subprocess.run(command, check=False, capture_output=True)
        except FileNotFoundError as exc:
            raise BusinessError(message="exiftool 不可用", code="EXIF_WRITE_FAILED") from exc
        if written.returncode != 0:
            raise BusinessError(message="EXIF 写入失败", code="EXIF_WRITE_FAILED")
        read = subprocess.run(
            [
                "exiftool",
                "-json",
                "-Make",
                "-Model",
                "-ISO",
                "-ExposureTime",
                "-FNumber",
                "-FocalLength",
                "-ColorSpace",
                "-ShutterSpeedValue#",
                "-ApertureValue#",
                "-GPSLatitude",
                "-MakerNote",
                str(path),
            ],
            check=False,
            capture_output=True,
        )
        if read.returncode != 0:
            raise BusinessError(message="EXIF 回读失败", code="EXIF_WRITE_FAILED")
        payload = json.loads(read.stdout.decode() or "[]")
        row = payload[0] if payload else {}
        final = path.read_bytes()
    fields = [_verified(tag, requested[tag], row.get(tag)) for tag in requested]
    fields.append(
        {
            "tag": "GPSLatitude",
            "requested": "",
            "written": "",
            "read_back": str(row.get("GPSLatitude") or ""),
            "verification_status": "skipped",
            "reason": "gpsMode=none 不写入 GPS",
        }
    )
    fields.append(
        {
            "tag": "MakerNote",
            "requested": "",
            "written": "",
            "read_back": str(row.get("MakerNote") or ""),
            "verification_status": "disabled",
            "reason": "不伪造品牌 MakerNote",
        }
    )
    for field in fields:
        if field["tag"] == "GPSLatitude" and field["read_back"]:
            raise BusinessError(message="gpsMode=none 不应写入 GPS", code="EXIF_WRITE_FAILED")
        if field["tag"] == "MakerNote" and field["read_back"]:
            raise BusinessError(message="结果含未批准的 MakerNote", code="EXIF_WRITE_FAILED")
        if field["verification_status"] == "failed":
            raise BusinessError(message=f"{field['tag']} 回读与预设不一致", code="EXIF_WRITE_FAILED")
    if not final.startswith(b"\xff\xd8\xff"):
        raise BusinessError(message="最终文件不是 JPEG", code="OUTPUT_CONSTRAINT_UNSATISFIED")
    return final, fields


def _verified(tag: str, requested: str, read_back: object) -> dict:
    actual = "" if read_back is None else str(read_back)
    if tag in {"ShutterSpeedValue", "ApertureValue", "FNumber"}:
        ok = _close(actual, requested)
    elif tag == "FocalLength":
        ok = _focal_matches(actual, requested)
    elif tag == "ISO":
        ok = actual.split(".", 1)[0] == requested
    else:
        ok = actual == requested
    return {
        "tag": tag,
        "requested": requested,
        "written": requested,
        "read_back": actual,
        "verification_status": "verified" if ok else "failed",
        "reason": "" if ok else "回读与请求不一致",
    }


def _close(actual: str, requested: str) -> bool:
    try:
        return abs(float(actual) - float(requested)) < 0.02
    except ValueError:
        return False


def _focal_matches(actual: str, requested: str) -> bool:
    digits = "".join(ch if ch.isdigit() or ch == "." else " " for ch in actual).split()
    wanted = "".join(ch if ch.isdigit() or ch == "." else " " for ch in requested).split()
    if not digits or not wanted:
        return False
    return _close(digits[0], wanted[0])
