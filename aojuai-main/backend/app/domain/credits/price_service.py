"""费率来源：平台默认 = 代码内版本化 pricebook（default_price_items.json，内容 SHA 即 priceVersion）；
租户覆盖 = credit_price_items 表（tenant_id 非空，只存差异项）。

- `pricebook_items()` / `pricebook_version()`：平台默认价与版本号（不落库，随代码发布）。
- `list_effective_price_items(tenant_id)`：pricebook ∪ 租户覆盖（同 key 时租户优先由
  pricing.resolve_price_item 的排序保证，这里不做去重，保留两层便于前端显示"默认/已覆盖"）。
- 租户覆盖的增删改在 `upsert_tenant_price_item` / `delete_tenant_price_item`。
（codex 评审 2026-08-26：MVP 不建动态平台费率表；先版本化静态 pricebook + 租户覆盖。）
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessError
from app.domain.credits.models import CreditPriceItem
from app.domain.credits.pricing import PRICE_ITEM_TYPES, PriceItem, normalize_rate_schedule, price_item_from_row

DEFAULT_PRICE_ITEMS_PATH = Path(__file__).with_name("default_price_items.json")
_DECIMAL_FIELDS = ("input_points_per_1k", "output_points_per_1k", "cached_points_per_1k", "cache_write_points_per_1k", "points_per_unit", "unit_divisor")


def load_default_price_items() -> list[dict[str, Any]]:
    payload = json.loads(DEFAULT_PRICE_ITEMS_PATH.read_text(encoding="utf-8"))
    items = payload.get("items") if isinstance(payload, dict) else payload
    return [dict(item) for item in items if isinstance(item, dict)]


@lru_cache(maxsize=1)
def _pricebook_cache() -> tuple[str, tuple[PriceItem, ...]]:
    raw = DEFAULT_PRICE_ITEMS_PATH.read_bytes()
    version = hashlib.sha256(raw).hexdigest()[:16]
    items = tuple(PriceItem(tenant_id=None, id=None, **_normalize_item_payload(item)) for item in load_default_price_items())
    return version, items


def pricebook_version() -> str:
    """平台默认价的内容版本（SHA-256 前 16 位），写进流水便于对账；改 JSON 即换版本。"""
    return _pricebook_cache()[0]


def pricebook_items() -> list[PriceItem]:
    return list(_pricebook_cache()[1])


def _normalize_item_payload(payload: dict[str, Any]) -> dict[str, Any]:
    item_type = str(payload.get("item_type") or payload.get("itemType") or "").strip()
    if item_type not in PRICE_ITEM_TYPES:
        raise BusinessError(message=f"不支持的费率类型：{item_type or '(空)'}")
    match_key = str(payload.get("match_key") or payload.get("matchKey") or "").strip()
    if not match_key:
        raise BusinessError(message="费率项缺少匹配键")
    normalized: dict[str, Any] = {"item_type": item_type, "match_key": match_key}
    for field in _DECIMAL_FIELDS:
        camel = "".join(part.capitalize() if index else part for index, part in enumerate(field.split("_")))
        raw = payload.get(field, payload.get(camel))
        if raw is None or raw == "":
            normalized[field] = None if field in {"cached_points_per_1k", "cache_write_points_per_1k", "unit_divisor"} else Decimal(0)
            continue
        try:
            value = Decimal(str(raw))
        except Exception as exc:  # noqa: BLE001
            raise BusinessError(message=f"费率字段 {field} 不是合法数字") from exc
        if value < 0:
            raise BusinessError(message=f"费率字段 {field} 不能为负")
        normalized[field] = value
    normalized["priority"] = int(payload.get("priority") or 0)
    is_active = payload.get("is_active", payload.get("isActive"))
    normalized["is_active"] = True if is_active is None else bool(is_active)
    normalized["remark"] = str(payload.get("remark") or "")[:500]
    try:
        normalized["rate_schedule"] = normalize_rate_schedule(
            payload.get("rate_schedule", payload.get("rateSchedule"))
        )
    except ValueError as exc:
        raise BusinessError(message=f"时段费率配置无效：{exc}") from exc
    return normalized


async def list_price_rows(db: AsyncSession, *, tenant_id: int) -> list[CreditPriceItem]:
    stmt = (
        select(CreditPriceItem)
        .where(CreditPriceItem.deleted_at.is_(None), CreditPriceItem.tenant_id == int(tenant_id))
        .order_by(CreditPriceItem.item_type, CreditPriceItem.match_key)
    )
    return list((await db.execute(stmt)).scalars().all())


async def list_effective_price_items(db: AsyncSession, *, tenant_id: int) -> list[PriceItem]:
    """租户生效费率 = 平台 pricebook（按租户成本加价缩放）∪ 租户覆盖行（原样，不缩放）。

    平台标价内置 30% 成本加价（统一公式：官方牌价×1.3）；租户可配 `credits.marginPercent`（0–500），
    平台行按 (1+m%)/1.30 缩放，m=30 时不变。`credits.cachedBilling = full_price` 时缓存命中/写入
    按（缩放后的）输入价计——缓存节省归平台；缺省 passthrough：按官方缓存价，折扣让给客户。
    租户显式覆盖的行永远按填写值原样生效（覆盖优先由 resolve_price_item 排序保证）。
    """
    from app.domain.credits.pricing_mode import (
        PRICEBOOK_BASE_MARGIN_PERCENT,
        get_tenant_price_adjustment,
    )

    margin, cached_billing = await get_tenant_price_adjustment(db, tenant_id=tenant_id)
    numerator = Decimal(100) + margin
    denominator = Decimal(100) + Decimal(PRICEBOOK_BASE_MARGIN_PERCENT)
    platform: list[PriceItem] = []
    for item in pricebook_items():
        changes = {}
        if numerator != denominator:
            for field_name in ("input_points_per_1k", "output_points_per_1k", "cached_points_per_1k", "cache_write_points_per_1k", "points_per_unit"):
                value = getattr(item, field_name, None)
                if value is not None:
                    # 先乘后除：避免预先算无限小数 factor 损失精确性
                    changes[field_name] = Decimal(str(value)) * numerator / denominator
        if cached_billing == "full_price":
            effective_input = changes.get("input_points_per_1k", item.input_points_per_1k)
            if effective_input is not None:
                changes["cached_points_per_1k"] = Decimal(str(effective_input))
                changes["cache_write_points_per_1k"] = Decimal(str(effective_input))
        platform.append(replace(item, **changes) if changes else item)
    return platform + [price_item_from_row(row) for row in await list_price_rows(db, tenant_id=tenant_id)]


async def upsert_tenant_price_item(db: AsyncSession, *, tenant_id: int, payload: dict[str, Any]) -> CreditPriceItem:
    normalized = _normalize_item_payload(payload)
    rate_schedule = normalized.pop("rate_schedule", {})
    stmt = select(CreditPriceItem).where(
        CreditPriceItem.tenant_id == int(tenant_id),
        CreditPriceItem.item_type == normalized["item_type"],
        CreditPriceItem.match_key == normalized["match_key"],
        CreditPriceItem.deleted_at.is_(None),
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        now = datetime.now(UTC)
        normalized["extra"] = {"rateSchedule": rate_schedule} if rate_schedule else {}
        row = CreditPriceItem(tenant_id=int(tenant_id), created_at=now, updated_at=now, **normalized)
        db.add(row)
    else:
        extra = dict(row.extra or {})
        if rate_schedule:
            extra["rateSchedule"] = rate_schedule
        else:
            extra.pop("rateSchedule", None)
        normalized["extra"] = extra
        for key, value in normalized.items():
            setattr(row, key, value)
        row.updated_at = datetime.now(UTC)
    await db.flush()
    return row


async def delete_tenant_price_item(db: AsyncSession, *, tenant_id: int, item_id: int) -> bool:
    stmt = select(CreditPriceItem).where(
        CreditPriceItem.id == int(item_id),
        CreditPriceItem.tenant_id == int(tenant_id),
        CreditPriceItem.deleted_at.is_(None),
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        return False
    row.deleted_at = datetime.now(UTC)
    await db.flush()
    return True


def price_row_to_view(row: CreditPriceItem) -> dict[str, Any]:
    rate_schedule = dict((row.extra or {}).get("rateSchedule") or {})
    return {
        "id": row.id,
        "tenantId": row.tenant_id,
        "scope": "tenant" if row.tenant_id is not None else "platform",
        "itemType": row.item_type,
        "matchKey": row.match_key,
        "inputPointsPer1k": str(row.input_points_per_1k),
        "outputPointsPer1k": str(row.output_points_per_1k),
        "cachedPointsPer1k": str(row.cached_points_per_1k) if row.cached_points_per_1k is not None else None,
        "cacheWritePointsPer1k": str(row.cache_write_points_per_1k) if getattr(row, "cache_write_points_per_1k", None) is not None else None,
        "pointsPerUnit": str(row.points_per_unit),
        "unitDivisor": str(row.unit_divisor) if row.unit_divisor is not None else None,
        "priority": int(row.priority or 0),
        "isActive": bool(row.is_active),
        "remark": row.remark or "",
        "rateSchedule": rate_schedule or None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }
