"""PRD §9.3 / AD-007: library delete purges object copies; orphan cleanup."""

from __future__ import annotations

import io
from datetime import UTC, datetime

import pytest
from PIL import Image
from sqlalchemy import select

from app.capabilities.realphotos.adapters.storage import get_storage_adapter
from app.capabilities.realphotos.constants import (
    JOB_KIND_LIBRARY_ORPHAN_CLEANUP,
    SEED_OBJECT_KEY,
)
from app.capabilities.realphotos.models import RealphotosAsset
from app.capabilities.realphotos.permissions import ROLE_ADMIN
from app.capabilities.realphotos.services.bootstrap import bootstrap_s0_accounts
from app.capabilities.realphotos.services.job_service import RealphotosJobService
from app.capabilities.realphotos.services.s1_catalog import S1_ENABLED_PRESETS
from app.capabilities.realphotos.services.s1_processing import RealphotosS1Service
from app.capabilities.realphotos.services.s1_recharge import RealphotosRechargeService
from app.capabilities.realphotos.worker_roles import CLEANUP_JOB_KINDS
from app.core.exceptions import BusinessError


def _jpeg(width: int = 1024, height: int = 768) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (20, 40, 60)).save(buf, format="JPEG", quality=85)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_soft_delete_asset_purges_object_copy(db) -> None:
    summary = await bootstrap_s0_accounts(db)
    tenant = int(summary["rp_merchant_a1"]["tenantId"])
    user = int(summary["rp_merchant_a1"]["userId"])
    support = int(summary["rp_order_support"]["userId"])
    loop = RealphotosS1Service(db)
    recharge = RealphotosRechargeService(db)
    order = await recharge.create_order(
        tenant_id=tenant,
        requester_user_id=user,
        tier_yuan=100,
        voucher_note="purge-ut",
        idempotency_key="purge-recharge",
    )
    await recharge.confirm(order_id=int(order.id), operator_user_id=support)
    asset = await loop.upload(tenant_id=tenant, owner_account_id=user, data=_jpeg())
    key = str(asset.object_key)
    storage = get_storage_adapter()
    assert storage.exists(key)
    await loop.soft_delete_asset(tenant_id=tenant, asset_id=int(asset.id))
    await db.flush()
    assert asset.deleted_at is not None
    assert storage.exists(key) is False


@pytest.mark.asyncio
async def test_soft_delete_blocked_while_running_keeps_file(db) -> None:
    summary = await bootstrap_s0_accounts(db)
    tenant = int(summary["rp_merchant_a1"]["tenantId"])
    user = int(summary["rp_merchant_a1"]["userId"])
    support = int(summary["rp_order_support"]["userId"])
    loop = RealphotosS1Service(db)
    recharge = RealphotosRechargeService(db)
    order = await recharge.create_order(
        tenant_id=tenant,
        requester_user_id=user,
        tier_yuan=100,
        voucher_note="inuse-ut",
        idempotency_key="inuse-recharge",
    )
    await recharge.confirm(order_id=int(order.id), operator_user_id=support)
    asset = await loop.upload(tenant_id=tenant, owner_account_id=user, data=_jpeg())
    key = str(asset.object_key)
    await loop.submit_single(
        tenant_id=tenant,
        owner_account_id=user,
        actor_role_codes={ROLE_ADMIN},
        asset_id=int(asset.id),
        preset_code=S1_ENABLED_PRESETS[0]["code"],
        idempotency_key="inuse-task",
        detection_mode="pass",
        pre_review_mode="pass",
    )
    with pytest.raises(BusinessError) as exc:
        await loop.soft_delete_asset(tenant_id=tenant, asset_id=int(asset.id))
    assert exc.value.code == "ASSET_IN_USE"
    assert get_storage_adapter().exists(key) is True


@pytest.mark.asyncio
async def test_cleanup_library_orphans_soft_and_disk(db) -> None:
    summary = await bootstrap_s0_accounts(db)
    tenant = int(summary["rp_merchant_a1"]["tenantId"])
    user = int(summary["rp_merchant_a1"]["userId"])
    support = int(summary["rp_order_support"]["userId"])
    loop = RealphotosS1Service(db)
    recharge = RealphotosRechargeService(db)
    order = await recharge.create_order(
        tenant_id=tenant,
        requester_user_id=user,
        tier_yuan=100,
        voucher_note="orphan-ut",
        idempotency_key="orphan-recharge",
    )
    await recharge.confirm(order_id=int(order.id), operator_user_id=support)
    live = await loop.upload(tenant_id=tenant, owner_account_id=user, data=_jpeg())
    soft = await loop.upload(tenant_id=tenant, owner_account_id=user, data=_jpeg(1100, 800))
    storage = get_storage_adapter()
    soft_key = str(soft.object_key)
    live_key = str(live.object_key)
    # Simulate legacy soft-delete without purge.
    soft.deleted_at = datetime.now(UTC)
    await db.flush()
    assert storage.exists(soft_key)
    orphan_key = f"tenant/{tenant}/upload/orphan-no-row.jpg"
    storage.put_bytes(orphan_key, _jpeg(640, 480), content_type="image/jpeg")
    output_key = f"tenant/{tenant}/output/keep-me.jpg"
    storage.put_bytes(output_key, _jpeg(640, 480), content_type="image/jpeg")
    storage.ensure_seed_file()
    assert storage.exists(SEED_OBJECT_KEY)

    result = await loop.cleanup_library_orphans()
    assert result["status"] == "ok"
    assert int(result["soft_deleted_purged"]) >= 1
    assert int(result["disk_orphans_purged"]) >= 1
    assert storage.exists(soft_key) is False
    assert storage.exists(orphan_key) is False
    assert storage.exists(live_key) is True
    assert storage.exists(output_key) is True
    assert storage.exists(SEED_OBJECT_KEY) is True
    # Live row still undeleted.
    row = (
        await db.execute(select(RealphotosAsset).where(RealphotosAsset.id == int(live.id)))
    ).scalar_one()
    assert row.deleted_at is None


def test_library_orphan_cleanup_in_cleanup_whitelist() -> None:
    assert JOB_KIND_LIBRARY_ORPHAN_CLEANUP in CLEANUP_JOB_KINDS


@pytest.mark.asyncio
async def test_enqueue_library_orphan_cleanup_job(db) -> None:
    summary = await bootstrap_s0_accounts(db)
    tenant = int(summary["rp_admin"]["tenantId"])
    admin = int(summary["rp_admin"]["userId"])
    job = await RealphotosJobService(db).enqueue_cleanup(
        tenant_id=tenant,
        owner_account_id=admin,
        job_kind=JOB_KIND_LIBRARY_ORPHAN_CLEANUP,
        payload={"source": "unit"},
    )
    assert job.job_kind == JOB_KIND_LIBRARY_ORPHAN_CLEANUP
