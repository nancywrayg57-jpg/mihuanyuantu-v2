"""S6 HTTP: content review, tech desk, users, logs, presets, metrics."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.api.deps import CurrentUser, DBSession, PermissionChecker, TenantCtx
from app.capabilities.realphotos.permissions import ADMIN_READ, ROLE_ADMIN, TECH_DESK_READ, WORKSPACE_READ
from app.capabilities.realphotos.services.s6_ops import RealphotosOpsService
from app.core.exceptions import ForbiddenError
from app.core.response import SuccessResponse
from app.domain.roles.models import Role
from app.domain.users.models import UserRole

router = APIRouter()


class ReleaseBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    reason: str
    tenant_id: int = Field(alias="tenantId")


class UnfreezeBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: int = Field(alias="userId")
    tenant_id: int = Field(alias="tenantId")
    reason: str


class UserCreateBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tenant_id: int = Field(alias="tenantId")
    username: str
    password: str
    role_code: str = Field(alias="roleCode")


class CreditBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tenant_id: int = Field(alias="tenantId")
    user_id: int = Field(alias="userId")
    delta: int
    reason: str
    event_key: str = Field(alias="eventKey")


class RoleBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tenant_id: int = Field(alias="tenantId")
    role_codes: list[str] = Field(alias="roleCodes")


class StatusBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    enabled: bool


class PasswordBody(BaseModel):
    password: str
    confirm: str


class DeleteBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    confirm_username: str = Field(alias="confirmUsername")


class PresetBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    code: str
    device_type: str = Field(default="phone", alias="deviceType")
    brand: str
    model_name: str = Field(alias="model")
    gps_mode: str = Field(default="none", alias="gpsMode")
    enabled: bool = True
    maker_note: str | None = Field(default=None, alias="makerNote")
    author: str | None = None
    ip_geo: str | None = Field(default=None, alias="ipGeo")
    iso: str | None = None
    shutter: str | None = None
    aperture: str | None = None
    focal_length: str | None = Field(default=None, alias="focalLength")
    gps_config: dict | None = Field(default=None, alias="gpsConfig")
    ai_positive_prompt: str | None = Field(default=None, alias="aiPositivePrompt")
    ai_negative_prompt: str | None = Field(default=None, alias="aiNegativePrompt")


class TicketCreateBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    ticket_type: str = Field(alias="ticketType")
    reason: str


class PresetEnabledBody(BaseModel):
    enabled: bool


class ActivateImportBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    template_ref: str = Field(alias="templateRef")
    enabled: bool = True


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


@router.post("/content-reviews")
async def review_content(
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    file: UploadFile = File(...),
    subject: str = Form(...),
    provider: str = Form(default="unconfigured"),
    verdict: str = Form(default="reject"),
    _: None = Depends(PermissionChecker([TECH_DESK_READ, WORKSPACE_READ])),
) -> dict[str, Any]:
    data = await file.read()
    payload = await RealphotosOpsService(db).review_content(
        tenant_id=int(tenant_ctx.tenant_id),
        owner_account_id=int(current_user.id),
        data=data,
        subject=subject,
        provider=provider,
        verdict=verdict,
    )
    await db.commit()
    return SuccessResponse(data=payload)


@router.post("/held-credits/{task_id}/release")
async def release_held(
    task_id: int,
    body: ReleaseBody,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([TECH_DESK_READ])),
) -> dict[str, Any]:
    roles = await _roles(db, int(current_user.id), int(tenant_ctx.tenant_id))
    payload = await RealphotosOpsService(db).release_held_credit(
        actor_role_codes=roles,
        operator_user_id=int(current_user.id),
        tenant_id=int(body.tenant_id),
        task_id=int(task_id),
        reason=body.reason,
    )
    await db.commit()
    return SuccessResponse(data=payload)


@router.post("/account-freezes/release")
async def unfreeze(
    body: UnfreezeBody,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([TECH_DESK_READ])),
) -> dict[str, Any]:
    roles = await _roles(db, int(current_user.id), int(tenant_ctx.tenant_id))
    payload = await RealphotosOpsService(db).unfreeze_account(
        actor_role_codes=roles,
        tenant_id=int(body.tenant_id),
        user_id=int(body.user_id),
        reason=body.reason,
    )
    await db.commit()
    return SuccessResponse(data=payload)


@router.get("/support-tickets")
async def list_tickets(
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([TECH_DESK_READ])),
) -> dict[str, Any]:
    roles = await _roles(db, int(current_user.id), int(tenant_ctx.tenant_id))
    payload = await RealphotosOpsService(db).list_tickets(actor_role_codes=roles)
    return SuccessResponse(data=payload)


@router.get("/my-support-tickets")
async def list_my_tickets(
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([WORKSPACE_READ])),
) -> dict[str, Any]:
    payload = await RealphotosOpsService(db).list_merchant_tickets(
        tenant_id=int(tenant_ctx.tenant_id),
        owner_account_id=int(current_user.id),
    )
    return SuccessResponse(data=payload)


@router.post("/support-tickets")
async def create_ticket(
    body: TicketCreateBody,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([WORKSPACE_READ, TECH_DESK_READ])),
) -> dict[str, Any]:
    roles = await _roles(db, int(current_user.id), int(tenant_ctx.tenant_id))
    payload = await RealphotosOpsService(db).create_ticket(
        tenant_id=int(tenant_ctx.tenant_id),
        owner_account_id=int(current_user.id),
        ticket_type=body.ticket_type,
        reason=body.reason,
        actor_role_codes=roles,
    )
    await db.commit()
    return SuccessResponse(data=payload)


@router.get("/managed-users")
async def list_users(
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    page: int = 1,
    _: None = Depends(PermissionChecker([TECH_DESK_READ])),
) -> dict[str, Any]:
    roles = await _roles(db, int(current_user.id), int(tenant_ctx.tenant_id))
    payload = await RealphotosOpsService(db).list_users(actor_role_codes=roles, page=page)
    return SuccessResponse(data=payload)


@router.post("/managed-users")
async def create_user(
    body: UserCreateBody,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([TECH_DESK_READ])),
) -> dict[str, Any]:
    roles = await _roles(db, int(current_user.id), int(tenant_ctx.tenant_id))
    payload = await RealphotosOpsService(db).create_user(
        actor_role_codes=roles,
        operator_user_id=int(current_user.id),
        tenant_id=int(body.tenant_id),
        username=body.username,
        password=body.password,
        role_code=body.role_code,
    )
    await db.commit()
    return SuccessResponse(data=payload)


@router.post("/managed-users/credits")
async def adjust_credits(
    body: CreditBody,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([TECH_DESK_READ])),
) -> dict[str, Any]:
    roles = await _roles(db, int(current_user.id), int(tenant_ctx.tenant_id))
    payload = await RealphotosOpsService(db).adjust_credits(
        actor_role_codes=roles,
        operator_user_id=int(current_user.id),
        tenant_id=int(body.tenant_id),
        user_id=int(body.user_id),
        delta=body.delta,
        reason=body.reason,
        event_key=body.event_key,
    )
    await db.commit()
    return SuccessResponse(data=payload)


@router.post("/managed-users/{user_id}/roles")
async def set_roles(
    user_id: int,
    body: RoleBody,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([TECH_DESK_READ])),
) -> dict[str, Any]:
    roles = await _roles(db, int(current_user.id), int(tenant_ctx.tenant_id))
    payload = await RealphotosOpsService(db).set_roles(
        actor_role_codes=roles,
        operator_user_id=int(current_user.id),
        tenant_id=int(body.tenant_id),
        user_id=int(user_id),
        role_codes=body.role_codes,
    )
    await db.commit()
    return SuccessResponse(data=payload)


@router.post("/managed-users/{user_id}/status")
async def set_status(
    user_id: int,
    body: StatusBody,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([TECH_DESK_READ])),
) -> dict[str, Any]:
    roles = await _roles(db, int(current_user.id), int(tenant_ctx.tenant_id))
    payload = await RealphotosOpsService(db).set_status(
        actor_role_codes=roles,
        operator_user_id=int(current_user.id),
        user_id=int(user_id),
        enabled=body.enabled,
    )
    await db.commit()
    return SuccessResponse(data=payload)


@router.post("/managed-users/{user_id}/password")
async def reset_password(
    user_id: int,
    body: PasswordBody,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([TECH_DESK_READ])),
) -> dict[str, Any]:
    roles = await _roles(db, int(current_user.id), int(tenant_ctx.tenant_id))
    payload = await RealphotosOpsService(db).reset_password(
        actor_role_codes=roles,
        operator_user_id=int(current_user.id),
        user_id=int(user_id),
        password=body.password,
        confirm=body.confirm,
    )
    await db.commit()
    return SuccessResponse(data=payload)


@router.post("/managed-users/{user_id}/delete")
async def delete_user(
    user_id: int,
    body: DeleteBody,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([TECH_DESK_READ])),
) -> dict[str, Any]:
    roles = await _roles(db, int(current_user.id), int(tenant_ctx.tenant_id))
    payload = await RealphotosOpsService(db).delete_user(
        actor_role_codes=roles,
        operator_user_id=int(current_user.id),
        user_id=int(user_id),
        confirm_username=body.confirm_username,
    )
    await db.commit()
    return SuccessResponse(data=payload)


@router.get("/account-logs")
async def list_logs(
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    page: int = 1,
    _: None = Depends(PermissionChecker([TECH_DESK_READ])),
) -> dict[str, Any]:
    roles = await _roles(db, int(current_user.id), int(tenant_ctx.tenant_id))
    payload = await RealphotosOpsService(db).list_logs(actor_role_codes=roles, page=page)
    return SuccessResponse(data=payload)


@router.get("/device-preset-imports")
async def list_preset_imports(
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    page: int = 1,
    page_size: int = 20,
    _: None = Depends(PermissionChecker([ADMIN_READ])),
) -> dict[str, Any]:
    roles = await _roles(db, int(current_user.id), int(tenant_ctx.tenant_id))
    if ROLE_ADMIN not in roles and "admin" not in roles:
        raise ForbiddenError(message="只有平台管理员可以浏览导入记录")
    from app.capabilities.realphotos.services.legacy_preset_imports import browse_legacy_imports

    return SuccessResponse(data=await browse_legacy_imports(db, page=page, page_size=page_size))


@router.post("/device-preset-imports/activate")
async def activate_preset_import(
    body: ActivateImportBody,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([ADMIN_READ])),
) -> dict[str, Any]:
    roles = await _roles(db, int(current_user.id), int(tenant_ctx.tenant_id))
    if ROLE_ADMIN not in roles and "admin" not in roles:
        raise ForbiddenError(message="只有平台管理员可以激活旧版导入")
    from app.capabilities.realphotos.services.legacy_preset_imports import activate_legacy_template

    payload = await activate_legacy_template(
        db,
        actor_role_codes=roles,
        template_ref=body.template_ref,
        enabled=bool(body.enabled),
    )
    await db.commit()
    return SuccessResponse(data=payload)


@router.post("/device-preset-imports/clear-placeholders")
async def clear_preset_placeholders(
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([ADMIN_READ])),
) -> dict[str, Any]:
    roles = await _roles(db, int(current_user.id), int(tenant_ctx.tenant_id))
    if ROLE_ADMIN not in roles and "admin" not in roles:
        raise ForbiddenError(message="只有平台管理员可以清除占位预设")
    from app.capabilities.realphotos.services.legacy_preset_imports import clear_placeholder_presets

    payload = await clear_placeholder_presets(db, actor_role_codes=roles)
    await db.commit()
    return SuccessResponse(data=payload)


@router.post("/device-preset-imports/activate-all")
async def activate_all_preset_imports(
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([ADMIN_READ])),
) -> dict[str, Any]:
    roles = await _roles(db, int(current_user.id), int(tenant_ctx.tenant_id))
    if ROLE_ADMIN not in roles and "admin" not in roles:
        raise ForbiddenError(message="只有平台管理员可以全量导入旧版预设")
    from app.capabilities.realphotos.services.legacy_preset_imports import activate_all_legacy_templates

    payload = await activate_all_legacy_templates(db, actor_role_codes=roles, enabled=True)
    await db.commit()
    return SuccessResponse(data=payload)


@router.get("/device-presets")
async def list_device_presets(
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([ADMIN_READ])),
) -> dict[str, Any]:
    roles = await _roles(db, int(current_user.id), int(tenant_ctx.tenant_id))
    items = await RealphotosOpsService(db).list_admin_presets(actor_role_codes=roles)
    return SuccessResponse(data={"items": items})


@router.post("/device-presets")
async def save_preset(
    body: PresetBody,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([ADMIN_READ])),
) -> dict[str, Any]:
    roles = await _roles(db, int(current_user.id), int(tenant_ctx.tenant_id))
    payload = await RealphotosOpsService(db).save_preset(
        actor_role_codes=roles,
        code=body.code,
        device_type=body.device_type,
        brand=body.brand,
        model_name=body.model_name,
        gps_mode=body.gps_mode,
        enabled=body.enabled,
        maker_note=body.maker_note,
        author=body.author,
        ip_geo=body.ip_geo,
        iso=body.iso,
        shutter=body.shutter,
        aperture=body.aperture,
        focal_length=body.focal_length,
        gps_config=body.gps_config,
        ai_positive_prompt=body.ai_positive_prompt,
        ai_negative_prompt=body.ai_negative_prompt,
    )
    await db.commit()
    return SuccessResponse(data=payload)


@router.get("/device-presets/{code}/versions")
async def list_preset_versions(
    code: str,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([ADMIN_READ])),
) -> dict[str, Any]:
    roles = await _roles(db, int(current_user.id), int(tenant_ctx.tenant_id))
    items = await RealphotosOpsService(db).list_preset_versions(actor_role_codes=roles, code=code)
    return SuccessResponse(data={"items": items})


@router.post("/device-presets/{code}/enabled")
async def set_preset_enabled(
    code: str,
    body: PresetEnabledBody,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([ADMIN_READ])),
) -> dict[str, Any]:
    roles = await _roles(db, int(current_user.id), int(tenant_ctx.tenant_id))
    payload = await RealphotosOpsService(db).set_preset_enabled(
        actor_role_codes=roles, code=code, enabled=body.enabled
    )
    await db.commit()
    return SuccessResponse(data=payload)


@router.get("/ops-metrics")
async def ops_metrics(
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([ADMIN_READ])),
) -> dict[str, Any]:
    roles = await _roles(db, int(current_user.id), int(tenant_ctx.tenant_id))
    payload = await RealphotosOpsService(db).metrics(actor_role_codes=roles)
    return SuccessResponse(data=payload)
