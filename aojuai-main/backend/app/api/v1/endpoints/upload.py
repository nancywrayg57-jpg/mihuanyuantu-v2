"""
AOJU Backend - File Upload Endpoints
"""
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, UploadFile, File, Form

from app.api.deps import CurrentUser
from app.core.config import settings
from app.core.exceptions import BusinessError
from app.core.response import SuccessResponse

router = APIRouter()

# 图片上传默认支持格式
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
# 头像额外支持 SVG（用于品牌化默认头像和矢量头像）
ALLOWED_AVATAR_IMAGE_TYPES = ALLOWED_IMAGE_TYPES | {"image/svg+xml"}


def generate_filename(original_filename: str) -> str:
    """Generate unique filename"""
    ext = Path(original_filename).suffix.lower()
    date_path = datetime.now().strftime("%Y%m%d")
    unique_name = f"{int(datetime.now().timestamp())}{uuid.uuid4().hex[:8]}{ext}"
    return f"{date_path}/{unique_name}"


@router.post("/image")
async def upload_image(
    current_user: CurrentUser,
    file: UploadFile = File(...),
    path: str = Form("avatar"),
) -> dict[str, Any]:
    """
    Upload image file to local storage.
    """
    normalized_path = (path or "").strip().lower()
    allowed_types = ALLOWED_AVATAR_IMAGE_TYPES if normalized_path.startswith("avatar") else ALLOWED_IMAGE_TYPES

    if file.content_type not in allowed_types:
        allowed_text = ", ".join(sorted(allowed_types))
        raise BusinessError(message=f"不支持的图片格式，仅支持 {allowed_text}")

    content = await file.read()
    size_mb = len(content) / 1024 / 1024
    if size_mb > settings.MAX_UPLOAD_SIZE_MB:
        raise BusinessError(message=f"文件过大，最大支持 {settings.MAX_UPLOAD_SIZE_MB}MB")

    relative_path = f"{path}/{generate_filename(file.filename)}"
    full_path = Path(settings.UPLOAD_DIR) / relative_path

    full_path.parent.mkdir(parents=True, exist_ok=True)
    with open(full_path, "wb") as f:
        f.write(content)

    url = f"{settings.STATIC_URL}/uploads/{relative_path}"
    return SuccessResponse(
        data={"url": url},
        message="上传成功",
    )
