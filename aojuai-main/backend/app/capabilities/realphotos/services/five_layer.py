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

PIPELINE_VERSION = "s2-five-layer-2"
ENCODE_PROFILE = "s2-ecommerce-1"
_QUALITIES = (90, 93, 96, 98, 100)
# ND-020 fidelity regression: mean abs RGB delta after decode vs source pixels.
# Logged in FIVE-LAYER-PHYS-TUNE e2e; do not raise silently without ticket.
FIDELITY_MAD_MAX = 3.5
# L2 high-frequency relative amplitude sigma (was 0.02 on s2-five-layer-1).
_L2_SIGMA = 0.028
_L2_RADIUS = 0.35


@dataclass(frozen=True)
class FiveLayerOutput:
    jpeg: bytes
    fields: list[dict]
    width: int
    height: int


def _byte_floor(source: bytes) -> int:
    """S2 T-012 floor: output JPEG bytes >= source_bytes.

    For JPEG uploads, source_bytes is the file length. For non-JPEG sources
    (e.g. generation PNG), comparing to PNG length is not satisfiable by any
    JPEG encode of the same pixels; use quality-100 JPEG of the decoded RGB
    as the comparable floor. Never pad the file to fake compliance.
    """
    if source.startswith(b"\xff\xd8\xff"):
        return len(source)
    with Image.open(io.BytesIO(source)) as image:
        rgb = image.convert("RGB")
    return len(_encode(rgb, quality=100))


def l1_noise_sigma(iso: object) -> float:
    """ISO-linked CMOS-like L1 sigma for s2-five-layer-2 (ND-020 damped).

    Qualitative reference only from legacy ``isoToNoiseSigma ≈ 0.5*sqrt(ISO/100)``.
    This curve is weaker and capped so ISO100 is modestly above v1's fixed 0.8
    without importing vignette / chromatic aberration / saturation paths.
    """
    raw = str(iso or "100").strip().split()[0]
    try:
        value = float(raw)
    except ValueError:
        value = 100.0
    value = max(50.0, min(value, 6400.0))
    # ISO100 → ~1.10; ISO400 → ~1.50; ISO1600 → ~2.30 → capped 1.85
    sigma = 0.40 * math.sqrt(value / 100.0) + 0.70
    return float(min(1.85, max(1.05, sigma)))


def mean_abs_delta(before: np.ndarray, after: np.ndarray) -> float:
    """Mean absolute per-channel delta; used by fidelity regression tests."""
    a = np.asarray(before, dtype=np.float32)
    b = np.asarray(after, dtype=np.float32)
    if a.shape != b.shape:
        raise ValueError("shape mismatch")
    return float(np.mean(np.abs(a - b)))


def run_five_layer(*, source: bytes, preset: dict, seed: int) -> FiveLayerOutput:
    """Run L1–L5 and return the final JPEG plus the EXIF field ledger."""
    baseline = _decode_baseline(source)
    height, width = int(baseline.shape[0]), int(baseline.shape[1])
    pixels = _l1_l3(baseline, seed=int(seed), iso=preset.get("iso"))
    if pixels.shape[0] != height or pixels.shape[1] != width:
        raise BusinessError(message="五层改变了宽高", code="OUTPUT_CONSTRAINT_UNSATISFIED")
    image = Image.fromarray(pixels.astype(np.uint8), mode="RGB")
    floor = _byte_floor(source)
    # L4 is written onto an intermediate JPEG. That size is not the byte floor.
    intermediate = _encode(image, quality=90)
    _write_and_read(intermediate, preset, seed=int(seed))
    last_fields: list[dict] = []
    for quality in _QUALITIES:
        # L5 re-encodes pixels and drops metadata. Restore the approved snapshot after it.
        encoded = _encode(image, quality=int(quality))
        final, last_fields = _write_and_read(encoded, preset, seed=int(seed))
        if len(final) >= floor and _same_size(final, width=width, height=height):
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


def _l1_l3(baseline: np.ndarray, *, seed: int, iso: object = "100") -> np.ndarray:
    rng = np.random.default_rng(int(seed))
    arr = np.array(baseline, copy=True)
    # L1 细微像素噪声（ISO 弱相关）。不旋转、不裁切、不缩放；无暗角/色差。
    sigma = l1_noise_sigma(iso)
    arr += rng.normal(0.0, sigma, size=arr.shape)
    # L2 高频幅度的小幅扰动（s2-five-layer-2 略强于 0.02，仍须肉眼不可见）。
    for channel in range(3):
        freq = np.fft.rfft2(arr[:, :, channel])
        height, width = freq.shape
        yy, xx = np.ogrid[:height, :width]
        radius = np.sqrt((yy / max(height, 1)) ** 2 + (xx / max(width, 1)) ** 2)
        mask = radius > _L2_RADIUS
        delta = rng.normal(0.0, _L2_SIGMA, size=freq.shape)
        freq = freq * (1.0 + mask * delta)
        arr[:, :, channel] = np.fft.irfft2(freq, s=arr.shape[:2])
    # L3 稀疏一档像素扰动，宽高保持基线；禁止借 L3 做大面积改图。
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


_EXIF_REQUIRED: tuple[tuple[str, str], ...] = (
    ("brand", "品牌"),
    ("model", "型号"),
    ("iso", "ISO"),
    ("shutter", "快门"),
    ("aperture", "光圈"),
    ("focalLength", "焦距"),
)


def missing_exif_fields(preset: dict) -> list[str]:
    """Return Chinese labels of missing brand/model/exposure fields (R2)."""
    missing: list[str] = []
    for key, label in _EXIF_REQUIRED:
        if not str(preset.get(key) or "").strip():
            missing.append(label)
    return missing


def assert_preset_exif_ready(preset: dict) -> None:
    """Reject submit/save-enable when EXIF required fields are incomplete (R2).

    Does not invent default exposure values.
    """
    missing = missing_exif_fields(preset)
    if missing:
        raise BusinessError(
            message=f"预设缺少必填字段：{'、'.join(missing)}",
            code="PRESET_EXIF_INCOMPLETE",
        )


def _write_and_read(jpeg: bytes, preset: dict, *, seed: int = 0) -> tuple[bytes, list[dict]]:
    from app.capabilities.realphotos.services.gps_write import resolve_gps

    brand = str(preset.get("brand") or "")
    model = str(preset.get("model") or "")
    if not brand or not model:
        raise BusinessError(message="预设缺少品牌或型号", code="EXIF_WRITE_FAILED")
    gps_plan = resolve_gps(preset=preset, seed=int(seed))
    if gps_plan.get("action") == "fail":
        raise BusinessError(message=str(gps_plan.get("reason") or "GPS 写入失败"), code="EXIF_WRITE_FAILED")
    iso = str(preset.get("iso") or "")
    shutter = str(preset.get("shutter") or "")
    aperture = str(preset.get("aperture") or "")
    focal = str(preset.get("focalLength") or "")
    if not iso or not shutter or not aperture or not focal:
        raise BusinessError(message="预设缺少曝光字段", code="EXIF_WRITE_FAILED")
    tv = apex_shutter_value(shutter_seconds(shutter))
    f_number = _f_number(aperture)
    av = apex_aperture_value(f_number)
    requested = {
        "Make": brand,
        "Model": model,
        "ISO": iso,
        "ExposureTime": shutter,
        "FNumber": f"{f_number:.1f}",
        "FocalLength": focal,
        "ColorSpace": "sRGB",
        "ShutterSpeedValue": f"{tv:.6f}",
        "ApertureValue": f"{av:.6f}",
    }
    maker_note = str(preset.get("makerNote") or "").strip()
    # exiftool 13.x rejects ExifIFD:ApertureValue when APEX < 1 (e.g. f/1.4 → ~0.97)
    # with "Must be a positive number"; FNumber remains the writable source of truth.
    write_aperture_value = av >= 1.0 - 1e-9
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
            f"-FNumber={f_number}",
            f"-FocalLength={requested['FocalLength']}",
            "-ColorSpace=sRGB",
            f"-ShutterSpeedValue={tv:.6f}",
            "-GPS:all=",
            "-MakerNote=",
        ]
        if write_aperture_value:
            command.append(f"-ApertureValue={av:.6f}")
        if maker_note:
            # PRODUCT-GAP A7：管理员 2026-11-07 授权写入；必须可回读，失败不静默。
            command.append(f"-MakerNote={maker_note}")
        if gps_plan.get("action") == "write":
            lat = float(gps_plan["latitude"])
            lon = float(gps_plan["longitude"])
            alt = float(gps_plan["altitude"])
            lat_ref = "N" if lat >= 0 else "S"
            lon_ref = "E" if lon >= 0 else "W"
            command.extend(
                [
                    f"-GPSLatitude={abs(lat)}",
                    f"-GPSLatitudeRef={lat_ref}",
                    f"-GPSLongitude={abs(lon)}",
                    f"-GPSLongitudeRef={lon_ref}",
                    f"-GPSAltitude={abs(alt)}",
                    f"-GPSAltitudeRef={'0' if alt >= 0 else '1'}",
                ]
            )
        command.append(str(path))
        try:
            written = subprocess.run(command, check=False, capture_output=True)
        except FileNotFoundError as exc:
            raise BusinessError(message="exiftool 不可用", code="EXIF_WRITE_FAILED") from exc
        if written.returncode != 0:
            detail = (written.stderr or written.stdout or b"").decode(errors="replace").strip()
            raise BusinessError(
                message=("EXIF 写入失败" + (f"：{detail[:200]}" if detail else "")),
                code="EXIF_WRITE_FAILED",
            )
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
                "-GPSLatitude#",
                "-GPSLongitude#",
                "-GPSAltitude#",
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
    fields = []
    for tag in requested:
        if tag == "ApertureValue":
            fields.append(
                _verified_aperture_value(
                    requested_av=requested["ApertureValue"],
                    requested_fnumber=requested["FNumber"],
                    row=row,
                    wrote_tag=write_aperture_value,
                )
            )
        else:
            fields.append(_verified(tag, requested[tag], row.get(tag)))
    fields.append(_gps_field(gps_plan, row))
    maker_read = str(row.get("MakerNote") or "")
    if maker_note:
        maker_ok = maker_note in maker_read or maker_read.strip() == maker_note
        fields.append(
            {
                "tag": "MakerNote",
                "requested": maker_note,
                "written": maker_note,
                "read_back": maker_read,
                "verification_status": "verified" if maker_ok else "failed",
                "reason": "" if maker_ok else "MakerNote 回读与请求不一致",
            }
        )
    else:
        fields.append(
            {
                "tag": "MakerNote",
                "requested": "",
                "written": "",
                "read_back": maker_read,
                "verification_status": "skipped" if not maker_read else "failed",
                "reason": "" if not maker_read else "未授权预设却出现 MakerNote",
            }
        )
    for field in fields:
        if field["tag"] == "GPSLatitude" and field.get("verification_status") == "failed":
            raise BusinessError(message="GPS 回读与请求不一致", code="EXIF_WRITE_FAILED")
        if field["tag"] == "GPSLatitude" and gps_plan.get("action") == "skip" and field["read_back"]:
            raise BusinessError(message="gpsMode 不应写入 GPS", code="EXIF_WRITE_FAILED")
        if field["tag"] == "MakerNote" and field.get("verification_status") == "failed":
            raise BusinessError(
                message=str(field.get("reason") or "MakerNote 写入或回读失败"),
                code="MAKERNOTE_WRITE_FAILED",
            )
        if field["verification_status"] == "failed" and field["tag"] not in {"GPSLatitude", "MakerNote"}:
            raise BusinessError(message=f"{field['tag']} 回读与预设不一致", code="EXIF_WRITE_FAILED")
    if not final.startswith(b"\xff\xd8\xff"):
        raise BusinessError(message="最终文件不是 JPEG", code="OUTPUT_CONSTRAINT_UNSATISFIED")
    return final, fields


def _gps_field(plan: dict, row: dict) -> dict:
    read_lat = row.get("GPSLatitude")
    read_lon = row.get("GPSLongitude")
    read_alt = row.get("GPSAltitude")
    read_back = ""
    if read_lat not in (None, "") or read_lon not in (None, ""):
        read_back = f"{read_lat},{read_lon},{read_alt}"
    if plan.get("action") == "skip":
        return {
            "tag": "GPSLatitude",
            "requested": "",
            "written": "",
            "read_back": read_back,
            "verification_status": "skipped",
            "reason": str(plan.get("reason") or "未写入 GPS"),
            "gpsMode": plan.get("mode"),
        }
    requested = f"{float(plan['latitude']):.6f},{float(plan['longitude']):.6f},{float(plan['altitude']):.2f}"
    ok = False
    try:
        ok = (
            abs(float(read_lat) - float(plan["latitude"])) < 0.0005
            and abs(float(read_lon) - float(plan["longitude"])) < 0.0005
        )
    except (TypeError, ValueError):
        ok = False
    return {
        "tag": "GPSLatitude",
        "requested": requested,
        "written": requested,
        "read_back": read_back,
        "verification_status": "verified" if ok else "failed",
        "reason": "" if ok else "GPS 回读与请求不一致",
        "gpsMode": plan.get("mode"),
        "actualGps": {
            "latitude": float(plan["latitude"]),
            "longitude": float(plan["longitude"]),
            "altitude": float(plan["altitude"]),
        },
    }


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


def _verified_aperture_value(
    *,
    requested_av: str,
    requested_fnumber: str,
    row: dict,
    wrote_tag: bool,
) -> dict:
    """Verify ApertureValue; fall back to FNumber-derived APEX when tag cannot be stored.

    Some exiftool builds refuse APEX ApertureValue < 1 (large apertures like f/1.4).
    FNumber is always written; deriving AV from a verified FNumber keeps honesty without
    inventing exposure values.
    """
    actual = row.get("ApertureValue")
    if actual is not None and str(actual).strip() != "":
        ok = _close(str(actual), requested_av)
        return {
            "tag": "ApertureValue",
            "requested": requested_av,
            "written": requested_av if wrote_tag else "",
            "read_back": str(actual),
            "verification_status": "verified" if ok else "failed",
            "reason": "" if ok else "回读与请求不一致",
        }
    fn_raw = row.get("FNumber")
    if fn_raw is None or not _close(str(fn_raw), requested_fnumber):
        return {
            "tag": "ApertureValue",
            "requested": requested_av,
            "written": requested_av if wrote_tag else "",
            "read_back": "",
            "verification_status": "failed",
            "reason": "ApertureValue 缺失且 FNumber 回读不可用",
        }
    derived = apex_aperture_value(float(fn_raw))
    ok = _close(f"{derived:.6f}", requested_av)
    return {
        "tag": "ApertureValue",
        "requested": requested_av,
        "written": "derived_from_FNumber",
        "read_back": f"derived:{derived:.6f}",
        "verification_status": "verified" if ok else "failed",
        "reason": (
            ""
            if ok
            else "ApertureValue 无法写入时由 FNumber 推导仍不一致"
        ),
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
