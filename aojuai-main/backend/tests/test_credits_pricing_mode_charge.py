"""charge_usage_with_pricing_mode：legacy 与旧路径一致；shadow 扣旧金额并附统一结果；unified 按用量计价。"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.credits.billing import charge_usage_with_pricing_mode
from app.domain.credits.pricing_mode import set_tenant_pricing_mode
from app.domain.credits.service import CreditService
from app.domain.credits.usage import collect_usage, record_llm_usage
from app.infrastructure.database import get_db_context

# 真库集成测试：断言的是真实 PostgreSQL 的行为，没有可连接的库时跳过（守卫见 tests/conftest.py）
pytestmark = pytest.mark.requires_database


async def _run(db, *, mode: str, legacy_points: Decimal, key: str):
    svc = CreditService(db)
    account = await svc.init_user_account(tenant_id=1, user_id=1)
    if Decimal(account.balance) < Decimal("50"):
        await svc.recharge(tenant_id=1, account_id=account.id, amount=Decimal("50"), operator_id=1)
    await set_tenant_pricing_mode(db, tenant_id=1, mode=mode)
    with collect_usage(label="chat"):
        record_llm_usage(model="gpt-5.5", usage={"prompt_tokens": 1000, "completion_tokens": 1000})
        charge = await charge_usage_with_pricing_mode(
            credit_service=svc, tenant_id=1, user_id=1, legacy_points=legacy_points,
            reference_type="assistant_chat", reference_id=None, idempotency_key=key, extra={"foo": "bar"},
        )
    tx = await svc.get_transaction_by_id(tx_id=charge.transaction_id, tenant_id=1) if charge.transaction_id else None
    return charge, tx


@pytest.mark.asyncio
async def test_legacy_mode_keeps_old_amount_and_key() -> None:
    async with get_db_context() as db:
        try:
            charge, tx = await _run(db, mode="legacy", legacy_points=Decimal("2"), key="unit-mode-legacy")
            assert charge.charged and charge.amount == Decimal("2") and tx.idempotency_key == "unit-mode-legacy"
            assert "billing" not in (tx.extra or {}) and tx.extra["foo"] == "bar"
            none, _ = await _run(db, mode="legacy", legacy_points=Decimal("0"), key="unit-mode-legacy-0")
            assert none.charged is False
        finally:
            await db.rollback()


@pytest.mark.asyncio
async def test_shadow_mode_charges_legacy_and_records_unified() -> None:
    async with get_db_context() as db:
        try:
            charge, tx = await _run(db, mode="shadow", legacy_points=Decimal("2"), key="unit-mode-shadow")
            assert charge.charged and charge.amount == Decimal("2.00") and tx.idempotency_key == "unit-mode-shadow:settle"
            billing = tx.extra["billing"]
            assert billing["pricingMode"] == "shadow" and billing["legacyAmount"] == "2.00" and Decimal(billing["shadow"]["points"]) > 0
            assert billing["shadow"]["items"][0]["model"] == "gpt-5.5" and tx.extra["foo"] == "bar"
        finally:
            await db.rollback()


@pytest.mark.asyncio
async def test_unified_mode_ignores_legacy_points() -> None:
    async with get_db_context() as db:
        try:
            charge, tx = await _run(db, mode="unified", legacy_points=Decimal("2"), key="unit-mode-unified")
            assert charge.charged and charge.amount != Decimal("2.00") and Decimal(tx.extra["billing"]["points"]) == charge.amount
            assert tx.extra["billing"]["pricingMode"] == "unified"
        finally:
            await db.rollback()


@pytest.mark.asyncio
async def test_unified_replay_does_not_fall_back_to_legacy_charge() -> None:
    async with get_db_context() as db:
        try:
            svc = CreditService(db)
            account = await svc.init_user_account(tenant_id=1, user_id=1)
            if Decimal(account.balance) < Decimal("50"):
                await svc.recharge(tenant_id=1, account_id=account.id, amount=Decimal("50"), operator_id=1)
            await set_tenant_pricing_mode(db, tenant_id=1, mode="unified")
            with collect_usage(label="replay"):
                record_llm_usage(model="gpt-5.5", usage={"prompt_tokens": 1000, "completion_tokens": 1000})
                kwargs = dict(
                    credit_service=svc, tenant_id=1, user_id=1, legacy_points=Decimal("2"),
                    reference_type="unit_replay", idempotency_key="unit-unified-wrapper-replay",
                    account_id=int(account.id),
                )
                first = await charge_usage_with_pricing_mode(**kwargs)
                replay = await charge_usage_with_pricing_mode(**kwargs)
                assert replay.transaction_id == first.transaction_id
                assert replay.amount == first.amount
                assert await svc.get_transaction_by_idempotency_key(
                    tenant_id=1, idempotency_key="unit-unified-wrapper-replay"
                ) is None

                # A different root must not charge the child's already-settled usage.
                nested = await charge_usage_with_pricing_mode(
                    **{**kwargs, "idempotency_key": "unit-unified-wrapper-parent"}
                )
                assert not nested.charged
                assert nested.amount == 0
        finally:
            await db.rollback()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["legacy", "unified"])
async def test_capped_fixed_fee_records_overrun_and_replays_after_exhaustion(mode) -> None:
    async with get_db_context() as db:
        try:
            svc = CreditService(db)
            account = await svc.init_user_account(tenant_id=1, user_id=1)
            if Decimal(account.balance) < Decimal("50"):
                await svc.recharge(tenant_id=1, account_id=account.id, amount=Decimal("50"), operator_id=1)
            await set_tenant_pricing_mode(db, tenant_id=1, mode=mode)
            with collect_usage(root=True, label="fixed-fee-no-model"):
                kwargs = dict(
                    credit_service=svc, tenant_id=1, user_id=1, legacy_points=Decimal("8"),
                    reference_type="fixed_fee", idempotency_key=f"unit-capped-fixed-{mode}",
                    account_id=int(account.id),
                )
                first = await charge_usage_with_pricing_mode(**kwargs, maximum_amount=Decimal("3"))
                replay = await charge_usage_with_pricing_mode(**kwargs, maximum_amount=Decimal("0"))
                assert first.amount == replay.amount == Decimal("3")
                assert first.transaction_id == replay.transaction_id
                assert first.actual_amount == replay.actual_amount == Decimal("8")
                assert first.unbilled_overrun == replay.unbilled_overrun == Decimal("5")
                tx = await svc.get_transaction_by_id(tx_id=first.transaction_id, tenant_id=1)
                assert Decimal(tx.extra["billing"]["chargedAmount"]) == Decimal("3")
                zero = await charge_usage_with_pricing_mode(
                    **{**kwargs, "idempotency_key": f"unit-capped-fixed-zero-{mode}"}, maximum_amount=Decimal("0")
                )
                assert not zero.charged and zero.amount == 0
                assert zero.actual_amount == zero.unbilled_overrun == Decimal("8")
        finally:
            await db.rollback()


@pytest.mark.asyncio
async def test_unified_without_events_falls_back_to_flat_amount() -> None:
    """unified 下"没接计量的固定费动作"仍按旧金额扣，并标 basis=flat_fallback（灰度期可识别）。

    来自 nextjs-plugins `test_credits_module_wiring.py`；该文件另两条用例绑定 speech / ppt_master
    的业务接入点，基座没有 ppt_master，只回流这条与模块无关的原语。
    """
    async with get_db_context() as db:
        try:
            svc = CreditService(db)
            account = await svc.init_user_account(tenant_id=1, user_id=1)
            if Decimal(account.balance) < Decimal("50"):
                await svc.recharge(tenant_id=1, account_id=account.id, amount=Decimal("50"), operator_id=1)
            await set_tenant_pricing_mode(db, tenant_id=1, mode="unified")
            with collect_usage(root=True, label="unit:flat"):
                charge = await charge_usage_with_pricing_mode(
                    credit_service=svc,
                    tenant_id=1,
                    user_id=1,
                    legacy_points=Decimal("2"),
                    reference_type="unit_flat_fallback",
                    idempotency_key="unit-flat-fallback-1",
                    account_id=int(account.id),
                )
            assert charge.charged and charge.amount == Decimal("2")
            tx = await svc.get_transaction_by_id(tx_id=charge.transaction_id, tenant_id=1)
            assert tx.extra["billing"]["basis"] == "flat_fallback"
            assert tx.extra["billing"]["pricingMode"] == "unified"
            assert tx.extra["billing"]["tenantTimezone"]
        finally:
            await db.rollback()
