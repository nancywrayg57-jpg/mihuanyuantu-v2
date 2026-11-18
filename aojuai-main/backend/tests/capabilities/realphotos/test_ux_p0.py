"""UX-P0 (2026-11-18): business key management, ledger detail, tenant task numbers."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.capabilities.realphotos.api.s5 import list_business_keys, rotate_business_key
from app.capabilities.realphotos.api.wallet import get_ledger
from app.capabilities.realphotos.models import (
    RealphotosGenerationTask,
    RealphotosImageTask,
)
from app.capabilities.realphotos.services.bootstrap import bootstrap_s0_accounts
from app.capabilities.realphotos.services.credit_service import RealphotosCreditService
from app.capabilities.realphotos.services.s1_recharge import RealphotosRechargeService
from app.capabilities.realphotos.services.task_numbering import (
    generation_task_no_map,
    processing_task_no_map,
)
from app.domain.auth.api_key_service import ApiKeyService
from app.domain.users.models import User


def _data(response) -> dict:
    return json.loads(response.body)["data"]


def _request():
    return SimpleNamespace(state=SimpleNamespace(auth_via_api_key=False))


async def _merchant(db):
    summary = await bootstrap_s0_accounts(db)
    tenant = int(summary["rp_merchant_a1"]["tenantId"])
    user_id = int(summary["rp_merchant_a1"]["userId"])
    user = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one()
    support = int(summary["rp_order_support"]["userId"])
    recharge = RealphotosRechargeService(db)
    order = await recharge.create_order(
        tenant_id=tenant,
        requester_user_id=user_id,
        tier_yuan=100,
        voucher_note="ux-p0",
        idempotency_key="ux-p0-recharge",
    )
    await recharge.confirm(order_id=int(order.id), operator_user_id=support)
    await db.commit()
    return tenant, user, user_id


@pytest.mark.asyncio
async def test_business_key_list_filters_scope_and_rotate_replaces(db) -> None:
    tenant, user, user_id = await _merchant(db)
    image_key, _ = await ApiKeyService.create_key(
        db, tenant, user_id, name="ERP 对接", scopes=["image_processing"]
    )
    await ApiKeyService.create_key(
        db, tenant, user_id, name="培训同步", scopes=["/api/v1/training"]
    )
    await db.commit()

    listed = _data(
        await list_business_keys(
            current_user=user, request=_request(), db=db, _=None
        )
    )
    assert [item["name"] for item in listed["items"]] == ["ERP 对接"]
    assert listed["items"][0]["keyPrefix"] == image_key.key_prefix
    assert listed["items"][0]["maskedKey"].startswith(image_key.key_prefix)
    assert listed["items"][0]["status"] == "active"
    assert listed["items"][0]["lastUsedAt"] is None

    rotated = _data(
        await rotate_business_key(
            key_id=int(image_key.id),
            current_user=user,
            request=_request(),
            db=db,
            _=None,
        )
    )
    assert rotated["rotatedFrom"] == str(int(image_key.id))
    assert rotated["name"] == "ERP 对接"
    assert rotated["apiKey"].startswith(rotated["keyPrefix"])
    assert str(int(image_key.id)) != rotated["id"]

    keys = await ApiKeyService.list_keys(db, tenant, user_id)
    image_keys = [key for key in keys if "image_processing" in (key.scopes or [])]
    assert len(image_keys) == 1
    assert int(image_keys[0].id) == int(rotated["id"])


@pytest.mark.asyncio
async def test_ledger_exposes_reserved_delta_balance_and_task_no(db) -> None:
    tenant, _user, user_id = await _merchant(db)
    task = RealphotosImageTask(
        tenant_id=tenant,
        owner_account_id=user_id,
        batch_id=1,
        chain_id=7,
        asset_id=1,
        status="SUBMITTED",
        preset_code="iphone-15-pro",
        idempotency_key="ux-p0-task-1",
    )
    db.add(task)
    await db.flush()

    credits = RealphotosCreditService(db)
    await credits.freeze(
        tenant_id=tenant,
        amount=10,
        operator_user_id=user_id,
        event_key="ux-p0-freeze",
        reference={"taskId": int(task.id), "images": 1},
    )
    # 批次结算只记 chainId，流水仍应能回溯到链内任务号。
    await credits.consume_reserved(
        tenant_id=tenant,
        amount=10,
        operator_user_id=user_id,
        event_key="ux-p0-consume",
        reference={"chainId": int(task.chain_id), "images": 1},
    )
    await db.commit()

    payload = _data(
        await get_ledger(
            tenant_ctx=SimpleNamespace(tenant_id=tenant),
            db=db,
            page=1,
            page_size=20,
            _=None,
        )
    )
    rows = payload["list"]
    consume = next(row for row in rows if row["entryType"] == "consume")
    assert consume["deltaAvailable"] == "0"
    assert consume["deltaReserved"] == "-10"
    assert consume["afterReserved"] == "0"
    assert consume["beforeReserved"] == "10"
    assert consume["taskNo"] == 1
    assert consume["taskKind"] == "processing"
    assert consume["taskId"] == str(int(task.id))
    assert consume["chainId"] == "7"


@pytest.mark.asyncio
async def test_tenant_numbers_are_per_tenant_and_per_kind(db) -> None:
    tenant, _user, user_id = await _merchant(db)
    tasks = []
    for index in range(3):
        task = RealphotosImageTask(
            tenant_id=tenant,
            owner_account_id=user_id,
            batch_id=index + 1,
            chain_id=index + 1,
            asset_id=index + 1,
            status="SUBMITTED",
            preset_code="iphone-15-pro",
            idempotency_key=f"ux-p0-number-{index}",
        )
        db.add(task)
        tasks.append(task)
    generation = RealphotosGenerationTask(
        tenant_id=tenant,
        owner_account_id=user_id,
        mode="text_to_image",
        quantity=1,
        width=1024,
        height=768,
        positive_prompt="一只獾",
        provider="fixture",
        idempotency_key="ux-p0-generation-1",
    )
    db.add(generation)
    await db.flush()

    image_map = await processing_task_no_map(
        db, tenant_id=tenant, task_ids=[tasks[0].id, tasks[2].id]
    )
    assert image_map == {int(tasks[0].id): 1, int(tasks[2].id): 3}
    generation_map = await generation_task_no_map(
        db, tenant_id=tenant, task_ids=[generation.id]
    )
    assert generation_map == {int(generation.id): 1}

    # 另一个租户从 1 开始，不串号。
    other = RealphotosImageTask(
        tenant_id=tenant + 100,
        owner_account_id=user_id,
        batch_id=1,
        chain_id=1,
        asset_id=1,
        status="SUBMITTED",
        preset_code="iphone-15-pro",
        idempotency_key="ux-p0-number-other",
    )
    db.add(other)
    await db.flush()
    assert await processing_task_no_map(
        db, tenant_id=tenant + 100, task_ids=[other.id]
    ) == {int(other.id): 1}
