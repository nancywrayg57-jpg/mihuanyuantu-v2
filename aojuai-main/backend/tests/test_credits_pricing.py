"""credits.pricing：费率匹配优先级、按模型分输入/输出/缓存计价、按件计价、兜底与总额取整。"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.domain.credits.pricing import (
    PriceItem,
    PricingContext,
    normalize_rate_schedule,
    price_usage,
    resolve_price_item,
)
from app.domain.credits.usage import UsageEvent

ITEMS = [
    PriceItem(item_type="llm", match_key="*", input_points_per_1k="1", output_points_per_1k="1"),
    PriceItem(item_type="llm", match_key="gpt-5*", input_points_per_1k="0.6", output_points_per_1k="2.4"),
    PriceItem(item_type="llm", match_key="gpt-5.5", input_points_per_1k="0.8", output_points_per_1k="3.2", cached_points_per_1k="0.08"),
    PriceItem(item_type="llm", match_key="deepseek-*", input_points_per_1k="0.1", output_points_per_1k="0.2"),
    PriceItem(item_type="image", match_key="gpt-image-2", points_per_unit="4"),
    PriceItem(item_type="image", match_key="gpt-image-2/1024x1024/high", points_per_unit="6"),
    PriceItem(item_type="tool_call", match_key="web_search", points_per_unit="0.5"),
    PriceItem(item_type="tts", match_key="*", points_per_unit="10"),  # 每 1000 字符 10 分
    PriceItem(item_type="asr", match_key="glm-asr-*", points_per_unit="3"),  # 每分钟 3 分
]


def _llm(model: str, i: int, o: int, cached: int = 0) -> UsageEvent:
    return UsageEvent(kind="llm", model=model, input_tokens=i, output_tokens=o, cached_tokens=cached)


def test_exact_beats_glob_beats_star() -> None:
    assert resolve_price_item(_llm("gpt-5.5", 1, 1), ITEMS)[0].match_key == "gpt-5.5"
    assert resolve_price_item(_llm("gpt-5-mini", 1, 1), ITEMS)[0].match_key == "gpt-5*"
    item, fallback = resolve_price_item(_llm("claude-x", 1, 1), ITEMS)
    assert item.match_key == "*" and fallback is True
    assert resolve_price_item(_llm("GPT-5.5", 1, 1), ITEMS)[0].match_key == "gpt-5.5"  # 大小写不敏感


def test_tenant_override_wins_over_platform_default() -> None:
    items = ITEMS + [PriceItem(item_type="llm", match_key="gpt-5*", input_points_per_1k="9", output_points_per_1k="9", tenant_id=7)]
    assert resolve_price_item(_llm("gpt-5.5", 1, 1), items)[0].tenant_id == 7  # 租户 glob 胜过平台精确


def test_llm_pricing_splits_input_output_cached() -> None:
    priced = price_usage([_llm("gpt-5.5", 1000, 500, cached=400)], ITEMS)
    # 600 未缓存输入×0.8/1k + 400 缓存×0.08/1k + 500 输出×3.2/1k = 0.48 + 0.032 + 1.6
    assert priced.points == Decimal("2.11")
    assert priced.lines[0].to_dict()["rateCachedPer1k"] == "0.08"
    assert priced.used_fallback is False


def test_default_cached_rate_is_ten_percent_of_input() -> None:
    priced = price_usage([_llm("deepseek-chat", 1000, 0, cached=1000)], ITEMS)
    assert priced.points == Decimal("0.01")  # 0.1×10% = 0.01/1k


def test_unit_pricing_image_tool_tts_asr() -> None:
    events = [
        UsageEvent(kind="image", model="gpt-image-2", unit_key="1024x1024/high", quantity=Decimal(2)),
        UsageEvent(kind="image", model="gpt-image-2", unit_key="1536x1024/medium", quantity=Decimal(1)),
        UsageEvent(kind="tool_call", model="gpt-5.5", unit_key="web_search", quantity=Decimal(3)),
        UsageEvent(kind="tts", model="edge-tts", quantity=Decimal(2500)),
        UsageEvent(kind="asr", model="glm-asr-2512", quantity=Decimal(90)),
    ]
    priced = price_usage(events, ITEMS)
    points = [line.points for line in priced.lines]
    assert points == [Decimal(12), Decimal(4), Decimal("1.5"), Decimal(25), Decimal("4.5")]
    assert priced.points == Decimal("47.00")


def test_rounding_happens_once_on_total_and_unpriced_is_reported() -> None:
    events = [_llm("deepseek-chat", 3, 3), _llm("deepseek-chat", 3, 3), UsageEvent(kind="flat", unit_key="unknown_thing", quantity=Decimal(1))]
    priced = price_usage(events, ITEMS)
    # 每条 0.0009，逐条抹零会变成 0；总额 0.0018 → 0.00（仍不虚增）；unpriced 单独列出
    assert priced.raw_points == Decimal("0.0018") and priced.points == Decimal("0.00")
    assert [e.unit_key for e in priced.unpriced] == ["unknown_thing"] and priced.used_fallback is True
    payload = priced.to_dict()
    assert payload["fallbackRate"] is True and len(payload["items"]) == 2 and len(payload["unpriced"]) == 1


def _scheduled_llm(*, timezone: str, windows: list[list[str]], weekdays: list[int] | None = None) -> PriceItem:
    return PriceItem(
        item_type="llm",
        match_key="scheduled-model",
        input_points_per_1k="0.22",
        output_points_per_1k="0.66",
        rate_schedule={
            "timezone": timezone,
            "defaultBand": "off_peak",
            "bands": [
                {
                    "key": "peak",
                    "multiplier": "2",
                    "weekdays": weekdays or [1, 2, 3, 4, 5],
                    "windows": windows,
                }
            ],
        },
    )


def test_fixed_utc_schedule_uses_provider_clock_not_tenant_clock() -> None:
    item = _scheduled_llm(timezone="UTC", windows=[["01:00", "04:00"], ["06:00", "10:00"]])
    context = PricingContext(tenant_timezone="Asia/Shanghai")
    peak = UsageEvent(
        kind="llm",
        model="scheduled-model",
        input_tokens=1000,
        occurred_at=datetime(2026, 8, 31, 1, 30, tzinfo=UTC),  # Monday
    )
    off_peak = UsageEvent(
        kind="llm",
        model="scheduled-model",
        input_tokens=1000,
        occurred_at=datetime(2026, 8, 31, 5, 0, tzinfo=UTC),
    )

    priced = price_usage([peak, off_peak], [item], context=context)

    assert [line.points for line in priced.lines] == [Decimal("0.44"), Decimal("0.22")]
    assert priced.lines[0].applied_rate.timezone == "UTC"
    assert priced.lines[0].to_dict()["rateBand"] == "peak"


def test_tenant_schedule_uses_configured_tenant_timezone() -> None:
    item = _scheduled_llm(timezone="tenant", windows=[["09:00", "12:00"]])
    event = UsageEvent(
        kind="llm",
        model="scheduled-model",
        input_tokens=1000,
        occurred_at=datetime(2026, 8, 31, 1, 30, tzinfo=UTC),  # 09:30 Asia/Shanghai
    )

    shanghai = price_usage([event], [item], context=PricingContext(tenant_timezone="Asia/Shanghai"))
    london = price_usage([event], [item], context=PricingContext(tenant_timezone="Europe/London"))

    assert shanghai.points == Decimal("0.44")
    assert shanghai.lines[0].applied_rate.timezone == "Asia/Shanghai"
    assert london.points == Decimal("0.22")


def test_conservative_reserve_uses_maximum_scheduled_multiplier() -> None:
    item = _scheduled_llm(timezone="UTC", windows=[["01:00", "04:00"]])
    event = UsageEvent(
        kind="llm",
        model="scheduled-model",
        input_tokens=1000,
        occurred_at=datetime(2026, 8, 30, 12, 0, tzinfo=UTC),  # Sunday, normally off-peak
    )

    actual = price_usage([event], [item], context=PricingContext())
    reserved = price_usage([event], [item], context=PricingContext(conservative=True))

    assert actual.points == Decimal("0.22")
    assert reserved.points == Decimal("0.44")
    assert reserved.lines[0].to_dict()["rateBand"] == "reserve_max:peak"


def test_conservative_reserve_never_goes_below_default_multiplier() -> None:
    item = _scheduled_llm(timezone="UTC", windows=[["01:00", "04:00"]])
    item.rate_schedule["bands"][0]["multiplier"] = "0.5"
    event = UsageEvent(kind="llm", model="scheduled-model", input_tokens=1000)

    reserved = price_usage([event], [item], context=PricingContext(conservative=True))

    assert reserved.points == Decimal("0.22")
    assert reserved.lines[0].to_dict()["rateBand"] == "reserve_max:off_peak"


def test_overnight_window_attributes_after_midnight_to_previous_weekday() -> None:
    item = _scheduled_llm(timezone="UTC", windows=[["22:00", "02:00"]], weekdays=[5])
    friday = UsageEvent(kind="llm", model="scheduled-model", input_tokens=1000, occurred_at=datetime(2026, 9, 4, 23, 0, tzinfo=UTC))
    saturday_tail = UsageEvent(kind="llm", model="scheduled-model", input_tokens=1000, occurred_at=datetime(2026, 9, 5, 1, 0, tzinfo=UTC))
    saturday_late = UsageEvent(kind="llm", model="scheduled-model", input_tokens=1000, occurred_at=datetime(2026, 9, 5, 23, 0, tzinfo=UTC))

    priced = price_usage([friday, saturday_tail, saturday_late], [item])

    assert [line.applied_rate.key for line in priced.lines] == ["peak", "peak", "off_peak"]


@pytest.mark.parametrize(
    "schedule",
    [
        {"timezone": "UTC", "bands": []},
        {"timezone": "Invalid/Zone", "bands": []},
        {"timezone": "UTC", "bands": [{"key": "peak", "multiplier": 0, "windows": [["09:00", "10:00"]]}]},
        {"timezone": "UTC", "bands": [{"key": "peak", "multiplier": "NaN", "windows": [["09:00", "10:00"]]}]},
        {"timezone": "UTC", "bands": [{"key": "peak", "multiplier": 2, "weekdays": [], "windows": [["09:00", "10:00"]]}]},
        {"timezone": "UTC", "bands": [{"key": "peak", "multiplier": 2, "weekdays": [8], "windows": [["09:00", "10:00"]]}]},
        {"timezone": "UTC", "bands": [{"key": "peak", "multiplier": 2, "windows": [["09:00", "09:00"]]}]},
        {"timezone": "UTC", "bands": [{"key": "peak", "multiplier": 2, "windows": [["25:00", "10:00"]]}]},
        {"timezone": "UTC", "bands": [{"key": "peak", "multiplier": 2, "windows": [["09:00", "10:00"]]}, {"key": "peak", "multiplier": 3, "windows": [["10:00", "11:00"]]}]},
    ],
)
def test_invalid_rate_schedules_are_rejected(schedule: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        normalize_rate_schedule(schedule)
