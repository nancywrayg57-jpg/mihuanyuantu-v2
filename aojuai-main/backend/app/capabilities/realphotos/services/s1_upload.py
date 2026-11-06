"""FR-003 / FR-004 upload inspection. Invalid files must not become assets."""

from __future__ import annotations

import hashlib
import io

from PIL import Image, UnidentifiedImageError

from app.capabilities.realphotos.constants import MAX_PIXELS, MAX_UPLOAD_BYTES
from app.core.exceptions import BusinessError

# 管理员 2026-11-06 确认：宽等于高时按横图下限（宽>=1024 且高>=768）检查。
_SQUARE_USES_LANDSCAPE_FLOOR = True


def inspect_upload(data: bytes) -> dict:
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    if not isinstance(data, (bytes, bytearray)) or len(data) == 0:
        raise BusinessError(message="空文件", code="INPUT_INVALID")
    raw = bytes(data)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise BusinessError(message="超过 20 MiB", code="UPLOAD_TOO_LARGE")
    kind = _magic(raw)
    if kind is None:
        raise BusinessError(message="仅支持 JPG、JPEG、PNG", code="UPLOAD_TYPE_REJECTED")
    try:
        with Image.open(io.BytesIO(raw)) as image:
            image.verify()
        with Image.open(io.BytesIO(raw)) as image:
            width, height = image.size
            image.load()
    except Image.DecompressionBombError as exc:
        raise BusinessError(message="超过 40MP", code="UPLOAD_PIXELS_REJECTED") from exc
    except (UnidentifiedImageError, OSError) as exc:
        raise BusinessError(message="图片无法解码", code="UPLOAD_DECODE_REJECTED") from exc
    if width <= 0 or height <= 0 or width * height > MAX_PIXELS:
        raise BusinessError(message="超过 40MP 或尺寸非法", code="UPLOAD_PIXELS_REJECTED")
    _require_orientation(width, height)
    return {
        "content_type": "image/jpeg" if kind == "jpeg" else "image/png",
        "byte_size": len(raw),
        "width": int(width),
        "height": int(height),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "extension": "jpg" if kind == "jpeg" else "png",
    }


def _magic(raw: bytes) -> str | None:
    if raw.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    return None


def _require_orientation(width: int, height: int) -> None:
    if width > height or (width == height and _SQUARE_USES_LANDSCAPE_FLOOR):
        if width < 1024 or height < 768:
            raise BusinessError(message="横图至少 1024×768", code="UPLOAD_RESOLUTION_REJECTED")
        return
    if height > width:
        if height < 1024 or width < 768:
            raise BusinessError(message="竖图至少 768×1024", code="UPLOAD_RESOLUTION_REJECTED")
        return
    raise BusinessError(message="分辨率不符合方向规则", code="UPLOAD_RESOLUTION_REJECTED")
