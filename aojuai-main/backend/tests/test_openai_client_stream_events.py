"""responses_stream_events：typed 事件流解析（样本来自 2026-08-10 真实网关抓包）。"""
import json

import httpx
import pytest

from app.domain.assistant import openai_client as oc
from app.domain.assistant.openai_client import build_responses_input_items


def _events(*payloads):
    lines = []
    for p in payloads:
        lines.append(p if isinstance(p, str) else f"data: {json.dumps(p)}")
        lines.append("")
    return lines


class FakeStreamResponse:
    def __init__(self, lines, status_code=200):
        self._lines = lines
        self.status_code = status_code

    async def aiter_lines(self):
        for line in self._lines:
            yield line

    async def aread(self):
        return b"{}"

    def raise_for_status(self):
        raise httpx.HTTPStatusError(
            "err", request=httpx.Request("POST", "http://x"), response=httpx.Response(self.status_code)
        )


class FakeStreamCM:
    def __init__(self, response_or_exc):
        self._r = response_or_exc

    async def __aenter__(self):
        if isinstance(self._r, Exception):
            raise self._r
        return self._r

    async def __aexit__(self, *args):
        return None


def _make_client():
    return oc.OpenAIClient(
        base_url="https://gw.example/v1", api_key="k", model="deepseek-v4-flash",
        api_mode="responses", max_tokens=8000, timeout_seconds=5,
    )


def _completed(usage=None):
    return {
        "type": "response.completed",
        "response": {"status": "completed", "usage": usage or {"input_tokens": 10, "output_tokens": 5}},
    }


def _function_call_lines():
    """真实网关序列：output_item.added(function_call) → arguments.delta×2 → arguments.done。"""
    return _events(
        {"type": "response.created"},
        {
            "type": "response.output_item.added",
            "item": {"type": "function_call", "id": "item-1", "call_id": "call_00_abc", "name": "training_project_list"},
        },
        {"type": "response.function_call_arguments.delta", "item_id": "item-1", "delta": '{"keyword": '},
        {"type": "response.function_call_arguments.delta", "item_id": "item-1", "delta": '"数字化"}'},
        {"type": "response.function_call_arguments.done", "item_id": "item-1", "arguments": '{"keyword": "数字化"}'},
        _completed(),
    )


async def _collect(client, items, **kwargs):
    events = []
    async for ev in client.responses_stream_events(items, **kwargs):
        events.append(ev)
    return events


@pytest.mark.asyncio
async def test_stream_events_emits_function_call_without_empty_error(monkeypatch):
    client = _make_client()
    captured = {}

    def fake_stream(self, method, url, **kwargs):
        captured["url"] = url
        captured["json"] = kwargs.get("json")
        return FakeStreamCM(FakeStreamResponse(_function_call_lines()))

    monkeypatch.setattr(httpx.AsyncClient, "stream", fake_stream)
    fn_tool = {"type": "function", "name": "training_project_list", "parameters": {"type": "object"}}
    events = await _collect(client, [{"role": "user", "content": "查项目"}], extra_tools=[fn_tool])

    calls = [e for e in events if e["type"] == "function_call"]
    assert len(calls) == 1
    assert calls[0]["callId"] == "call_00_abc"
    assert calls[0]["name"] == "training_project_list"
    assert json.loads(calls[0]["arguments"]) == {"keyword": "数字化"}
    done = events[-1]
    assert done["type"] == "completed"
    assert done["functionCallCount"] == 1
    assert done["hasText"] is False
    # payload 契约：结构化 input 原样透传 + extra_tools 并入 tools
    assert captured["url"].endswith("/responses")
    assert captured["json"]["input"] == [{"role": "user", "content": "查项目"}]
    assert fn_tool in captured["json"]["tools"]


@pytest.mark.asyncio
async def test_stream_events_output_item_done_fallback_emits_once(monkeypatch):
    """网关不发 arguments.done 时由 output_item.done 兜底；两者都发也只产出一次。"""
    client = _make_client()
    lines = _events(
        {
            "type": "response.output_item.added",
            "item": {"type": "function_call", "id": "item-1", "call_id": "call_1", "name": "f"},
        },
        {"type": "response.function_call_arguments.done", "item_id": "item-1", "arguments": "{}"},
        {
            "type": "response.output_item.done",
            "item": {"type": "function_call", "id": "item-1", "call_id": "call_1", "name": "f", "arguments": "{}"},
        },
        _completed(),
    )
    monkeypatch.setattr(
        httpx.AsyncClient, "stream", lambda self, method, url, **kw: FakeStreamCM(FakeStreamResponse(lines))
    )
    events = await _collect(client, [{"role": "user", "content": "x"}])
    assert len([e for e in events if e["type"] == "function_call"]) == 1

    lines_no_done = _events(
        {
            "type": "response.output_item.done",
            "item": {"type": "function_call", "id": "item-2", "call_id": "call_2", "name": "g", "arguments": '{"a":1}'},
        },
        _completed(),
    )
    monkeypatch.setattr(
        httpx.AsyncClient, "stream", lambda self, method, url, **kw: FakeStreamCM(FakeStreamResponse(lines_no_done))
    )
    events = await _collect(client, [{"role": "user", "content": "x"}])
    calls = [e for e in events if e["type"] == "function_call"]
    assert len(calls) == 1
    assert calls[0]["callId"] == "call_2"
    assert calls[0]["arguments"] == '{"a":1}'


@pytest.mark.asyncio
async def test_stream_events_text_and_web_search(monkeypatch):
    client = _make_client()
    lines = _events(
        {"type": "response.web_search_call.searching"},
        {"type": "response.web_search_call.completed"},
        {"type": "response.output_text.delta", "delta": "苏州"},
        {"type": "response.output_text.delta", "delta": "多云"},
        _completed(),
    )
    monkeypatch.setattr(
        httpx.AsyncClient, "stream", lambda self, method, url, **kw: FakeStreamCM(FakeStreamResponse(lines))
    )
    events = await _collect(client, [{"role": "user", "content": "天气"}])
    assert "".join(e["delta"] for e in events if e["type"] == "text_delta") == "苏州多云"
    assert [e["status"] for e in events if e["type"] == "web_search"] == ["searching", "completed"]
    done = events[-1]
    assert done["webSearchCalls"] == 1
    assert done["hasText"] is True


@pytest.mark.asyncio
async def test_stream_events_empty_and_truncated_errors(monkeypatch):
    client = _make_client()
    monkeypatch.setattr(
        httpx.AsyncClient,
        "stream",
        lambda self, method, url, **kw: FakeStreamCM(FakeStreamResponse(_events(_completed()))),
    )
    with pytest.raises(oc._EmptyStreamError):
        await _collect(client, [{"role": "user", "content": "x"}], request_max_attempts=1)

    monkeypatch.setattr(
        httpx.AsyncClient,
        "stream",
        lambda self, method, url, **kw: FakeStreamCM(
            FakeStreamResponse(_events({"type": "response.output_text.delta", "delta": "半"}))
        ),
    )
    with pytest.raises(oc._TruncatedStreamError):
        await _collect(client, [{"role": "user", "content": "x"}], request_max_attempts=1)


@pytest.mark.asyncio
async def test_stream_events_retries_pre_output_then_succeeds(monkeypatch):
    client = _make_client()
    attempts = []

    def fake_stream(self, method, url, **kwargs):
        attempts.append(1)
        if len(attempts) == 1:
            return FakeStreamCM(FakeStreamResponse([], status_code=503))
        return FakeStreamCM(FakeStreamResponse(_function_call_lines()))

    monkeypatch.setattr(httpx.AsyncClient, "stream", fake_stream)
    monkeypatch.setattr(oc, "_retry_delay_seconds", lambda attempt, response=None: 0)
    events = await _collect(client, [{"role": "user", "content": "x"}])
    assert len(attempts) == 2
    assert any(e["type"] == "function_call" for e in events)


def test_build_responses_input_items_normalizes_roles():
    items = build_responses_input_items(
        [
            {"role": "system", "content": "s"},
            {"role": "tool", "content": "t"},
            {"role": "assistant", "content": ""},
            {"role": "user", "content": "u"},
        ]
    )
    assert items == [
        {"role": "system", "content": "s"},
        {"role": "user", "content": "t"},
        {"role": "user", "content": "u"},
    ]


@pytest.mark.asyncio
async def test_stream_events_retries_truncated_when_nothing_emitted(monkeypatch):
    """200 后空断且未向下游产出任何事件:等价失败请求,可安全重试。"""
    client = _make_client()
    attempts = []

    def fake_stream(self, method, url, **kwargs):
        attempts.append(1)
        if len(attempts) == 1:
            return FakeStreamCM(FakeStreamResponse(_events({"type": "response.created"})))
        return FakeStreamCM(FakeStreamResponse(_function_call_lines()))

    monkeypatch.setattr(httpx.AsyncClient, "stream", fake_stream)
    monkeypatch.setattr(oc, "_retry_delay_seconds", lambda attempt, response=None: 0)
    events = await _collect(client, [{"role": "user", "content": "x"}], request_max_attempts=3)
    assert len(attempts) == 2
    assert any(e["type"] == "function_call" for e in events)


@pytest.mark.asyncio
async def test_stream_events_no_retry_after_downstream_emission(monkeypatch):
    """已向下游产出文本增量后流截断:不得重试(下游已消费,重放会重复)。"""
    client = _make_client()
    attempts = []

    def fake_stream(self, method, url, **kwargs):
        attempts.append(1)
        return FakeStreamCM(
            FakeStreamResponse(_events({"type": "response.output_text.delta", "delta": "半"}))
        )

    monkeypatch.setattr(httpx.AsyncClient, "stream", fake_stream)
    monkeypatch.setattr(oc, "_retry_delay_seconds", lambda attempt, response=None: 0)
    with pytest.raises(oc._TruncatedStreamError):
        await _collect(client, [{"role": "user", "content": "x"}], request_max_attempts=3)
    assert len(attempts) == 1
