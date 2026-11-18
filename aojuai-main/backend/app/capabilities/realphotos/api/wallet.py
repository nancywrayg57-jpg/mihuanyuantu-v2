"""Integer wallet read APIs (S0)."""

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.api.deps import DBSession, PermissionChecker, TenantCtx
from app.capabilities.realphotos.models import RealphotosImageTask
from app.capabilities.realphotos.permissions import WALLET_READ
from app.capabilities.realphotos.services.credit_service import RealphotosCreditService
from app.capabilities.realphotos.services.task_numbering import (
    generation_task_no_map,
    processing_task_no_map,
)
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
    references = [dict(row.reference or {}) for row in rows]
    # 批次结算流水按 chainId 记账；用链内首个任务补出「关联任务」。
    chain_ids = {
        int(reference["chainId"])
        for reference in references
        if reference.get("chainId") is not None and reference.get("taskId") is None
    }
    chain_task_map: dict[int, int] = {}
    if chain_ids:
        chain_rows = (
            await db.execute(
                select(RealphotosImageTask.chain_id, RealphotosImageTask.id)
                .where(
                    RealphotosImageTask.tenant_id == int(tenant_ctx.tenant_id),
                    RealphotosImageTask.chain_id.in_(chain_ids),
                    RealphotosImageTask.deleted_at.is_(None),
                )
                .order_by(RealphotosImageTask.id.asc())
            )
        ).all()
        for chain_id, task_id in chain_rows:
            chain_task_map.setdefault(int(chain_id), int(task_id))

    resolved: list[tuple[dict, int | None]] = []
    processing_ids: list[int] = []
    generation_ids: list[int] = []
    for reference in references:
        task_id = reference.get("taskId")
        if task_id is None and reference.get("chainId") is not None:
            task_id = chain_task_map.get(int(reference["chainId"]))
        task_id_int = int(task_id) if task_id is not None else None
        resolved.append((reference, task_id_int))
        if task_id_int is None:
            continue
        if str(reference.get("source") or "") == "generation_store":
            generation_ids.append(task_id_int)
        else:
            processing_ids.append(task_id_int)
    processing_no_map = await processing_task_no_map(
        db, tenant_id=int(tenant_ctx.tenant_id), task_ids=processing_ids
    )
    generation_no_map = await generation_task_no_map(
        db, tenant_id=int(tenant_ctx.tenant_id), task_ids=generation_ids
    )
    items = []
    for row, (reference, task_id) in zip(rows, resolved, strict=True):
        task_kind = (
            "generation"
            if str(reference.get("source") or "") == "generation_store" and task_id is not None
            else "processing"
            if task_id is not None
            else None
        )
        task_no = None
        if task_id is not None:
            task_no = (
                generation_no_map.get(int(task_id))
                if task_kind == "generation"
                else processing_no_map.get(int(task_id))
            )
        items.append(
            {
                "id": str(int(row.id)),
                "eventKey": row.event_key,
                "entryType": row.entry_type,
                "deltaAvailable": str(int(row.delta_available)),
                "deltaReserved": str(int(row.delta_reserved)),
                "beforeAvailable": str(int(row.before_available)),
                "afterAvailable": str(int(row.after_available)),
                "beforeReserved": str(int(row.before_reserved)),
                "afterReserved": str(int(row.after_reserved)),
                "operatorUserId": str(row.operator_user_id) if row.operator_user_id else None,
                "operatorDisplay": displays.get(int(row.operator_user_id)) if row.operator_user_id else None,
                "reason": row.reason,
                "taskId": str(int(task_id)) if task_id is not None else None,
                "taskNo": task_no,
                "taskKind": task_kind,
                "batchId": str(reference.get("batchId")) if reference.get("batchId") is not None else None,
                "chainId": str(reference.get("chainId")) if reference.get("chainId") is not None else None,
                "referenceSource": reference.get("source"),
                "createdAt": row.created_at.isoformat() if row.created_at else None,
            }
        )
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
