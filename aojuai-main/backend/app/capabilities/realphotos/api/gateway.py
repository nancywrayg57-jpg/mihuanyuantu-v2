"""Controlled access gateway for LocalDisk objects (S0)."""

from __future__ import annotations

import hashlib
import io
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response, StreamingResponse
from PIL import Image

from app.api.deps import CurrentUser, DBSession, PermissionChecker, TenantCtx
from app.capabilities.realphotos.adapters.storage import get_storage_adapter
from app.capabilities.realphotos.constants import SEED_OBJECT_KEY
from app.capabilities.realphotos.permissions import GATEWAY_READ
from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.core.response import SuccessResponse

router = APIRouter(prefix="/gateway")

# 2026-11-17：缩略图缓存目录（位于 LocalDisk 根下的隐藏目录，不对外暴露）。
_THUMB_DIR_NAME = ".thumbs"
_THUMB_MAX_AGE = 86400


def _thumb_cache_path(key: str, width: int) -> Path:
    root = str(getattr(settings, "REALPHOTOS_STORAGE_ROOT", "") or "").strip()
    base = Path(root) if root else Path("/tmp/realphotos-storage")
    digest = hashlib.sha1(f"{key}:{width}".encode()).hexdigest()
    return base / _THUMB_DIR_NAME / f"{digest}.jpg"


def _resize_jpeg(payload: bytes, width: int) -> bytes | None:
    try:
        with Image.open(io.BytesIO(payload)) as image:
            rgb = image.convert("RGB")
            rgb.thumbnail((width, width), Image.LANCZOS)
            out = io.BytesIO()
            rgb.save(out, format="JPEG", quality=75, optimize=True)
            return out.getvalue()
    except Exception:
        return None


def _thumbnail(key: str, payload: bytes, width: int) -> bytes | None:
    """读缓存；缺失则缩放并写回。失败时返回 None，由调用方回退原图。"""
    path = _thumb_cache_path(key, width)
    try:
        if path.is_file():
            return path.read_bytes()
    except OSError:
        pass
    data = _resize_jpeg(payload, width)
    if data is None:
        return None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    except OSError:
        pass
    return data


def _read_all(handle: Any) -> bytes:
    try:
        return handle.read()
    finally:
        handle.close()


@router.post("/seed")
async def ensure_seed(
    tenant_ctx: TenantCtx,
    current_user: CurrentUser,
    _: None = Depends(PermissionChecker([GATEWAY_READ])),
) -> dict[str, Any]:
    """确保开发种子文件存在；响应不含裸磁盘路径。"""
    stored = get_storage_adapter().ensure_seed_file()
    return SuccessResponse(
        data={
            "objectKey": stored.object_key,
            "size": stored.size,
            "contentType": stored.content_type,
            "tenantId": str(int(tenant_ctx.tenant_id)),
            "requestedBy": str(int(current_user.id)),
        }
    )


@router.get("/objects/{object_key:path}")
async def read_object(
    object_key: str,
    tenant_ctx: TenantCtx,
    current_user: CurrentUser,
    db: DBSession,
    thumb: int | None = Query(default=None, ge=32, le=512),
    _: None = Depends(PermissionChecker([GATEWAY_READ])),
) -> Response:
    """鉴权后读取；`?thumb=<px>` 返回缩放缓存图，否则流式返回原对象。"""
    key = object_key.strip().lstrip("/")
    tenant_id = int(tenant_ctx.tenant_id)
    base_headers = {
        "X-Realphotos-Object-Key": key,
        "X-Realphotos-Tenant-Id": str(tenant_id),
    }

    def _thumb_response(payload: bytes) -> Response | None:
        if thumb is None:
            return None
        data = _thumbnail(key, payload, int(thumb))
        if data is None:
            return None
        return Response(
            content=data,
            media_type="image/jpeg",
            headers={
                **base_headers,
                "Cache-Control": f"private, max-age={_THUMB_MAX_AGE}",
            },
        )

    # S0：种子文件允许已登录且有 gateway 权限的账号读取（grill Q6）
    if key != SEED_OBJECT_KEY:
        expected_prefix = f"tenant/{tenant_id}/"
        if not key.startswith(expected_prefix):
            raise NotFoundError(message="对象不存在")
        from app.capabilities.realphotos.services.s1_processing import RealphotosS1Service

        content_type, payload = await RealphotosS1Service(db).read_object_for_gateway(
            tenant_id=tenant_id,
            object_key=key,
            owner_account_id=int(current_user.id) if "/output/" in key else None,
        )
        thumbed = _thumb_response(payload)
        if thumbed is not None:
            return thumbed

        def _once():
            yield payload

        return StreamingResponse(
            _once(),
            media_type=content_type,
            headers={**base_headers, "Cache-Control": "private, no-store"},
        )

    adapter = get_storage_adapter()
    if not adapter.exists(key):
        raise NotFoundError(message="对象不存在")

    if thumb is not None:
        payload = _read_all(adapter.open_read(key))
        thumbed = _thumb_response(payload)
        if thumbed is not None:
            return thumbed

    handle = adapter.open_read(key)

    def _iter():
        try:
            while True:
                chunk = handle.read(64 * 1024)
                if not chunk:
                    break
                yield chunk
        finally:
            handle.close()

    # 不把磁盘路径写入 header / body
    return StreamingResponse(
        _iter(),
        media_type="application/octet-stream",
        headers={**base_headers, "Cache-Control": "private, no-store"},
    )
