"""S5 growth rules on SQLite. PostgreSQL evidence is the smoke script."""

from __future__ import annotations

import io
import json

import pytest
from PIL import Image
from sqlalchemy import func, select

from app.capabilities.realphotos.models import (
    RealphotosAsset,
    RealphotosCreditReservation,
    RealphotosImageTask,
)
from app.capabilities.realphotos.permissions import ROLE_ADMIN, ROLE_MERCHANT, ROLE_ORDER_SUPPORT
from app.capabilities.realphotos.services.bootstrap import bootstrap_s0_accounts
from app.capabilities.realphotos.services.credit_service import RealphotosCreditService
from app.capabilities.realphotos.services.s1_processing import RealphotosS1Service
from app.capabilities.realphotos.services.s1_recharge import RealphotosRechargeService
from app.capabilities.realphotos.services.s5_growth import RealphotosGrowthService
from app.core.exceptions import BusinessError, UnauthorizedError
from app.domain.auth.api_key_service import ApiKeyService


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (1024, 768), (18, 40, 62)).save(buf, format="JPEG", quality=85)
    return buf.getvalue()


async def _funded(db):
    summary = await bootstrap_s0_accounts(db)
    tenant1 = int(summary["rp_merchant_a1"]["tenantId"])
    user_a = int(summary["rp_merchant_a1"]["userId"])
    support = int(summary["rp_order_support"]["userId"])
    admin = int(summary["rp_admin"]["userId"])
    recharge = RealphotosRechargeService(db)
    order = await recharge.create_order(
        tenant_id=tenant1,
        requester_user_id=user_a,
        tier_yuan=100,
        voucher_note="s5",
        idempotency_key="s5-recharge",
    )
    await recharge.confirm(order_id=int(order.id), operator_user_id=support)
    return {
        "tenant": tenant1,
        "user": user_a,
        "admin": admin,
        "support": support,
        "growth": RealphotosGrowthService(db),
        "credits": RealphotosCreditService(db),
        "loop": RealphotosS1Service(db),
    }


async def _available(credits: RealphotosCreditService, tenant_id: int) -> int:
    wallet = await credits.get_wallet(tenant_id=tenant_id)
    return int(wallet["availableInteger"])


async def _reserved(credits: RealphotosCreditService, tenant_id: int) -> int:
    wallet = await credits.get_wallet(tenant_id=tenant_id)
    return int(wallet["reservedInteger"])


@pytest.mark.asyncio
async def test_generation_stores_without_processing_or_reservation(db):
    ctx = await _funded(db)
    before = await _available(ctx["credits"], ctx["tenant"])
    task = await ctx["growth"].submit_generation(
        tenant_id=ctx["tenant"],
        owner_account_id=ctx["user"],
        mode="text_to_image",
        positive_prompt="一只獾",
        width=256,
        height=256,
        quantity=2,
        idempotency_key="gen-two",
        provider="fixture",
        fail_indexes={1},
    )
    items = await ctx["growth"].list_generation_items(tenant_id=ctx["tenant"], task_id=int(task.id))
    stored = [item for item in items if item.status == "stored"]
    failed = [item for item in items if item.status == "failed"]
    assert len(stored) == 1 and int(stored[0].credits_consumed) == 10
    assert len(failed) == 1 and failed[0].asset_id is None and int(failed[0].credits_consumed) == 0
    assert await _available(ctx["credits"], ctx["tenant"]) == before - 10
    assert await _reserved(ctx["credits"], ctx["tenant"]) == 0
    reservations = int(
        await db.scalar(
            select(func.count()).select_from(RealphotosCreditReservation).where(
                RealphotosCreditReservation.tenant_id == ctx["tenant"]
            )
        )
        or 0
    )
    assert reservations == 0
    asset_ids = [int(item.asset_id) for item in stored]
    assert await ctx["growth"].processing_task_count_for_assets(
        tenant_id=ctx["tenant"], asset_ids=asset_ids
    ) == 0
    again = await ctx["growth"].submit_generation(
        tenant_id=ctx["tenant"],
        owner_account_id=ctx["user"],
        mode="text_to_image",
        positive_prompt="一只獾",
        width=256,
        height=256,
        quantity=2,
        idempotency_key="gen-two",
        provider="fixture",
    )
    assert int(again.id) == int(task.id)
    assert await _available(ctx["credits"], ctx["tenant"]) == before - 10


@pytest.mark.asyncio
async def test_generation_rejects_eleventh_and_unconfigured_and_low_balance(db):
    ctx = await _funded(db)
    assets_before = int(
        await db.scalar(select(func.count()).select_from(RealphotosAsset)) or 0
    )
    with pytest.raises(BusinessError) as eleventh:
        await ctx["growth"].submit_generation(
            tenant_id=ctx["tenant"],
            owner_account_id=ctx["user"],
            mode="text_to_image",
            positive_prompt="太多",
            width=256,
            height=256,
            quantity=11,
            idempotency_key="gen-11",
            provider="fixture",
        )
    assert eleventh.value.code == "INPUT_INVALID"
    with pytest.raises(BusinessError) as missing:
        await ctx["growth"].submit_generation(
            tenant_id=ctx["tenant"],
            owner_account_id=ctx["user"],
            mode="text_to_image",
            positive_prompt="未配置",
            width=256,
            height=256,
            quantity=1,
            idempotency_key="gen-live",
        )
    assert missing.value.code == "SERVICE_NOT_CONFIGURED"
    poor = await bootstrap_s0_accounts(db)
    tenant2 = int(poor["rp_merchant_b1"]["tenantId"])
    user_b = int(poor["rp_merchant_b1"]["userId"])
    with pytest.raises(BusinessError) as broke:
        await ctx["growth"].submit_generation(
            tenant_id=tenant2,
            owner_account_id=user_b,
            mode="text_to_image",
            positive_prompt="没钱",
            width=256,
            height=256,
            quantity=1,
            idempotency_key="gen-poor",
            provider="fixture",
        )
    assert broke.value.code == "INSUFFICIENT_CREDITS"
    assets_after = int(await db.scalar(select(func.count()).select_from(RealphotosAsset)) or 0)
    assert assets_after == assets_before
    assert await db.scalar(select(func.count()).select_from(RealphotosImageTask)) in (0, None) or int(
        await db.scalar(select(func.count()).select_from(RealphotosImageTask)) or 0
    ) == 0


@pytest.mark.asyncio
async def test_image_to_image_temp_reference_is_not_stored(db):
    ctx = await _funded(db)
    before = int(await db.scalar(select(func.count()).select_from(RealphotosAsset)) or 0)
    await ctx["growth"].submit_generation(
        tenant_id=ctx["tenant"],
        owner_account_id=ctx["user"],
        mode="image_to_image",
        positive_prompt="改光线",
        width=1024,
        height=768,
        quantity=1,
        idempotency_key="img2img",
        provider="fixture",
        reference_bytes=_jpeg(),
    )
    after = int(await db.scalar(select(func.count()).select_from(RealphotosAsset)) or 0)
    assert after == before + 1


@pytest.mark.asyncio
async def test_prompt_optimization_and_template_do_not_share_generation_freeze(db):
    ctx = await _funded(db)
    before = await _available(ctx["credits"], ctx["tenant"])
    ok = await ctx["growth"].optimize_prompt(
        tenant_id=ctx["tenant"],
        owner_account_id=ctx["user"],
        original_text="商品图",
        provider="fixture",
        succeed=True,
    )
    assert ok.status == "succeeded"
    assert await _available(ctx["credits"], ctx["tenant"]) == before - 1
    assert await _reserved(ctx["credits"], ctx["tenant"]) == 0
    confirmed = await ctx["growth"].confirm_optimization(
        tenant_id=ctx["tenant"],
        owner_account_id=ctx["user"],
        optimization_id=int(ok.id),
    )
    assert confirmed.confirmed is True
    assert await _available(ctx["credits"], ctx["tenant"]) == before - 1
    failed = await ctx["growth"].optimize_prompt(
        tenant_id=ctx["tenant"],
        owner_account_id=ctx["user"],
        original_text="失败这句",
        provider="fixture",
        succeed=False,
    )
    assert failed.status == "failed"
    assert await _available(ctx["credits"], ctx["tenant"]) == before - 1
    assert await _reserved(ctx["credits"], ctx["tenant"]) == 0
    with pytest.raises(BusinessError) as live:
        await ctx["growth"].optimize_prompt(
            tenant_id=ctx["tenant"],
            owner_account_id=ctx["user"],
            original_text="没有供应商",
        )
    assert live.value.code == "SERVICE_NOT_CONFIGURED"
    template = await ctx["growth"].save_template(
        tenant_id=ctx["tenant"],
        owner_account_id=ctx["user"],
        actor_role_codes={ROLE_MERCHANT},
        name="常用",
        mode="general",
        positive_prompt="白底",
    )
    assert template.scope == "tenant"
    assert await _available(ctx["credits"], ctx["tenant"]) == before - 1
    with pytest.raises(BusinessError):
        await ctx["growth"].save_template(
            tenant_id=ctx["tenant"],
            owner_account_id=ctx["support"],
            actor_role_codes={ROLE_ORDER_SUPPORT},
            name="客服",
            mode="general",
            positive_prompt="不行",
        )
    with pytest.raises(BusinessError):
        await ctx["growth"].save_template(
            tenant_id=ctx["tenant"],
            owner_account_id=ctx["user"],
            actor_role_codes={ROLE_MERCHANT},
            name="平台",
            mode="general",
            positive_prompt="不行",
            scope="platform",
        )
    platform = await ctx["growth"].save_template(
        tenant_id=ctx["tenant"],
        owner_account_id=ctx["admin"],
        actor_role_codes={ROLE_ADMIN},
        name="平台",
        mode="text_to_image",
        positive_prompt="可以",
        scope="platform",
    )
    assert platform.scope == "platform"


@pytest.mark.asyncio
async def test_url_import_rejects_101_and_stays_unconfigured(db):
    ctx = await _funded(db)
    before = int(await db.scalar(select(func.count()).select_from(RealphotosAsset)) or 0)
    with pytest.raises(BusinessError) as too_many:
        await ctx["growth"].import_resources(
            payload="\n".join(f"https://example.invalid/{index}.jpg" for index in range(101))
        )
    assert too_many.value.code == "INPUT_INVALID"
    with pytest.raises(BusinessError) as unconfigured:
        await ctx["growth"].import_resources(payload="https://example.invalid/a.jpg")
    assert unconfigured.value.code == "SERVICE_NOT_CONFIGURED"
    hundred = [
        {
            "name": str(index),
            "seller": "s",
            "sku": "k",
            "asn": "a",
            "price": "1",
            "website": "https://example.invalid",
            "url": f"https://example.invalid/{index}.jpg",
        }
        for index in range(100)
    ]
    with pytest.raises(BusinessError) as pasted:
        await ctx["growth"].import_resources(payload=json.dumps(hundred))
    assert pasted.value.code == "SERVICE_NOT_CONFIGURED"
    with pytest.raises(BusinessError) as pasted_file:
        await ctx["growth"].import_resource_file(raw=json.dumps(hundred).encode())
    assert pasted_file.value.code == "SERVICE_NOT_CONFIGURED"
    with pytest.raises(BusinessError) as too_many_json:
        await ctx["growth"].import_resource_file(raw=json.dumps(hundred + [hundred[0]]).encode())
    assert too_many_json.value.code == "INPUT_INVALID"
    after = int(await db.scalar(select(func.count()).select_from(RealphotosAsset)) or 0)
    assert after == before


@pytest.mark.asyncio
async def test_image_processing_key_allows_processing_paths_only(db):
    ctx = await _funded(db)
    _key, plaintext = await ApiKeyService.create_key(
        db,
        ctx["tenant"],
        ctx["user"],
        name="erp",
        scopes=["image_processing"],
    )
    allowed = await ApiKeyService.validate_key(db, plaintext, "/api/v1/realphotos/processing-batches")
    assert allowed.scopes == ["image_processing"]
    with pytest.raises(UnauthorizedError):
        await ApiKeyService.validate_key(db, plaintext, "/api/v1/realphotos/generation-tasks")
    with pytest.raises(UnauthorizedError):
        await ApiKeyService.validate_key(db, plaintext, "/api/v1/realphotos/resource-imports")
    with pytest.raises(BusinessError):
        await ApiKeyService.create_key(
            db, ctx["tenant"], ctx["user"], name="wild", scopes=["*"]
        )
    with pytest.raises(BusinessError):
        await ApiKeyService.create_key(
            db, ctx["tenant"], ctx["user"], name="empty", scopes=[]
        )
    await ApiKeyService.revoke_key(db, ctx["tenant"], ctx["user"], int(_key.id))
    with pytest.raises(UnauthorizedError):
        await ApiKeyService.validate_key(db, plaintext, "/api/v1/realphotos/assets")
