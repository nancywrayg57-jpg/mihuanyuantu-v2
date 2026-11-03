"""统一结算 primitive：三模式即时结算、不足 0.01 免费、硬预算预留 → 完成只退差额 / 超限不追扣 / 全退，幂等。"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.domain.credits.pricing import PriceItem
from app.domain.credits.service import CreditService
from app.domain.credits.settlement import SettlementContext, complete, refund_all, reserve, settle_immediate
from app.domain.credits.usage import UsageCollector, UsageEvent, collect_usage, record_llm_usage, record_unit_usage
from app.infrastructure.database import get_db_context

# 真库集成测试：断言的是真实 PostgreSQL 的行为，没有可连接的库时跳过（守卫见 tests/conftest.py）
pytestmark = pytest.mark.requires_database

ITEMS = [
    PriceItem(item_type="llm", match_key="*", input_points_per_1k="1", output_points_per_1k="1"),
    PriceItem(item_type="llm", match_key="gpt-5.5", input_points_per_1k="1", output_points_per_1k="4"),
    PriceItem(item_type="image", match_key="*", points_per_unit="2"),
]
VERSION = "v-test"


async def _setup(db, *, balance: Decimal = Decimal("100")):
    svc = CreditService(db)
    account = await svc.init_user_account(tenant_id=1, user_id=1)
    if Decimal(account.balance) < balance:
        await svc.recharge(tenant_id=1, account_id=account.id, amount=balance, operator_id=1)
    return svc, account


def _ctx(base: str) -> SettlementContext:
    return SettlementContext(tenant_id=1, payer_user_id=1, reference_type="unit_settlement", idempotency_base=base, remark="unit")


@pytest.mark.asyncio
async def test_capped_settlement_replay_uses_original_amount_after_budget_exhausted():
    async with get_db_context() as db:
        try:
            svc, account = await _setup(db)
            before = Decimal(account.balance)
            with collect_usage(label="first"):
                record_llm_usage(model="gpt-5.5", usage={"prompt_tokens": 1000, "completion_tokens": 1000})
                first = await settle_immediate(
                    svc, _ctx("unit:capped:replay"), mode="unified", price_items=ITEMS,
                    price_version=VERSION, maximum_amount=Decimal("2"),
                )
            with collect_usage(label="replay"):
                record_llm_usage(model="gpt-5.5", usage={"prompt_tokens": 1000, "completion_tokens": 1000})
                ctx = _ctx("unit:capped:replay")
                replay = await settle_immediate(
                    svc, ctx, mode="unified", price_items=ITEMS,
                    price_version=VERSION, maximum_amount=Decimal("0"),
                )
            assert replay.amount == first.amount == Decimal("2")
            assert replay.transaction_id == first.transaction_id
            assert replay.unbilled_overrun == first.unbilled_overrun == Decimal("3")
            assert ctx.account_id == account.id
            assert Decimal(account.balance) == before - Decimal("2")
        finally:
            await db.rollback()


@pytest.mark.asyncio
async def test_zero_budget_preserves_unbilled_usage_without_debit():
    async with get_db_context() as db:
        try:
            svc, account = await _setup(db)
            before = Decimal(account.balance)
            with collect_usage(label="no-budget"):
                record_llm_usage(model="gpt-5.5", usage={"prompt_tokens": 1000, "completion_tokens": 1000})
                result = await settle_immediate(
                    svc, _ctx("unit:capped:zero"), mode="unified", price_items=ITEMS,
                    price_version=VERSION, maximum_amount=Decimal("0"),
                )
            assert result.free and not result.charged
            assert result.billing["actualAmount"] == "5.00"
            assert result.unbilled_overrun == Decimal("5")
            assert result.billing["chargedAmount"] == "0"
            assert Decimal(account.balance) == before
        finally:
            await db.rollback()


@pytest.mark.asyncio
async def test_immediate_unified_charges_priced_points_and_attaches_billing() -> None:
    async with get_db_context() as db:
        try:
            svc, account = await _setup(db)
            before = Decimal(account.balance)
            with collect_usage(label="chat"):
                record_llm_usage(model="gpt-5.5", usage={"prompt_tokens": 1000, "completion_tokens": 500}, api_type="responses", web_search_calls=0)
                result = await settle_immediate(svc, _ctx("unit:imm:1"), mode="unified", price_items=ITEMS, price_version=VERSION)
            assert result.charged and result.amount == Decimal("3.00") and result.unified_points == Decimal("3.00")
            tx = await svc.get_transaction_by_id(tenant_id=1, tx_id=result.transaction_id)
            assert tx.extra["billing"]["pricingMode"] == "unified" and tx.extra["billing"]["priceVersion"] == VERSION
            assert tx.extra["billing"]["items"][0]["model"] == "gpt-5.5" and tx.extra["billing"]["byModel"]["gpt-5.5"]["calls"] == 1
            assert Decimal((await svc.get_account_by_id(tenant_id=1, account_id=account.id)).balance) == before - Decimal("3.00")
        finally:
            await db.rollback()


@pytest.mark.asyncio
async def test_settlement_records_tenant_timezone_and_applied_rate_band() -> None:
    scheduled_item = PriceItem(
        item_type="llm",
        match_key="scheduled-model",
        input_points_per_1k="1",
        output_points_per_1k="1",
        rate_schedule={
            "timezone": "tenant",
            "defaultBand": "off_peak",
            "bands": [{"key": "peak", "multiplier": "2", "weekdays": [1, 2, 3, 4, 5], "windows": [["09:00", "12:00"]]}],
        },
    )
    collector = UsageCollector(label="scheduled")
    collector.add(
        UsageEvent(
            kind="llm",
            model="scheduled-model",
            input_tokens=1000,
            occurred_at=datetime(2026, 8, 31, 1, 30, tzinfo=UTC),
        )
    )
    ctx = SettlementContext(
        tenant_id=1,
        payer_user_id=1,
        reference_type="unit_settlement",
        idempotency_base="unit:scheduled:1",
        tenant_timezone="Asia/Shanghai",
    )

    async with get_db_context() as db:
        try:
            svc, _ = await _setup(db)
            result = await settle_immediate(
                svc,
                ctx,
                mode="unified",
                price_items=[scheduled_item],
                price_version=VERSION,
                collector=collector,
            )

            line = result.billing["items"][0]
            assert result.amount == Decimal("2.00")
            assert result.billing["tenantTimezone"] == "Asia/Shanghai"
            assert line["rateMultiplier"] == "2"
            assert line["rateBand"] == "peak"
            assert line["rateTimezone"] == "Asia/Shanghai"
            assert line["ratedAt"].endswith("+08:00")
        finally:
            await db.rollback()


@pytest.mark.asyncio
async def test_immediate_shadow_charges_legacy_and_records_unified_side_by_side() -> None:
    async with get_db_context() as db:
        try:
            svc, _ = await _setup(db)
            with collect_usage(label="chat"):
                record_llm_usage(model="deepseek-chat", usage={"prompt_tokens": 2000, "completion_tokens": 0})
                result = await settle_immediate(svc, _ctx("unit:shadow:1"), mode="shadow", price_items=ITEMS, price_version=VERSION, legacy_amount=Decimal("0.5"))
            assert result.charged and result.amount == Decimal("0.50") and result.unified_points == Decimal("2.00")
            tx = await svc.get_transaction_by_id(tenant_id=1, tx_id=result.transaction_id)
            assert tx.extra["billing"]["legacyAmount"] == "0.50" and tx.extra["billing"]["shadow"]["points"] == "2.00"
        finally:
            await db.rollback()


@pytest.mark.asyncio
async def test_immediate_below_minimum_is_free_and_idempotent_key_dedups() -> None:
    async with get_db_context() as db:
        try:
            svc, _ = await _setup(db)
            with collect_usage():
                record_llm_usage(model="x", usage={"prompt_tokens": 1, "completion_tokens": 1})  # 0.002 → 0.00 免费
                free = await settle_immediate(svc, _ctx("unit:free:1"), mode="unified", price_items=ITEMS, price_version=VERSION)
            assert free.free and not free.charged and free.transaction_id is None
            with collect_usage():
                record_llm_usage(model="x", usage={"prompt_tokens": 1000, "completion_tokens": 0})
                first = await settle_immediate(svc, _ctx("unit:dup:1"), mode="unified", price_items=ITEMS, price_version=VERSION)
                second = await settle_immediate(svc, _ctx("unit:dup:1"), mode="unified", price_items=ITEMS, price_version=VERSION)
            assert first.transaction_id == second.transaction_id  # 幂等键 {base}:settle
        finally:
            await db.rollback()


@pytest.mark.asyncio
async def test_reserve_complete_refunds_difference_and_overrun_is_not_charged() -> None:
    async with get_db_context() as db:
        try:
            svc, account = await _setup(db)
            before = Decimal(account.balance)
            ctx = _ctx("unit:task:1")
            reserve_tx = await reserve(svc, ctx, amount=Decimal("10"), mode="unified", price_version=VERSION)
            again = await reserve(svc, ctx, amount=Decimal("10"), mode="unified", price_version=VERSION)
            assert reserve_tx.id == again.id  # 并发/重试只预留一笔
            with collect_usage(label="task"):
                record_unit_usage(kind="image", quantity=2, model="gpt-image-2")  # 4 分
                result = await complete(svc, ctx, reserve_tx=reserve_tx, mode="unified", price_items=ITEMS, price_version=VERSION)
            assert result.amount == Decimal("4.00") and result.refunded == Decimal("6.00") and result.unbilled_overrun == 0
            assert reserve_tx.extra["billing"]["status"] == "completed" and reserve_tx.extra["billing"]["charged"] == "4.00"
            balance = Decimal((await svc.get_account_by_id(tenant_id=1, account_id=account.id)).balance)
            assert balance == before - Decimal("4.00")
            # 重复 complete：幂等键 {base}:complete → 不再退第二次
            with collect_usage(label="task"):
                record_unit_usage(kind="image", quantity=2, model="gpt-image-2")
                dup = await complete(svc, ctx, reserve_tx=reserve_tx, mode="unified", price_items=ITEMS, price_version=VERSION)
            assert dup.refund_transaction_id == result.refund_transaction_id
            assert Decimal((await svc.get_account_by_id(tenant_id=1, account_id=account.id)).balance) == balance

            # 超限：实际 20 > 预留 5 → 只收 5，记 unbilledOverrun，不追扣
            ctx2 = _ctx("unit:task:2")
            reserve_tx2 = await reserve(svc, ctx2, amount=Decimal("5"), mode="unified", price_version=VERSION)
            with collect_usage(label="task"):
                record_unit_usage(kind="image", quantity=10, model="gpt-image-2")
                over = await complete(svc, ctx2, reserve_tx=reserve_tx2, mode="unified", price_items=ITEMS, price_version="v-new")
            assert over.amount == Decimal("5.00") and over.unbilled_overrun == Decimal("15.00") and over.refund_transaction_id is None
            assert reserve_tx2.extra["billing"]["unbilledOverrun"] == "15.00"
            assert reserve_tx2.extra["billing"]["priceVersionDrift"] == {"reserved": VERSION, "settled": "v-new"}
        finally:
            await db.rollback()


@pytest.mark.asyncio
async def test_refund_all_returns_reservation_once() -> None:
    async with get_db_context() as db:
        try:
            svc, account = await _setup(db)
            before = Decimal(account.balance)
            ctx = _ctx("unit:task:cancel")
            reserve_tx = await reserve(svc, ctx, amount=Decimal("7"), mode="legacy", price_version=None)
            first = await refund_all(svc, ctx, reserve_tx=reserve_tx, reason="task_failed")
            second = await refund_all(svc, ctx, reserve_tx=reserve_tx, reason="task_failed")
            assert first is not None and second is None
            assert reserve_tx.extra["billing"]["status"] == "refunded"
            assert Decimal((await svc.get_account_by_id(tenant_id=1, account_id=account.id)).balance) == before
        finally:
            await db.rollback()


@pytest.mark.asyncio
async def test_nested_settlement_is_not_repriced_by_root() -> None:
    """planner 在子收集器先结算，其事件冒泡到根后不得被根动作再计一次（真实验收 2026-08-26 抓到的双计）。"""
    from app.domain.credits.usage import usage_snapshot_for_extra

    async with get_db_context() as db:
        try:
            svc, account = await _setup(db)
            before = Decimal(account.balance)
            with collect_usage(label="chat_reply") as root:
                with collect_usage(label="planner"):
                    record_llm_usage(model="gpt-5.5", usage={"prompt_tokens": 1000, "completion_tokens": 0})  # 1 分
                    planner = await settle_immediate(svc, _ctx("unit:nested:planner"), mode="unified", price_items=ITEMS, price_version=VERSION)
                record_llm_usage(model="gpt-5.5", usage={"prompt_tokens": 0, "completion_tokens": 1000})  # 4 分
                assert len(root.events) == 2 and len(root.unsettled_events()) == 1
                snapshot = usage_snapshot_for_extra(root_only=True)
                assert snapshot["totals"]["llmCalls"] == 1 and snapshot["settledElsewhere"] == 1
                chat = await settle_immediate(svc, _ctx("unit:nested:chat"), mode="unified", price_items=ITEMS, price_version=VERSION)
            assert planner.amount == Decimal("1.00") and chat.amount == Decimal("4.00")
            assert chat.billing["totals"]["llmCalls"] == 1
            assert Decimal((await svc.get_account_by_id(tenant_id=1, account_id=account.id)).balance) == before - Decimal("5.00")
        finally:
            await db.rollback()


@pytest.mark.asyncio
async def test_legacy_consume_also_claims_events_for_root_snapshot() -> None:
    async with get_db_context() as db:
        try:
            svc, account = await _setup(db)
            with collect_usage(label="root") as root:
                with collect_usage(label="planner"):
                    record_llm_usage(model="a", usage={"prompt_tokens": 10, "completion_tokens": 1})
                    await svc.consume(tenant_id=1, account_id=account.id, amount=Decimal("1"), reference_type="unit_nested_legacy", idempotency_key="unit-nested-legacy-planner")
                record_llm_usage(model="b", usage={"prompt_tokens": 10, "completion_tokens": 1})
                tx = await svc.consume(tenant_id=1, account_id=account.id, amount=Decimal("1"), reference_type="unit_nested_legacy", idempotency_key="unit-nested-legacy-root")
            assert list(tx.extra["usage"]["byModel"].keys()) == ["b"] and tx.extra["usage"]["settledElsewhere"] == 1
            assert all(e.settled_tx_id for e in root.events)
        finally:
            await db.rollback()


@pytest.mark.asyncio
async def test_complete_and_refund_all_are_mutually_exclusive() -> None:
    """codex 复审：complete 后到的失败补偿不能把已消费部分退回；refund 后到的 complete 不能再记 charged。"""
    async with get_db_context() as db:
        try:
            svc, account = await _setup(db)
            before = Decimal(account.balance)
            ctx = _ctx("unit:excl:1")
            tx = await reserve(svc, ctx, amount=Decimal("10"), mode="unified", price_version=VERSION)
            with collect_usage():
                record_unit_usage(kind="image", quantity=2, model="gpt-image-2")  # 4 分
                await complete(svc, ctx, reserve_tx=tx, mode="unified", price_items=ITEMS, price_version=VERSION)
            assert await refund_all(svc, ctx, reserve_tx=tx, reason="late_failure") is None  # 已完成 → 不退已消费的 4
            assert Decimal((await svc.get_account_by_id(tenant_id=1, account_id=account.id)).balance) == before - Decimal("4.00")
            ctx2 = _ctx("unit:excl:2")
            tx2 = await reserve(svc, ctx2, amount=Decimal("5"), mode="unified", price_version=VERSION)
            assert await refund_all(svc, ctx2, reserve_tx=tx2, reason="failed") is not None
            with collect_usage():
                record_unit_usage(kind="image", quantity=1, model="gpt-image-2")
                late = await complete(svc, ctx2, reserve_tx=tx2, mode="unified", price_items=ITEMS, price_version=VERSION)
            assert late.charged is False and tx2.extra["billing"]["status"] == "refunded"
            assert Decimal((await svc.get_account_by_id(tenant_id=1, account_id=account.id)).balance) == before - Decimal("4.00")
        finally:
            await db.rollback()
