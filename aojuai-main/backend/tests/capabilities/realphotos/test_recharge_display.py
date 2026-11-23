"""Order-support display: tenant/account names and processed history."""

from __future__ import annotations

import pytest

from app.capabilities.realphotos.services.bootstrap import bootstrap_s0_accounts
from app.capabilities.realphotos.services.s1_recharge import RealphotosRechargeService


@pytest.mark.asyncio
async def test_pending_display_uses_tenant_and_account_not_raw_id(db) -> None:
    summary = await bootstrap_s0_accounts(db)
    tenant = int(summary["rp_merchant_a1"]["tenantId"])
    user = int(summary["rp_merchant_a1"]["userId"])
    service = RealphotosRechargeService(db)
    await service.create_order(
        tenant_id=tenant,
        requester_user_id=user,
        tier_yuan=100,
        voucher_note="display",
        idempotency_key="display-recharge-1",
    )
    rows = await service.list_pending_display(limit=10)
    row = next(item for item in rows if item["tenantId"] == str(tenant))
    assert row["tenantName"] == "蜜獾演示租户一"
    assert row["tenantCode"] == "rp-tenant-1"
    assert row["requesterUsername"] == "rp_merchant_a1"
    assert row["tenantId"] != row["requesterUsername"]


@pytest.mark.asyncio
async def test_processed_display_includes_confirmed_and_rejected(db) -> None:
    summary = await bootstrap_s0_accounts(db)
    tenant = int(summary["rp_merchant_a1"]["tenantId"])
    user = int(summary["rp_merchant_a1"]["userId"])
    support = int(summary["rp_order_support"]["userId"])
    service = RealphotosRechargeService(db)
    confirmed = await service.create_order(
        tenant_id=tenant,
        requester_user_id=user,
        tier_yuan=100,
        voucher_note="confirmed",
        idempotency_key="display-history-confirmed",
    )
    await service.confirm(order_id=int(confirmed.id), operator_user_id=support)
    rejected = await service.create_order(
        tenant_id=tenant,
        requester_user_id=user,
        tier_yuan=300,
        voucher_note="rejected",
        idempotency_key="display-history-rejected",
    )
    await service.reject(order_id=int(rejected.id), operator_user_id=support, reason="test")
    await db.flush()

    rows = await service.list_processed_display(limit=10)
    statuses = {row["id"]: row["status"] for row in rows}
    assert statuses[str(int(confirmed.id))] == "confirmed"
    assert statuses[str(int(rejected.id))] == "rejected"
    assert all(row["tenantName"] and row["requesterUsername"] for row in rows)
