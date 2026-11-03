"""credits.usage：用量事件归一、收集器嵌套/冒泡、asyncio 子任务共享、无收集器静默。"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.domain.credits.usage import (
    UsageEvent,
    collect_usage,
    collects_usage,
    current_usage_collector,
    normalize_usage_payload,
    record_llm_usage,
    record_unit_usage,
    record_usage,
)


def test_normalize_openai_chat_usage_with_cached_and_reasoning() -> None:
    usage = {
        "prompt_tokens": 1200,
        "completion_tokens": 300,
        "total_tokens": 1500,
        "prompt_tokens_details": {"cached_tokens": 1000},
        "completion_tokens_details": {"reasoning_tokens": 120},
    }
    assert normalize_usage_payload(usage) == {
        "input_tokens": 1200,
        "output_tokens": 300,
        "cached_tokens": 1000,
        "cache_write_tokens": 0,
        "reasoning_tokens": 120,
    }


def test_normalize_responses_and_google_shapes() -> None:
    responses = {"input_tokens": 50, "output_tokens": 20, "input_tokens_details": {"cached_tokens": 10}, "output_tokens_details": {"reasoning_tokens": 5}}
    assert normalize_usage_payload(responses) == {"input_tokens": 50, "output_tokens": 20, "cached_tokens": 10, "cache_write_tokens": 0, "reasoning_tokens": 5}
    google = {"promptTokenCount": 7, "candidatesTokenCount": 3, "totalTokenCount": 10}
    assert normalize_usage_payload(google) == {"input_tokens": 7, "output_tokens": 3, "cached_tokens": 0, "cache_write_tokens": 0, "reasoning_tokens": 0}
    # 只有 total 时全部记到输入侧（比丢掉好，且不会虚增输出价）
    assert normalize_usage_payload({"total_tokens": 9})["input_tokens"] == 9
    assert normalize_usage_payload(None) == {"input_tokens": 0, "output_tokens": 0, "cached_tokens": 0, "cache_write_tokens": 0, "reasoning_tokens": 0}


def test_record_without_collector_is_silent() -> None:
    assert current_usage_collector() is None
    assert record_llm_usage(model="gpt-5.5", usage={"prompt_tokens": 1, "completion_tokens": 1}) is False
    assert record_unit_usage(kind="image", quantity=1, model="gpt-image-2") is False
    assert record_usage(UsageEvent(kind="flat")) is False


@pytest.mark.asyncio
async def test_worker_decorator_isolates_parent_and_parallel_job_usage() -> None:
    @collects_usage("image-job", root=True)
    async def job(model: str):
        record_unit_usage(kind="image", model=model, quantity=1)
        await asyncio.sleep(0.01)
        collector = current_usage_collector()
        assert collector.is_root
        return [event.model for event in collector.events]

    with collect_usage(label="request") as parent:
        results = await asyncio.gather(job("first"), job("second"))
        assert results == [["first"], ["second"]]
        assert not parent.events


def test_usage_event_serializes_occurrence_time_for_auditable_rating() -> None:
    occurred_at = datetime(2026, 8, 29, 3, 4, 5, tzinfo=UTC)

    payload = UsageEvent(kind="llm", model="m", occurred_at=occurred_at).to_dict()

    assert payload["occurred_at"] == "2026-08-29T03:04:05+00:00"


def test_nested_collectors_bubble_up_and_tag_stage() -> None:
    with collect_usage(label="task") as task:
        record_llm_usage(model="gpt-5.5", usage={"prompt_tokens": 100, "completion_tokens": 10}, api_type="responses", web_search_calls=2)
        with collect_usage(stage="insight:search") as stage:
            record_llm_usage(model="gemini-2.5-pro", usage={"promptTokenCount": 40, "candidatesTokenCount": 4})
            assert len(stage) == 1 and stage.events[0].stage == "insight:search"
        record_unit_usage(kind="image", quantity=2, model="gpt-image-2", unit_key="1024x1024/high")
    assert current_usage_collector() is None
    kinds = [e.kind for e in task.events]
    assert kinds == ["llm", "tool_call", "llm", "image"]
    assert task.events[1].unit_key == "web_search" and task.events[1].quantity == Decimal(2)
    assert task.events[2].stage == "insight:search"
    totals = task.totals()
    assert totals == {
        "inputTokens": 140,
        "outputTokens": 14,
        "cachedTokens": 0,
        "cacheWriteTokens": 0,
        "reasoningTokens": 0,
        "llmCalls": 2,
        "toolCalls": 2,
        "images": 2,
    }
    assert task.by_model() == {
        "gpt-5.5": {"inputTokens": 100, "outputTokens": 10, "cachedTokens": 0, "cacheWriteTokens": 0, "reasoningTokens": 0, "calls": 1},
        "gemini-2.5-pro": {"inputTokens": 40, "outputTokens": 4, "cachedTokens": 0, "cacheWriteTokens": 0, "reasoningTokens": 0, "calls": 1},
    }
    item = task.to_items()[0]
    assert item["model"] == "gpt-5.5" and item["totalTokens"] == 110 and item["quantity"] == "0"


@pytest.mark.asyncio
async def test_asyncio_subtasks_share_the_collector() -> None:
    async def call(model: str) -> None:
        await asyncio.sleep(0)
        record_llm_usage(model=model, usage={"prompt_tokens": 1, "completion_tokens": 1})

    with collect_usage() as collector:
        await asyncio.gather(call("a"), call("b"), asyncio.create_task(call("c")))
    assert sorted(e.model for e in collector.events) == ["a", "b", "c"]


def test_unit_usage_rejects_llm_kind_and_non_positive_quantity() -> None:
    with collect_usage() as collector:
        with pytest.raises(ValueError):
            record_unit_usage(kind="llm", quantity=1)
        assert record_unit_usage(kind="tts", quantity=0) is False
        assert record_unit_usage(kind="tts", quantity="abc") is False
        assert record_unit_usage(kind="tts", quantity=1500, model="edge-tts", unit_key="zh-CN-XiaoxiaoNeural") is True
    assert collector.events[0].quantity == Decimal(1500)


@pytest.mark.asyncio
async def test_collects_usage_decorator_wraps_coroutines_and_async_generators() -> None:
    from app.domain.credits.usage import collects_usage, current_usage_collector, usage_snapshot_for_extra

    seen: dict[str, object] = {}

    @collects_usage("chat")
    async def reply() -> str:
        record_llm_usage(model="m1", usage={"prompt_tokens": 2, "completion_tokens": 3})
        seen["snapshot"] = usage_snapshot_for_extra()
        return "ok"

    @collects_usage("stream")
    async def stream():
        record_llm_usage(model="m2", usage={"prompt_tokens": 1, "completion_tokens": 1})
        yield "a"
        seen["inner"] = current_usage_collector() is not None
        yield "b"

    assert await reply() == "ok"
    assert seen["snapshot"]["totals"]["outputTokens"] == 3 and seen["snapshot"]["items"][0]["model"] == "m1"
    assert [chunk async for chunk in stream()] == ["a", "b"] and seen["inner"] is True
    assert current_usage_collector() is None and usage_snapshot_for_extra() is None


def test_overflow_keeps_event_identity_and_compresses_only_output() -> None:
    from app.domain.credits.usage import UsageCollector

    old = UsageCollector.MAX_EVENTS
    UsageCollector.MAX_EVENTS = 5
    try:
        with collect_usage(label="root") as root:
            with collect_usage(label="child") as child:
                for i in range(8):
                    record_llm_usage(model=f"m{i % 2}", usage={"prompt_tokens": 1, "completion_tokens": 1})
                assert len(child.events) == 8 and child.overflow == 3
                child.mark_settled(99)
            assert len(root.events) == 8 and all(e.settled_tx_id == 99 for e in root.events)  # 父子共享同一事件对象
            assert root.unsettled_events() == []
            items = child.to_items()
            assert len(items) == 5 + 2 and sum(int(i["extra"].get("aggregated", 0)) for i in items) == 3
    finally:
        UsageCollector.MAX_EVENTS = old
