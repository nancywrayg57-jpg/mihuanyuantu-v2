"""Current session identity + role visibility (S0 RBAC evidence)."""

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.deps import CurrentUser, DBSession, PermissionChecker, TenantCtx
from app.capabilities.realphotos.models import RealphotosMerchantProfile
from app.capabilities.realphotos.permissions import WORKSPACE_READ
from app.capabilities.realphotos.services.credit_service import RealphotosCreditService
from app.core.response import SuccessResponse

router = APIRouter()


@router.get("/me")
async def get_me(
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([WORKSPACE_READ])),
) -> dict[str, Any]:
    role_codes = sorted(
        {
            str(getattr(role, "code", "") or "")
            for role in (current_user.roles or [])
            if getattr(role, "code", None)
        }
    )
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
    _: None = Depends(PermissionChecker([WORKSPACE_READ])),
) -> dict[str, Any]:
    wallet = await RealphotosCreditService(db).get_wallet(tenant_id=int(tenant_ctx.tenant_id))
    role_codes = sorted(
        {
            str(getattr(role, "code", "") or "")
            for role in (current_user.roles or [])
            if getattr(role, "code", None)
        }
    )
    return SuccessResponse(
        data={
            "wallet": wallet,
            "roleCodes": role_codes,
            "copyInProgress": False,
            "taskSummary": {"queued": 0, "running": 0},
            "messageSummary": {"unread": 0},
        }
    )
