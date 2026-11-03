from __future__ import annotations

import pytest

from app.core.exceptions import BusinessError
from app.domain.speech.providers.aliyun_qwen_voice_clone import (
    DEFAULT_ALIYUN_QWEN_VOICE_CLONE_BASE_URL,
    aliyun_qwen_create_voice_clone,
    resolve_aliyun_qwen_voice_clone_base_url,
)


def test_resolve_aliyun_qwen_voice_clone_base_url_defaults_to_cn_endpoint() -> None:
    assert resolve_aliyun_qwen_voice_clone_base_url(None) == DEFAULT_ALIYUN_QWEN_VOICE_CLONE_BASE_URL


def test_resolve_aliyun_qwen_voice_clone_base_url_maps_intl_dashscope_host() -> None:
    assert (
        resolve_aliyun_qwen_voice_clone_base_url("https://dashscope-intl.aliyuncs.com")
        == "https://dashscope-intl.aliyuncs.com/api/v1/services/audio/tts/customization"
    )


@pytest.mark.asyncio
async def test_aliyun_qwen_create_voice_clone_rejects_missing_api_key() -> None:
    with pytest.raises(BusinessError, match="API Key"):
        await aliyun_qwen_create_voice_clone(
            api_key="",
            audio_bytes=b"demo",
            content_type="audio/mpeg",
            preferred_name="demo-voice",
        )
