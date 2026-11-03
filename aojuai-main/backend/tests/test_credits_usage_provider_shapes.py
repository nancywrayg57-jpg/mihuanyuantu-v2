"""供应商黄金样例：不同模型返回的 usage 形状/缓存字段各不相同，归一层与计价必须逐家正确。

口径：input = 全部输入（含缓存命中与写入），cached/cache_write ⊆ input；output = 全部输出（含思考），reasoning ⊆ output。
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.domain.credits.pricing import PriceItem, price_usage
from app.domain.credits.usage import UsageEvent, normalize_usage_payload

CASES = [
    (
        "openai_chat_gpt5_cached",
        {"prompt_tokens": 2100, "completion_tokens": 300, "total_tokens": 2400, "prompt_tokens_details": {"cached_tokens": 2048, "audio_tokens": 0}, "completion_tokens_details": {"reasoning_tokens": 200, "audio_tokens": 0}},
        (2100, 300, 2048, 0, 200),
    ),
    (
        "openai_responses_gpt5",
        {"input_tokens": 1500, "input_tokens_details": {"cached_tokens": 1024}, "output_tokens": 400, "output_tokens_details": {"reasoning_tokens": 256}, "total_tokens": 1900},
        (1500, 400, 1024, 0, 256),
    ),
    (
        "deepseek_hit_miss_old_style",
        {"prompt_tokens": 5000, "completion_tokens": 120, "total_tokens": 5120, "prompt_cache_hit_tokens": 4800, "prompt_cache_miss_tokens": 200},
        (5000, 120, 4800, 0, 0),
    ),
    (
        "deepseek_both_styles",
        {"prompt_tokens": 5000, "completion_tokens": 120, "prompt_cache_hit_tokens": 4800, "prompt_cache_miss_tokens": 200, "prompt_tokens_details": {"cached_tokens": 4800}, "completion_tokens_details": {"reasoning_tokens": 90}},
        (5000, 120, 4800, 0, 90),
    ),
    (
        "deepseek_only_hit_miss_no_prompt_tokens",
        {"prompt_cache_hit_tokens": 300, "prompt_cache_miss_tokens": 700, "completion_tokens": 10},
        (1000, 10, 300, 0, 0),
    ),
    (
        "anthropic_cache_read_and_write",
        {"input_tokens": 100, "cache_creation_input_tokens": 2000, "cache_read_input_tokens": 3000, "output_tokens": 50},
        (5100, 50, 3000, 2000, 0),
    ),
    (
        "gateway_responses_with_cache_write_details",  # gateway-a.example.com 实测形状（2026-08-26）
        {"input_tokens": 4458, "input_tokens_details": {"cache_write_tokens": 600, "cached_tokens": 3840}, "output_tokens": 23, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 4481},
        (4458, 23, 3840, 600, 0),
    ),
    (
        "openai_client_prenormalized_shape",  # 共享 OpenAIClient 归一后再上报的形状：缓存/写入/思考不得丢
        {"prompt_tokens": 4460, "completion_tokens": 33, "total_tokens": 4493, "cached_tokens": 3840, "cache_write_tokens": 128, "reasoning_tokens": 9},
        (4460, 33, 3840, 128, 9),
    ),
    (
        "gemini_cached_and_thoughts",
        {"promptTokenCount": 8000, "cachedContentTokenCount": 6000, "candidatesTokenCount": 400, "thoughtsTokenCount": 900, "totalTokenCount": 9300},
        (8000, 1300, 6000, 0, 900),
    ),
    (
        "gemini_usage_metadata_no_cache",
        {"promptTokenCount": 12, "candidatesTokenCount": 8, "totalTokenCount": 20},
        (12, 8, 0, 0, 0),
    ),
    (
        "qianfan_ernie",
        {"prompt_tokens": 90, "completion_tokens": 40, "total_tokens": 130},
        (90, 40, 0, 0, 0),
    ),
    (
        "ollama",
        {"prompt_eval_count": 33, "eval_count": 21},
        (33, 21, 0, 0, 0),
    ),
    (
        "string_and_float_numbers",
        {"prompt_tokens": "1200", "completion_tokens": 30.0, "prompt_tokens_details": {"cached_tokens": "1000"}},
        (1200, 30, 1000, 0, 0),
    ),
    (
        "garbage_values",
        {"prompt_tokens": None, "completion_tokens": "abc", "prompt_tokens_details": {"cached_tokens": -5}, "total_tokens": True},
        (0, 0, 0, 0, 0),
    ),
    (
        "cached_never_exceeds_input",
        {"prompt_tokens": 100, "completion_tokens": 1, "prompt_tokens_details": {"cached_tokens": 999}},
        (100, 1, 100, 0, 0),
    ),
]


@pytest.mark.parametrize("name,usage,expected", CASES, ids=[c[0] for c in CASES])
def test_provider_usage_shapes(name: str, usage: dict, expected: tuple[int, int, int, int, int]) -> None:
    normalized = normalize_usage_payload(usage)
    assert (
        normalized["input_tokens"],
        normalized["output_tokens"],
        normalized["cached_tokens"],
        normalized["cache_write_tokens"],
        normalized["reasoning_tokens"],
    ) == expected, name


def test_cache_pricing_three_segments_and_reasoning_not_double_counted() -> None:
    items = [PriceItem(item_type="llm", match_key="claude-x", input_points_per_1k="1", output_points_per_1k="5", cached_points_per_1k="0.1", cache_write_points_per_1k="1.25")]
    n = normalize_usage_payload({"input_tokens": 100, "cache_creation_input_tokens": 2000, "cache_read_input_tokens": 3000, "output_tokens": 1000, "output_tokens_details": {"reasoning_tokens": 600}})
    event = UsageEvent(kind="llm", model="claude-x", **{k: v for k, v in n.items()})
    priced = price_usage([event], items)
    # 未缓存 100×1 + 命中 3000×0.1 + 写入 2000×1.25 + 输出 1000×5（reasoning 600 已含其中，不再加）= 0.1 + 0.3 + 2.5 + 5
    assert priced.points == Decimal("7.90")
    line = priced.lines[0].to_dict()
    assert line["rateCacheWritePer1k"] == "1.25" and line["rateCachedPer1k"] == "0.1"


def test_cache_default_rates_from_pricebook() -> None:
    from app.domain.credits.price_service import pricebook_items

    items = pricebook_items()
    ds = normalize_usage_payload({"prompt_tokens": 10000, "completion_tokens": 0, "prompt_cache_hit_tokens": 9000, "prompt_cache_miss_tokens": 1000})
    priced = price_usage(
        [
            UsageEvent(
                kind="llm",
                model="deepseek-v4-flash",
                occurred_at=datetime(2026, 8, 30, 12, 0, tzinfo=UTC),  # Sunday, off-peak
                **ds,
            )
        ],
        items,
    )
    # DeepSeek V4 Flash 官网谷时价：1000×0.22 + 9000×0.007 = 0.22 + 0.063
    assert priced.points == Decimal("0.04")  # 2026-08-31 统一毛利费率：谷时 1k×0.028 + 9k×0.001
    gm = normalize_usage_payload({"promptTokenCount": 10000, "cachedContentTokenCount": 8000, "candidatesTokenCount": 0})
    priced = price_usage([UsageEvent(kind="llm", model="gemini-2.5-pro", **gm)], items)
    # 2000×0.7 + 8000×0.175 = 1.4 + 1.4
    assert priced.points == Decimal("0.64")  # gemini-2.5-pro 新费率 0.16/1k


def test_openai_client_normalize_keeps_cache_fields() -> None:
    from app.domain.assistant.openai_client import _normalize_usage

    out = _normalize_usage({"input_tokens": 4458, "input_tokens_details": {"cache_write_tokens": 600, "cached_tokens": 3840}, "output_tokens": 23, "output_tokens_details": {"reasoning_tokens": 5}})
    assert (out["prompt_tokens"], out["completion_tokens"], out["cached_tokens"], out["cache_write_tokens"], out["reasoning_tokens"]) == (4458, 23, 3840, 600, 5)
    back = normalize_usage_payload(out)
    assert (back["input_tokens"], back["cached_tokens"], back["cache_write_tokens"], back["reasoning_tokens"]) == (4458, 3840, 600, 5)
