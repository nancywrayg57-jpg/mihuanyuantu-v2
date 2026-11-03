"""Xiaomi MiMo provider runtime."""

from __future__ import annotations

import asyncio
import base64
import json
from typing import Any

import httpx

from app.core.exceptions import BusinessError
from app.domain.speech.providers.common import (
    SpeechAudioStream,
    apply_xiaomi_style,
    bytes_to_stream,
    decode_base64_audio,
    deep_merge,
    media_type_and_ext_from_hint,
    normalize_object_overrides,
)
from app.domain.speech.schemas import (
    SpeechFieldOption,
    SpeechFieldType,
    SpeechProviderCapabilities,
    SpeechProviderDescriptor,
    SpeechProviderFieldSchema,
)

DEFAULT_XIAOMI_MIMO_BASE_URL = "https://api.xiaomimimo.com/v1"
DEFAULT_XIAOMI_MIMO_MODEL = "mimo-v2.5-tts"
DEFAULT_XIAOMI_MIMO_VOICE = "mimo_default"
DEFAULT_XIAOMI_MIMO_AUDIO_FORMAT = "mp3"
DEFAULT_XIAOMI_MIMO_MAX_ATTEMPTS = 3

XIAOMI_MIMO_BUILT_IN_VOICE_OPTIONS = [
    SpeechFieldOption(value="mimo_default", label="MiMo 默认"),
    SpeechFieldOption(value="冰糖", label="冰糖 · 中文女声"),
    SpeechFieldOption(value="茉莉", label="茉莉 · 中文女声"),
    SpeechFieldOption(value="苏打", label="苏打 · 中文男声"),
    SpeechFieldOption(value="白桦", label="白桦 · 中文男声"),
    SpeechFieldOption(value="Mia", label="Mia · English Female"),
    SpeechFieldOption(value="Chloe", label="Chloe · English Female"),
    SpeechFieldOption(value="Milo", label="Milo · English Male"),
    SpeechFieldOption(value="Dean", label="Dean · English Male"),
]


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
    ui: dict[str, Any] | None = None,
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


def build_xiaomi_mimo_provider_descriptor() -> SpeechProviderDescriptor:
    return SpeechProviderDescriptor(
        id="xiaomi_mimo",
        category="tts",
        name="Xiaomi MiMo TTS",
        description="小米 MiMo TTS，适合中文陪伴场景，可单独配置音色与风格。",
        capabilities=SpeechProviderCapabilities(
            supports_tts_stream_audio=False,
            supports_voice_clone=True,
        ),
        fields=[
            _field(
                key="apiKey",
                label="API Key",
                field_type=SpeechFieldType.SECRET,
                required=True,
            ),
            _field(
                key="baseUrl",
                label="Base URL",
                field_type=SpeechFieldType.STRING,
                default=DEFAULT_XIAOMI_MIMO_BASE_URL,
            ),
            _field(
                key="model",
                label="Model",
                field_type=SpeechFieldType.SELECT,
                default=DEFAULT_XIAOMI_MIMO_MODEL,
                options=[
                    SpeechFieldOption(value="mimo-v2.5-tts", label="mimo-v2.5-tts"),
                    SpeechFieldOption(value="mimo-v2.5-tts-voicedesign", label="mimo-v2.5-tts-voicedesign"),
                    SpeechFieldOption(value="mimo-v2.5-tts-voiceclone", label="mimo-v2.5-tts-voiceclone"),
                    SpeechFieldOption(value="mimo-v2-tts", label="mimo-v2-tts (legacy)"),
                ],
                ui={"allowCreate": True, "filterable": True},
            ),
            _field(
                key="voice",
                label="Voice",
                field_type=SpeechFieldType.SELECT,
                default=DEFAULT_XIAOMI_MIMO_VOICE,
                description="MiMo v2.5 内置音色或复刻样本引用；voiceclone 模式通常由声音复刻工作区自动填入。",
                options=XIAOMI_MIMO_BUILT_IN_VOICE_OPTIONS,
                ui={"allowCreate": True, "filterable": True},
            ),
            _field(
                key="style",
                label="风格 / 指令",
                field_type=SpeechFieldType.STRING,
                default="温柔陪伴",
                description="自然语言风格会放入 user message；开启音频标签控制时，也会作为 assistant 文本开头的 (风格) 标签。",
            ),
            _field(
                key="textInjectionMode",
                label="控制方式",
                field_type=SpeechFieldType.SELECT,
                default="plain",
                options=[
                    SpeechFieldOption(value="plain", label="自然语言控制"),
                    SpeechFieldOption(value="audio_tag", label="音频标签控制"),
                ],
                description="音频标签控制会把风格写成 (风格) 前缀放入 assistant content，适合细粒度语速、情绪、停顿控制。",
            ),
            _field(
                key="audioFormat",
                label="Audio Format",
                field_type=SpeechFieldType.SELECT,
                default=DEFAULT_XIAOMI_MIMO_AUDIO_FORMAT,
                options=[
                    SpeechFieldOption(value="wav", label="wav"),
                    SpeechFieldOption(value="mp3", label="mp3"),
                    SpeechFieldOption(value="pcm", label="pcm"),
                ],
            ),
            _field(
                key="requestOverrides",
                label="Request Overrides (JSON)",
                field_type=SpeechFieldType.JSON,
                default={},
                description="按当前模型支持字段填写，将与默认请求体深合并；适合不同模型的动态参数。",
            ),
            _field(
                key="previewText",
                label="Preview Text",
                field_type=SpeechFieldType.TEXTAREA,
                description="当前渠道声音试听的默认文案。留空时系统会按当前租户品牌名和使用场景自动生成。",
                placeholder="例如：这里是你的品牌语音，正在试听当前声音，语气自然，适合长时间收听。",
            ),
            _field(
                key="timeoutSeconds",
                label="Timeout (s)",
                field_type=SpeechFieldType.NUMBER,
                default=60,
                ui={"component": "slider", "min": 5, "max": 300, "step": 5, "showInput": True},
            ),
        ],
    )


def build_xiaomi_mimo_prompt_context(*, model: str | None = None) -> dict[str, Any]:
    descriptor = build_xiaomi_mimo_provider_descriptor()
    selected_model = str(model or DEFAULT_XIAOMI_MIMO_MODEL).strip() or DEFAULT_XIAOMI_MIMO_MODEL
    return {
        "providerName": str(descriptor.name or "xiaomi_mimo").strip(),
        "providerDescription": str(descriptor.description or "").strip(),
        "selectedModel": selected_model,
        "modelCapabilities": {
            "selectedModel": selected_model,
            "supportsVoiceClone": selected_model == "mimo-v2.5-tts-voiceclone",
            "supportsVoiceDesign": selected_model == "mimo-v2.5-tts-voicedesign",
            "supportsInstructions": True,
            "supportsOptimizeInstructions": False,
            "supportsStyle": True,
            "supportsLanguageType": False,
            "supportsRequestOverrides": True,
            "voiceSelectionMode": "voice_sample" if selected_model == "mimo-v2.5-tts-voiceclone" else "official_or_custom",
            "allowedCueFields": ["voice", "style", "requestOverrides"],
        },
        "supportedVoices": [
            {"voice": "mimo_default", "description": "MiMo 默认音色；中国集群通常默认为冰糖，其他集群通常默认为 Mia。"},
            {"voice": "冰糖", "description": "中文女声。"},
            {"voice": "茉莉", "description": "中文女声。"},
            {"voice": "苏打", "description": "中文男声。"},
            {"voice": "白桦", "description": "中文男声。"},
            {"voice": "Mia", "description": "英文女声。"},
            {"voice": "Chloe", "description": "英文女声。"},
            {"voice": "Milo", "description": "英文男声。"},
            {"voice": "Dean", "description": "英文男声。"},
        ],
        "supportedLanguages": [],
        "instructionGuidance": [
            "该 provider 更适合围绕 voice、style 和 requestOverrides 来调表现，通常不需要 languageType。",
            "自然语言控制放在 user message；音频标签控制放在 assistant content，可在目标文本开头使用 (风格1 风格2) 这类标签。",
            "如果需要中途细粒度控制，可在合成文本中插入括号标签，但不要把标签写成解释性旁白。",
            "若只是想让语气更贴近内容氛围，优先改 style；只有确实要换音色时再改 voice。",
        ],
        "cueSchemaGuidance": [
            "建议返回 voice / style / requestOverrides 这组字段，不要机械带上 languageType。",
        ],
        "modelNotes": [
            f"当前模型：{selected_model}",
            "MiMo v2.5 内置音色、文本设计音色和按样本复刻分别对应不同 model。",
        ],
        "generationGuidance": [
            "内容生成时先看当前 voice 和 supportedVoices 来确定声音人格，再用 style 控制氛围和情绪。",
            "MiMo 的自然语言风格进入 user message；若启用音频标签控制，style 会作为 assistant 文本开头的 (风格) 标签。",
        ],
    }


def _resolve_xiaomi_mimo_endpoint(base_url: str | None) -> str:
    normalized_base_url = str(base_url or DEFAULT_XIAOMI_MIMO_BASE_URL).strip().rstrip("/")
    if not normalized_base_url:
        raise BusinessError(message="Xiaomi MiMo 缺少 Base URL")
    if normalized_base_url.endswith("/chat/completions"):
        return normalized_base_url
    return f"{normalized_base_url}/chat/completions"


def build_xiaomi_mimo_voice_clone_data_uri(*, audio_bytes: bytes, content_type: str) -> str:
    normalized_content_type = str(content_type or "").strip().lower()
    if normalized_content_type in {"audio/mp3", "audio/mpeg"}:
        media_type = "audio/mpeg"
    elif normalized_content_type in {"audio/wav", "audio/x-wav", "audio/wave"}:
        media_type = "audio/wav"
    else:
        raise BusinessError(message="MiMo v2.5 声音复刻仅支持 mp3 或 wav 样本")
    encoded = base64.b64encode(audio_bytes).decode("ascii")
    if len(encoded.encode("utf-8")) > 10 * 1024 * 1024:
        raise BusinessError(message="MiMo v2.5 声音复刻样本超过 10MB Base64 限制")
    return f"data:{media_type};base64,{encoded}"


async def xiaomi_mimo_tts_synthesize_stream(
    *,
    api_key: str,
    text: str,
    base_url: str | None = None,
    model: str | None = None,
    voice: str | None = None,
    style: str | None = None,
    text_injection_mode: str | None = None,
    audio_format: str | None = None,
    request_overrides: object | None = None,
    timeout_seconds: float = 60,
) -> SpeechAudioStream:
    normalized_model = str(model or DEFAULT_XIAOMI_MIMO_MODEL).strip()
    if not normalized_model:
        raise BusinessError(message="Xiaomi MiMo 缺少 Model")

    normalized_format = str(audio_format or DEFAULT_XIAOMI_MIMO_AUDIO_FORMAT).strip().lower()
    if normalized_format not in {"wav", "mp3", "pcm"}:
        raise BusinessError(message="Xiaomi MiMo Audio Format 不受支持")

    rendered_text = apply_xiaomi_style(text, style=style, mode=text_injection_mode)
    request_voice = str(voice or "").strip() or DEFAULT_XIAOMI_MIMO_VOICE
    style_text = str(style or "").strip()
    messages = []
    if style_text:
        messages.append({"role": "user", "content": style_text})
    messages.append({"role": "assistant", "content": rendered_text})
    endpoint = _resolve_xiaomi_mimo_endpoint(base_url)
    payload = deep_merge(
        {
            "model": normalized_model,
            "stream": False,
            "messages": messages,
            "audio": {"voice": request_voice, "format": normalized_format},
        },
        normalize_object_overrides(request_overrides, label="Xiaomi MiMo requestOverrides"),
    )

    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds), follow_redirects=True) as client:
        response: httpx.Response | None = None
        last_error: httpx.HTTPError | None = None
        for attempt in range(1, DEFAULT_XIAOMI_MIMO_MAX_ATTEMPTS + 1):
            try:
                response = await client.post(
                    endpoint,
                    headers={
                        "Content-Type": "application/json",
                        "api-key": api_key,
                    },
                    json=payload,
                )
                last_error = None
                break
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt >= DEFAULT_XIAOMI_MIMO_MAX_ATTEMPTS:
                    break
                await asyncio.sleep(0.5 * attempt)

        if last_error is not None or response is None:
            raise BusinessError(message="Xiaomi MiMo 请求失败", details={"error": str(last_error) if last_error else "unknown"}) from last_error

        if response.status_code >= 400:
            raise BusinessError(
                message=f"Xiaomi MiMo 接口返回 HTTP {response.status_code}",
                details={"body": response.text[:1000]},
            )

        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise BusinessError(message="Xiaomi MiMo 返回不是合法 JSON", details={"error": str(exc)}) from exc

    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise BusinessError(message="Xiaomi MiMo 响应缺少 choices")

    first_choice = choices[0] if isinstance(choices[0], dict) else {}
    message = first_choice.get("message") if isinstance(first_choice.get("message"), dict) else {}
    audio = message.get("audio") if isinstance(message.get("audio"), dict) else {}
    audio_data = audio.get("data")
    if not isinstance(audio_data, str) or not audio_data.strip():
        raise BusinessError(message="Xiaomi MiMo 响应缺少音频数据")

    audio_bytes = decode_base64_audio(audio_data)
    media_type, ext = media_type_and_ext_from_hint(normalized_format)
    return bytes_to_stream(data=audio_bytes, media_type=media_type, ext=ext)
