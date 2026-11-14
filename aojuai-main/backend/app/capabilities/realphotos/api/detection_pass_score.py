"""Admin write / operator read for the Gemini detection pass line."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.api.deps import CurrentUser, DBSession, PermissionChecker, TenantCtx
from app.capabilities.realphotos.permissions import ADMIN_READ, ROLE_ADMIN, WORKSPACE_READ
from app.capabilities.realphotos.services.detection_pass_score import DetectionPassScoreService
from app.core.response import SuccessResponse
from app.domain.roles.models import Role
from app.domain.users.models import UserRole

router = APIRouter()

# Merchants and tech support can open 系统管理 (WORKSPACE_READ). Write is still admin-only.
detection_pass_score_guard = PermissionChecker([WORKSPACE_READ, ADMIN_READ])


class PassScoreBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    pass_score: int = Field(alias="passScore", ge=0, le=100)


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


@router.get("/detection-pass-score")
async def get_detection_pass_score(
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(detection_pass_score_guard),
) -> dict[str, Any]:
    roles = await _role_codes(db, int(current_user.id), int(tenant_ctx.tenant_id))
    payload = await DetectionPassScoreService(db).view(actor_role_codes=roles)
    return SuccessResponse(data=payload)


@router.put("/detection-pass-score")
async def put_detection_pass_score(
    body: PassScoreBody,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(detection_pass_score_guard),
) -> dict[str, Any]:
    roles = await _role_codes(db, int(current_user.id), int(tenant_ctx.tenant_id))
    payload = await DetectionPassScoreService(db).update(
        actor_role_codes=roles,
        pass_score=int(body.pass_score),
        tenant_id=int(tenant_ctx.tenant_id),
        actor_user_id=int(current_user.id),
    )
    await db.commit()
    return SuccessResponse(data=payload)
