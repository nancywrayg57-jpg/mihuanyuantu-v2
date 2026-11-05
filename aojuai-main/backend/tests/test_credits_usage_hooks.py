"""共享 OpenAIClient 与直连客户端在拿到 usage 的地方必须向收集器上报（计量层挂钩回归）。

注：plugins 侧还有一条 insight runner 的挂钩用例，基座没有 insight 域，未回流。
"""

from __future__ import annotations

import httpx
import pytest

from app.domain.assistant import openai_client as oc
from app.domain.credits.usage import collect_usage, record_llm_usage
from tests.test_openai_client_stream_collect import FakeStreamCM, FakeStreamResponse, _make_client, _sse_lines_ok


@pytest.mark.asyncio
async def test_chat_stream_collect_reports_llm_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _make_client()
    monkeypatch.setattr(httpx.AsyncClient, "stream", lambda self, method, url, **kw: FakeStreamCM(FakeStreamResponse(_sse_lines_ok())))
    with collect_usage() as collector:
        text, meta = await client.chat_stream_collect([{"role": "user", "content": "hi"}])
    assert text == "长江"
    assert [e.kind for e in collector.events] == ["llm"]
    event = collector.events[0]
    assert event.model == "gpt-5.5" and event.api_type == "chat_completions" and event.source == "openai_client"
    assert (event.input_tokens, event.output_tokens) == (12, 56)


@pytest.mark.asyncio
async def test_sync_chat_reports_usage_once(monkeypatch: pytest.MonkeyPatch) -> None:
    client = oc.OpenAIClient(base_url="https://gw.example/v1", api_key="k", model="deepseek-chat", api_mode="chat_completions")

    async def fake_post(self, url, **kwargs):
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "ok"}}], "usage": {"prompt_tokens": 5, "completion_tokens": 7, "total_tokens": 12}},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    with collect_usage() as collector:
        text, usage = await client.chat_with_usage([{"role": "user", "content": "hi"}], stream=False)
    assert text == "ok" and usage["completion_tokens"] == 7
    assert len(collector.events) == 1
    assert collector.events[0].model == "deepseek-chat" and collector.events[0].total_tokens == 12


def test_speech_tts_reports_character_usage() -> None:
    from decimal import Decimal

    from app.domain.credits.usage import record_unit_usage
    from app.domain.speech.billing import calc_speech_text_credits  # noqa: F401 - 确保模块可导入

    with collect_usage() as collector:
        assert record_unit_usage(kind="tts", quantity=120, model="edge-tts", provider="edge", unit_key="zh-CN-XiaoxiaoNeural") is True
    assert collector.events[0].quantity == Decimal(120) and collector.events[0].kind == "tts"


def test_root_scope_and_snapshot_once_semantics() -> None:
    from app.domain.credits.usage import record_llm_usage, usage_snapshot_for_extra

    with collect_usage(label="request") as outer:
        record_llm_usage(model="m", usage={"prompt_tokens": 1, "completion_tokens": 1})
        with collect_usage(root=True, label="detached") as detached:
            record_llm_usage(model="d", usage={"prompt_tokens": 2, "completion_tokens": 2})
            assert detached.is_root and usage_snapshot_for_extra(root_only=True) is not None
        with collect_usage(stage="child"):
            record_llm_usage(model="c", usage={"prompt_tokens": 3, "completion_tokens": 3})
            assert usage_snapshot_for_extra(root_only=True) is None  # 子阶段不得落账
        assert [e.model for e in outer.events] == ["m", "c"]  # detached 不冒泡
        first = usage_snapshot_for_extra(root_only=True, once=True)
        assert first is not None and first["byStage"]["child"]["calls"] == 1
        assert usage_snapshot_for_extra(root_only=True, once=True) is None  # 同一根动作只附一次



# 真库集成测试：没有可连接的库时跳过（守卫见 tests/conftest.py）
@pytest.mark.requires_database
@pytest.mark.asyncio
async def test_consume_attaches_usage_snapshot_to_transaction_extra() -> None:
    from decimal import Decimal

    from app.domain.credits.service import CreditService
    from app.infrastructure.database import get_db_context

    async with get_db_context() as db:
        try:
            svc = CreditService(db)
            account = await svc.init_user_account(tenant_id=1, user_id=1)
            if Decimal(account.balance) < Decimal("1"):
                await svc.recharge(tenant_id=1, account_id=account.id, amount=Decimal("10"), operator_id=1)
            with collect_usage(label="unit"):
                record_llm_usage(model="gpt-5.5", usage={"prompt_tokens": 100, "completion_tokens": 20}, api_type="responses", web_search_calls=1, stage="insight:search")
                tx = await svc.consume(
                    tenant_id=1, account_id=account.id, amount=Decimal("0.5"), reference_type="unit_usage_test",
                    idempotency_key="unit-usage-snapshot-test", extra={"foo": "bar"},
                )
            usage = tx.extra["usage"]
            assert tx.extra["foo"] == "bar"
            assert usage["totals"]["inputTokens"] == 100 and usage["byModel"]["gpt-5.5"]["calls"] == 1
            assert [i["kind"] for i in usage["items"]] == ["llm", "tool_call"] and usage["items"][0]["stage"] == "insight:search"
        finally:
            await db.rollback()
