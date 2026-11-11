"""Admin-only supplier contract CRUD. Secrets accepted on write; never returned plaintext."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.api.deps import CurrentUser, DBSession, PermissionChecker, TenantCtx
from app.capabilities.realphotos.permissions import ADMIN_READ, ROLE_ADMIN
from app.capabilities.realphotos.services.supplier_config import RealphotosSupplierConfigService
from app.core.exceptions import ForbiddenError
from app.core.response import SuccessResponse
from app.domain.roles.models import Role
from app.domain.users.models import UserRole

router = APIRouter()


class ContractBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    duty: str
    model_id: str = Field(default="", alias="modelId")
    provider: str | None = None
    base_url: str | None = Field(default=None, alias="baseUrl")
    api_key: str | None = Field(default=None, alias="apiKey")
    enabled: bool | None = None


class EnabledBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    duty: str
    enabled: bool


def _reject_key_auth(request: Request) -> None:
    if getattr(request.state, "auth_via_api_key", False):
        raise ForbiddenError(message="业务 API Key 不能登记上游配置")


async def _roles(db: DBSession, user_id: int, tenant_id: int) -> set[str]:
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


@router.get("/provider-contracts")
async def list_contracts(
    request: Request,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([ADMIN_READ])),
) -> dict[str, Any]:
    _reject_key_auth(request)
    roles = await _roles(db, int(current_user.id), int(tenant_ctx.tenant_id))
    payload = await RealphotosSupplierConfigService(db).list_masked(actor_role_codes=roles)
    return SuccessResponse(data=payload)


@router.post("/provider-contracts")
async def save_contract(
    body: ContractBody,
    request: Request,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([ADMIN_READ])),
) -> dict[str, Any]:
    _reject_key_auth(request)
    roles = await _roles(db, int(current_user.id), int(tenant_ctx.tenant_id))
    payload = await RealphotosSupplierConfigService(db).save(
        actor_role_codes=roles,
        duty=body.duty,
        model_id=body.model_id,
        provider=body.provider,
        base_url=body.base_url,
        api_key=body.api_key,
        enabled=body.enabled,
        actor_user_id=int(current_user.id),
    )
    await db.commit()
    return SuccessResponse(data=payload)


@router.post("/provider-contracts/enabled")
async def set_contract_enabled(
    body: EnabledBody,
    request: Request,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([ADMIN_READ])),
) -> dict[str, Any]:
    _reject_key_auth(request)
    roles = await _roles(db, int(current_user.id), int(tenant_ctx.tenant_id))
    payload = await RealphotosSupplierConfigService(db).set_enabled(
        actor_role_codes=roles,
        duty=body.duty,
        enabled=bool(body.enabled),
        actor_user_id=int(current_user.id),
    )
    await db.commit()
    return SuccessResponse(data=payload)


@router.delete("/provider-contracts/{duty}")
async def delete_contract(
    duty: str,
    request: Request,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([ADMIN_READ])),
) -> dict[str, Any]:
    _reject_key_auth(request)
    roles = await _roles(db, int(current_user.id), int(tenant_ctx.tenant_id))
    payload = await RealphotosSupplierConfigService(db).soft_delete(
        actor_role_codes=roles,
        duty=duty,
        actor_user_id=int(current_user.id),
    )
    await db.commit()
    return SuccessResponse(data=payload)
