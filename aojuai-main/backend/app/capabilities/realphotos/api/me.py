"""Current session identity + workspace overview (PG-002)."""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DBSession, PermissionChecker, TenantCtx
from app.capabilities.realphotos.constants import RUNNING_TASK_STATUSES, TASK_DELIVERED
from app.capabilities.realphotos.models import (
    RealphotosAsset,
    RealphotosGenerationItem,
    RealphotosGenerationTask,
    RealphotosImageTask,
    RealphotosInboxMessage,
    RealphotosMerchantProfile,
    RealphotosRechargeOrder,
    RealphotosSupportTicket,
)
from app.capabilities.realphotos.permissions import (
    ADMIN_READ,
    ORDER_SUPPORT_READ,
    ROLE_ADMIN,
    ROLE_ORDER_SUPPORT,
    ROLE_TECH_SUPPORT,
    TECH_DESK_READ,
    WORKSPACE_READ,
)
from app.capabilities.realphotos.services.credit_service import RealphotosCreditService
from app.capabilities.realphotos.services.s6_ops import RealphotosOpsService
from app.capabilities.realphotos.services.task_numbering import (
    generation_task_no_map,
    processing_task_no_map,
)
from app.core.response import SuccessResponse
from app.domain.roles.models import Role
from app.domain.users.models import UserRole

router = APIRouter()


async def _role_codes(db: DBSession, user_id: int, tenant_id: int) -> set[str]:
    rows = (
        await db.execute(
            select(Role.code)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(
                UserRole.user_id == int(user_id),
                UserRole.tenant_id == int(tenant_id),
                Role.deleted_at.is_(None),
            )
        )
    ).all()
    codes = {str(code) for (code,) in rows}
    if "admin" in codes:
        codes.add(ROLE_ADMIN)
    return codes


def _view_kind(roles: set[str]) -> str:
    if ROLE_ADMIN in roles or "admin" in roles:
        return "admin"
    if ROLE_ORDER_SUPPORT in roles:
        return "order_support"
    if ROLE_TECH_SUPPORT in roles:
        return "tech_support"
    return "merchant"


@router.get("/me")
async def get_me(
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(
        PermissionChecker([WORKSPACE_READ, ORDER_SUPPORT_READ, TECH_DESK_READ, ADMIN_READ])
    ),
) -> dict[str, Any]:
    role_codes = sorted(await _role_codes(db, int(current_user.id), int(tenant_ctx.tenant_id)))
    profile = (
        await db.execute(
            select(RealphotosMerchantProfile).where(
                RealphotosMerchantProfile.tenant_id == int(tenant_ctx.tenant_id),
                RealphotosMerchantProfile.user_id == int(current_user.id),
                RealphotosMerchantProfile.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    wallet = await RealphotosCreditService(db).get_wallet(tenant_id=int(tenant_ctx.tenant_id))
    return SuccessResponse(
        data={
            "userId": str(int(current_user.id)),
            "username": current_user.username,
            "tenantId": str(int(tenant_ctx.tenant_id)),
            "roleCodes": role_codes,
            "preReviewFrozen": bool(profile.pre_review_frozen) if profile else False,
            "wallet": wallet,
        }
    )


@router.get("/workspace")
async def get_workspace(
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(
        PermissionChecker([WORKSPACE_READ, ORDER_SUPPORT_READ, TECH_DESK_READ, ADMIN_READ])
    ),
) -> dict[str, Any]:
    """Role-scoped workspace: merchant cards / admin metrics / order desk / tech desk."""
    tenant_id = int(tenant_ctx.tenant_id)
    user_id = int(current_user.id)
    roles = await _role_codes(db, user_id, tenant_id)
    view = _view_kind(roles)
    wallet = await RealphotosCreditService(db).get_wallet(tenant_id=tenant_id)
    profile = (
        await db.execute(
            select(RealphotosMerchantProfile).where(
                RealphotosMerchantProfile.tenant_id == tenant_id,
                RealphotosMerchantProfile.user_id == user_id,
                RealphotosMerchantProfile.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()

    cards = None
    recent: list[dict[str, Any]] = []
    ops_metrics = None
    order_desk = None
    tech_desk = None

    if view == "merchant":
        active = int(
            await db.scalar(
                select(func.count())
                .select_from(RealphotosImageTask)
                .where(
                    RealphotosImageTask.tenant_id == tenant_id,
                    RealphotosImageTask.owner_account_id == user_id,
                    RealphotosImageTask.deleted_at.is_(None),
                    RealphotosImageTask.status.in_(tuple(RUNNING_TASK_STATUSES)),
                )
            )
            or 0
        )
        month_start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_done = int(
            await db.scalar(
                select(func.count())
                .select_from(RealphotosImageTask)
                .where(
                    RealphotosImageTask.tenant_id == tenant_id,
                    RealphotosImageTask.owner_account_id == user_id,
                    RealphotosImageTask.deleted_at.is_(None),
                    RealphotosImageTask.status == TASK_DELIVERED,
                    RealphotosImageTask.created_at >= month_start,
                )
            )
            or 0
        )
        unread = int(
            await db.scalar(
                select(func.count())
                .select_from(RealphotosInboxMessage)
                .where(
                    RealphotosInboxMessage.tenant_id == tenant_id,
                    RealphotosInboxMessage.recipient_user_id == user_id,
                    RealphotosInboxMessage.deleted_at.is_(None),
                    RealphotosInboxMessage.read_at.is_(None),
                )
            )
            or 0
        )
        cards = {
            "availableInteger": wallet.get("availableInteger"),
            "reservedInteger": wallet.get("reservedInteger"),
            "activeTasks": active,
            "monthDelivered": month_done,
            "unreadMessages": unread,
        }
        recent_processing = (
            await db.execute(
                select(RealphotosImageTask)
                .where(
                    RealphotosImageTask.tenant_id == tenant_id,
                    RealphotosImageTask.owner_account_id == user_id,
                    RealphotosImageTask.deleted_at.is_(None),
                )
                .order_by(RealphotosImageTask.id.desc())
                .limit(10)
            )
        ).scalars().all()
        recent_generation = (
            await db.execute(
                select(RealphotosGenerationTask)
                .where(
                    RealphotosGenerationTask.tenant_id == tenant_id,
                    RealphotosGenerationTask.owner_account_id == user_id,
                    RealphotosGenerationTask.deleted_at.is_(None),
                )
                .order_by(RealphotosGenerationTask.id.desc())
                .limit(10)
            )
        ).scalars().all()
        processing_no_map = await processing_task_no_map(
            db, tenant_id=tenant_id, task_ids=[row.id for row in recent_processing]
        )
        generation_no_map = await generation_task_no_map(
            db, tenant_id=tenant_id, task_ids=[row.id for row in recent_generation]
        )
        # 2026-11-18 UX-P1-7：最近历史补缩略图与失败摘要。
        from app.capabilities.realphotos.services.s1_processing import RealphotosS1Service

        asset_ids = {int(row.asset_id) for row in recent_processing}
        generation_items = (
            await db.execute(
                select(RealphotosGenerationItem)
                .where(
                    RealphotosGenerationItem.tenant_id == tenant_id,
                    RealphotosGenerationItem.task_id.in_(
                        [row.id for row in recent_generation] or [-1]
                    ),
                    RealphotosGenerationItem.deleted_at.is_(None),
                )
                .order_by(RealphotosGenerationItem.id.asc())
            )
        ).scalars().all()
        generation_asset: dict[int, int] = {}
        for item in generation_items:
            if item.asset_id is not None:
                generation_asset.setdefault(int(item.task_id), int(item.asset_id))
                asset_ids.add(int(item.asset_id))
        assets = {
            int(asset.id): asset
            for asset in (
                await db.execute(
                    select(RealphotosAsset).where(
                        RealphotosAsset.tenant_id == tenant_id,
                        RealphotosAsset.id.in_(asset_ids or [-1]),
                        RealphotosAsset.deleted_at.is_(None),
                    )
                )
            ).scalars().all()
        }
        task_service = RealphotosS1Service(db)
        for row in recent_processing:
            failure = await task_service.failure_detail_payload(
                tenant_id=tenant_id, task_id=int(row.id)
            )
            asset = assets.get(int(row.asset_id))
            snapshot = dict(row.preset_snapshot or {})
            legacy = snapshot.get("legacyParameters") if isinstance(snapshot.get("legacyParameters"), dict) else {}
            preset_name = (
                str((legacy or {}).get("name") or "").strip()
                or str(snapshot.get("name") or "").strip()
                or row.preset_code
            )
            recent.append(
                {
                    "kind": "processing",
                    "id": str(int(row.id)),
                    "taskNo": processing_no_map.get(int(row.id)),
                    "status": row.status,
                    "presetCode": row.preset_code,
                    "presetName": preset_name,
                    "objectKey": row.output_object_key
                    or (asset.object_key if asset is not None else None),
                    "failureClass": row.failure_class,
                    "failureTitle": (failure or {}).get("title")
                    or (failure or {}).get("failureClass"),
                    "failureMessage": (failure or {}).get("message"),
                    "canReprocess": bool(
                        row.output_object_key
                        and str(row.failure_class or "") == "detection_not_passed"
                    ),
                    "createdAt": row.created_at.isoformat() if row.created_at else None,
                }
            )
        for row in recent_generation:
            asset = assets.get(generation_asset.get(int(row.id), 0))
            recent.append(
                {
                    "kind": "generation",
                    "id": str(int(row.id)),
                    "taskNo": generation_no_map.get(int(row.id)),
                    "status": "stored",
                    "mode": row.mode,
                    "provider": row.provider,
                    "objectKey": asset.object_key if asset is not None else None,
                    "failureClass": None,
                    "failureTitle": None,
                    "failureMessage": None,
                    "canReprocess": False,
                    "createdAt": row.created_at.isoformat() if row.created_at else None,
                }
            )
        recent.sort(key=lambda item: item.get("createdAt") or "", reverse=True)
        recent = recent[:10]

    elif view == "admin":
        ops_metrics = await RealphotosOpsService(db).metrics(actor_role_codes=roles)

    elif view == "order_support":
        pending_rows = (
            await db.execute(
                select(RealphotosRechargeOrder)
                .where(
                    RealphotosRechargeOrder.status == "pending",
                    RealphotosRechargeOrder.deleted_at.is_(None),
                )
                .order_by(RealphotosRechargeOrder.id.asc())
                .limit(20)
            )
        ).scalars().all()
        pending_count = int(
            await db.scalar(
                select(func.count())
                .select_from(RealphotosRechargeOrder)
                .where(
                    RealphotosRechargeOrder.status == "pending",
                    RealphotosRechargeOrder.deleted_at.is_(None),
                )
            )
            or 0
        )
        order_desk = {
            "pendingRechargeOrders": pending_count,
            "items": [
                {
                    "id": str(int(row.id)),
                    "tenantId": str(int(row.tenant_id)),
                    "requesterUserId": str(int(row.requester_user_id)),
                    "tierYuan": int(row.tier_yuan),
                    "creditPoints": int(row.credit_points),
                    "status": row.status,
                    "createdAt": row.created_at.isoformat() if row.created_at else None,
                }
                for row in pending_rows
            ],
        }

    elif view == "tech_support":
        open_count = int(
            await db.scalar(
                select(func.count())
                .select_from(RealphotosSupportTicket)
                .where(
                    RealphotosSupportTicket.deleted_at.is_(None),
                    RealphotosSupportTicket.status == "open",
                )
            )
            or 0
        )
        by_type_rows = (
            await db.execute(
                select(RealphotosSupportTicket.ticket_type, func.count())
                .where(
                    RealphotosSupportTicket.deleted_at.is_(None),
                    RealphotosSupportTicket.status == "open",
                )
                .group_by(RealphotosSupportTicket.ticket_type)
            )
        ).all()
        recent_tickets = (
            await db.execute(
                select(RealphotosSupportTicket)
                .where(
                    RealphotosSupportTicket.deleted_at.is_(None),
                    RealphotosSupportTicket.status == "open",
                )
                .order_by(RealphotosSupportTicket.id.desc())
                .limit(10)
            )
        ).scalars().all()
        tech_desk = {
            "openTickets": open_count,
            "byType": {str(code): int(count) for code, count in by_type_rows},
            "items": [
                {
                    "id": int(row.id),
                    "tenantId": int(row.tenant_id),
                    "ownerAccountId": int(row.owner_account_id),
                    "ticketType": row.ticket_type,
                    "status": row.status,
                    "reason": row.reason,
                    "createdAt": row.created_at.isoformat() if row.created_at else None,
                }
                for row in recent_tickets
            ],
        }

    return SuccessResponse(
        data={
            "roleCodes": sorted(roles),
            "viewKind": view,
            "preReviewFrozen": bool(profile.pre_review_frozen) if profile else False,
            "merchantCards": view == "merchant",
            "showTaskChainBanner": False,
            "wallet": wallet if view == "merchant" else None,
            "cards": cards,
            "opsMetrics": ops_metrics,
            "orderSupportDesk": order_desk,
            "techSupportDesk": tech_desk,
            "recentHistory": recent,
        }
    )
