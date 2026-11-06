"""S1 HTTP surface: presets, upload, single submit, recharge, inbox."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.api.deps import CurrentUser, DBSession, PermissionChecker, TenantCtx
from app.capabilities.realphotos.permissions import (
    ADMIN_READ,
    GATEWAY_READ,
    JOBS_ENQUEUE,
    ORDER_SUPPORT_READ,
    ROLE_ADMIN,
    WALLET_READ,
)
from app.capabilities.realphotos.services.s1_catalog import S1_ENABLED_PRESETS
from app.capabilities.realphotos.services.s1_processing import RealphotosS1Service
from app.capabilities.realphotos.services.s1_recharge import RealphotosRechargeService
from app.core.response import SuccessResponse
from app.domain.roles.models import Role
from app.domain.users.models import UserRole

router = APIRouter()


class SubmitBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    asset_id: int = Field(alias="assetId")
    preset_code: str = Field(alias="presetCode")
    idempotency_key: str = Field(alias="idempotencyKey")
    pre_review_mode: str = Field(default="pass", alias="preReviewMode")
    detection_mode: str = Field(default="pass", alias="detectionMode")


class RechargeBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tier_yuan: int = Field(alias="tierYuan")
    voucher_note: str = Field(min_length=1, alias="voucherNote")
    idempotency_key: str = Field(alias="idempotencyKey")


class RejectBody(BaseModel):
    reason: str = Field(min_length=1)


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
    return {str(code) for (code,) in rows}


def _task_payload(task) -> dict[str, Any]:
    return {
        "id": str(int(task.id)),
        "tenantId": str(int(task.tenant_id)),
        "ownerAccountId": str(int(task.owner_account_id)),
        "assetId": str(int(task.asset_id)),
        "status": task.status,
        "presetCode": task.preset_code,
        "presetSnapshot": dict(task.preset_snapshot or {}),
        "failureClass": task.failure_class,
        "creditDisposition": task.credit_disposition,
        "outputObjectKey": task.output_object_key,
        "outputExpiresAt": task.output_expires_at.isoformat() if task.output_expires_at else None,
        "pipelineVersion": task.pipeline_version,
    }


@router.get("/presets")
async def list_presets(_: None = Depends(PermissionChecker([WALLET_READ]))) -> dict[str, Any]:
    return SuccessResponse(data={"items": list(S1_ENABLED_PRESETS), "enabledCount": len(S1_ENABLED_PRESETS)})


@router.post("/assets")
async def upload_asset(
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    file: UploadFile = File(...),
    _: None = Depends(PermissionChecker([GATEWAY_READ])),
) -> dict[str, Any]:
    data = await file.read()
    asset = await RealphotosS1Service(db).upload(
        tenant_id=int(tenant_ctx.tenant_id),
        owner_account_id=int(current_user.id),
        data=data,
    )
    await db.commit()
    return SuccessResponse(
        data={
            "id": str(int(asset.id)),
            "contentType": asset.content_type,
            "byteSize": int(asset.byte_size),
            "width": int(asset.width),
            "height": int(asset.height),
            "objectKey": asset.object_key,
        }
    )


@router.post("/processing-tasks")
async def submit_task(
    body: SubmitBody,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([JOBS_ENQUEUE])),
) -> dict[str, Any]:
    roles = await _role_codes(db, int(current_user.id), int(tenant_ctx.tenant_id))
    if "admin" in roles:
        roles.add(ROLE_ADMIN)
    task = await RealphotosS1Service(db).submit_single(
        tenant_id=int(tenant_ctx.tenant_id),
        owner_account_id=int(current_user.id),
        actor_role_codes=roles,
        asset_id=int(body.asset_id),
        preset_code=body.preset_code,
        idempotency_key=body.idempotency_key,
        pre_review_mode=body.pre_review_mode,
        detection_mode=body.detection_mode,
    )
    await db.commit()
    return SuccessResponse(data=_task_payload(task))


@router.get("/processing-tasks/{task_id}")
async def get_task(
    task_id: int,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([JOBS_ENQUEUE])),
) -> dict[str, Any]:
    service = RealphotosS1Service(db)
    task = await service.get_task(tenant_id=int(tenant_ctx.tenant_id), task_id=int(task_id))
    payload = _task_payload(task)
    payload["detection"] = await service.detection_payload(
        tenant_id=int(tenant_ctx.tenant_id), task_id=int(task.id)
    )
    return SuccessResponse(data=payload)


@router.delete("/assets/{asset_id}")
async def delete_asset(
    asset_id: int,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([GATEWAY_READ])),
) -> dict[str, Any]:
    await RealphotosS1Service(db).soft_delete_asset(
        tenant_id=int(tenant_ctx.tenant_id), asset_id=int(asset_id)
    )
    await db.commit()
    return SuccessResponse(data={"deleted": True})


@router.get("/inbox")
async def inbox(
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([WALLET_READ])),
) -> dict[str, Any]:
    rows = await RealphotosS1Service(db).list_inbox(
        tenant_id=int(tenant_ctx.tenant_id),
        recipient_user_id=int(current_user.id),
    )
    return SuccessResponse(
        data={
            "items": [
                {"id": str(int(row.id)), "title": row.title, "body": row.body}
                for row in rows
            ]
        }
    )


@router.get("/recharge-orders")
async def list_recharge_orders(
    db: DBSession,
    _: None = Depends(PermissionChecker([ORDER_SUPPORT_READ])),
) -> dict[str, Any]:
    rows = await RealphotosRechargeService(db).list_pending()
    return SuccessResponse(
        data={
            "items": [
                {
                    "id": str(int(order.id)),
                    "tenantId": str(int(order.tenant_id)),
                    "requesterUserId": str(int(order.requester_user_id)),
                    "tierYuan": int(order.tier_yuan),
                    "creditPoints": int(order.credit_points),
                    "voucherNote": order.voucher_note,
                    "status": order.status,
                    "priceFormula": order.price_formula,
                }
                for order in rows
            ]
        }
    )


@router.post("/recharge-orders")
async def create_recharge(
    body: RechargeBody,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([WALLET_READ])),
) -> dict[str, Any]:
    order = await RealphotosRechargeService(db).create_order(
        tenant_id=int(tenant_ctx.tenant_id),
        requester_user_id=int(current_user.id),
        tier_yuan=int(body.tier_yuan),
        voucher_note=body.voucher_note,
        idempotency_key=body.idempotency_key,
    )
    await db.commit()
    return SuccessResponse(
        data={
            "id": str(int(order.id)),
            "status": order.status,
            "tierYuan": int(order.tier_yuan),
            "creditPoints": int(order.credit_points),
            "priceFormula": order.price_formula,
        }
    )


@router.post("/recharge-orders/{order_id}/confirm")
async def confirm_recharge(
    order_id: int,
    current_user: CurrentUser,
    db: DBSession,
    _: None = Depends(PermissionChecker([ORDER_SUPPORT_READ])),
) -> dict[str, Any]:
    order = await RealphotosRechargeService(db).confirm(
        order_id=int(order_id), operator_user_id=int(current_user.id)
    )
    await db.commit()
    return SuccessResponse(data={"id": str(int(order.id)), "status": order.status})


@router.post("/recharge-orders/{order_id}/reject")
async def reject_recharge(
    order_id: int,
    body: RejectBody,
    current_user: CurrentUser,
    db: DBSession,
    _: None = Depends(PermissionChecker([ORDER_SUPPORT_READ])),
) -> dict[str, Any]:
    order = await RealphotosRechargeService(db).reject(
        order_id=int(order_id),
        operator_user_id=int(current_user.id),
        reason=body.reason,
    )
    await db.commit()
    return SuccessResponse(
        data={"id": str(int(order.id)), "status": order.status, "rejectReason": order.reject_reason}
    )


@router.post("/admin/detection-note")
async def admin_capability_marker(_: None = Depends(PermissionChecker([ADMIN_READ]))) -> dict[str, Any]:
    """管理员注入走 processing-tasks 的 detectionMode，本路由只声明权限位仍在。"""
    return SuccessResponse(data={"injectVia": "POST /processing-tasks detectionMode"})
