"""AUDIT-REMAIN-CLOSEOUT：A1 冻结禁获取；A2 扩展名辅助由前端单测覆盖。"""

from __future__ import annotations

import io

import pytest
from PIL import Image
from sqlalchemy import select

from app.capabilities.realphotos.models import RealphotosAsset, RealphotosMerchantProfile
from app.capabilities.realphotos.services.bootstrap import bootstrap_s0_accounts
from app.capabilities.realphotos.services.s1_processing import RealphotosS1Service
from app.capabilities.realphotos.services.s5_growth import RealphotosGrowthService
from app.core.exceptions import BusinessError


def _jpeg(color: tuple[int, int, int] = (12, 34, 56), size: tuple[int, int] = (1280, 960)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def _png(color: tuple[int, int, int] = (10, 20, 30), size: tuple[int, int] = (1280, 960)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


async def _merchant(db):
    summary = await bootstrap_s0_accounts(db)
    return {
        "tenant": int(summary["rp_merchant_a1"]["tenantId"]),
        "user": int(summary["rp_merchant_a1"]["userId"]),
        "s1": RealphotosS1Service(db),
        "growth": RealphotosGrowthService(db),
    }


async def _set_frozen(db, *, tenant_id: int, user_id: int, frozen: bool) -> None:
    profile = (
        await db.execute(
            select(RealphotosMerchantProfile).where(
                RealphotosMerchantProfile.tenant_id == int(tenant_id),
                RealphotosMerchantProfile.user_id == int(user_id),
            )
        )
    ).scalar_one()
    profile.pre_review_frozen = bool(frozen)
    await db.flush()


@pytest.mark.asyncio
async def test_a1_frozen_blocks_upload_batch_and_import(db) -> None:
    ctx = await _merchant(db)
    tenant = ctx["tenant"]
    user = ctx["user"]

    before = await ctx["s1"].upload(tenant_id=tenant, owner_account_id=user, data=_jpeg((1, 2, 3)))
    assert before.id

    await _set_frozen(db, tenant_id=tenant, user_id=user, frozen=True)

    with pytest.raises(BusinessError) as upload_err:
        await ctx["s1"].upload(tenant_id=tenant, owner_account_id=user, data=_jpeg((4, 5, 6)))
    assert upload_err.value.code == "ACCOUNT_FROZEN"

    with pytest.raises(BusinessError) as batch_err:
        await ctx["s1"].upload_batch(
            tenant_id=tenant, owner_account_id=user, files=[_jpeg((7, 8, 9))]
        )
    assert batch_err.value.code == "ACCOUNT_FROZEN"

    with pytest.raises(BusinessError) as import_err:
        await ctx["growth"].import_resources(
            payload=["https://example.invalid/images/x.jpg"],
            tenant_id=tenant,
            owner_account_id=user,
        )
    assert import_err.value.code == "ACCOUNT_FROZEN"

    # 列表/已有资源仍可读（不因冻结消失）
    rows = (
        await db.execute(
            select(RealphotosAsset).where(
                RealphotosAsset.tenant_id == tenant,
                RealphotosAsset.owner_account_id == user,
                RealphotosAsset.deleted_at.is_(None),
            )
        )
    ).scalars().all()
    assert any(int(row.id) == int(before.id) for row in rows)

    await _set_frozen(db, tenant_id=tenant, user_id=user, frozen=False)
    restored = await ctx["s1"].upload(tenant_id=tenant, owner_account_id=user, data=_jpeg((11, 12, 13)))
    assert restored.id


@pytest.mark.asyncio
async def test_a2_png_upload_keeps_png_content_type(db) -> None:
    """后端保留源 content_type；前端按 contentType 映射扩展名（见 FE 单测）。"""
    ctx = await _merchant(db)
    asset = await ctx["s1"].upload(
        tenant_id=ctx["tenant"], owner_account_id=ctx["user"], data=_png()
    )
    assert asset.content_type == "image/png"


@pytest.mark.asyncio
async def test_b2_lease_deferred_and_busy_code(db) -> None:
    from app.capabilities.realphotos.services.copy_execution_guard import (
        ACCOUNT_SPEND_BUSY,
        LEASE_TTL_DEFERRED,
        RealphotosCopyExecutionGuardService,
    )
    from app.capabilities.realphotos.services.credit_service import RealphotosCreditService
    from app.capabilities.realphotos.services.s1_recharge import RealphotosRechargeService

    assert LEASE_TTL_DEFERRED is True
    summary = await bootstrap_s0_accounts(db)
    tenant = int(summary["rp_merchant_a1"]["tenantId"])
    user = int(summary["rp_merchant_a1"]["userId"])
    support = int(summary["rp_order_support"]["userId"])
    recharge = RealphotosRechargeService(db)
    order = await recharge.create_order(
        tenant_id=tenant,
        requester_user_id=user,
        tier_yuan=100,
        voucher_note="audit-b2",
        idempotency_key="audit-b2-recharge",
    )
    await recharge.confirm(order_id=int(order.id), operator_user_id=support)
    guard_svc = RealphotosCopyExecutionGuardService(db)
    await guard_svc.force_clear_active(tenant_id=tenant, owner_account_id=user)
    guard = await guard_svc.acquire(tenant_id=tenant, owner_account_id=user, batch_id=42)
    assert guard.lease_until is None
    with pytest.raises(BusinessError) as busy:
        await RealphotosCreditService(db).freeze(
            tenant_id=tenant,
            amount=10,
            operator_user_id=user,
            event_key="audit-b2-freeze",
        )
    assert busy.value.code == ACCOUNT_SPEND_BUSY
    assert busy.value.code != "COPY_LATCH_ACTIVE"
