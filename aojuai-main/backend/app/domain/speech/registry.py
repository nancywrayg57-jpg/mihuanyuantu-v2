"""
AOJU Backend - Speech Provider Registry

基座语音 provider 真值：
- TTS: system_tts / edge_tts / aliyun_qwen_tts / xiaomi_mimo
- STT: system_stt

下游产品只消费这里的基座目录，不再各自维护额外 provider 集合。
"""

from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from typing import Any

from app.domain.speech.providers.aliyun_qwen_tts import (
    build_aliyun_qwen_tts_prompt_context,
    build_aliyun_qwen_tts_provider_descriptor,
)
from app.domain.speech.providers.aliyun_qwen_tts_realtime_sdk import (
    build_aliyun_qwen_tts_realtime_sdk_prompt_context,
    build_aliyun_qwen_tts_realtime_sdk_provider_descriptor,
)
from app.domain.speech.providers.xiaomi_mimo import (
    build_xiaomi_mimo_prompt_context,
    build_xiaomi_mimo_provider_descriptor,
)
from app.domain.speech.schemas import (
    SpeechFieldOption,
    SpeechFieldType,
    SpeechProviderCapabilities,
    SpeechProviderDescriptor,
    SpeechProviderFieldSchema,
)


def _field(
    *,
    key: str,
    label: str,
    field_type: SpeechFieldType,
    required: bool = False,
    description: str | None = None,
    placeholder: str | None = None,
    default: object | None = None,
    options: list[SpeechFieldOption] | None = None,
    ui: dict | None = None,
) -> SpeechProviderFieldSchema:
    return SpeechProviderFieldSchema(
        key=key,
        label=label,
        type=field_type,
        required=required,
        description=description,
        placeholder=placeholder,
        default=default,
        options=options or [],
        ui=ui,
    )


def _build_system_tts_provider_descriptor() -> SpeechProviderDescriptor:
    return SpeechProviderDescriptor(
        id="system_tts",
        category="tts",
        name="System TTS (Browser, free)",
        description="浏览器原生语音合成（Web Speech API）。仅在前端运行，不经过后端。",
        capabilities=SpeechProviderCapabilities(
            supports_voices_list=True,
            supports_cancel=True,
        ),
        fields=[],
    )


def _build_edge_tts_provider_descriptor() -> SpeechProviderDescriptor:
    edge_common_voices = [
        SpeechFieldOption(value="zh-CN-XiaoxiaoNeural", label="zh-CN Xiaoxiao (女)"),
        SpeechFieldOption(value="zh-CN-YunxiNeural", label="zh-CN Yunxi (男)"),
        SpeechFieldOption(value="zh-CN-XiaoyiNeural", label="zh-CN Xiaoyi (女)"),
        SpeechFieldOption(value="zh-CN-YunyangNeural", label="zh-CN Yunyang (男)"),
        SpeechFieldOption(value="ja-JP-NanamiNeural", label="ja-JP Nanami (女)"),
        SpeechFieldOption(value="ko-KR-SunHiNeural", label="ko-KR SunHi (여)"),
    ]

    return SpeechProviderDescriptor(
        id="edge_tts",
        category="tts",
        name="Microsoft Edge TTS (free)",
        description="基于 Edge ReadAloud 的在线语音合成（非官方接口），作为免费默认/备用 TTS。",
        capabilities=SpeechProviderCapabilities(
            supports_voices_list=True,
            supports_tts_stream_audio=True,
            supports_cancel=False,
        ),
        fields=[
            _field(
                key="voice",
                label="Voice",
                field_type=SpeechFieldType.SELECT,
                required=True,
                description="常用音色下拉可选；也可手动输入完整 Voice 名称。",
                default="zh-CN-XiaoxiaoNeural",
                options=edge_common_voices,
                ui={"allowCreate": True, "filterable": True},
            ),
            _field(
                key="rate",
                label="Rate",
                field_type=SpeechFieldType.NUMBER,
                description="语速（百分比，-50 ~ +50；运行态会转换为 +0% 形式）",
                default=0,
                ui={"component": "slider", "min": -50, "max": 50, "step": 1, "unit": "%", "showInput": True},
            ),
            _field(
                key="volume",
                label="Volume",
                field_type=SpeechFieldType.NUMBER,
                description="音量（百分比，-50 ~ +50）",
                default=0,
                ui={"component": "slider", "min": -50, "max": 50, "step": 1, "unit": "%", "showInput": True},
            ),
            _field(
                key="pitch",
                label="Pitch",
                field_type=SpeechFieldType.NUMBER,
                description="音高（Hz，-50 ~ +50）",
                default=0,
                ui={"component": "slider", "min": -50, "max": 50, "step": 1, "unit": "Hz", "showInput": True},
            ),
            _field(
                key="outputFormat",
                label="Output Format",
                field_type=SpeechFieldType.SELECT,
                description="TTS 输出格式（仅配置项；实际取决于运行态实现）。",
                default="mp3",
                options=[
                    SpeechFieldOption(value="mp3", label="mp3"),
                    SpeechFieldOption(value="wav", label="wav"),
                    SpeechFieldOption(value="opus", label="opus"),
                ],
            ),
        ],
    )


def _build_system_stt_provider_descriptor() -> SpeechProviderDescriptor:
    return SpeechProviderDescriptor(
        id="system_stt",
        category="stt",
        name="System STT (Browser, free)",
        description="浏览器原生语音识别（Web Speech API）。需要 Chrome/Edge 且使用 HTTPS 或 localhost。",
        capabilities=SpeechProviderCapabilities(
            supports_asr_stream=True,
            supports_cancel=True,
        ),
        fields=[],
    )


@lru_cache
def get_speech_provider_catalog() -> list[SpeechProviderDescriptor]:
    return [
        _build_system_tts_provider_descriptor(),
        _build_edge_tts_provider_descriptor(),
        build_aliyun_qwen_tts_provider_descriptor(),
        build_aliyun_qwen_tts_realtime_sdk_provider_descriptor(),
        build_xiaomi_mimo_provider_descriptor(),
        _build_system_stt_provider_descriptor(),
    ]


_PROVIDER_ID_ALIASES = {
    "mimo_tts": "xiaomi_mimo",
    "xiaomi_mimo_tts": "xiaomi_mimo",
}


def normalize_provider_id(provider_id: str | None) -> str:
    normalized = str(provider_id or "").strip()
    if not normalized:
        return ""
    return _PROVIDER_ID_ALIASES.get(normalized, normalized)


def get_provider_by_id(provider_id: str) -> SpeechProviderDescriptor | None:
    normalized_provider_id = normalize_provider_id(provider_id)
    if not normalized_provider_id:
        return None
    for provider in get_speech_provider_catalog():
        if provider.id == normalized_provider_id:
            return provider
    return None


def get_provider_secret_keys(provider_id: str) -> set[str]:
    provider = get_provider_by_id(provider_id)
    if not provider:
        return set()
    return {field.key for field in provider.fields if field.type == SpeechFieldType.SECRET}


def get_speech_provider_prompt_context(
    provider_id: str,
    *,
    provider_settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_provider_id = normalize_provider_id(provider_id)
    if not normalized_provider_id:
        return {}
    settings = provider_settings if isinstance(provider_settings, dict) else {}
    selected_model = str(settings.get("model") or "").strip() or None
    selected_voice = str(settings.get("voice") or "").strip() or None
    voice_clone_id = settings.get("voiceCloneId")

    if normalized_provider_id == "aliyun_qwen_tts":
        return deepcopy(
            build_aliyun_qwen_tts_prompt_context(
                model=selected_model,
                voice=selected_voice,
                voice_clone_id=voice_clone_id,
            )
        )
    if normalized_provider_id == "aliyun_qwen_tts_realtime_sdk":
        return deepcopy(
            build_aliyun_qwen_tts_realtime_sdk_prompt_context(
                model=selected_model,
            )
        )
    if normalized_provider_id == "xiaomi_mimo":
        return deepcopy(build_xiaomi_mimo_prompt_context(model=selected_model))

    descriptor = get_provider_by_id(normalized_provider_id)
    if descriptor is None:
        return {}

    supported_voices: list[dict[str, str]] = []
    supported_languages: list[dict[str, str]] = []
    voice_field = next((field for field in descriptor.fields if field.key == "voice"), None)
    language_field = next((field for field in descriptor.fields if field.key == "languageType"), None)

    if voice_field is not None:
        for option in voice_field.options[:8]:
            voice = str(option.value or "").strip()
            if voice:
                supported_voices.append(
                    {
                        "voice": voice,
                        "description": str(option.description or option.label or voice).strip(),
                    }
                )

    if language_field is not None:
        for option in language_field.options[:8]:
            language_type = str(option.value or "").strip()
            if language_type:
                supported_languages.append(
                    {
                        "languageType": language_type,
                        "description": str(option.description or option.label or language_type).strip(),
                    }
                )

    guidance: list[str] = []
    if str(descriptor.description or "").strip():
        guidance.append(str(descriptor.description or "").strip())
    allowed_cue_fields: list[str] = []
    for field_key in ("voice", "style", "instructions", "languageType", "optimizeInstructions", "requestOverrides"):
        if any(str(field.key or "").strip() == field_key for field in descriptor.fields):
            allowed_cue_fields.append(field_key)

    generation_guidance: list[str] = []
    if "instructions" in allowed_cue_fields:
        generation_guidance.append(
            "内容生成时先参考 supportedVoices 选择声音基线，再用 instructions 细化语气、情绪和停顿。"
        )
    elif "style" in allowed_cue_fields:
        generation_guidance.append(
            "内容生成时先稳定当前 voice，再用 style 控制长期氛围和表达气质，不要套用 instructions 通道。"
        )
    elif "voice" in allowed_cue_fields:
        generation_guidance.append(
            "内容生成时主要通过 voice 选择声音基线；如果当前音色已经合适，优先沿用，不必为了变化强行切换。"
        )
    else:
        generation_guidance.append(
            "当前模型没有适合按段调节的标准声音字段，内容生成应以固定声音基线为主。"
        )

    if "languageType" in allowed_cue_fields:
        generation_guidance.append(
            "只有在内容确实涉及多语或跨语种表达时才调整 languageType，其余场景优先保持当前语言基线。"
        )

    return {
        "providerName": str(descriptor.name or normalized_provider_id).strip(),
        "providerDescription": str(descriptor.description or "").strip(),
        "selectedModel": selected_model,
        "modelCapabilities": {
            "selectedModel": selected_model,
            "supportsVoiceClone": bool(getattr(descriptor.capabilities, "supports_voice_clone", False)),
            "supportsInstructions": "instructions" in allowed_cue_fields,
            "supportsOptimizeInstructions": "optimizeInstructions" in allowed_cue_fields,
            "supportsStyle": "style" in allowed_cue_fields,
            "supportsLanguageType": "languageType" in allowed_cue_fields,
            "supportsRequestOverrides": "requestOverrides" in allowed_cue_fields,
            "voiceSelectionMode": "official_or_custom",
            "allowedCueFields": allowed_cue_fields,
        },
        "supportedVoices": supported_voices,
        "supportedLanguages": supported_languages,
        "instructionGuidance": guidance[:4],
        "cueSchemaGuidance": [
            (
                "建议仅返回当前模型实际支持的字段：" + " / ".join(allowed_cue_fields)
                if allowed_cue_fields
                else "当前模型没有可按段调整的标准字段。"
            )
        ],
        "generationGuidance": generation_guidance[:4],
    }
