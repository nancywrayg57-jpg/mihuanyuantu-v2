"""租户可配毛利与缓存计费方式：平台行缩放、覆盖行原样、full_price 缓存归平台。"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.credits.price_service import list_effective_price_items
from app.domain.credits.pricing import UsageEvent, price_usage, resolve_price_item
from app.domain.credits.pricing_mode import get_tenant_price_adjustment, set_tenant_price_adjustment
from app.infrastructure.database import get_db_context

# 真库集成测试：断言的是真实 PostgreSQL 的行为，没有可连接的库时跳过（守卫见 tests/conftest.py）
pytestmark = pytest.mark.requires_database

TENANT = 1


async def _flash(db):
    items = await list_effective_price_items(db, tenant_id=TENANT)
    item, fallback = resolve_price_item(UsageEvent(kind="llm", model="deepseek-v4-flash", input_tokens=1), items)
    assert fallback is False
    return item


@pytest.mark.asyncio
async def test_default_margin_30_keeps_pricebook_rates() -> None:
    async with get_db_context() as db:
        try:
            margin, cached = await get_tenant_price_adjustment(db, tenant_id=TENANT)
            item = await _flash(db)
            if margin == Decimal(30):
                assert item.input_points_per_1k == Decimal("0.028")
        finally:
            await db.rollback()


@pytest.mark.asyncio
async def test_margin_scales_platform_rows_only() -> None:
    async with get_db_context() as db:
        try:
            await set_tenant_price_adjustment(db, tenant_id=TENANT, margin_percent="60")
            item = await _flash(db)
            # (1+60%)/(1+30%) = 16/13
            assert item.input_points_per_1k == Decimal("0.028") * Decimal(160) / Decimal(130)
            assert item.output_points_per_1k == Decimal("0.084") * Decimal(160) / Decimal(130)
            # 毛利=0 → 成本价（官方÷70）
            await set_tenant_price_adjustment(db, tenant_id=TENANT, margin_percent="0")
            item = await _flash(db)
            assert item.input_points_per_1k == Decimal("0.028") * Decimal(100) / Decimal(130)
        finally:
            await db.rollback()


@pytest.mark.asyncio
async def test_full_price_cached_billing_charges_cache_at_input_rate() -> None:
    async with get_db_context() as db:
        try:
            await set_tenant_price_adjustment(db, tenant_id=TENANT, margin_percent="30", cached_billing="full_price")
            item = await _flash(db)
            assert item.cached_points_per_1k == item.input_points_per_1k
            assert item.cache_write_points_per_1k == item.input_points_per_1k
            # 定价整链：9k 命中按输入价 → 与 10k 全未命中同价
            items = await list_effective_price_items(db, tenant_id=TENANT)
            hit = price_usage([UsageEvent(kind="llm", model="deepseek-v4-flash", input_tokens=10000, cached_tokens=9000)], items)
            miss = price_usage([UsageEvent(kind="llm", model="deepseek-v4-flash", input_tokens=10000)], items)
            assert hit.points == miss.points
        finally:
            await db.rollback()


@pytest.mark.asyncio
async def test_invalid_values_rejected() -> None:
    from app.core.exceptions import BusinessError

    async with get_db_context() as db:
        try:
            with pytest.raises(BusinessError):
                await set_tenant_price_adjustment(db, tenant_id=TENANT, margin_percent="9999")
            with pytest.raises(BusinessError):
                await set_tenant_price_adjustment(db, tenant_id=TENANT, cached_billing="keep_it_all")
        finally:
            await db.rollback()
