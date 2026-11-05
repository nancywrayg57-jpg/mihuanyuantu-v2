"""Integer wallet read APIs (S0)."""

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.api.deps import DBSession, PermissionChecker, TenantCtx
from app.capabilities.realphotos.permissions import WALLET_READ
from app.capabilities.realphotos.services.credit_service import RealphotosCreditService
from app.core.response import SuccessResponse
from app.core.schemas import PageResponse

router = APIRouter(prefix="/wallet")


@router.get("")
async def get_wallet(
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([WALLET_READ])),
) -> dict[str, Any]:
    data = await RealphotosCreditService(db).get_wallet(tenant_id=int(tenant_ctx.tenant_id))
    return SuccessResponse(data=data)


@router.get("/ledger")
async def get_ledger(
    tenant_ctx: TenantCtx,
    db: DBSession,
    page: int = Query(default=1, ge=1, alias="currentPage"),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize"),
    _: None = Depends(PermissionChecker([WALLET_READ])),
) -> dict[str, Any]:
    rows, total = await RealphotosCreditService(db).list_ledger(
        tenant_id=int(tenant_ctx.tenant_id),
        page=page,
        page_size=page_size,
    )
    items = [
        {
            "id": str(int(row.id)),
            "eventKey": row.event_key,
            "entryType": row.entry_type,
            "deltaAvailable": str(int(row.delta_available)),
            "deltaReserved": str(int(row.delta_reserved)),
            "beforeAvailable": str(int(row.before_available)),
            "afterAvailable": str(int(row.after_available)),
            "operatorUserId": str(row.operator_user_id) if row.operator_user_id else None,
            "reason": row.reason,
            "createdAt": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]
    return SuccessResponse(
        data=PageResponse(
            list=items,
            total=total,
            pageSize=page_size,
            currentPage=page,
        )
    )


@router.post("/decimal-bridge")
async def reject_decimal_bridge(
    _: None = Depends(PermissionChecker([WALLET_READ])),
) -> dict[str, Any]:
    """显式拒绝旧 Decimal 入口对 realphotos 的桥接（exit_evidence）。"""
    RealphotosCreditService.reject_decimal_bridge()
    return SuccessResponse(data={})  # pragma: no cover
