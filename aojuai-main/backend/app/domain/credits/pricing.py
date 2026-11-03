"""统一积分计价（纯函数，不碰数据库）。

输入：一组 ``UsageEvent`` + 一组费率项 ``PriceItem``；输出：总积分与逐条明细。
费率项匹配规则：同 item_type 内，精确 key > 通配 key（按 key 长度降序，
再按 priority 降序）> ``*`` 兜底；租户覆盖（tenant_id 非空）优先于平台默认。

llm：points = in×input_per_1k/1000 + (in_cached 部分按 cached_per_1k) + out×output_per_1k/1000；
     reasoning 已包含在 output 里，不另计。
其余（image/tool_call/tts/asr/flat）：points = quantity × points_per_unit
（tts 的 quantity 是字符数、asr 是秒数，费率项自带 unit_divisor：tts 1000、asr 60）。
四舍五入只在总额做一次（HALF_UP，0.01）。
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from zoneinfo import ZoneInfo

from app.domain.credits.usage import UsageEvent, UsageKind

PRICE_ITEM_TYPES: tuple[str, ...] = ("llm", "image", "tool_call", "tts", "asr", "flat")
DEFAULT_UNIT_DIVISOR: dict[str, Decimal] = {"tts": Decimal(1000), "asr": Decimal(60)}
_QUANT = Decimal("0.01")
_THOUSAND = Decimal(1000)
TENANT_TIMEZONE_KEY = "tenant"


def _parse_clock_minutes(value: object) -> int:
    text = str(value or "").strip()
    parts = text.split(":")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        raise ValueError(f"invalid rate schedule time: {text or '(empty)'}")
    hour, minute = (int(part) for part in parts)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"invalid rate schedule time: {text}")
    return hour * 60 + minute


def normalize_rate_schedule(value: object) -> dict[str, Any]:
    """Normalize the JSONB-backed rate schedule used by platform and tenant price items."""

    if value in (None, "", {}):
        return {}
    if not isinstance(value, dict):
        raise ValueError("rate schedule must be an object")
    timezone_name = str(value.get("timezone") or "UTC").strip()
    if timezone_name != TENANT_TIMEZONE_KEY:
        try:
            ZoneInfo(timezone_name)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"invalid rate schedule timezone: {timezone_name}") from exc
    default_band = str(value.get("defaultBand") or value.get("default_band") or "standard").strip() or "standard"
    raw_bands = value.get("bands") or []
    if not isinstance(raw_bands, list):
        raise ValueError("rate schedule bands must be a list")
    if not raw_bands:
        raise ValueError("rate schedule requires at least one band")
    bands: list[dict[str, Any]] = []
    band_keys: set[str] = set()
    for index, raw_band in enumerate(raw_bands):
        if not isinstance(raw_band, dict):
            raise ValueError("rate schedule band must be an object")
        key = str(raw_band.get("key") or f"band_{index + 1}").strip()
        if not key:
            raise ValueError("rate schedule band key is required")
        if key in band_keys:
            raise ValueError(f"duplicate rate schedule band key: {key}")
        band_keys.add(key)
        raw_multiplier = raw_band.get("multiplier")
        try:
            multiplier = Decimal(str("1" if raw_multiplier in (None, "") else raw_multiplier))
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"invalid rate multiplier for {key}") from exc
        if not multiplier.is_finite() or multiplier <= 0:
            raise ValueError(f"rate multiplier for {key} must be positive")
        raw_weekdays = raw_band.get("weekdays")
        if raw_weekdays is None:
            raw_weekdays = list(range(1, 8))
        if not isinstance(raw_weekdays, list):
            raise ValueError(f"weekdays for {key} must be a list")
        try:
            weekdays = sorted({int(day) for day in raw_weekdays})
        except (TypeError, ValueError) as exc:
            raise ValueError(f"weekdays for {key} must use ISO values 1-7") from exc
        if not weekdays or any(day < 1 or day > 7 for day in weekdays):
            raise ValueError(f"weekdays for {key} must use ISO values 1-7")
        raw_windows = raw_band.get("windows") or []
        if not isinstance(raw_windows, list) or not raw_windows:
            raise ValueError(f"rate schedule band {key} requires at least one window")
        windows: list[dict[str, str]] = []
        for raw_window in raw_windows:
            if isinstance(raw_window, (list, tuple)) and len(raw_window) == 2:
                start, end = raw_window
            elif isinstance(raw_window, dict):
                start, end = raw_window.get("start"), raw_window.get("end")
            else:
                raise ValueError(f"invalid rate schedule window for {key}")
            start_text, end_text = str(start or "").strip(), str(end or "").strip()
            start_minutes, end_minutes = _parse_clock_minutes(start_text), _parse_clock_minutes(end_text)
            if start_minutes == end_minutes:
                raise ValueError(f"rate schedule window for {key} cannot cover 24 hours")
            windows.append({"start": start_text, "end": end_text})
        try:
            priority = int(raw_band.get("priority") or 0)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"priority for {key} must be an integer") from exc
        bands.append(
            {
                "key": key,
                "multiplier": str(multiplier),
                "weekdays": weekdays,
                "windows": windows,
                "priority": priority,
            }
        )
    normalized: dict[str, Any] = {
        "timezone": timezone_name,
        "defaultBand": default_band,
        "bands": bands,
    }
    for key in ("source", "sourceUrl", "effectiveAt", "verifiedAt", "remark"):
        if value.get(key) not in (None, ""):
            normalized[key] = str(value[key])
    return normalized


@dataclass(slots=True, frozen=True)
class PricingContext:
    tenant_timezone: str = "UTC"
    at: datetime | None = None
    conservative: bool = False


@dataclass(slots=True, frozen=True)
class AppliedRateBand:
    multiplier: Decimal = Decimal(1)
    key: str | None = None
    timezone: str | None = None
    rated_at: datetime | None = None


def quantize_points(value: Decimal) -> Decimal:
    return Decimal(value).quantize(_QUANT, rounding=ROUND_HALF_UP)


@dataclass(slots=True)
class PriceItem:
    item_type: str
    match_key: str
    input_points_per_1k: Decimal = Decimal(0)
    output_points_per_1k: Decimal = Decimal(0)
    cached_points_per_1k: Decimal | None = None  # None → input 的 10%（缓存命中/读）
    cache_write_points_per_1k: Decimal | None = None  # None → 与 input 同价（Anthropic 缓存写入）
    points_per_unit: Decimal = Decimal(0)
    unit_divisor: Decimal | None = None
    priority: int = 0
    tenant_id: int | None = None
    is_active: bool = True
    id: int | None = None
    remark: str = ""
    rate_schedule: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.item_type = str(self.item_type or "").strip()
        self.match_key = str(self.match_key or "").strip()
        for name in ("input_points_per_1k", "output_points_per_1k", "points_per_unit"):
            setattr(self, name, Decimal(str(getattr(self, name) or 0)))
        if self.cached_points_per_1k is not None:
            self.cached_points_per_1k = Decimal(str(self.cached_points_per_1k))
        if self.cache_write_points_per_1k is not None:
            self.cache_write_points_per_1k = Decimal(str(self.cache_write_points_per_1k))
        if self.unit_divisor is not None:
            self.unit_divisor = Decimal(str(self.unit_divisor))
        self.rate_schedule = normalize_rate_schedule(self.rate_schedule)

    @property
    def effective_cached_per_1k(self) -> Decimal:
        if self.cached_points_per_1k is not None:
            return self.cached_points_per_1k
        return (self.input_points_per_1k * Decimal("0.1")).quantize(Decimal("0.000001"))

    @property
    def effective_cache_write_per_1k(self) -> Decimal:
        return self.cache_write_points_per_1k if self.cache_write_points_per_1k is not None else self.input_points_per_1k

    @property
    def effective_unit_divisor(self) -> Decimal:
        if self.unit_divisor is not None and self.unit_divisor > 0:
            return self.unit_divisor
        return DEFAULT_UNIT_DIVISOR.get(self.item_type, Decimal(1))

    def is_wildcard(self) -> bool:
        return any(ch in self.match_key for ch in "*?[")


@dataclass(slots=True)
class PricedLine:
    event: UsageEvent
    item: PriceItem | None
    points: Decimal
    fallback: bool = False  # 命中 `*` 兜底或无费率
    applied_rate: AppliedRateBand = field(default_factory=AppliedRateBand)

    def to_dict(self) -> dict[str, Any]:
        payload = self.event.to_dict()
        payload.update(
            {
                "points": str(quantize_points(self.points)),
                "priceItemId": self.item.id if self.item else None,
                "matchKey": self.item.match_key if self.item else None,
                "rateInputPer1k": str(self.item.input_points_per_1k * self.applied_rate.multiplier) if self.item else None,
                "rateOutputPer1k": str(self.item.output_points_per_1k * self.applied_rate.multiplier) if self.item else None,
                "rateCachedPer1k": str(self.item.effective_cached_per_1k * self.applied_rate.multiplier) if self.item and self.event.kind == "llm" else None,
                "rateCacheWritePer1k": str(self.item.effective_cache_write_per_1k * self.applied_rate.multiplier) if self.item and self.event.kind == "llm" and self.event.cache_write_tokens else None,
                "ratePerUnit": str(self.item.points_per_unit * self.applied_rate.multiplier) if self.item else None,
                "baseRateInputPer1k": str(self.item.input_points_per_1k) if self.item and self.applied_rate.multiplier != 1 else None,
                "baseRateOutputPer1k": str(self.item.output_points_per_1k) if self.item and self.applied_rate.multiplier != 1 else None,
                "baseRateCachedPer1k": str(self.item.effective_cached_per_1k) if self.item and self.event.kind == "llm" and self.applied_rate.multiplier != 1 else None,
                "baseRateCacheWritePer1k": str(self.item.effective_cache_write_per_1k) if self.item and self.event.kind == "llm" and self.event.cache_write_tokens and self.applied_rate.multiplier != 1 else None,
                "baseRatePerUnit": str(self.item.points_per_unit) if self.item and self.event.kind != "llm" and self.applied_rate.multiplier != 1 else None,
                "rateMultiplier": str(self.applied_rate.multiplier),
                "rateBand": self.applied_rate.key,
                "rateTimezone": self.applied_rate.timezone,
                "ratedAt": self.applied_rate.rated_at.isoformat() if self.applied_rate.rated_at else None,
                "fallbackRate": self.fallback,
            }
        )
        return payload


@dataclass(slots=True)
class PricedUsage:
    lines: list[PricedLine] = field(default_factory=list)
    unpriced: list[UsageEvent] = field(default_factory=list)

    @property
    def raw_points(self) -> Decimal:
        return sum((line.points for line in self.lines), Decimal(0))

    @property
    def points(self) -> Decimal:
        return quantize_points(self.raw_points)

    @property
    def used_fallback(self) -> bool:
        return any(line.fallback for line in self.lines) or bool(self.unpriced)

    def to_dict(self) -> dict[str, Any]:
        return {
            "points": str(self.points),
            "items": [line.to_dict() for line in self.lines],
            "unpriced": [event.to_dict() for event in self.unpriced],
            "fallbackRate": self.used_fallback,
        }


def _match_key_for_event(event: UsageEvent) -> list[str]:
    """一个事件可能有多个候选 key，按优先级从具体到宽泛。"""
    model = (event.model or "").strip()
    unit = (event.unit_key or "").strip()
    if event.kind == "llm":
        return [model] if model else []
    if event.kind == "image":
        keys = []
        if model and unit:
            keys.append(f"{model}/{unit}")
        if model:
            keys.append(model)
        return keys
    if event.kind == "tool_call":
        keys = []
        if unit and model:
            keys.append(f"{unit}@{model}")
        if unit:
            keys.append(unit)
        return keys
    if event.kind in {"tts", "asr"}:
        keys = []
        if model and unit:
            keys.append(f"{model}/{unit}")
        if model:
            keys.append(model)
        if event.provider:
            keys.append(str(event.provider))
        return keys
    return [unit] if unit else ([model] if model else [])


def _candidates(items: list[PriceItem], item_type: str) -> list[PriceItem]:
    return [item for item in items if item.is_active and item.item_type == item_type]


def resolve_price_item(event: UsageEvent, items: list[PriceItem]) -> tuple[PriceItem | None, bool]:
    """返回 (费率项, 是否兜底)。租户覆盖优先，其次精确、通配、`*`。"""
    pool = _candidates(items, event.kind)
    if not pool:
        return None, True
    keys = _match_key_for_event(event)

    def rank(item: PriceItem, exact: bool) -> tuple[int, int, int, int]:
        return (
            1 if item.tenant_id is not None else 0,
            1 if exact else 0,
            len(item.match_key) if not exact else 10_000,
            int(item.priority or 0),
        )

    best: tuple[tuple[int, int, int, int], PriceItem] | None = None
    for key in keys:
        for item in pool:
            if item.match_key == "*":
                continue
            exact = item.match_key.lower() == key.lower()
            wild = (not exact) and item.is_wildcard() and fnmatch.fnmatchcase(key.lower(), item.match_key.lower())
            if not (exact or wild):
                continue
            score = rank(item, exact)
            if best is None or score > best[0]:
                best = (score, item)
        if best is not None:
            return best[1], False
    fallbacks = [item for item in pool if item.match_key == "*"]
    if fallbacks:
        fallbacks.sort(key=lambda item: (1 if item.tenant_id is not None else 0, int(item.priority or 0)), reverse=True)
        return fallbacks[0], True
    return None, True


def _window_matches(local_at: datetime, *, weekdays: list[int], start: int, end: int) -> bool:
    minute = local_at.hour * 60 + local_at.minute
    weekday = local_at.isoweekday()
    if start < end:
        return weekday in weekdays and start <= minute < end
    if minute >= start:
        return weekday in weekdays
    previous_weekday = 7 if weekday == 1 else weekday - 1
    return minute < end and previous_weekday in weekdays


def resolve_rate_band(
    event: UsageEvent,
    item: PriceItem | None,
    context: PricingContext | None = None,
) -> AppliedRateBand:
    if item is None or not item.rate_schedule:
        return AppliedRateBand()
    schedule = item.rate_schedule
    ctx = context or PricingContext()
    timezone_name = str(schedule.get("timezone") or "UTC")
    if timezone_name == TENANT_TIMEZONE_KEY:
        timezone_name = str(ctx.tenant_timezone or "UTC")
    try:
        zone = ZoneInfo(timezone_name)
    except Exception:
        timezone_name, zone = "UTC", ZoneInfo("UTC")
    # ``at`` is an explicit as-of override for previews/tests. Normal settlement
    # leaves it empty and rates each call by the event's own timestamp.
    source_at = ctx.at or event.occurred_at or datetime.now(UTC)
    if source_at.tzinfo is None:
        source_at = source_at.replace(tzinfo=UTC)
    local_at = source_at.astimezone(zone)
    bands = list(schedule.get("bands") or [])
    if ctx.conservative and bands:
        selected = max(bands, key=lambda band: (Decimal(str(band.get("multiplier") or 1)), int(band.get("priority") or 0)))
        multiplier = Decimal(str(selected.get("multiplier") or 1))
        if multiplier <= 1:
            return AppliedRateBand(
                multiplier=Decimal(1),
                key=f"reserve_max:{schedule.get('defaultBand') or 'standard'}",
                timezone=timezone_name,
                rated_at=local_at,
            )
        return AppliedRateBand(
            multiplier=multiplier,
            key=f"reserve_max:{selected.get('key') or 'scheduled'}",
            timezone=timezone_name,
            rated_at=local_at,
        )
    matches: list[dict[str, Any]] = []
    for band in bands:
        weekdays = [int(day) for day in band.get("weekdays") or list(range(1, 8))]
        for window in band.get("windows") or []:
            start = _parse_clock_minutes(window.get("start"))
            end = _parse_clock_minutes(window.get("end"))
            if _window_matches(local_at, weekdays=weekdays, start=start, end=end):
                matches.append(band)
                break
    if matches:
        selected = max(matches, key=lambda band: (int(band.get("priority") or 0), Decimal(str(band.get("multiplier") or 1))))
        return AppliedRateBand(
            multiplier=Decimal(str(selected.get("multiplier") or 1)),
            key=str(selected.get("key") or "scheduled"),
            timezone=timezone_name,
            rated_at=local_at,
        )
    return AppliedRateBand(
        multiplier=Decimal(1),
        key=str(schedule.get("defaultBand") or "standard"),
        timezone=timezone_name,
        rated_at=local_at,
    )


def price_event(event: UsageEvent, item: PriceItem | None, *, multiplier: Decimal = Decimal(1)) -> Decimal:
    if item is None:
        return Decimal(0)
    if event.kind == "llm":
        # input = 未缓存 + 缓存命中 + 缓存写入 三段分价；output 含 reasoning 不另计
        cached = Decimal(max(int(event.cached_tokens), 0))
        cache_write = Decimal(max(int(event.cache_write_tokens), 0))
        input_uncached = Decimal(max(int(event.input_tokens) - int(cached) - int(cache_write), 0))
        output = Decimal(max(int(event.output_tokens), 0))
        return multiplier * (
            input_uncached * item.input_points_per_1k / _THOUSAND
            + cached * item.effective_cached_per_1k / _THOUSAND
            + cache_write * item.effective_cache_write_per_1k / _THOUSAND
            + output * item.output_points_per_1k / _THOUSAND
        )
    quantity = Decimal(str(event.quantity or 0))
    return multiplier * quantity * item.points_per_unit / item.effective_unit_divisor


def price_usage(
    events: list[UsageEvent],
    items: list[PriceItem],
    *,
    context: PricingContext | None = None,
) -> PricedUsage:
    result = PricedUsage()
    for event in events:
        item, fallback = resolve_price_item(event, items)
        if item is None:
            result.unpriced.append(event)
            continue
        applied_rate = resolve_rate_band(event, item, context)
        result.lines.append(
            PricedLine(
                event=event,
                item=item,
                points=price_event(event, item, multiplier=applied_rate.multiplier),
                fallback=fallback,
                applied_rate=applied_rate,
            )
        )
    return result


def price_item_from_row(row: Any) -> PriceItem:
    """由 ORM 行/字典构造费率项（字段名与 credit_price_items 表一致）。"""
    get = (lambda key: row.get(key)) if isinstance(row, dict) else (lambda key: getattr(row, key, None))
    extra = get("extra") if isinstance(get("extra"), dict) else {}
    return PriceItem(
        id=get("id"),
        tenant_id=get("tenant_id"),
        item_type=str(get("item_type") or ""),
        match_key=str(get("match_key") or ""),
        input_points_per_1k=Decimal(str(get("input_points_per_1k") or 0)),
        output_points_per_1k=Decimal(str(get("output_points_per_1k") or 0)),
        cached_points_per_1k=(Decimal(str(get("cached_points_per_1k"))) if get("cached_points_per_1k") is not None else None),
        cache_write_points_per_1k=(Decimal(str(get("cache_write_points_per_1k"))) if get("cache_write_points_per_1k") is not None else None),
        points_per_unit=Decimal(str(get("points_per_unit") or 0)),
        unit_divisor=(Decimal(str(get("unit_divisor"))) if get("unit_divisor") is not None else None),
        priority=int(get("priority") or 0),
        is_active=bool(get("is_active") if get("is_active") is not None else True),
        remark=str(get("remark") or ""),
        rate_schedule=(extra.get("rateSchedule") or extra.get("rate_schedule") or {}),
    )


__all__ = [
    "PRICE_ITEM_TYPES",
    "AppliedRateBand",
    "PriceItem",
    "PricingContext",
    "PricedLine",
    "PricedUsage",
    "UsageKind",
    "price_event",
    "price_item_from_row",
    "price_usage",
    "quantize_points",
    "normalize_rate_schedule",
    "resolve_rate_band",
    "resolve_price_item",
]
