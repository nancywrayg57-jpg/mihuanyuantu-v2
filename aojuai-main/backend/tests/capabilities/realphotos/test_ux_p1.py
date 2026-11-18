"""UX-P1 (2026-11-18): asset sorting, ticket time view, tenant detail, inbox enrichment."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.capabilities.realphotos.api.s1 import inbox
from app.capabilities.realphotos.api.s6 import list_tenants, list_tickets, tenant_detail
from app.capabilities.realphotos.models import (
    RealphotosAsset,
    RealphotosImageTask,
    RealphotosInboxMessage,
    RealphotosSupportTicket,
)
from app.capabilities.realphotos.services.bootstrap import bootstrap_s0_accounts
from app.capabilities.realphotos.services.s5_growth import RealphotosGrowthService
from app.domain.users.models import User


def _data(response) -> dict:
    return json.loads(response.body)["data"]


async def _seed(db):
    summary = await bootstrap_s0_accounts(db)
    tenant = int(summary["rp_merchant_a1"]["tenantId"])
    merchant_id = int(summary["rp_merchant_a1"]["userId"])
    tech_id = int(summary["rp_tech_support"]["userId"])
    tech = (await db.execute(select(User).where(User.id == tech_id))).scalar_one()
    merchant = (await db.execute(select(User).where(User.id == merchant_id))).scalar_one()
    return tenant, merchant, merchant_id, tech


async def _asset(db, tenant: int, user_id: int, *, name: str, size: int) -> RealphotosAsset:
    row = RealphotosAsset(
        tenant_id=tenant,
        owner_account_id=user_id,
        object_key=f"upload/{name}.jpg",
        content_type="image/jpeg",
        byte_size=size,
        width=1024,
        height=768,
        sha256="a" * 64,
        origin_kind="local_upload",
        meta_name=name,
    )
    db.add(row)
    await db.flush()
    return row


@pytest.mark.asyncio
async def test_asset_sort_and_ticket_waiting_view(db) -> None:
    tenant, _merchant, user_id, tech = await _seed(db)
    small = await _asset(db, tenant, user_id, name="small", size=1000)
    large = await _asset(db, tenant, user_id, name="large", size=9000)
    newest = await _asset(db, tenant, user_id, name="newest", size=5000)
    await db.commit()

    growth = RealphotosGrowthService(db)
    by_size, total, _, _ = await growth.list_assets_page(
        tenant_id=tenant, owner_account_id=user_id, sort="largest"
    )
    assert total == 3
    assert [int(row.id) for row in by_size] == [int(large.id), int(newest.id), int(small.id)]

    by_newest, _, _, _ = await growth.list_assets_page(
        tenant_id=tenant, owner_account_id=user_id, sort="newest"
    )
    assert int(by_newest[0].id) == int(newest.id)

    old = RealphotosSupportTicket(
        tenant_id=tenant,
        owner_account_id=user_id,
        ticket_type="image_appeal",
        status="open",
        reason="old open",
    )
    db.add(old)
    await db.flush()
    old.created_at = datetime.now(UTC) - timedelta(hours=5)
    closed = RealphotosSupportTicket(
        tenant_id=tenant,
        owner_account_id=user_id,
        ticket_type="image_appeal",
        status="resolved",
        reason="done",
    )
    db.add(closed)
    await db.flush()
    await db.commit()

    tech_ctx = SimpleNamespace(tenant_id=int(tech.tenant_id))
    payload = _data(
        await list_tickets(
            current_user=tech,
            tenant_ctx=tech_ctx,
            db=db,
            page=1,
            page_size=10,
            sort="waiting",
            _=None,
        )
    )
    assert payload["pageSize"] == 10
    assert payload["openTotal"] == 1
    assert payload["items"][0]["reason"] == "old open"


@pytest.mark.asyncio
async def test_tenant_list_and_detail_expose_status_and_stats(db) -> None:
    tenant, _merchant, user_id, tech = await _seed(db)
    await _asset(db, tenant, user_id, name="detail", size=2048)
    task = RealphotosImageTask(
        tenant_id=tenant,
        owner_account_id=user_id,
        batch_id=1,
        chain_id=1,
        asset_id=1,
        status="DELIVERED",
        preset_code="iphone-15-pro",
        idempotency_key="ux-p1-detail-task",
    )
    db.add(task)
    await db.commit()

    tech_ctx = SimpleNamespace(tenant_id=int(tech.tenant_id))
    listed = _data(
        await list_tenants(current_user=tech, tenant_ctx=tech_ctx, db=db, page=1, _=None)
    )
    row = next(item for item in listed["items"] if item["tenantId"] == tenant)
    assert row["isActive"] is True
    assert "createdAt" in row
    assert "lastActiveAt" in row
    assert row["accountCount"] >= 1

    detail = _data(
        await tenant_detail(
            target_tenant_id=tenant,
            current_user=tech,
            tenant_ctx=tech_ctx,
            db=db,
            _=None,
        )
    )
    assert detail["tenant"]["tenantId"] == tenant
    assert detail["stats"]["assetCount"] >= 1
    assert detail["stats"]["taskTotal"] >= 1
    assert detail["stats"]["taskDelivered"] >= 1
    assert "availableInteger" in detail["wallet"]
    assert detail["accounts"]


@pytest.mark.asyncio
async def test_inbox_enriches_task_number_and_asset_name(db) -> None:
    tenant, merchant, user_id, _tech = await _seed(db)
    asset = await _asset(db, tenant, user_id, name="IMG_0001", size=3000)
    task = RealphotosImageTask(
        tenant_id=tenant,
        owner_account_id=user_id,
        batch_id=11,
        chain_id=11,
        asset_id=int(asset.id),
        status="FAILED",
        preset_code="iphone-15-pro",
        idempotency_key="ux-p1-inbox-task",
        failure_class="detection_not_passed",
    )
    db.add(task)
    await db.flush()
    db.add(
        RealphotosInboxMessage(
            tenant_id=tenant,
            recipient_user_id=user_id,
            event_key=f"inbox:task:{int(task.id)}:detection_not_passed:1",
            title="检测未通过",
            body="本次检测未通过，可按建议调整后重处理。",
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
    )
    await db.commit()

    payload = _data(
        await inbox(
            current_user=merchant,
            tenant_ctx=SimpleNamespace(tenant_id=tenant),
            db=db,
            _=None,
        )
    )
    item = next(row for row in payload["items"] if row["taskId"] == str(int(task.id)))
    assert item["kind"] == "task"
    assert item["taskNo"] == 1
    assert item["batchId"] == "11"
    assert item["assetName"] == "IMG_0001"
