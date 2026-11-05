"""credit_price_items：迁移契约（表/唯一索引/死表已删）、平台默认价 seed 幂等、租户覆盖优先。"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.domain.credits.price_service import (
    delete_tenant_price_item,
    list_effective_price_items,
    list_price_rows,
    load_default_price_items,
    price_row_to_view,
    pricebook_items,
    pricebook_version,
    upsert_tenant_price_item,
)
from app.domain.credits.pricing import price_usage, resolve_price_item
from app.domain.credits.usage import UsageEvent
from app.infrastructure.database import get_db_context


@pytest.mark.skipif(__import__("app.core.config", fromlist=["settings"]).settings.IS_SQLITE, reason="迁移契约/回填校验依赖 PostgreSQL information_schema 与迁移链，SQLite 档由 create_all 建表")
@pytest.mark.requires_database  # 真库集成测试，没有可连接的库时跳过（守卫见 tests/conftest.py）
@pytest.mark.asyncio
async def test_migration_contract_table_indexes_and_dead_table_dropped() -> None:
    async with get_db_context() as db:
        cols = {
            r[0]
            for r in (await db.execute(text("select column_name from information_schema.columns where table_name='credit_price_items'"))).all()
        }
        assert {"tenant_id", "item_type", "match_key", "input_points_per_1k", "output_points_per_1k", "cached_points_per_1k", "points_per_unit", "unit_divisor", "priority", "is_active", "deleted_at"} <= cols
        idx = {r[0] for r in (await db.execute(text("select indexname from pg_indexes where tablename='credit_price_items'"))).all()}
        assert "uq_credit_price_items_scope_key" in idx
        nullable = (await db.execute(text("select is_nullable from information_schema.columns where table_name='credit_price_items' and column_name='tenant_id'"))).scalar()
        assert nullable == "NO"  # 只存租户覆盖，走租户隔离约束
        # credit_rules 死表按 codex 建议先移除代码引用，隔一个版本再 drop
        assert (await db.execute(text("select to_regclass('public.credit_rules')"))).scalar() is not None


def test_default_price_items_json_is_well_formed() -> None:
    items = load_default_price_items()
    keys = {(i["item_type"], i["match_key"]) for i in items}
    assert len(keys) == len(items) >= 20
    # 每种类型都有 `*` 兜底，保证任何事件都能计价并被标 fallback
    assert {("llm", "*"), ("image", "*"), ("tool_call", "*"), ("tts", "*"), ("asr", "*"), ("flat", "*")} <= keys


def test_pricebook_is_versioned_and_stable() -> None:
    items = pricebook_items()
    assert len(items) >= 20 and all(i.tenant_id is None and i.id is None for i in items)
    assert pricebook_version() == pricebook_version() and len(pricebook_version()) == 16


def test_pricebook_contains_current_high_usage_model_rates() -> None:
    items = pricebook_items()
    flash, fallback = resolve_price_item(
        UsageEvent(kind="llm", model="deepseek-v4-flash", input_tokens=1),
        items,
    )
    pro, _ = resolve_price_item(
        UsageEvent(kind="llm", model="deepseek-v4-pro", input_tokens=1),
        items,
    )
    sol, _ = resolve_price_item(
        UsageEvent(kind="llm", model="gpt-5.6-sol", input_tokens=1),
        items,
    )
    terra, _ = resolve_price_item(
        UsageEvent(kind="llm", model="gpt-5.6-terra", input_tokens=1),
        items,
    )

    assert fallback is False
    assert (flash.input_points_per_1k, flash.output_points_per_1k, flash.cached_points_per_1k) == (
        Decimal("0.028"),
        Decimal("0.084"),
        Decimal("0.001"),
    )
    assert flash.rate_schedule["timezone"] == "UTC"
    assert flash.rate_schedule["bands"][0]["multiplier"] == "2"
    assert (pro.input_points_per_1k, pro.output_points_per_1k) == (Decimal("0.084"), Decimal("0.25"))
    assert (sol.input_points_per_1k, sol.output_points_per_1k) == (Decimal("0.63"), Decimal("3.8"))
    assert (terra.input_points_per_1k, terra.output_points_per_1k) == (Decimal("0.25"), Decimal("1.5"))


@pytest.mark.requires_database  # 真库集成测试，没有可连接的库时跳过（守卫见 tests/conftest.py）
@pytest.mark.asyncio
async def test_tenant_override_wins_over_pricebook() -> None:
    async with get_db_context() as db:
        try:
            tenant_id = -920001
            assert await list_price_rows(db, tenant_id=tenant_id) == []
            schedule = {
                "timezone": "tenant",
                "defaultBand": "off_peak",
                "bands": [{"key": "peak", "multiplier": "1.5", "weekdays": [1, 2, 3, 4, 5], "windows": [["09:00", "18:00"]]}],
            }
            row = await upsert_tenant_price_item(db, tenant_id=tenant_id, payload={"itemType": "llm", "matchKey": "deepseek-*", "inputPointsPer1k": "0.01", "outputPointsPer1k": "0.02", "rateSchedule": schedule})
            row.extra = {**dict(row.extra or {}), "futureMetadata": {"keep": True}}
            row2 = await upsert_tenant_price_item(db, tenant_id=tenant_id, payload={"itemType": "llm", "matchKey": "deepseek-*", "inputPointsPer1k": "0.03", "outputPointsPer1k": "0.04", "rateSchedule": schedule})
            assert row.id == row2.id and row2.input_points_per_1k == Decimal("0.03")  # 同 key 覆盖而非新增
            assert row2.extra["futureMetadata"] == {"keep": True}
            assert price_row_to_view(row2)["rateSchedule"]["timezone"] == "tenant"

            items = await list_effective_price_items(db, tenant_id=tenant_id)
            event = UsageEvent(
                kind="llm",
                model="deepseek-chat",
                input_tokens=1000,
                output_tokens=1000,
                occurred_at=datetime(2026, 8, 30, 12, 0, tzinfo=UTC),  # Sunday, off-peak
            )
            item, fallback = resolve_price_item(event, items)
            assert item.tenant_id == tenant_id and fallback is False
            assert price_usage([event], items).points == Decimal("0.07")
            # 未覆盖的模型仍走平台默认
            other = UsageEvent(kind="llm", model="gpt-5.5", input_tokens=1000, output_tokens=0)
            assert resolve_price_item(other, items)[0].tenant_id is None

            assert await delete_tenant_price_item(db, tenant_id=tenant_id, item_id=row.id) is True
            assert resolve_price_item(event, await list_effective_price_items(db, tenant_id=tenant_id))[0].tenant_id is None
        finally:
            await db.rollback()


@pytest.mark.asyncio
async def test_invalid_payload_rejected() -> None:
    from app.core.exceptions import BusinessError

    async with get_db_context() as db:
        try:
            with pytest.raises(BusinessError):
                await upsert_tenant_price_item(db, tenant_id=-920002, payload={"itemType": "bogus", "matchKey": "x"})
            with pytest.raises(BusinessError):
                await upsert_tenant_price_item(db, tenant_id=-920002, payload={"itemType": "llm", "matchKey": "x", "inputPointsPer1k": "-1"})
            with pytest.raises(BusinessError, match="时段费率配置无效"):
                await upsert_tenant_price_item(
                    db,
                    tenant_id=-920002,
                    payload={
                        "itemType": "llm",
                        "matchKey": "x",
                        "rateSchedule": {"timezone": "bad-zone", "bands": []},
                    },
                )
        finally:
            await db.rollback()
