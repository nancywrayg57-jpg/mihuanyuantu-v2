"""chat_stream_collect：流式聚合解析与断流重试（样本来自真实网关 SSE 抓包）。"""
import asyncio
import json

import httpx
import pytest

from app.domain.assistant import openai_client as oc


def _events(*payloads):
    """按真实 SSE 形态构造行序列：每个事件一个 data 行 + 空行分隔。"""
    lines = []
    for p in payloads:
        lines.append(p if isinstance(p, str) else f"data: {json.dumps(p)}")
        lines.append("")
    return lines


def _sse_lines_ok():
    rid = "resp_test"
    return _events(
        {"id": rid, "object": "chat.completion.chunk", "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}]},
        {"id": rid, "object": "chat.completion.chunk", "choices": [{"index": 0, "delta": {"content": "长"}, "finish_reason": None}]},
        {"id": rid, "object": "chat.completion.chunk", "choices": [{"index": 0, "delta": {"content": "江"}, "finish_reason": None}]},
        ": sse-comment-line",
        {"id": rid, "choices": [{"index": 0, "delta": {"content": ""}, "finish_reason": "stop"}]},
        # 真实网关的 usage 收尾块：choices 为空数组（旧解析 data["choices"][0] 在此越界）
        {"id": rid, "choices": [], "usage": {"prompt_tokens": 12, "completion_tokens": 56, "total_tokens": 68}},
        "data: [DONE]",
    )


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
        raise httpx.HTTPStatusError("err", request=httpx.Request("POST", "http://x"), response=httpx.Response(self.status_code))


class KeepAliveAfterCompletedResponse(FakeStreamResponse):
    async def aiter_lines(self):
        for line in self._lines:
            yield line
        await asyncio.Event().wait()


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
    return oc.OpenAIClient(base_url="https://gw.example/v1", api_key="k", model="gpt-5.5", max_tokens=8000, timeout_seconds=5)


@pytest.mark.asyncio
async def test_stream_collect_aggregates_and_captures_usage(monkeypatch):
    client = _make_client()
    calls = []

    def fake_stream(self, method, url, **kwargs):
        calls.append(url)
        return FakeStreamCM(FakeStreamResponse(_sse_lines_ok()))

    monkeypatch.setattr(httpx.AsyncClient, "stream", fake_stream)
    text, meta = await client.chat_stream_collect([{"role": "user", "content": "hi"}])
    assert text == "长江"
    assert meta["finishReason"] == "stop"
    assert 56 in meta["usage"].values()
    assert client.last_request_metrics["responseChars"] == 2
    assert calls and calls[0].endswith("/chat/completions")


@pytest.mark.asyncio
async def test_stream_collect_retries_after_midstream_disconnect(monkeypatch):
    client = _make_client()
    attempts = {"n": 0}

    class BrokenResponse(FakeStreamResponse):
        async def aiter_lines(self):
            yield _sse_lines_ok()[2]
            yield ""
            raise httpx.ReadError("connection reset")

    def fake_stream(self, method, url, **kwargs):
        attempts["n"] += 1
        if attempts["n"] == 1:
            return FakeStreamCM(BrokenResponse([]))
        return FakeStreamCM(FakeStreamResponse(_sse_lines_ok()))

    monkeypatch.setattr(httpx.AsyncClient, "stream", fake_stream)
    monkeypatch.setattr(oc, "_retry_delay_seconds", lambda attempt, response=None: 0)
    text, meta = await client.chat_stream_collect([{"role": "user", "content": "hi"}], request_max_attempts=2)
    assert text == "长江"  # 首次断流的半截内容被整体丢弃，无重复拼接
    assert attempts["n"] == 2
    assert meta["attempt"] == 2


@pytest.mark.asyncio
async def test_stream_collect_empty_stream_raises_after_attempts(monkeypatch):
    client = _make_client()

    def fake_stream(self, method, url, **kwargs):
        return FakeStreamCM(FakeStreamResponse(["data: [DONE]", ""]))

    monkeypatch.setattr(httpx.AsyncClient, "stream", fake_stream)
    monkeypatch.setattr(oc, "_retry_delay_seconds", lambda attempt, response=None: 0)
    with pytest.raises(oc._EmptyStreamError):
        await client.chat_stream_collect([{"role": "user", "content": "hi"}], request_max_attempts=2)


@pytest.mark.asyncio
async def test_stream_collect_alternate_delta_shapes(monkeypatch):
    client = _make_client()
    lines = _events(
        {"choices": [{"index": 0, "text": "你", "finish_reason": None}]},
        {"choices": [{"index": 0, "message": {"content": "好"}, "finish_reason": "stop"}]},
        "data: [DONE]",
    )

    def fake_stream(self, method, url, **kwargs):
        return FakeStreamCM(FakeStreamResponse(lines))

    monkeypatch.setattr(httpx.AsyncClient, "stream", fake_stream)
    text, _ = await client.chat_stream_collect([{"role": "user", "content": "hi"}])
    assert text == "你好"


@pytest.mark.asyncio
async def test_stream_collect_rejects_truncated_finish_reason(monkeypatch):
    client = _make_client()
    lines = _events(
        {"choices": [{"index": 0, "delta": {"content": "半截"}, "finish_reason": None}]},
        {"choices": [{"index": 0, "delta": {"content": ""}, "finish_reason": "length"}]},
        "data: [DONE]",
    )

    def fake_stream(self, method, url, **kwargs):
        return FakeStreamCM(FakeStreamResponse(lines))

    monkeypatch.setattr(httpx.AsyncClient, "stream", fake_stream)
    with pytest.raises(oc._StreamFinishError):
        await client.chat_stream_collect([{"role": "user", "content": "hi"}], request_max_attempts=1)


@pytest.mark.asyncio
async def test_stream_collect_natural_eof_without_done_retries(monkeypatch):
    client = _make_client()
    attempts = {"n": 0}
    half = _events({"choices": [{"index": 0, "delta": {"content": "半"}, "finish_reason": None}]})

    def fake_stream(self, method, url, **kwargs):
        attempts["n"] += 1
        if attempts["n"] == 1:
            return FakeStreamCM(FakeStreamResponse(half))  # 无 [DONE] 无 finish → 静默截断
        return FakeStreamCM(FakeStreamResponse(_sse_lines_ok()))

    monkeypatch.setattr(httpx.AsyncClient, "stream", fake_stream)
    monkeypatch.setattr(oc, "_retry_delay_seconds", lambda attempt, response=None: 0)
    text, meta = await client.chat_stream_collect([{"role": "user", "content": "hi"}], request_max_attempts=2)
    assert text == "长江"
    assert attempts["n"] == 2


@pytest.mark.asyncio
async def test_stream_collect_preserves_whitespace_across_chunks(monkeypatch):
    """历史 bug 回归锁：逐 chunk strip 会吃掉聚合文本的空格。"""
    client = _make_client()
    lines = _events(
        {"choices": [{"index": 0, "delta": {"content": "<svg"}, "finish_reason": None}]},
        {"choices": [{"index": 0, "delta": {"content": " xmlns=\"x\""}, "finish_reason": None}]},
        {"choices": [{"index": 0, "delta": {"content": " viewBox=\"0 0 1280 720\">"}, "finish_reason": None}]},
        {"choices": [{"index": 0, "delta": {"content": "\n</svg>"}, "finish_reason": "stop"}]},
        "data: [DONE]",
    )

    def fake_stream(self, method, url, **kwargs):
        return FakeStreamCM(FakeStreamResponse(lines))

    monkeypatch.setattr(httpx.AsyncClient, "stream", fake_stream)
    text, _ = await client.chat_stream_collect([{"role": "user", "content": "hi"}])
    assert text == '<svg xmlns="x" viewBox="0 0 1280 720">\n</svg>'


@pytest.mark.asyncio
async def test_responses_stream_collect_aggregates(monkeypatch):
    """responses SSE：正文在 output_text.delta.delta，usage 在 completed 事件（真实网关样本）。"""
    client = _make_client()
    lines = _events(
        {"type": "response.created", "response": {"id": "resp_x", "status": "in_progress"}},
        {"type": "response.output_item.added", "output_index": 0},
        {"type": "response.output_text.delta", "content_index": 0, "delta": "长", "output_index": 1},
        {"type": "response.output_text.delta", "content_index": 0, "delta": " 江", "output_index": 1},
        {"type": "response.output_text.done", "output_index": 1},
        {"type": "response.completed", "response": {"id": "resp_x", "status": "completed", "usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30}}},
    )

    def fake_stream(self, method, url, **kwargs):
        assert url.endswith("/responses")
        return FakeStreamCM(FakeStreamResponse(lines))

    monkeypatch.setattr(httpx.AsyncClient, "stream", fake_stream)
    text, meta = await client.responses_stream_collect([{"role": "user", "content": "hi"}])
    assert text == "长 江"  # 空格保真
    assert meta["finishReason"] == "completed"
    assert 20 in meta["usage"].values()


@pytest.mark.asyncio
async def test_responses_stream_collect_returns_on_completed_before_transport_closes(monkeypatch):
    client = _make_client()
    lines = _events(
        {"type": "response.output_text.delta", "delta": "完整结果"},
        {"type": "response.completed", "response": {"status": "completed", "usage": {}}},
    )
    monkeypatch.setattr(
        httpx.AsyncClient,
        "stream",
        lambda self, method, url, **kwargs: FakeStreamCM(KeepAliveAfterCompletedResponse(lines)),
    )

    text, meta = await asyncio.wait_for(
        client.responses_stream_collect([{"role": "user", "content": "hi"}]),
        timeout=0.2,
    )
    assert text == "完整结果"
    assert meta["finishReason"] == "completed"


@pytest.mark.asyncio
async def test_responses_stream_collect_missing_completed_retries(monkeypatch):
    client = _make_client()
    attempts = {"n": 0}
    partial = _events({"type": "response.output_text.delta", "delta": "半"})
    full = _events(
        {"type": "response.output_text.delta", "delta": "全"},
        {"type": "response.completed", "response": {"status": "completed", "usage": {}}},
    )

    def fake_stream(self, method, url, **kwargs):
        attempts["n"] += 1
        return FakeStreamCM(FakeStreamResponse(partial if attempts["n"] == 1 else full))

    monkeypatch.setattr(httpx.AsyncClient, "stream", fake_stream)
    monkeypatch.setattr(oc, "_retry_delay_seconds", lambda attempt, response=None: 0)
    text, meta = await client.responses_stream_collect([{"role": "user", "content": "hi"}], request_max_attempts=2)
    assert text == "全" and attempts["n"] == 2


def test_prompt_cache_scope_injected_into_payloads():
    client = _make_client()
    client.prompt_cache_scope = "aoju-ppt-tenant-1"
    chat_payload = client._build_payload([{"role": "user", "content": "hi"}], stream=True)
    assert chat_payload["user"] == "aoju-ppt-tenant-1"
    assert chat_payload["prompt_cache_key"] == "aoju-ppt-tenant-1"
    resp_payload = client._build_responses_payload([{"role": "user", "content": "hi"}])
    assert resp_payload["prompt_cache_key"] == "aoju-ppt-tenant-1"
    # 未设置 scope 时不注入，避免影响其他域既有行为
    bare = _make_client()
    assert "prompt_cache_key" not in bare._build_payload([{"role": "user", "content": "hi"}])


def test_responses_cacheable_input_preserves_stable_user_role():
    client = _make_client()
    payload = client._build_responses_payload(
        [
            {"role": "system", "content": "system contract"},
            {"role": "user", "content": "stable project context"},
            {"role": "user", "content": "dynamic page"},
        ],
        stable_prefix_messages=2,
    )

    assert payload["input"] == [
        {
            "type": "message",
            "role": "developer",
            "content": [{"type": "input_text", "text": "system contract"}],
        },
        {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": "stable project context"}],
        },
        {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": "dynamic page"}],
        },
    ]


@pytest.mark.asyncio
async def test_prime_prompt_cache_uses_shared_request_path(monkeypatch):
    client = _make_client()
    client.api_mode = "responses"
    captured = []

    async def fake_with_metrics(messages, **kwargs):
        captured.append((messages, kwargs))
        return "READY", {"prompt_tokens": 1200, "cached_tokens": 0}, {"apiType": "responses"}

    monkeypatch.setattr(client, "chat_with_usage_and_metrics", fake_with_metrics)
    messages = [{"role": "system", "content": "stable"}, {"role": "user", "content": "prefix"}]
    usage, metrics = await client.prime_prompt_cache(messages, stream=True)

    assert captured == [
        (
            messages,
            {
                "stream": True,
                "max_tokens": 16,
                "request_max_attempts": 1,
                "stable_prefix_messages": 2,
            },
        )
    ]
    assert usage["prompt_tokens"] == 1200
    assert metrics == {"apiType": "responses"}
