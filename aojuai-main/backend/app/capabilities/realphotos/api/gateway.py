"""Controlled access gateway for LocalDisk objects (S0)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUser, DBSession, PermissionChecker, TenantCtx
from app.capabilities.realphotos.adapters.storage import get_storage_adapter
from app.capabilities.realphotos.constants import SEED_OBJECT_KEY
from app.capabilities.realphotos.permissions import GATEWAY_READ
from app.core.exceptions import NotFoundError
from app.core.response import SuccessResponse

router = APIRouter(prefix="/gateway")


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
    _: None = Depends(PermissionChecker([GATEWAY_READ])),
) -> StreamingResponse:
    """鉴权后流式读取；跨租户对象在 S0 以种子键为公共开发证据，业务键须同租户前缀。"""
    key = object_key.strip().lstrip("/")
    # S0：种子文件允许已登录且有 gateway 权限的账号读取（grill Q6）
    if key != SEED_OBJECT_KEY:
        expected_prefix = f"tenant/{int(tenant_ctx.tenant_id)}/"
        if not key.startswith(expected_prefix):
            raise NotFoundError(message="对象不存在")
        from app.capabilities.realphotos.services.s1_processing import RealphotosS1Service

        content_type, payload = await RealphotosS1Service(db).read_object_for_gateway(
            tenant_id=int(tenant_ctx.tenant_id),
            object_key=key,
            owner_account_id=int(current_user.id) if "/output/" in key else None,
        )

        def _once():
            yield payload

        return StreamingResponse(
            _once(),
            media_type=content_type,
            headers={
                "Cache-Control": "private, no-store",
                "X-Realphotos-Object-Key": key,
                "X-Realphotos-Tenant-Id": str(int(tenant_ctx.tenant_id)),
            },
        )

    adapter = get_storage_adapter()
    if not adapter.exists(key):
        raise NotFoundError(message="对象不存在")

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
        headers={
            "Cache-Control": "private, no-store",
            "X-Realphotos-Object-Key": key,
            "X-Realphotos-Tenant-Id": str(int(tenant_ctx.tenant_id)),
        },
    )
