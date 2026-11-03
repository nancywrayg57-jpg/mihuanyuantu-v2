from __future__ import annotations

from app.domain.speech.registry import (
    get_provider_by_id,
    get_provider_secret_keys,
    get_speech_provider_catalog,
    get_speech_provider_prompt_context,
    normalize_provider_id,
)
from app.domain.speech.schemas import SpeechTenantConfigUpsertRequest


def test_provider_catalog_contains_expected_ids() -> None:
    providers = get_speech_provider_catalog()
    ids = {p.id for p in providers}
    tts_ids = [p.id for p in providers if p.category == "tts"]
    stt_ids = [p.id for p in providers if p.category == "stt"]

    assert ids == {
        "system_tts",
        "edge_tts",
        "aliyun_qwen_tts",
        "aliyun_qwen_tts_realtime_sdk",
        "xiaomi_mimo",
        "system_stt",
    }
    assert tts_ids == ["system_tts", "edge_tts", "aliyun_qwen_tts", "aliyun_qwen_tts_realtime_sdk", "xiaomi_mimo"]
    assert stt_ids == ["system_stt"]


def test_provider_lookup() -> None:
    p = get_provider_by_id("edge_tts")
    assert p is not None
    assert p.category == "tts"
    assert p.model_dump(by_alias=True)["capabilities"]["supportsVoiceClone"] is False

    mimo = get_provider_by_id("mimo_tts")
    assert mimo is not None
    assert mimo.id == "xiaomi_mimo"

    aliyun = get_provider_by_id("aliyun_qwen_tts")
    assert aliyun is not None
    model_field = next(field for field in aliyun.fields if field.key == "model")
    assert any(str(option.value) == "qwen3-tts-vc-2026-01-22" for option in model_field.options)
    assert aliyun.model_dump(by_alias=True)["capabilities"]["supportsVoiceClone"] is True


def test_secret_keys_detection() -> None:
    assert "apiKey" in get_provider_secret_keys("xiaomi_mimo")
    assert "apiKey" in get_provider_secret_keys("mimo_tts")
    assert "apiKey" in get_provider_secret_keys("aliyun_qwen_tts")
    assert "apiKey" in get_provider_secret_keys("aliyun_qwen_tts_realtime_sdk")
    assert get_provider_secret_keys("edge_tts") == set()
    assert get_provider_secret_keys("system_tts") == set()
    assert get_provider_secret_keys("system_stt") == set()


def test_stt_alias_asr_supported() -> None:
    data = SpeechTenantConfigUpsertRequest.model_validate(
        {
            "asr": {
                "providerId": "openai_whisper",
                "settings": {"model": "whisper-1"},
                "secrets": {"apiKey": "sk-test"},
            }
        }
    )
    assert data.stt is not None
    assert data.stt.provider_id == "openai_whisper"


def test_provider_alias_normalization() -> None:
    assert normalize_provider_id("mimo_tts") == "xiaomi_mimo"
    assert normalize_provider_id("xiaomi_mimo_tts") == "xiaomi_mimo"
    assert normalize_provider_id("aliyun_qwen_tts") == "aliyun_qwen_tts"


def test_prompt_context_becomes_model_aware_for_qwen_voice_clone_model() -> None:
    context = get_speech_provider_prompt_context(
        "aliyun_qwen_tts",
        provider_settings={
            "model": "qwen3-tts-vc-2026-01-22",
            "voice": "voice_clone_001",
            "voiceCloneId": 8,
        },
    )

    assert context["selectedModel"] == "qwen3-tts-vc-2026-01-22"
    assert context["modelCapabilities"]["supportsVoiceClone"] is True
    assert context["modelCapabilities"]["supportsInstructions"] is False
    assert context["modelCapabilities"]["allowedCueFields"] == []
    assert context["supportedVoices"][0]["voice"] == "voice_clone_001"
    assert any("复刻音色通道" in item for item in context["modelNotes"])
    assert any("固定声音人格" in item for item in context["generationGuidance"])



def test_prompt_context_supports_qwen_realtime_sdk_provider() -> None:
    context = get_speech_provider_prompt_context(
        "aliyun_qwen_tts_realtime_sdk",
        provider_settings={"model": "qwen3-tts-instruct-flash-realtime", "voice": "Cherry"},
    )

    assert context["selectedModel"] == "qwen3-tts-instruct-flash-realtime"
    assert context["modelCapabilities"]["supportsInstructions"] is False
    assert context["modelCapabilities"]["allowedCueFields"] == ["voice", "languageType"]
    assert any("DashScope Python SDK" in item for item in context["instructionGuidance"])


def test_mimo_provider_allows_voice_clone_candidate_toggle() -> None:
    mimo = get_provider_by_id("xiaomi_mimo")

    assert mimo is not None
    assert mimo.model_dump(by_alias=True)["capabilities"]["supportsVoiceClone"] is True

def test_prompt_context_marks_xiaomi_mimo_as_style_driven() -> None:
    context = get_speech_provider_prompt_context(
        "xiaomi_mimo",
        provider_settings={"model": "mimo-v2.5-tts"},
    )

    assert context["selectedModel"] == "mimo-v2.5-tts"
    assert context["modelCapabilities"]["supportsStyle"] is True
    assert context["modelCapabilities"]["supportsInstructions"] is True
    assert context["modelCapabilities"]["allowedCueFields"] == ["voice", "style", "requestOverrides"]
