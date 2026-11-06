"""S1 exit path at service level (SQLite)."""

from __future__ import annotations

import io
from datetime import UTC, datetime, timedelta

import pytest
from PIL import Image
from sqlalchemy import func, select

from app.capabilities.realphotos.constants import (
    TASK_DELIVERED,
    TASK_FAILED,
    TASK_PRE_REVIEW_FAILED,
    TASK_SUBMITTED,
)
from app.capabilities.realphotos.models import RealphotosAsset, RealphotosCreditLedgerEntry
from app.capabilities.realphotos.permissions import ROLE_ADMIN, ROLE_MERCHANT
from app.capabilities.realphotos.services.bootstrap import bootstrap_s0_accounts
from app.capabilities.realphotos.services.credit_service import RealphotosCreditService
from app.capabilities.realphotos.services.job_service import RealphotosJobService
from app.capabilities.realphotos.services.s1_catalog import S1_ENABLED_PRESETS
from app.capabilities.realphotos.services.s1_processing import RealphotosS1Service
from app.capabilities.realphotos.services.s1_recharge import RealphotosRechargeService
from app.capabilities.realphotos.services.s1_upload import inspect_upload
from app.core.exceptions import AOJUException, BusinessError, NotFoundError


def _jpeg(width: int, height: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (12, 34, 56)).save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def test_upload_rejects_bad_magic_and_resolution() -> None:
    with pytest.raises(BusinessError) as bad:
        inspect_upload(b"not-an-image")
    assert bad.value.code == "UPLOAD_TYPE_REJECTED"
    with pytest.raises(BusinessError) as small:
        inspect_upload(_jpeg(100, 80))
    assert small.value.code == "UPLOAD_RESOLUTION_REJECTED"


@pytest.mark.asyncio
async def test_s1_single_image_loop(db) -> None:
    summary = await bootstrap_s0_accounts(db)
    tenant1 = int(summary["rp_merchant_a1"]["tenantId"])
    tenant2 = int(summary["rp_merchant_b1"]["tenantId"])
    user_a = int(summary["rp_merchant_a1"]["userId"])
    user_b = int(summary["rp_merchant_a2"]["userId"])
    support = int(summary["rp_order_support"]["userId"])
    admin = int(summary["rp_admin"]["userId"])
    loop = RealphotosS1Service(db)
    recharge = RealphotosRechargeService(db)
    credits = RealphotosCreditService(db)

    assert len(S1_ENABLED_PRESETS) == 3

    before = await db.scalar(
        select(func.count()).select_from(RealphotosAsset).where(RealphotosAsset.tenant_id == tenant1)
    )
    with pytest.raises(BusinessError):
        await loop.upload(tenant_id=tenant1, owner_account_id=user_a, data=b"hello")
    after = await db.scalar(
        select(func.count()).select_from(RealphotosAsset).where(RealphotosAsset.tenant_id == tenant1)
    )
    assert before == after

    order = await recharge.create_order(
        tenant_id=tenant1,
        requester_user_id=user_a,
        tier_yuan=100,
        voucher_note="转账备注-测试",
        idempotency_key="recharge-a",
    )
    rejected = await recharge.create_order(
        tenant_id=tenant1,
        requester_user_id=user_a,
        tier_yuan=300,
        voucher_note="另一笔",
        idempotency_key="recharge-reject",
    )
    with pytest.raises(BusinessError):
        await recharge.reject(order_id=int(rejected.id), operator_user_id=support, reason="  ")
    await recharge.reject(order_id=int(rejected.id), operator_user_id=support, reason="凭证不符")
    assert rejected.status == "rejected"
    assert int(rejected.credit_points) == 3150
    await recharge.confirm(order_id=int(order.id), operator_user_id=support)
    wallet = await credits.get_wallet(tenant_id=tenant1)
    assert wallet["availableInteger"] == "1000"

    asset = await loop.upload(tenant_id=tenant1, owner_account_id=user_a, data=_jpeg(1024, 768))
    with pytest.raises(BusinessError):
        await loop.submit_single(
            tenant_id=tenant1,
            owner_account_id=user_a,
            actor_role_codes={ROLE_MERCHANT},
            asset_id=int(asset.id),
            preset_code=S1_ENABLED_PRESETS[0]["code"],
            idempotency_key="inject-denied",
            detection_mode="not_passed",
        )
    task = await loop.submit_single(
        tenant_id=tenant1,
        owner_account_id=user_a,
        actor_role_codes={ROLE_MERCHANT},
        asset_id=int(asset.id),
        preset_code=S1_ENABLED_PRESETS[0]["code"],
        idempotency_key="task-pass",
    )
    assert task.status == TASK_SUBMITTED
    with pytest.raises(BusinessError):
        await loop.soft_delete_asset(tenant_id=tenant1, asset_id=int(asset.id))

    jobs = RealphotosJobService(db)
    claimed = await jobs.claim(worker_id="s1-test", job_kinds=("process_image",))
    assert claimed is not None
    finished_task = await loop.execute_queued(claimed)
    await jobs.complete_success(job=claimed, result={"ok": True})
    assert finished_task.status == TASK_DELIVERED
    report = await loop.detection_payload(tenant_id=tenant1, task_id=int(finished_task.id))
    assert report is not None
    assert set(report) >= {
        "noise",
        "depthOfField",
        "lighting",
        "colorRealism",
        "overallRealism",
        "total_score",
        "passed",
    }
    assert report["accepted"] is True
    wallet = await credits.get_wallet(tenant_id=tenant1)
    assert wallet["availableInteger"] == "990"
    assert wallet["reservedInteger"] == "0"
    consume = (
        await db.execute(
            select(RealphotosCreditLedgerEntry).where(
                RealphotosCreditLedgerEntry.event_key == f"consume:task:{int(finished_task.id)}"
            )
        )
    ).scalar_one()
    assert int(consume.operator_user_id) == user_a

    _ctype, body = await loop.read_object_for_gateway(
        tenant_id=tenant1, object_key=str(finished_task.output_object_key)
    )
    assert body.startswith(b"\xff\xd8\xff")
    finished_task.output_expires_at = datetime.now(UTC) - timedelta(hours=1)
    await db.flush()
    with pytest.raises(AOJUException) as expired:
        await loop.read_object_for_gateway(
            tenant_id=tenant1, object_key=str(finished_task.output_object_key)
        )
    assert expired.value.status_code == 410
    with pytest.raises(NotFoundError):
        await loop.get_task(tenant_id=tenant2, task_id=int(finished_task.id))

    await loop.soft_delete_asset(tenant_id=tenant1, asset_id=int(asset.id))

    asset_b = await loop.upload(tenant_id=tenant1, owner_account_id=user_b, data=_jpeg(768, 1024))
    task_b = await loop.submit_single(
        tenant_id=tenant1,
        owner_account_id=user_b,
        actor_role_codes={ROLE_MERCHANT},
        asset_id=int(asset_b.id),
        preset_code=S1_ENABLED_PRESETS[1]["code"],
        idempotency_key="task-b",
    )
    claimed_b = await jobs.claim(worker_id="s1-test-b", job_kinds=("process_image",))
    await loop.execute_queued(claimed_b)
    await jobs.complete_success(job=claimed_b, result={"ok": True})
    consume_b = (
        await db.execute(
            select(RealphotosCreditLedgerEntry).where(
                RealphotosCreditLedgerEntry.event_key == f"consume:task:{int(task_b.id)}"
            )
        )
    ).scalar_one()
    assert int(consume_b.operator_user_id) == user_b
    wallet = await credits.get_wallet(tenant_id=tenant1)
    assert wallet["availableInteger"] == "980"

    asset_r = await loop.upload(tenant_id=tenant1, owner_account_id=user_a, data=_jpeg(1024, 768))
    await loop.submit_single(
        tenant_id=tenant1,
        owner_account_id=user_a,
        actor_role_codes={ROLE_ADMIN},
        asset_id=int(asset_r.id),
        preset_code=S1_ENABLED_PRESETS[2]["code"],
        idempotency_key="task-reject",
        pre_review_mode="reject",
    )
    claimed_r = await jobs.claim(worker_id="s1-reject", job_kinds=("process_image",))
    done_r = await loop.execute_queued(claimed_r)
    assert done_r.status == TASK_PRE_REVIEW_FAILED
    assert (await credits.get_wallet(tenant_id=tenant1))["reservedInteger"] == "0"

    asset_n = await loop.upload(tenant_id=tenant1, owner_account_id=user_a, data=_jpeg(1024, 768))
    task_n = await loop.submit_single(
        tenant_id=tenant1,
        owner_account_id=user_a,
        actor_role_codes={ROLE_ADMIN},
        asset_id=int(asset_n.id),
        preset_code=S1_ENABLED_PRESETS[0]["code"],
        idempotency_key="task-not-passed",
        detection_mode="not_passed",
    )
    claimed_n = await jobs.claim(worker_id="s1-np", job_kinds=("process_image",))
    done_n = await loop.execute_queued(claimed_n)
    assert done_n.status == TASK_FAILED
    assert done_n.output_object_key
    report_n = await loop.detection_payload(tenant_id=tenant1, task_id=int(task_n.id))
    assert report_n["passed"] is False
    assert report_n["accepted"] is False

    asset_t = await loop.upload(tenant_id=tenant1, owner_account_id=user_a, data=_jpeg(1024, 768))
    await loop.submit_single(
        tenant_id=tenant1,
        owner_account_id=user_a,
        actor_role_codes={ROLE_ADMIN},
        asset_id=int(asset_t.id),
        preset_code=S1_ENABLED_PRESETS[0]["code"],
        idempotency_key="task-tech",
        detection_mode="technical",
    )
    claimed_t = await jobs.claim(worker_id="s1-tech", job_kinds=("process_image",))
    done_t = await loop.execute_queued(claimed_t)
    assert done_t.failure_class == "technical"
    assert done_t.output_object_key is None
    assert done_t.credit_disposition == "held_until_tech_support"
    held = await credits.get_wallet(tenant_id=tenant1)
    assert int(held["reservedInteger"]) == 10
    messages = await loop.list_inbox(tenant_id=tenant1, recipient_user_id=user_a)
    assert messages
    assert admin
