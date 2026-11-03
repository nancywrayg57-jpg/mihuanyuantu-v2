"""租户计价模式 `tenant.config.credits.pricingMode`：legacy | shadow | unified。

- legacy：沿用各模块现有扣费算法（默认；缺字段也按 legacy 解释——存量租户零行为变化）。
- shadow：照旧扣费，同时按统一费率计算并把对账明细写进流水，不改余额（灰度观察）。
- unified：只按统一费率结算，忽略散落的 ratio/按次常量（模块级 deductCredits 开关仍尊重）。

codex 评审（2026-08-26）：存量租户必须显式回填 legacy；新租户只有在计量覆盖率验收后
才默认 unified——所以这里的代码缺省永远是 legacy，切换是显式动作。
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.exceptions import BusinessError, NotFoundError
from app.domain.auth.models import Tenant

PricingMode = Literal["legacy", "shadow", "unified"]
PRICING_MODES: tuple[str, ...] = ("legacy", "shadow", "unified")
DEFAULT_PRICING_MODE: PricingMode = "legacy"
CONFIG_KEY = "credits"
MODE_KEY = "pricingMode"

#: 平台 pricebook 标价内置的成本加价（2026-08-31 统一公式：官方牌价×1.3）。租户成本加价按 (1+m%)/(1+基准%) 对平台行缩放。
PRICEBOOK_BASE_MARGIN_PERCENT = 30
MARGIN_KEY = "marginPercent"
#: 缓存计费方式：passthrough = 命中按官方缓存价（折扣让给客户，缺省）；full_price = 命中仍按输入价计（缓存节省归平台）
CACHED_BILLING_MODES: tuple[str, ...] = ("passthrough", "full_price")
CACHED_BILLING_KEY = "cachedBilling"


def resolve_pricing_mode(config: dict[str, Any] | None) -> PricingMode:
    """从租户 config 解析模式；缺失/非法一律 legacy。"""
    section = (config or {}).get(CONFIG_KEY) if isinstance(config, dict) else None
    raw = str((section or {}).get(MODE_KEY) or "").strip().lower() if isinstance(section, dict) else ""
    return raw if raw in PRICING_MODES else DEFAULT_PRICING_MODE  # type: ignore[return-value]


def normalize_pricing_mode(value: object) -> PricingMode:
    raw = str(value or "").strip().lower()
    if raw not in PRICING_MODES:
        raise BusinessError(message=f"不支持的计价模式：{raw or '(空)'}，可选 legacy / shadow / unified")
    return raw  # type: ignore[return-value]


async def _get_tenant(db: AsyncSession, tenant_id: int) -> Tenant:
    tenant = (await db.execute(select(Tenant).where(Tenant.id == int(tenant_id), Tenant.deleted_at.is_(None)))).scalar_one_or_none()
    if tenant is None:
        raise NotFoundError(message="租户不存在")
    return tenant


async def get_tenant_pricing_mode(db: AsyncSession, *, tenant_id: int) -> PricingMode:
    tenant = await _get_tenant(db, tenant_id)
    return resolve_pricing_mode(tenant.config)


async def set_tenant_pricing_mode(db: AsyncSession, *, tenant_id: int, mode: object) -> PricingMode:
    normalized = normalize_pricing_mode(mode)
    tenant = await _get_tenant(db, tenant_id)
    config = dict(tenant.config or {})
    section = dict(config.get(CONFIG_KEY) or {}) if isinstance(config.get(CONFIG_KEY), dict) else {}
    section[MODE_KEY] = normalized
    section["pricingModeUpdatedAt"] = datetime.now(UTC).isoformat()
    config[CONFIG_KEY] = section
    tenant.config = config
    flag_modified(tenant, "config")
    await db.flush()
    return normalized


__all__ = [
    "DEFAULT_PRICING_MODE",
    "PRICING_MODES",
    "PricingMode",
    "get_tenant_pricing_mode",
    "normalize_pricing_mode",
    "resolve_pricing_mode",
    "set_tenant_pricing_mode",
]


def resolve_price_adjustment(config: dict[str, Any] | None) -> tuple[Decimal, str]:
    """(成本加价百分比, 缓存计费方式)。加价缺省 = 平台基准 30；缓存缺省 passthrough。"""
    section = (config or {}).get(CONFIG_KEY) if isinstance((config or {}).get(CONFIG_KEY), dict) else {}
    raw = (section or {}).get(MARGIN_KEY)
    try:
        margin = Decimal(str(raw)) if raw is not None else Decimal(PRICEBOOK_BASE_MARGIN_PERCENT)
    except Exception:  # noqa: BLE001
        margin = Decimal(PRICEBOOK_BASE_MARGIN_PERCENT)
    if not margin.is_finite() or margin < 0 or margin > 500:
        margin = Decimal(PRICEBOOK_BASE_MARGIN_PERCENT)
    cached = str((section or {}).get(CACHED_BILLING_KEY) or "passthrough")
    if cached not in CACHED_BILLING_MODES:
        cached = "passthrough"
    return margin, cached


async def get_tenant_price_adjustment(db: AsyncSession, *, tenant_id: int) -> tuple[Decimal, str]:
    try:
        tenant = await _get_tenant(db, tenant_id)
    except NotFoundError:
        # 读路径容错：租户不存在（测试用负 ID、边角并发）按平台缺省计价，不因取配置而 404
        return resolve_price_adjustment(None)
    return resolve_price_adjustment(tenant.config)


async def set_tenant_price_adjustment(
    db: AsyncSession,
    *,
    tenant_id: int,
    margin_percent: object = None,
    cached_billing: object = None,
) -> tuple[Decimal, str]:
    """设置租户成本加价（%）与缓存计费方式；None 表示不改。旧值保留在 config 里，流水按当时生效值计。"""
    tenant = await _get_tenant(db, tenant_id)
    config = dict(tenant.config or {})
    section = dict(config.get(CONFIG_KEY) or {}) if isinstance(config.get(CONFIG_KEY), dict) else {}
    if margin_percent is not None:
        try:
            margin = Decimal(str(margin_percent))
        except Exception as exc:  # noqa: BLE001
            raise BusinessError(message=f"非法的成本加价百分比: {margin_percent!r}") from exc
        if not margin.is_finite() or margin < 0 or margin > 500:
            raise BusinessError(message="成本加价百分比需在 0–500 之间")
        section[MARGIN_KEY] = str(margin)
    if cached_billing is not None:
        mode = str(cached_billing)
        if mode not in CACHED_BILLING_MODES:
            raise BusinessError(message=f"非法的缓存计费方式: {cached_billing!r}（passthrough|full_price）")
        section[CACHED_BILLING_KEY] = mode
    section["priceAdjustmentUpdatedAt"] = datetime.now(UTC).isoformat()
    config[CONFIG_KEY] = section
    tenant.config = config
    flag_modified(tenant, "config")
    await db.flush()
    return resolve_price_adjustment(config)
