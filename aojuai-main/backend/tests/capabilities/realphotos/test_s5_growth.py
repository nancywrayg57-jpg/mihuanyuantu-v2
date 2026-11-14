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
from app.core.exceptions import BusinessError, NotFoundError, UnauthorizedError
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
async def test_gateway_reads_generation_asset_bytes(db):
    """BROWSER-E2E-FIX F8: generation/* must resolve via RealphotosAsset, not path allowlist alone."""
    ctx = await _funded(db)
    task = await ctx["growth"].submit_generation(
        tenant_id=ctx["tenant"],
        owner_account_id=ctx["user"],
        mode="text_to_image",
        positive_prompt="网关可读",
        width=256,
        height=256,
        quantity=1,
        idempotency_key="gen-gateway-f8",
        provider="fixture",
    )
    items = await ctx["growth"].list_generation_items(tenant_id=ctx["tenant"], task_id=int(task.id))
    stored = [item for item in items if item.status == "stored" and item.asset_id]
    assert len(stored) == 1
    asset = await db.get(RealphotosAsset, int(stored[0].asset_id))
    assert asset is not None
    assert "/generation/" in asset.object_key
    content_type, body = await ctx["loop"].read_object_for_gateway(
        tenant_id=ctx["tenant"], object_key=asset.object_key
    )
    assert content_type.startswith("image/")
    assert body.startswith(b"\xff\xd8\xff") or body.startswith(b"\x89PNG")
    with pytest.raises(NotFoundError):
        await ctx["loop"].read_object_for_gateway(
            tenant_id=ctx["tenant"] + 999_001, object_key=asset.object_key
        )
    img2 = await ctx["growth"].submit_generation(
        tenant_id=ctx["tenant"],
        owner_account_id=ctx["user"],
        mode="image_to_image",
        positive_prompt="网关可读图生图",
        width=256,
        height=256,
        quantity=1,
        idempotency_key="gen-gateway-f8-i2i",
        provider="fixture",
        reference_bytes=_jpeg(),
    )
    i2i_items = await ctx["growth"].list_generation_items(
        tenant_id=ctx["tenant"], task_id=int(img2.id)
    )
    i2i_stored = [item for item in i2i_items if item.status == "stored" and item.asset_id]
    assert len(i2i_stored) == 1
    i2i_asset = await db.get(RealphotosAsset, int(i2i_stored[0].asset_id))
    assert i2i_asset is not None and "/generation/" in i2i_asset.object_key
    _ct2, body2 = await ctx["loop"].read_object_for_gateway(
        tenant_id=ctx["tenant"], object_key=i2i_asset.object_key
    )
    assert body2.startswith(b"\xff\xd8\xff") or body2.startswith(b"\x89PNG")


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
            payload="\n".join(f"https://example.invalid/{index}.jpg" for index in range(101)),
            tenant_id=ctx["tenant"],
            owner_account_id=ctx["user"],
        )
    assert too_many.value.code == "INPUT_INVALID"
    with pytest.raises(BusinessError) as unconfigured:
        await ctx["growth"].import_resources(
            payload="https://example.invalid/a.jpg",
            tenant_id=ctx["tenant"],
            owner_account_id=ctx["user"],
        )
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
        await ctx["growth"].import_resources(
            payload=json.dumps(hundred),
            tenant_id=ctx["tenant"],
            owner_account_id=ctx["user"],
        )
    assert pasted.value.code == "SERVICE_NOT_CONFIGURED"
    with pytest.raises(BusinessError) as pasted_file:
        await ctx["growth"].import_resource_file(
            raw=json.dumps(hundred).encode(),
            tenant_id=ctx["tenant"],
            owner_account_id=ctx["user"],
        )
    assert pasted_file.value.code == "SERVICE_NOT_CONFIGURED"
    with pytest.raises(BusinessError) as too_many_json:
        await ctx["growth"].import_resource_file(
            raw=json.dumps(hundred + [hundred[0]]).encode(),
            tenant_id=ctx["tenant"],
            owner_account_id=ctx["user"],
        )
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


@pytest.mark.asyncio
async def test_generation_seed_capability_disables_gap_and_keeps_backstop(db):
    """T3: gpt-image-2 gap-not-sent is not editable; a forced seed still returns SEED_UNSUPPORTED."""
    import inspect

    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import select as sa_select

    from app.api.deps import TenantContext, get_current_user, get_db, get_tenant_context
    from app.capabilities.realphotos.api.s5 import create_generation, generation_capabilities
    from app.capabilities.realphotos.api.s5 import router as s5_router
    from app.capabilities.realphotos.models.supplier_contract import RealphotosProviderContract
    from app.capabilities.realphotos.services.supplier_config import (
        RealphotosSupplierConfigService,
        seed_capability_supported,
    )

    ctx = await _funded(db)
    config = RealphotosSupplierConfigService(db)
    view = await config.generation_seed_capability()
    assert view == {
        "duty": "generation",
        "modelId": "gpt-image-2",
        "seed": "gap-not-sent",
        "seedSupported": False,
        "seedNote": view["seedNote"],
    }
    assert view["seedSupported"] is False
    assert "gpt-image-2" in view["seedNote"]
    assert "gap-not-sent" in view["seedNote"]
    dumped = json.dumps(view)
    assert "sk-" not in dumped
    assert "baseUrl" not in view
    assert "apiKey" not in view
    assert "credentialRef" not in view
    assert "keyPrefix" not in view

    row = (
        await db.execute(sa_select(RealphotosProviderContract).where(RealphotosProviderContract.duty == "generation"))
    ).scalar_one()
    assert "gpt-image-2" in row.gap_note
    assert "gap-not-sent" in row.gap_note
    row.enabled = True
    await db.flush()

    with pytest.raises(BusinessError) as gap:
        await ctx["growth"].submit_generation(
            tenant_id=ctx["tenant"],
            owner_account_id=ctx["user"],
            mode="text_to_image",
            positive_prompt="带种子",
            width=256,
            height=256,
            quantity=1,
            idempotency_key="gen-seed-gap",
            seed="42",
        )
    assert gap.value.code == "SEED_UNSUPPORTED"

    with pytest.raises(BusinessError) as fixture_seed:
        await ctx["growth"].submit_generation(
            tenant_id=ctx["tenant"],
            owner_account_id=ctx["user"],
            mode="text_to_image",
            positive_prompt="夹具种子",
            width=256,
            height=256,
            quantity=1,
            idempotency_key="gen-seed-fixture",
            provider="fixture",
            seed="7",
        )
    assert fixture_seed.value.code == "SEED_UNSUPPORTED"

    caps = dict(row.capabilities or {})
    caps["adminManaged"] = True
    caps["seed"] = "supported"
    row.capabilities = caps
    await db.flush()
    opened = await config.generation_seed_capability()
    assert opened["seed"] == "supported"
    assert opened["seedSupported"] is True
    assert seed_capability_supported({"seed": "supported"}) is True
    assert seed_capability_supported({"seed": "gap-not-sent"}) is False
    assert seed_capability_supported({"seed": "unsupported"}) is False
    assert seed_capability_supported({"seed": "false"}) is False
    assert seed_capability_supported({}) is False
    assert seed_capability_supported({"seed": True}) is True

    caps["seed"] = "gap-not-sent"
    row.capabilities = caps
    row.enabled = True
    await db.flush()

    app = FastAPI()
    app.include_router(s5_router, prefix="/api/v1/realphotos")

    async def _user():
        return type("UserStub", (), {"id": ctx["user"], "is_superuser": False})()

    async def _tenant():
        return TenantContext(
            tenant_id=ctx["tenant"],
            is_superuser=False,
            user_tenant_id=ctx["tenant"],
        )

    async def _session():
        yield db

    async def _allow():
        return None

    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_tenant_context] = _tenant
    app.dependency_overrides[get_db] = _session
    for endpoint in (generation_capabilities, create_generation):
        for param in inspect.signature(endpoint).parameters.values():
            dependency = getattr(param.default, "dependency", None)
            if dependency is not None and dependency not in {get_current_user, get_db, get_tenant_context}:
                app.dependency_overrides[dependency] = _allow

    @app.exception_handler(BusinessError)
    async def _business_error(_request, exc: BusinessError):
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=exc.status_code, content={"code": exc.code, "message": exc.message})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        listed = await client.get("/api/v1/realphotos/generation-capabilities")
        assert listed.status_code == 200, listed.text
        body = listed.json()["data"]
        assert body["seedSupported"] is False
        assert body["seed"] == "gap-not-sent"
        assert body["modelId"] == "gpt-image-2"
        assert "baseUrl" not in body
        assert "apiKey" not in body
        forced = await client.post(
            "/api/v1/realphotos/generation-tasks",
            json={
                "mode": "text_to_image",
                "positivePrompt": "强制种子",
                "width": 256,
                "height": 256,
                "quantity": 1,
                "idempotencyKey": "gen-seed-http",
                "seed": "99",
            },
        )
        assert forced.status_code == 400, forced.text
        assert forced.json()["code"] == "SEED_UNSUPPORTED"
