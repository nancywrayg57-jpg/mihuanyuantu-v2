"""S4 batch settlement at service level (SQLite). PostgreSQL evidence is the smoke script."""

from __future__ import annotations

import io

import pytest
from PIL import Image
from sqlalchemy import func, select

from app.capabilities.realphotos.constants import TASK_DELIVERED, TASK_FAILED, TASK_PRE_REVIEW_FAILED
from app.capabilities.realphotos.models import (
    RealphotosChainPolicy,
    RealphotosCreditReservation,
    RealphotosImageTask,
)
from app.capabilities.realphotos.permissions import ROLE_ADMIN, ROLE_MERCHANT
from app.capabilities.realphotos.services.bootstrap import bootstrap_s0_accounts
from app.capabilities.realphotos.services.credit_service import RealphotosCreditService
from app.capabilities.realphotos.services.job_service import RealphotosJobService
from app.capabilities.realphotos.services.s1_catalog import S1_ENABLED_PRESETS
from app.capabilities.realphotos.services.s1_processing import RealphotosS1Service
from app.capabilities.realphotos.services.s1_recharge import RealphotosRechargeService
from app.core.exceptions import BusinessError, NotFoundError


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (1024, 768), (18, 40, 62)).save(buf, format="JPEG", quality=85)
    return buf.getvalue()


async def _funded(db):
    summary = await bootstrap_s0_accounts(db)
    tenant1 = int(summary["rp_merchant_a1"]["tenantId"])
    user_a = int(summary["rp_merchant_a1"]["userId"])
    user_b = int(summary["rp_merchant_a2"]["userId"])
    admin = int(summary["rp_admin"]["userId"])
    support = int(summary["rp_order_support"]["userId"])
    tenant2 = int(summary["rp_merchant_b1"]["tenantId"])
    user_b1 = int(summary["rp_merchant_b1"]["userId"])
    recharge = RealphotosRechargeService(db)
    order = await recharge.create_order(
        tenant_id=tenant1,
        requester_user_id=user_a,
        tier_yuan=100,
        voucher_note="批次充值",
        idempotency_key="s4-recharge",
    )
    await recharge.confirm(order_id=int(order.id), operator_user_id=support)
    return {
        "tenant1": tenant1,
        "tenant2": tenant2,
        "user_a": user_a,
        "user_b": user_b,
        "user_b1": user_b1,
        "admin": admin,
        "preset": S1_ENABLED_PRESETS[0]["code"],
        "loop": RealphotosS1Service(db),
        "credits": RealphotosCreditService(db),
    }


async def _reservation_count(db, tenant_id: int) -> int:
    return int(
        await db.scalar(
            select(func.count())
            .select_from(RealphotosCreditReservation)
            .where(RealphotosCreditReservation.tenant_id == int(tenant_id))
        )
        or 0
    )


async def _execute(db, loop: RealphotosS1Service, task_id: int):
    jobs = RealphotosJobService(db)
    claimed = await jobs.claim(
        worker_id="s4-test",
        job_kinds=("process_image",),
        payload_task_id=int(task_id),
    )
    assert claimed is not None
    done = await loop.execute_queued(claimed)
    await jobs.complete_success(job=claimed, result={"path": "s4"})
    return done


@pytest.mark.asyncio
async def test_eleventh_image_rejects_the_whole_order(db) -> None:
    ctx = await _funded(db)
    before = await _reservation_count(db, ctx["tenant1"])
    with pytest.raises(BusinessError) as exc:
        await ctx["loop"].submit_batch(
            tenant_id=ctx["tenant1"],
            owner_account_id=ctx["user_a"],
            actor_role_codes={ROLE_MERCHANT},
            asset_ids=list(range(1, 12)),
            preset_code=ctx["preset"],
            idempotency_key="s4-eleven",
        )
    assert exc.value.code == "BATCH_REJECTED"
    assert await _reservation_count(db, ctx["tenant1"]) == before


@pytest.mark.asyncio
async def test_insufficient_balance_rejects_without_reservation(db) -> None:
    ctx = await _funded(db)
    before = await _reservation_count(db, ctx["tenant2"])
    with pytest.raises(BusinessError) as exc:
        await ctx["loop"].submit_batch(
            tenant_id=ctx["tenant2"],
            owner_account_id=ctx["user_b1"],
            actor_role_codes={ROLE_MERCHANT},
            asset_ids=[1],
            preset_code=ctx["preset"],
            idempotency_key="s4-poor",
        )
    assert exc.value.code == "INSUFFICIENT_CREDITS"
    assert await _reservation_count(db, ctx["tenant2"]) == before


@pytest.mark.asyncio
async def test_same_idempotency_key_does_not_freeze_twice(db) -> None:
    ctx = await _funded(db)
    asset = await ctx["loop"].upload(
        tenant_id=ctx["tenant1"], owner_account_id=ctx["user_a"], data=_jpeg()
    )
    first_batch, first_tasks = await ctx["loop"].submit_batch(
        tenant_id=ctx["tenant1"],
        owner_account_id=ctx["user_a"],
        actor_role_codes={ROLE_MERCHANT},
        asset_ids=[int(asset.id)],
        preset_code=ctx["preset"],
        idempotency_key="s4-same",
    )
    frozen = await _reservation_count(db, ctx["tenant1"])
    again_batch, again_tasks = await ctx["loop"].submit_batch(
        tenant_id=ctx["tenant1"],
        owner_account_id=ctx["user_a"],
        actor_role_codes={ROLE_MERCHANT},
        asset_ids=[int(asset.id)],
        preset_code=ctx["preset"],
        idempotency_key="s4-same",
    )
    assert int(again_batch.id) == int(first_batch.id)
    assert [int(task.id) for task in again_tasks] == [int(task.id) for task in first_tasks]
    assert await _reservation_count(db, ctx["tenant1"]) == frozen


@pytest.mark.asyncio
async def test_precheck_failure_releases_only_that_image(db) -> None:
    ctx = await _funded(db)
    good = await ctx["loop"].upload(
        tenant_id=ctx["tenant1"], owner_account_id=ctx["user_a"], data=_jpeg()
    )
    bad = await ctx["loop"].upload(
        tenant_id=ctx["tenant1"], owner_account_id=ctx["user_a"], data=_jpeg()
    )
    await ctx["loop"].soft_delete_asset(tenant_id=ctx["tenant1"], asset_id=int(bad.id))
    _batch, tasks = await ctx["loop"].submit_batch(
        tenant_id=ctx["tenant1"],
        owner_account_id=ctx["user_a"],
        actor_role_codes={ROLE_MERCHANT},
        asset_ids=[int(good.id), int(bad.id)],
        preset_code=ctx["preset"],
        idempotency_key="s4-partial",
    )
    assert tasks[0].status != TASK_PRE_REVIEW_FAILED
    assert tasks[1].status == TASK_PRE_REVIEW_FAILED
    assert tasks[1].failure_class == "precheck"
    assert tasks[1].credit_disposition == "released_precheck"
    done = await _execute(db, ctx["loop"], int(tasks[0].id))
    assert done.status == TASK_DELIVERED
    assert done.credit_disposition == "consumed_detection_pass"
    states = {
        int(row.task_id): row.state
        for row in (
            await db.execute(
                select(RealphotosCreditReservation).where(
                    RealphotosCreditReservation.task_id.in_([int(task.id) for task in tasks])
                )
            )
        ).scalars()
    }
    assert states[int(tasks[0].id)] == "consumed"
    assert states[int(tasks[1].id)] == "released"
    policies = (
        await db.execute(
            select(RealphotosChainPolicy).where(
                RealphotosChainPolicy.chain_id.in_([int(task.chain_id) for task in tasks])
            )
        )
    ).scalars().all()
    assert len(policies) == 2
    with pytest.raises(NotFoundError):
        await ctx["loop"].get_task(
            tenant_id=ctx["tenant1"], task_id=int(tasks[0].id), owner_account_id=ctx["user_b"]
        )
    with pytest.raises(NotFoundError):
        await ctx["loop"].list_batch_tasks(
            tenant_id=ctx["tenant1"], owner_account_id=ctx["user_b"], batch_id=int(tasks[0].batch_id)
        )


@pytest.mark.asyncio
async def test_two_passes_consume_twenty_and_not_pass_keeps_jpeg(db) -> None:
    ctx = await _funded(db)
    assets = [
        await ctx["loop"].upload(tenant_id=ctx["tenant1"], owner_account_id=ctx["user_a"], data=_jpeg())
        for _ in range(2)
    ]
    _batch, passed = await ctx["loop"].submit_batch(
        tenant_id=ctx["tenant1"],
        owner_account_id=ctx["user_a"],
        actor_role_codes={ROLE_MERCHANT},
        asset_ids=[int(asset.id) for asset in assets],
        preset_code=ctx["preset"],
        idempotency_key="s4-two-pass",
    )
    for task in passed:
        done = await _execute(db, ctx["loop"], int(task.id))
        assert done.credit_disposition == "consumed_detection_pass"
    consumed = (
        await db.execute(
            select(RealphotosCreditReservation).where(
                RealphotosCreditReservation.task_id.in_([int(task.id) for task in passed]),
                RealphotosCreditReservation.state == "consumed",
            )
        )
    ).scalars().all()
    assert sum(int(row.amount) for row in consumed) == 20

    other = await ctx["loop"].upload(
        tenant_id=ctx["tenant1"], owner_account_id=ctx["user_a"], data=_jpeg()
    )
    _miss, missed = await ctx["loop"].submit_batch(
        tenant_id=ctx["tenant1"],
        owner_account_id=ctx["admin"],
        actor_role_codes={ROLE_ADMIN},
        asset_ids=[int(other.id), int(assets[0].id)],
        preset_code=ctx["preset"],
        idempotency_key="s4-not-pass",
        detection_mode="not_passed",
    )
    # The admin does not own these assets, so both images fail precheck and nothing is charged.
    assert [task.credit_disposition for task in missed] == ["released_precheck", "released_precheck"]

    owned = await ctx["loop"].upload(
        tenant_id=ctx["tenant1"], owner_account_id=ctx["admin"], data=_jpeg()
    )
    _batch2, not_passed = await ctx["loop"].submit_batch(
        tenant_id=ctx["tenant1"],
        owner_account_id=ctx["admin"],
        actor_role_codes={ROLE_ADMIN},
        asset_ids=[int(owned.id)],
        preset_code=ctx["preset"],
        idempotency_key="s4-not-pass-owned",
        detection_mode="not_passed",
    )
    done = await _execute(db, ctx["loop"], int(not_passed[0].id))
    assert done.status == TASK_FAILED
    assert done.credit_disposition == "released_detection_not_passed"
    assert done.output_object_key
    blob = get_bytes(done.output_object_key)
    assert blob[:3] == b"\xff\xd8\xff"
    picked = await ctx["loop"].selected_download_items(
        tenant_id=ctx["tenant1"],
        owner_account_id=ctx["user_a"],
        task_ids=[int(passed[0].id)],
        pack="files",
    )
    assert [item["taskId"] for item in picked] == [str(int(passed[0].id))]
    assert all(item["pack"] == "file" for item in picked)
    omitted = await ctx["loop"].selected_download_items(
        tenant_id=ctx["tenant1"],
        owner_account_id=ctx["user_a"],
        task_ids=[int(passed[0].id)],
        pack="files",
    )
    assert str(int(passed[1].id)) not in {item["taskId"] for item in omitted}
    with pytest.raises(BusinessError) as exc:
        await ctx["loop"].selected_download_items(
            tenant_id=ctx["tenant1"],
            owner_account_id=ctx["user_a"],
            task_ids=[int(passed[0].id), int(passed[1].id)],
            pack="zip",
        )
    assert exc.value.code == "ZIP_REJECTED"


def get_bytes(object_key: str) -> bytes:
    from app.capabilities.realphotos.adapters.storage import get_storage_adapter

    handle = get_storage_adapter().open_read(object_key)
    try:
        return handle.read()
    finally:
        handle.close()


@pytest.mark.asyncio
async def test_technical_failure_stays_held_without_unfreeze(db) -> None:
    ctx = await _funded(db)
    asset = await ctx["loop"].upload(
        tenant_id=ctx["tenant1"], owner_account_id=ctx["admin"], data=_jpeg()
    )
    _batch, tasks = await ctx["loop"].submit_batch(
        tenant_id=ctx["tenant1"],
        owner_account_id=ctx["admin"],
        actor_role_codes={ROLE_ADMIN},
        asset_ids=[int(asset.id)],
        preset_code=ctx["preset"],
        idempotency_key="s4-tech",
        detection_mode="technical",
    )
    done = await _execute(db, ctx["loop"], int(tasks[0].id))
    assert done.status == TASK_FAILED
    assert done.credit_disposition == "held_until_tech_support"
    assert done.output_object_key is None
    reservation = (
        await db.execute(
            select(RealphotosCreditReservation).where(
                RealphotosCreditReservation.task_id == int(done.id)
            )
        )
    ).scalar_one()
    assert reservation.state == "held"
    assert not hasattr(ctx["loop"], "unfreeze_for_support")
    merchant = await ctx["loop"].upload(
        tenant_id=ctx["tenant1"], owner_account_id=ctx["user_a"], data=_jpeg()
    )
    with pytest.raises(BusinessError) as exc:
        await ctx["loop"].submit_batch(
            tenant_id=ctx["tenant1"],
            owner_account_id=ctx["user_a"],
            actor_role_codes={ROLE_MERCHANT},
            asset_ids=[int(merchant.id)],
            preset_code=ctx["preset"],
            idempotency_key="s4-tech-merchant",
            detection_mode="technical",
        )
    assert exc.value.code == "FORBIDDEN_INJECT"
    assert (
        await db.scalar(
            select(func.count())
            .select_from(RealphotosImageTask)
            .where(RealphotosImageTask.idempotency_key == "batch:s4-tech-merchant:0")
        )
        == 0
    )
