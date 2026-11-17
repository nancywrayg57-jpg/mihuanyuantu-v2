"""Integer wallet read APIs (S0)."""

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.api.deps import DBSession, PermissionChecker, TenantCtx
from app.capabilities.realphotos.permissions import WALLET_READ
from app.capabilities.realphotos.services.credit_service import RealphotosCreditService
from app.core.response import SuccessResponse
from app.core.schemas import PageResponse
from app.domain.roles.models import Role
from app.domain.users.models import User, UserRole

router = APIRouter(prefix="/wallet")

# 2026-11-17: 流水「操作账号」列展示账号+角色，而不是数字编号。
_ROLE_LABELS = {
    "rp_merchant": "商家",
    "rp_order_support": "订单客服",
    "rp_tech_support": "技术客服",
    "rp_admin": "平台管理员",
    "admin": "管理员",
    "tenant_admin": "租户管理员",
    "user": "普通用户",
}


async def _operator_displays(db: DBSession, user_ids: set[int]) -> dict[int, str]:
    if not user_ids:
        return {}
    users = {
        int(user.id): user
        for user in (await db.execute(select(User).where(User.id.in_(user_ids)))).scalars().all()
    }
    role_rows = (
        await db.execute(
            select(UserRole.user_id, Role.code)
            .join(Role, Role.id == UserRole.role_id)
            .where(UserRole.user_id.in_(user_ids))
        )
    ).all()
    roles: dict[int, list[str]] = {}
    for user_id, code in role_rows:
        roles.setdefault(int(user_id), []).append(str(code))
    displays: dict[int, str] = {}
    for user_id in user_ids:
        user = users.get(int(user_id))
        if user is None:
            displays[int(user_id)] = f"已删除用户 #{int(user_id)}"
            continue
        labels = [_ROLE_LABELS.get(code, code) for code in roles.get(int(user_id), [])]
        suffix = f"（{'/'.join(labels)}）" if labels else ""
        displays[int(user_id)] = f"{user.username}{suffix}"
    return displays


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
    operator_ids = {int(row.operator_user_id) for row in rows if row.operator_user_id}
    displays = await _operator_displays(db, operator_ids)
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
            "operatorDisplay": displays.get(int(row.operator_user_id)) if row.operator_user_id else None,
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
