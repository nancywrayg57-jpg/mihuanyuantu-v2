"""S1 HTTP surface: presets, upload, single submit, recharge, inbox."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.api.deps import CurrentUser, DBSession, PermissionChecker, TenantCtx
from app.capabilities.realphotos.permissions import (
    ADMIN_READ,
    GATEWAY_READ,
    JOBS_ENQUEUE,
    ORDER_SUPPORT_READ,
    ROLE_ADMIN,
    ROLE_ORDER_SUPPORT,
    TECH_DESK_READ,
    WALLET_READ,
    WORKSPACE_READ,
)
from app.capabilities.realphotos.services.s1_processing import RealphotosS1Service
from app.capabilities.realphotos.services.s1_recharge import (
    RealphotosRechargeService,
    is_recharge_inbox_event,
)
from app.core.response import SuccessResponse
from app.domain.roles.models import Role
from app.domain.users.models import UserRole

router = APIRouter()


def _order_support_only(roles: set[str]) -> bool:
    return ROLE_ORDER_SUPPORT in roles and ROLE_ADMIN not in roles and "admin" not in roles


class SubmitBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    asset_id: int = Field(alias="assetId")
    preset_code: str = Field(alias="presetCode")
    idempotency_key: str = Field(alias="idempotencyKey")
    pre_review_mode: str | None = Field(default=None, alias="preReviewMode")
    detection_mode: str = Field(default="gemini", alias="detectionMode")


class BatchBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    asset_ids: list[int] = Field(alias="assetIds")
    preset_code: str = Field(alias="presetCode")
    idempotency_key: str = Field(alias="idempotencyKey")
    pre_review_mode: str | None = Field(default=None, alias="preReviewMode")
    detection_mode: str = Field(default="gemini", alias="detectionMode")


class SelectedDownloadBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    task_ids: list[int] = Field(alias="taskIds")
    pack: str = "files"


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
        "copiedFrom": str(int(task.copied_from_task_id)) if task.copied_from_task_id else None,
        "billingMode": str(getattr(task, "billing_mode", "normal") or "normal"),
    }


class CopyBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    idempotency_key: str = Field(alias="idempotencyKey")
    detection_mode: str = Field(default="pass", alias="detectionMode")


@router.get("/presets")
async def list_presets(
    db: DBSession,
    _: None = Depends(PermissionChecker([WALLET_READ, WORKSPACE_READ, ADMIN_READ])),
) -> dict[str, Any]:
    from app.capabilities.realphotos.services.s6_ops import RealphotosOpsService

    items = await RealphotosOpsService(db).list_enabled_presets()
    return SuccessResponse(data={"items": items, "enabledCount": len(items)})


@router.post("/assets")
async def upload_asset(
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    file: UploadFile = File(...),
    name: str | None = Form(default=None),
    seller: str | None = Form(default=None),
    sku: str | None = Form(default=None),
    asn: str | None = Form(default=None),
    price: str | None = Form(default=None),
    website: str | None = Form(default=None),
    url: str | None = Form(default=None),
    _: None = Depends(PermissionChecker([GATEWAY_READ])),
) -> dict[str, Any]:
    from app.capabilities.realphotos.services.asset_naming import compose_list_filename, meta_from_asset

    data = await file.read()
    asset = await RealphotosS1Service(db).upload(
        tenant_id=int(tenant_ctx.tenant_id),
        owner_account_id=int(current_user.id),
        data=data,
        meta_name=name,
        meta_seller=seller,
        meta_sku=sku,
        meta_asn=asn,
        meta_price=price,
        meta_website=website,
        meta_url=url,
    )
    await db.commit()
    naming = compose_list_filename(
        meta=meta_from_asset(asset), asset_id=int(asset.id), origin_kind=str(asset.origin_kind)
    )
    return SuccessResponse(
        data={
            "id": str(int(asset.id)),
            "contentType": asset.content_type,
            "byteSize": int(asset.byte_size),
            "width": int(asset.width),
            "height": int(asset.height),
            "objectKey": asset.object_key,
            "displayName": naming["displayName"],
            "degraded": naming["degraded"] == "true",
        }
    )


@router.post("/processing-tasks/{task_id}/copy")
async def copy_processing_task(
    task_id: int,
    body: CopyBody,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([JOBS_ENQUEUE])),
) -> dict[str, Any]:
    task = await RealphotosS1Service(db).copy_processing_task(
        tenant_id=int(tenant_ctx.tenant_id),
        owner_account_id=int(current_user.id),
        source_task_id=int(task_id),
        idempotency_key=body.idempotency_key,
        detection_mode=body.detection_mode,
    )
    await db.commit()
    return SuccessResponse(data=_task_payload(task))


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
        pre_review_mode=await _customer_pre_review(db, body.pre_review_mode),
        detection_mode=body.detection_mode,
    )
    await db.commit()
    return SuccessResponse(data=_task_payload(task))


async def _customer_pre_review(db: DBSession, explicit: str | None) -> str:
    if explicit:
        return explicit
    from app.capabilities.realphotos.services.supplier_config import RealphotosSupplierConfigService

    row = await RealphotosSupplierConfigService(db).enabled("pre_review")
    return "live" if row is not None else "pass"


def _actor_roles(roles: set[str]) -> set[str]:
    if "admin" in roles:
        roles.add(ROLE_ADMIN)
    return roles


@router.post("/processing-batches")
async def submit_batch(
    body: BatchBody,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([JOBS_ENQUEUE])),
) -> dict[str, Any]:
    roles = _actor_roles(await _role_codes(db, int(current_user.id), int(tenant_ctx.tenant_id)))
    service = RealphotosS1Service(db)
    batch, tasks = await service.submit_batch(
        tenant_id=int(tenant_ctx.tenant_id),
        owner_account_id=int(current_user.id),
        actor_role_codes=roles,
        asset_ids=list(body.asset_ids),
        preset_code=body.preset_code,
        idempotency_key=body.idempotency_key,
        pre_review_mode=await _customer_pre_review(db, body.pre_review_mode),
        detection_mode=body.detection_mode,
    )
    await db.commit()
    payloads = []
    for task in tasks:
        payload = _task_payload(task)
        payload["detection"] = await service.detection_payload(
            tenant_id=int(tenant_ctx.tenant_id), task_id=int(task.id)
        )
        payloads.append(payload)
    return SuccessResponse(
        data={"batchId": str(int(batch.id)), "imageCount": int(batch.image_count), "tasks": payloads}
    )


@router.get("/processing-tasks")
async def list_processing_tasks(
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    page: int = 1,
    page_size: int = 10,
    status: str | None = None,
    _: None = Depends(PermissionChecker([JOBS_ENQUEUE])),
) -> dict[str, Any]:
    service = RealphotosS1Service(db)
    rows, total = await service.list_processing_tasks(
        tenant_id=int(tenant_ctx.tenant_id),
        owner_account_id=int(current_user.id),
        page=page,
        page_size=page_size,
        status=status,
    )
    payloads = []
    for task in rows:
        payload = _task_payload(task)
        payload["detection"] = await service.detection_payload(
            tenant_id=int(tenant_ctx.tenant_id), task_id=int(task.id)
        )
        payload["createdAt"] = task.created_at.isoformat() if task.created_at else None
        payloads.append(payload)
    return SuccessResponse(
        data={
            "items": payloads,
            "page": max(1, int(page or 1)),
            "pageSize": min(50, max(1, int(page_size or 10))),
            "total": total,
        }
    )


@router.get("/processing-batches/{batch_id}")
async def get_batch(
    batch_id: int,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([JOBS_ENQUEUE])),
) -> dict[str, Any]:
    service = RealphotosS1Service(db)
    tasks = await service.list_batch_tasks(
        tenant_id=int(tenant_ctx.tenant_id),
        owner_account_id=int(current_user.id),
        batch_id=int(batch_id),
    )
    payloads = []
    for task in tasks:
        payload = _task_payload(task)
        payload["detection"] = await service.detection_payload(
            tenant_id=int(tenant_ctx.tenant_id), task_id=int(task.id)
        )
        payloads.append(payload)
    return SuccessResponse(data={"batchId": str(int(batch_id)), "tasks": payloads})


@router.post("/processing-tasks/selected-downloads")
async def selected_downloads(
    body: SelectedDownloadBody,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([JOBS_ENQUEUE])),
) -> dict[str, Any]:
    items = await RealphotosS1Service(db).selected_download_items(
        tenant_id=int(tenant_ctx.tenant_id),
        owner_account_id=int(current_user.id),
        task_ids=list(body.task_ids),
        pack=body.pack,
    )
    return SuccessResponse(data={"items": items, "pack": "files"})


@router.get("/processing-tasks/{task_id}")
async def get_task(
    task_id: int,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([JOBS_ENQUEUE])),
) -> dict[str, Any]:
    service = RealphotosS1Service(db)
    task = await service.get_task(
        tenant_id=int(tenant_ctx.tenant_id),
        task_id=int(task_id),
        owner_account_id=int(current_user.id),
    )
    payload = _task_payload(task)
    payload["detection"] = await service.detection_payload(
        tenant_id=int(tenant_ctx.tenant_id), task_id=int(task.id)
    )
    payload["gpsWrite"] = await service.gps_write_summary(
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
    _: None = Depends(
        PermissionChecker([WALLET_READ, WORKSPACE_READ, ORDER_SUPPORT_READ, TECH_DESK_READ, ADMIN_READ])
    ),
) -> dict[str, Any]:
    rows = await RealphotosS1Service(db).list_inbox(
        tenant_id=int(tenant_ctx.tenant_id),
        recipient_user_id=int(current_user.id),
    )
    roles = await _role_codes(db, int(current_user.id), int(tenant_ctx.tenant_id))
    if _order_support_only(roles):
        rows = [row for row in rows if is_recharge_inbox_event(row.event_key, row.title)]
    unread = sum(1 for row in rows if row.read_at is None)
    return SuccessResponse(
        data={
            "items": [
                {
                    "id": str(int(row.id)),
                    "title": row.title,
                    "body": row.body,
                    "readAt": row.read_at.isoformat() if row.read_at else None,
                    "createdAt": row.created_at.isoformat() if row.created_at else None,
                    "eventKey": row.event_key,
                }
                for row in rows
            ],
            "unreadCount": unread,
            "scope": "recharge_only" if _order_support_only(roles) else "all",
        }
    )


@router.post("/inbox/mark-all-read")
async def mark_inbox_all_read(
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(
        PermissionChecker([WALLET_READ, WORKSPACE_READ, ORDER_SUPPORT_READ, TECH_DESK_READ, ADMIN_READ])
    ),
) -> dict[str, Any]:
    service = RealphotosS1Service(db)
    roles = await _role_codes(db, int(current_user.id), int(tenant_ctx.tenant_id))
    if _order_support_only(roles):
        rows = await service.list_inbox(
            tenant_id=int(tenant_ctx.tenant_id),
            recipient_user_id=int(current_user.id),
        )
        changed = 0
        for row in rows:
            if not is_recharge_inbox_event(row.event_key, row.title):
                continue
            if row.read_at is None:
                await service.mark_inbox_read(
                    tenant_id=int(tenant_ctx.tenant_id),
                    recipient_user_id=int(current_user.id),
                    message_id=int(row.id),
                )
                changed += 1
        await db.commit()
        return SuccessResponse(data={"marked": int(changed)})
    changed = await service.mark_inbox_all_read(
        tenant_id=int(tenant_ctx.tenant_id),
        recipient_user_id=int(current_user.id),
    )
    await db.commit()
    return SuccessResponse(data={"marked": int(changed)})


@router.post("/inbox/{message_id}/read")
async def mark_inbox_read(
    message_id: int,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(
        PermissionChecker([WALLET_READ, WORKSPACE_READ, ORDER_SUPPORT_READ, TECH_DESK_READ, ADMIN_READ])
    ),
) -> dict[str, Any]:
    service = RealphotosS1Service(db)
    roles = await _role_codes(db, int(current_user.id), int(tenant_ctx.tenant_id))
    if _order_support_only(roles):
        rows = await service.list_inbox(
            tenant_id=int(tenant_ctx.tenant_id),
            recipient_user_id=int(current_user.id),
        )
        target = next((row for row in rows if int(row.id) == int(message_id)), None)
        if target is None or not is_recharge_inbox_event(target.event_key, target.title):
            from app.core.exceptions import ForbiddenError

            raise ForbiddenError(message="订单客服只能操作充值类通知")
    row = await service.mark_inbox_read(
        tenant_id=int(tenant_ctx.tenant_id),
        recipient_user_id=int(current_user.id),
        message_id=int(message_id),
    )
    await db.commit()
    return SuccessResponse(
        data={"id": str(int(row.id)), "readAt": row.read_at.isoformat() if row.read_at else None}
    )


@router.post("/inbox/{message_id}/resend")
async def resend_inbox(
    message_id: int,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(
        PermissionChecker([WALLET_READ, WORKSPACE_READ, ORDER_SUPPORT_READ, TECH_DESK_READ, ADMIN_READ])
    ),
) -> dict[str, Any]:
    service = RealphotosS1Service(db)
    roles = await _role_codes(db, int(current_user.id), int(tenant_ctx.tenant_id))
    if _order_support_only(roles):
        rows = await service.list_inbox(
            tenant_id=int(tenant_ctx.tenant_id),
            recipient_user_id=int(current_user.id),
        )
        target = next((row for row in rows if int(row.id) == int(message_id)), None)
        if target is None or not is_recharge_inbox_event(target.event_key, target.title):
            from app.core.exceptions import ForbiddenError

            raise ForbiddenError(message="订单客服只能补发充值类通知")
    row = await service.resend_inbox(
        tenant_id=int(tenant_ctx.tenant_id),
        recipient_user_id=int(current_user.id),
        message_id=int(message_id),
    )
    await db.commit()
    return SuccessResponse(
        data={
            "id": str(int(row.id)),
            "title": row.title,
            "body": row.body,
            "readAt": None,
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


class RedoBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    enabled: bool
    score_threshold: int = Field(alias="scoreThreshold")
    extra_rounds: int = Field(alias="extraRounds")


class ReprocessBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    preset_code: str = Field(alias="presetCode")
    idempotency_key: str = Field(alias="idempotencyKey")


@router.get("/redo-settings")
async def get_redo(
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([WALLET_READ, WORKSPACE_READ])),
) -> dict[str, Any]:
    row = await RealphotosS1Service(db).get_redo_setting(tenant_id=int(tenant_ctx.tenant_id))
    await db.commit()
    return SuccessResponse(
        data={
            "enabled": bool(row.enabled),
            "scoreThreshold": int(row.score_threshold),
            "extraRounds": int(row.extra_rounds),
        }
    )


@router.put("/redo-settings")
async def put_redo(
    body: RedoBody,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([WALLET_READ, WORKSPACE_READ])),
) -> dict[str, Any]:
    row = await RealphotosS1Service(db).save_redo_setting(
        tenant_id=int(tenant_ctx.tenant_id),
        enabled=body.enabled,
        threshold=body.score_threshold,
        extra_rounds=body.extra_rounds,
    )
    await db.commit()
    return SuccessResponse(
        data={
            "enabled": bool(row.enabled),
            "scoreThreshold": int(row.score_threshold),
            "extraRounds": int(row.extra_rounds),
        }
    )


@router.post("/processing-tasks/{task_id}/retry")
async def retry_task(
    task_id: int,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([JOBS_ENQUEUE])),
) -> dict[str, Any]:
    task = await RealphotosS1Service(db).retry_technical(
        tenant_id=int(tenant_ctx.tenant_id),
        task_id=int(task_id),
        owner_account_id=int(current_user.id),
    )
    await db.commit()
    return SuccessResponse(data=_task_payload(task))


@router.post("/processing-tasks/{task_id}/reprocess")
async def reprocess_task(
    task_id: int,
    body: ReprocessBody,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
    _: None = Depends(PermissionChecker([JOBS_ENQUEUE])),
) -> dict[str, Any]:
    roles = await _role_codes(db, int(current_user.id), int(tenant_ctx.tenant_id))
    task = await RealphotosS1Service(db).reprocess(
        tenant_id=int(tenant_ctx.tenant_id),
        owner_account_id=int(current_user.id),
        actor_role_codes=roles,
        source_task_id=int(task_id),
        preset_code=body.preset_code,
        idempotency_key=body.idempotency_key,
    )
    await db.commit()
    return SuccessResponse(data=_task_payload(task))


@router.post("/admin/detection-note")
async def admin_capability_marker(_: None = Depends(PermissionChecker([ADMIN_READ]))) -> dict[str, Any]:
    """管理员注入走 processing-tasks 的 detectionMode，本路由只声明权限位仍在。"""
    return SuccessResponse(data={"injectVia": "POST /processing-tasks detectionMode"})
