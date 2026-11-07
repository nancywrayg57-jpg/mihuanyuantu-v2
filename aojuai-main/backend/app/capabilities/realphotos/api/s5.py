"""S5 HTTP: generation, prompts, unconfigured import, business API keys."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Request, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.api.deps import CurrentUser, DBSession, PermissionChecker, TenantCtx
from app.capabilities.realphotos.constants import IMAGE_PROCESSING_SCOPE
from app.capabilities.realphotos.permissions import ADMIN_READ, ROLE_ADMIN, WORKSPACE_READ
from app.capabilities.realphotos.services.s5_growth import RealphotosGrowthService
from app.core.exceptions import BusinessError, ForbiddenError
from app.core.response import SuccessResponse
from app.domain.auth.api_key_service import ApiKeyService
from app.domain.roles.models import Role
from app.domain.users.models import UserRole

router = APIRouter()


class GenerationBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    mode: str
    positive_prompt: str = Field(alias="positivePrompt")
    negative_prompt: str = Field(default="", alias="negativePrompt")
    width: int
    height: int
    quantity: int
    idempotency_key: str = Field(alias="idempotencyKey")
    provider: str = "unconfigured"
    template_id: int | None = Field(default=None, alias="templateId")
    reference_asset_id: int | None = Field(default=None, alias="referenceAssetId")
    fail_indexes: list[int] = Field(default_factory=list, alias="failIndexes")


class OptimizeBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    original_text: str = Field(alias="originalText")
    provider: str = "unconfigured"
    succeed: bool = True


class TemplateBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    mode: str
    positive_prompt: str = Field(alias="positivePrompt")
    negative_prompt: str = Field(default="", alias="negativePrompt")
    scope: str = "tenant"


class ImportBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    payload: str = ""


class BusinessKeyBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    scopes: list[str] | None = None
    expires_in_days: int | None = Field(default=None, alias="expiresInDays")


def _reject_key_auth(request: Request) -> None:
    if getattr(request.state, "auth_via_api_key", False):
        raise ForbiddenError(message="API Key 不能创建或吊销 Key")


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


@router.get("/assets")
async def list_assets(
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([WORKSPACE_READ])),
) -> dict[str, Any]:
    rows = await RealphotosGrowthService(db).list_assets(
        tenant_id=int(tenant_ctx.tenant_id),
        owner_account_id=int(current_user.id),
    )
    return SuccessResponse(
        data={
            "items": [
                {
                    "id": str(int(row.id)),
                    "originKind": row.origin_kind,
                    "width": int(row.width),
                    "height": int(row.height),
                    "byteSize": int(row.byte_size),
                }
                for row in rows
            ]
        }
    )


async def _generation_body(request: Request) -> tuple[GenerationBody, bytes | None]:
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" in content_type:
        form = await request.form()
        upload = form.get("reference")
        reference_bytes = await upload.read() if hasattr(upload, "read") else None
        raw_template = form.get("templateId")
        raw_asset = form.get("referenceAssetId")
        fail_raw = str(form.get("failIndexes") or "").strip()
        return (
            GenerationBody.model_validate(
                {
                    "mode": form.get("mode"),
                    "positivePrompt": form.get("positivePrompt"),
                    "negativePrompt": form.get("negativePrompt") or "",
                    "width": form.get("width"),
                    "height": form.get("height"),
                    "quantity": form.get("quantity"),
                    "idempotencyKey": form.get("idempotencyKey"),
                    "provider": form.get("provider") or "unconfigured",
                    "templateId": int(str(raw_template)) if raw_template else None,
                    "referenceAssetId": int(str(raw_asset)) if raw_asset else None,
                    "failIndexes": [int(item) for item in fail_raw.split(",") if item.strip()],
                }
            ),
            reference_bytes or None,
        )
    return GenerationBody.model_validate(await request.json()), None


@router.post("/generation-tasks")
async def create_generation(
    request: Request,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([WORKSPACE_READ])),
) -> dict[str, Any]:
    body, reference_bytes = await _generation_body(request)
    service = RealphotosGrowthService(db)
    try:
        task = await service.submit_generation(
            tenant_id=int(tenant_ctx.tenant_id),
            owner_account_id=int(current_user.id),
            mode=body.mode,
            positive_prompt=body.positive_prompt,
            negative_prompt=body.negative_prompt,
            width=int(body.width),
            height=int(body.height),
            quantity=int(body.quantity),
            idempotency_key=body.idempotency_key,
            provider=body.provider,
            template_id=body.template_id,
            reference_asset_id=body.reference_asset_id,
            reference_bytes=reference_bytes,
            fail_indexes=set(body.fail_indexes),
        )
    except BusinessError as exc:
        if exc.code in {"PRE_REVIEW_REJECTED", "PRE_REVIEW_FAILED"}:
            await db.commit()
        raise
    trace = getattr(task, "supplier_trace", None)
    await db.commit()
    items = await service.list_generation_items(tenant_id=int(tenant_ctx.tenant_id), task_id=int(task.id))
    return SuccessResponse(
        data={
            "id": str(int(task.id)),
            "provider": task.provider,
            "supplier": trace,
            "items": [
                {
                    "index": int(item.item_index),
                    "status": item.status,
                    "assetId": str(int(item.asset_id)) if item.asset_id else None,
                    "creditsConsumed": int(item.credits_consumed),
                }
                for item in items
            ],
        }
    )


@router.post("/prompt-optimizations")
async def create_optimization(
    body: OptimizeBody,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([WORKSPACE_READ])),
) -> dict[str, Any]:
    row = await RealphotosGrowthService(db).optimize_prompt(
        tenant_id=int(tenant_ctx.tenant_id),
        owner_account_id=int(current_user.id),
        original_text=body.original_text,
        provider=body.provider,
        succeed=bool(body.succeed),
    )
    trace = getattr(row, "supplier_trace", None)
    await db.commit()
    return SuccessResponse(
        data={
            "id": str(int(row.id)),
            "status": row.status,
            "originalText": row.original_text,
            "optimizedText": row.optimized_text,
            "confirmed": bool(row.confirmed),
            "supplier": trace,
        }
    )


@router.post("/prompt-optimizations/{optimization_id}/confirm")
async def confirm_optimization(
    optimization_id: int,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([WORKSPACE_READ])),
) -> dict[str, Any]:
    row = await RealphotosGrowthService(db).confirm_optimization(
        tenant_id=int(tenant_ctx.tenant_id),
        owner_account_id=int(current_user.id),
        optimization_id=int(optimization_id),
    )
    await db.commit()
    return SuccessResponse(data={"id": str(int(row.id)), "confirmed": bool(row.confirmed)})


@router.get("/prompt-templates")
async def list_templates(
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([WORKSPACE_READ, ADMIN_READ])),
) -> dict[str, Any]:
    roles = await _roles(db, int(current_user.id), int(tenant_ctx.tenant_id))
    rows = await RealphotosGrowthService(db).list_templates(
        tenant_id=int(tenant_ctx.tenant_id),
        actor_role_codes=roles,
    )
    return SuccessResponse(
        data={
            "items": [
                {
                    "id": str(int(row.id)),
                    "name": row.name,
                    "mode": row.mode,
                    "scope": row.scope,
                    "positivePrompt": row.positive_prompt,
                    "negativePrompt": row.negative_prompt,
                }
                for row in rows
            ]
        }
    )


@router.post("/prompt-templates")
async def create_template(
    body: TemplateBody,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([WORKSPACE_READ, ADMIN_READ])),
) -> dict[str, Any]:
    roles = await _roles(db, int(current_user.id), int(tenant_ctx.tenant_id))
    row = await RealphotosGrowthService(db).save_template(
        tenant_id=int(tenant_ctx.tenant_id),
        owner_account_id=int(current_user.id),
        actor_role_codes=roles,
        name=body.name,
        mode=body.mode,
        positive_prompt=body.positive_prompt,
        negative_prompt=body.negative_prompt,
        scope=body.scope,
    )
    await db.commit()
    return SuccessResponse(data={"id": str(int(row.id)), "scope": row.scope})


@router.post("/resource-imports")
async def import_resources(
    body: ImportBody,
    db: DBSession,
    _: None = Depends(PermissionChecker([WORKSPACE_READ])),
) -> dict[str, Any]:
    await RealphotosGrowthService(db).import_resources(payload=body.payload)
    return SuccessResponse(data={})


@router.post("/resource-imports/files")
async def import_resource_file(
    db: DBSession,
    file: UploadFile = File(...),
    _: None = Depends(PermissionChecker([WORKSPACE_READ])),
) -> dict[str, Any]:
    await RealphotosGrowthService(db).import_resource_file(raw=await file.read())
    return SuccessResponse(data={})


@router.post("/business-api-keys")
async def create_business_key(
    body: BusinessKeyBody,
    current_user: CurrentUser,
    request: Request,
    db: DBSession,
    _: None = Depends(PermissionChecker([WORKSPACE_READ, ADMIN_READ])),
) -> dict[str, Any]:
    _reject_key_auth(request)
    if body.scopes != [IMAGE_PROCESSING_SCOPE]:
        raise BusinessError(
            message="业务 Key 只能选择 image_processing",
            code="SCOPE_REJECTED",
        )
    api_key, plaintext = await ApiKeyService.create_key(
        db,
        int(current_user.tenant_id),
        int(current_user.id),
        name=body.name,
        scopes=[IMAGE_PROCESSING_SCOPE],
        expires_in_days=body.expires_in_days,
    )
    await db.commit()
    return SuccessResponse(
        data={
            "id": str(int(api_key.id)),
            "keyPrefix": api_key.key_prefix,
            "scopes": list(api_key.scopes),
            "apiKey": plaintext,
        }
    )


@router.delete("/business-api-keys/{key_id}")
async def revoke_business_key(
    key_id: int,
    current_user: CurrentUser,
    request: Request,
    db: DBSession,
    _: None = Depends(PermissionChecker([WORKSPACE_READ, ADMIN_READ])),
) -> dict[str, Any]:
    _reject_key_auth(request)
    await ApiKeyService.revoke_key(
        db, int(current_user.tenant_id), int(current_user.id), int(key_id)
    )
    await db.commit()
    return SuccessResponse(data={"id": str(int(key_id)), "revoked": True})
