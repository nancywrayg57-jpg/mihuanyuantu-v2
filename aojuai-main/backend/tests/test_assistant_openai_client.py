from __future__ import annotations

import pytest

from app.domain.assistant.openai_client import (
    OpenAIClient,
    _payload_after_parameter_error,
    _responses_input_from_messages,
)


def test_upstream_error_does_not_look_like_stream_parameter_error() -> None:
    payload = {"model": "gpt-test", "messages": [], "stream": False}

    assert _payload_after_parameter_error(payload, "Upstream request failed") is None


@pytest.mark.asyncio
async def test_openai_client_chat_with_usage_allows_per_call_max_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OpenAIClient(
        base_url="https://api.example.com/v1",
        api_key="test-key",
        model="test-model",
        max_tokens=2048,
    )
    captured: dict[str, object] = {}

    async def fake_sync_chat_with_usage(
        url: str,
        payload: dict[str, object],
        *,
        api_type: str = "chat_completions",
        allow_responses_fallback: bool = False,
    ) -> tuple[str, dict[str, int]]:
        _ = api_type, allow_responses_fallback
        captured["url"] = url
        captured["payload"] = payload
        return "ok", {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}

    monkeypatch.setattr(client, "_sync_chat_with_usage", fake_sync_chat_with_usage)

    text, usage = await client.chat_with_usage(
        [{"role": "user", "content": "hello"}],
        stream=False,
        max_tokens=512,
    )

    assert text == "ok"
    assert usage["total_tokens"] == 3
    assert captured["url"] == "https://api.example.com/v1/chat/completions"
    assert captured["payload"]["max_tokens"] == 512


@pytest.mark.asyncio
async def test_openai_client_chat_defaults_to_client_max_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OpenAIClient(
        base_url="https://api.example.com/v1",
        api_key="test-key",
        model="test-model",
        max_tokens=1024,
    )
    captured: dict[str, object] = {}

    async def fake_sync_chat_with_usage(
        url: str,
        payload: dict[str, object],
        *,
        api_type: str = "chat_completions",
        allow_responses_fallback: bool = False,
    ) -> tuple[str, dict[str, int]]:
        _ = api_type, allow_responses_fallback
        captured["payload"] = payload
        return "ok", {}

    monkeypatch.setattr(client, "_sync_chat_with_usage", fake_sync_chat_with_usage)

    text = await client.chat([{"role": "user", "content": "hello"}])

    assert text == "ok"
    assert captured["payload"]["max_tokens"] == 1024


def test_openai_client_responses_input_uses_message_list_for_gateway_compatibility() -> None:
    payload = _responses_input_from_messages(
        [
            {"role": "developer", "content": "保持简洁。"},
            {"role": "user", "content": [{"type": "input_text", "text": "查询项目"}]},
            {"role": "unknown", "content": "非标准角色"},
        ]
    )

    assert payload == "DEVELOPER:\n保持简洁。\n\nUSER:\n查询项目\n\nUSER:\n非标准角色"


@pytest.mark.asyncio
async def test_openai_client_auto_gpt_uses_responses_payload_list(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OpenAIClient(
        base_url="https://api.example.com/v1",
        api_key="test-key",
        model="gpt-5.4-mini",
        max_tokens=2048,
        api_mode="auto",
    )
    captured: dict[str, object] = {}

    # 新契约：responses 模式（含 auto 命中 gpt）下非流式调用统一走流式聚合——
    # 多网关的 responses 转发只支持 SSE 输出，非流式端点 400/500。
    async def fake_responses_stream_collect(
        messages: list[dict[str, object]],
        *,
        max_tokens: int | None = None,
        request_max_attempts: int | None = None,
    ) -> tuple[str, dict[str, object]]:
        captured["messages"] = messages
        captured["max_tokens"] = max_tokens
        return "ok", {"usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}}

    monkeypatch.setattr(client, "responses_stream_collect", fake_responses_stream_collect)

    text, usage = await client.chat_with_usage(
        [{"role": "user", "content": "hello"}],
        stream=False,
        max_tokens=512,
    )

    assert text == "ok"
    assert usage["total_tokens"] == 3
    assert captured["messages"] == [{"role": "user", "content": "hello"}]
    assert captured["max_tokens"] == 512
