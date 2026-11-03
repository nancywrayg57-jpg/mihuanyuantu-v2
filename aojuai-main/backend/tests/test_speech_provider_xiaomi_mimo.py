from __future__ import annotations

import base64

import httpx
import pytest

from app.core.exceptions import BusinessError
from app.domain.speech.providers.xiaomi_mimo import (
    build_xiaomi_mimo_voice_clone_data_uri,
    xiaomi_mimo_tts_synthesize_stream,
)


class _FakeAsyncClient:
    def __init__(self, *, outcomes: list[object], **_: object) -> None:
        self._outcomes = outcomes

    async def __aenter__(self) -> _FakeAsyncClient:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        return None

    async def post(self, *args, **kwargs) -> httpx.Response:  # noqa: ANN002, ANN003
        if not self._outcomes:
            raise AssertionError("unexpected extra post() call")
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.mark.asyncio
async def test_xiaomi_mimo_retries_transient_http_error_before_success(monkeypatch: pytest.MonkeyPatch) -> None:
    audio_payload = base64.b64encode(b"fake-audio").decode("ascii")
    attempts: list[int] = []
    outcomes: list[object] = [
        httpx.ReadTimeout("timed out"),
        httpx.Response(
            200,
            json={"choices": [{"message": {"audio": {"data": audio_payload}}}]},
        ),
    ]

    def _client_factory(**kwargs: object) -> _FakeAsyncClient:
        _ = kwargs
        return _FakeAsyncClient(outcomes=outcomes)

    async def _fake_sleep(delay: float) -> None:
        attempts.append(int(delay * 10))

    monkeypatch.setattr(httpx, "AsyncClient", _client_factory)
    monkeypatch.setattr("app.domain.speech.providers.xiaomi_mimo.asyncio.sleep", _fake_sleep)

    stream = await xiaomi_mimo_tts_synthesize_stream(
        api_key="test-key",
        text="测试一下",
        audio_format="mp3",
    )

    assert b"".join([chunk async for chunk in stream.iterator]) == b"fake-audio"
    assert attempts == [5]


@pytest.mark.asyncio
async def test_xiaomi_mimo_raises_after_retry_budget_exhausted(monkeypatch: pytest.MonkeyPatch) -> None:
    outcomes: list[object] = [
        httpx.ReadTimeout("timed out"),
        httpx.ReadTimeout("timed out again"),
        httpx.ConnectError("still failing"),
    ]

    def _client_factory(**kwargs: object) -> _FakeAsyncClient:
        _ = kwargs
        return _FakeAsyncClient(outcomes=outcomes)

    async def _fake_sleep(delay: float) -> None:
        _ = delay

    monkeypatch.setattr(httpx, "AsyncClient", _client_factory)
    monkeypatch.setattr("app.domain.speech.providers.xiaomi_mimo.asyncio.sleep", _fake_sleep)

    with pytest.raises(BusinessError, match="Xiaomi MiMo 请求失败"):
        await xiaomi_mimo_tts_synthesize_stream(
            api_key="test-key",
            text="测试一下",
            audio_format="mp3",
        )


@pytest.mark.asyncio
async def test_xiaomi_mimo_v25_payload_uses_user_style_and_assistant_text(monkeypatch: pytest.MonkeyPatch) -> None:
    audio_payload = base64.b64encode(b"fake-audio").decode("ascii")
    captured: dict[str, object] = {}

    def _client_factory(**kwargs: object) -> _FakeAsyncClient:
        _ = kwargs

        class _Client(_FakeAsyncClient):
            async def post(self, *args, **kwargs) -> httpx.Response:  # noqa: ANN002, ANN003
                captured.update(kwargs)
                return httpx.Response(200, json={"choices": [{"message": {"audio": {"data": audio_payload}}}]})

        return _Client(outcomes=[])

    monkeypatch.setattr(httpx, "AsyncClient", _client_factory)

    stream = await xiaomi_mimo_tts_synthesize_stream(
        api_key="test-key",
        text="欢迎回来",
        model="mimo-v2.5-tts",
        voice="default_zh",
        style="温柔但清晰",
        audio_format="wav",
    )

    assert b"".join([chunk async for chunk in stream.iterator]) == b"fake-audio"
    payload = captured["json"]
    assert payload["model"] == "mimo-v2.5-tts"
    assert payload["messages"] == [
        {"role": "user", "content": "温柔但清晰"},
        {"role": "assistant", "content": "欢迎回来"},
    ]
    assert payload["audio"] == {"voice": "default_zh", "format": "wav"}


def test_xiaomi_mimo_voice_clone_data_uri_accepts_mp3_and_wav() -> None:
    mp3_uri = build_xiaomi_mimo_voice_clone_data_uri(audio_bytes=b"abc", content_type="audio/mp3")
    wav_uri = build_xiaomi_mimo_voice_clone_data_uri(audio_bytes=b"abc", content_type="audio/wav")

    assert mp3_uri == "data:audio/mpeg;base64,YWJj"
    assert wav_uri == "data:audio/wav;base64,YWJj"


def test_xiaomi_mimo_voice_clone_data_uri_rejects_unsupported_type() -> None:
    with pytest.raises(BusinessError, match="仅支持 mp3 或 wav"):
        build_xiaomi_mimo_voice_clone_data_uri(audio_bytes=b"abc", content_type="audio/mp4")
