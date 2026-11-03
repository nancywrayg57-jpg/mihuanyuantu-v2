"""Alibaba Bailian Qwen TTS provider runtime."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.core.exceptions import BusinessError
from app.domain.speech.providers.common import (
    SpeechAudioStream,
    bytes_to_stream,
    concat_wav_audio_segments,
    decode_base64_audio,
    deep_merge,
    extract_first_base64,
    extract_first_url,
    iter_sse_json,
    media_type_and_ext_from_content_type,
    normalize_object_overrides,
    wrap_pcm16_as_wav_if_needed,
)
from app.domain.speech.schemas import (
    SpeechFieldOption,
    SpeechFieldType,
    SpeechProviderCapabilities,
    SpeechProviderDescriptor,
    SpeechProviderFieldSchema,
)

DEFAULT_ALIYUN_QWEN_TTS_BASE_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
DEFAULT_ALIYUN_QWEN_TTS_MODEL = "qwen3-tts-instruct-flash"
DEFAULT_ALIYUN_QWEN_TTS_VOICE = "Cherry"
ALIYUN_QWEN_TTS_MAX_INPUT_BYTES = 600
ALIYUN_QWEN_TTS_SAFE_INPUT_BYTES = 540
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？!?；;])")

ALIYUN_QWEN_TTS_VOICE_OPTIONS = [
    SpeechFieldOption(value="Cherry", label="Cherry · 芊悦", description="阳光积极、亲切自然小姐姐（女性）"),
    SpeechFieldOption(value="Serena", label="Serena · 苏瑶", description="温柔小姐姐（女性）"),
    SpeechFieldOption(value="Ethan", label="Ethan · 晨煦", description="阳光、温暖、活力、朝气（男性）"),
    SpeechFieldOption(value="Chelsie", label="Chelsie · 千雪", description="二次元虚拟女友（女性）"),
    SpeechFieldOption(value="Momo", label="Momo · 茉兔", description="撒娇搞怪，逗你开心（女性）"),
    SpeechFieldOption(value="Vivian", label="Vivian · 十三", description="拽拽的、可爱的小暴躁（女性）"),
    SpeechFieldOption(value="Moon", label="Moon · 月白", description="率性帅气的月白（男性）"),
    SpeechFieldOption(value="Maia", label="Maia · 四月", description="知性与温柔的碰撞（女性）"),
    SpeechFieldOption(value="Kai", label="Kai · 凯", description="耳朵的一场 SPA（男性）"),
    SpeechFieldOption(value="Neil", label="Neil · 阿闻", description="专业新闻播报（男性）"),
]

ALIYUN_QWEN_TTS_LANGUAGE_OPTIONS = [
    SpeechFieldOption(value="Chinese", label="Chinese · 中文"),
    SpeechFieldOption(value="English", label="English · 英文"),
    SpeechFieldOption(value="Japanese", label="Japanese · 日语"),
    SpeechFieldOption(value="Korean", label="Korean · 韩语"),
    SpeechFieldOption(value="French", label="French · 法语"),
    SpeechFieldOption(value="German", label="German · 德语"),
    SpeechFieldOption(value="Spanish", label="Spanish · 西班牙语"),
    SpeechFieldOption(value="Portuguese", label="Portuguese · 葡萄牙语"),
    SpeechFieldOption(value="Italian", label="Italian · 意大利语"),
    SpeechFieldOption(value="Russian", label="Russian · 俄语"),
]

_ALIYUN_LANGUAGE_TYPE_ALIASES = {
    "auto": "Auto",
    "zh": "Chinese",
    "zh-cn": "Chinese",
    "zh_cn": "Chinese",
    "zh-hans": "Chinese",
    "zh_hans": "Chinese",
    "chinese": "Chinese",
    "中文": "Chinese",
    "汉语": "Chinese",
    "普通话": "Chinese",
    "cn": "Chinese",
    "en": "English",
    "en-us": "English",
    "en_us": "English",
    "english": "English",
    "英语": "English",
    "es": "Spanish",
    "spanish": "Spanish",
    "西班牙语": "Spanish",
    "ja": "Japanese",
    "ja-jp": "Japanese",
    "ja_jp": "Japanese",
    "japanese": "Japanese",
    "日语": "Japanese",
    "ko": "Korean",
    "ko-kr": "Korean",
    "ko_kr": "Korean",
    "korean": "Korean",
    "韩语": "Korean",
    "fr": "French",
    "french": "French",
    "法语": "French",
    "de": "German",
    "german": "German",
    "德语": "German",
    "it": "Italian",
    "italian": "Italian",
    "意大利语": "Italian",
    "pt": "Portuguese",
    "portuguese": "Portuguese",
    "葡萄牙语": "Portuguese",
    "ru": "Russian",
    "russian": "Russian",
    "俄语": "Russian",
}


def normalize_aliyun_qwen_tts_model(model: str | None, *, fallback: str = DEFAULT_ALIYUN_QWEN_TTS_MODEL) -> str:
    normalized = str(model or "").strip()
    return normalized or fallback


def is_aliyun_qwen_tts_instruct_model(model: str | None) -> bool:
    return normalize_aliyun_qwen_tts_model(model).startswith("qwen3-tts-instruct")


def is_aliyun_qwen_tts_voice_clone_model(model: str | None) -> bool:
    return normalize_aliyun_qwen_tts_model(model).startswith("qwen3-tts-vc")


def _build_aliyun_qwen_tts_model_capabilities(model: str | None) -> dict[str, Any]:
    normalized_model = normalize_aliyun_qwen_tts_model(model)
    is_clone_model = is_aliyun_qwen_tts_voice_clone_model(normalized_model)
    is_instruct_model = is_aliyun_qwen_tts_instruct_model(normalized_model)
    return {
        "selectedModel": normalized_model,
        "supportsVoiceClone": is_clone_model,
        "supportsInstructions": is_instruct_model,
        "supportsOptimizeInstructions": is_instruct_model,
        "supportsStyle": False,
        "supportsLanguageType": not is_clone_model,
        "supportsRequestOverrides": not is_clone_model,
        "voiceSelectionMode": "cloned_voice_only" if is_clone_model else "official_or_custom",
        "allowedCueFields": (
            []
            if is_clone_model
            else (
                ["voice", "instructions", "languageType", "optimizeInstructions", "requestOverrides"]
                if is_instruct_model
                else ["voice", "languageType", "requestOverrides"]
            )
        ),
    }


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


def build_aliyun_qwen_tts_provider_descriptor() -> SpeechProviderDescriptor:
    return SpeechProviderDescriptor(
        id="aliyun_qwen_tts",
        category="tts",
        name="Alibaba Bailian Qwen TTS",
        description="阿里百炼 Qwen3 TTS，支持 instruct voice、语言类型和请求级参数扩展。",
        capabilities=SpeechProviderCapabilities(
            supports_tts_stream_audio=True,
            supports_voices_list=True,
            supports_voice_clone=True,
        ),
        fields=[
            _field(
                key="apiKey",
                label="API Key",
                field_type=SpeechFieldType.SECRET,
                required=True,
                description="DashScope / 百炼 API Key。",
            ),
            _field(
                key="baseUrl",
                label="Base URL",
                field_type=SpeechFieldType.STRING,
                default=DEFAULT_ALIYUN_QWEN_TTS_BASE_URL,
                description="默认接入北京地域；国际站可改为 dashscope-intl。",
            ),
            _field(
                key="model",
                label="Model",
                field_type=SpeechFieldType.SELECT,
                default=DEFAULT_ALIYUN_QWEN_TTS_MODEL,
                options=[
                    SpeechFieldOption(value=DEFAULT_ALIYUN_QWEN_TTS_MODEL, label=DEFAULT_ALIYUN_QWEN_TTS_MODEL),
                    SpeechFieldOption(value="qwen3-tts-instruct-flash-2026-01-26", label="qwen3-tts-instruct-flash-2026-01-26"),
                    SpeechFieldOption(value="qwen3-tts-vc-2026-01-22", label="qwen3-tts-vc-2026-01-22"),
                ],
                ui={"allowCreate": True, "filterable": True},
            ),
            _field(
                key="voice",
                label="Voice",
                field_type=SpeechFieldType.SELECT,
                default=DEFAULT_ALIYUN_QWEN_TTS_VOICE,
                options=ALIYUN_QWEN_TTS_VOICE_OPTIONS,
                description="可直接填写官方系统音色或自定义/复刻音色名。",
                ui={"allowCreate": True, "filterable": True},
            ),
            _field(
                key="languageType",
                label="Language Type",
                field_type=SpeechFieldType.SELECT,
                default="Chinese",
                options=ALIYUN_QWEN_TTS_LANGUAGE_OPTIONS,
                ui={"allowCreate": True, "filterable": True},
            ),
            _field(
                key="instructions",
                label="Instructions",
                field_type=SpeechFieldType.TEXTAREA,
                description="仅 instruct 系列模型生效，用自然语言描述语速、语气、情绪和角色气质。",
                placeholder="例如：语速偏慢，语气温柔克制，适合长时间收听，停顿自然，字头清楚，不要播音腔。",
            ),
            _field(
                key="optimizeInstructions",
                label="Optimize Instructions",
                field_type=SpeechFieldType.BOOLEAN,
                default=False,
                description="开启后先优化 instructions，再交给 instruct 模型执行。",
            ),
            _field(
                key="requestOverrides",
                label="Request Overrides (JSON)",
                field_type=SpeechFieldType.JSON,
                default={},
                description="与默认请求体深合并，适合补充官方暂未固化到表单里的参数。",
            ),
            _field(
                key="stream",
                label="Stream",
                field_type=SpeechFieldType.BOOLEAN,
                default=True,
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


def build_aliyun_qwen_tts_prompt_context(
    *,
    model: str | None = None,
    voice: str | None = None,
    voice_clone_id: Any = None,
) -> dict[str, Any]:
    descriptor = build_aliyun_qwen_tts_provider_descriptor()
    model_capabilities = _build_aliyun_qwen_tts_model_capabilities(model)
    selected_model = str(model_capabilities["selectedModel"]).strip()
    is_clone_model = bool(model_capabilities["supportsVoiceClone"])
    selected_voice = str(voice or "").strip()
    clone_voice_active = bool(voice_clone_id or (selected_voice and selected_voice.startswith("voice_clone")))
    supported_voices = [
        {
            "voice": str(option.value or "").strip(),
            "label": str(option.label or option.value or "").strip(),
            "description": str(option.description or option.label or option.value or "").strip(),
            "supportedLanguages": [
                str(language_option.value or "").strip()
                for language_option in ALIYUN_QWEN_TTS_LANGUAGE_OPTIONS
                if str(language_option.value or "").strip()
            ],
        }
        for option in ALIYUN_QWEN_TTS_VOICE_OPTIONS
        if str(option.value or "").strip()
    ]
    if is_clone_model:
        supported_voices = []
        if selected_voice:
            supported_voices.append(
                {
                    "voice": selected_voice,
                    "label": selected_voice,
                    "description": "当前配置已经切到复刻音色通道，后续应稳定沿用这一路 voice，不要再回退到官方示例音色。",
                    "supportedLanguages": [str(_normalize_aliyun_language_type(None) or "Chinese")],
                }
            )

    if is_clone_model:
        instruction_guidance = [
            "当前模型是声音复刻合成模型，重点是稳定复用当前 clone voice，不再依赖 instructions / style 做内容级人设控制。",
            "复刻模型阶段不要继续输出 instructions、optimizeInstructions、requestOverrides 这类 instruct 通道字段。",
            "如果需要换声音人格，应该回到内容级基线或重新选择 clone，而不是在分段 cue 里频繁切换 voice。",
        ]
        cue_schema_guidance = [
            "当前模型不建议返回任何按段 ttsCue 字段；默认沿用已激活的 clone voice 即可。",
        ]
        model_notes = [
            f"当前模型：{selected_model}",
            "该模型用于复刻音色合成，字段边界与 instruct 模型不同。",
            "内容生成与分段声线 agent 必须把当前 clone voice 视为固定声音人格，不要再尝试写 instructions 或 style。",
        ]
        generation_guidance = [
            "内容生成时把当前 clone voice 当成固定声音人格，内容基线和分段 ttsCue 都应优先沿用，不要切回官方示例音色。",
            "当前模型不适合靠 instructions 控制语气，若想改变表达气质，应在更上层重新选择 voice 或 clone 通道。",
        ]
        if clone_voice_active:
            model_notes.append("当前 voice 已识别为复刻音色通道。")
    else:
        instruction_guidance = [
            "该 provider 的 instructions 只对 qwen3-tts-instruct-flash 系列生效。",
            "instructions 采用自然语言描述声音表现，描述文本仅支持中文和英文，长度不超过 1600 Token。",
            "写 instructions 时要具体、客观、简洁，尽量同时覆盖音调、语速、情感、特点或用途中的 2 到 4 个维度。",
            "优先用 instructions 微调语速、语气、情绪、停顿和角色气质；只有确实需要换音色时才改 voice。",
            "避免模仿名人或写主观空话，像“好听”“普通”“像某位明星”这类描述都不适合。",
        ]
        cue_schema_guidance = [
            (
                "建议返回 voice / instructions / languageType / optimizeInstructions / requestOverrides 中真正需要变化的字段。"
                if bool(model_capabilities["supportsInstructions"])
                else "当前模型不走 instructions 通道，建议只返回 voice / languageType / requestOverrides。"
            )
        ]
        model_notes = [
            f"当前模型：{selected_model}",
            (
                "当前模型属于 instruct 通道，可用 instructions 描述语气、停顿、情绪和角色气质。"
                if bool(model_capabilities["supportsInstructions"])
                else "当前模型不走 instruct 通道，内容级气质主要依赖 voice 选择，不要输出 instructions。"
            ),
        ]
        generation_guidance = [
            (
                "内容生成时先参考 supportedVoices 的音色说明选择声音人格，再用 instructions 补足语气、情绪和停顿。"
                if bool(model_capabilities["supportsInstructions"])
                else "内容生成时优先根据 supportedVoices 选择合适音色，内容气质主要靠 voice 决定，不要继续输出 instructions。"
            ),
            "如果 currentSettings 已经贴近内容 brief，优先沿用当前 voice，只做少量长期语气补充，不要为了变化而强行换音色。",
        ]

    return {
        "providerName": str(descriptor.name or "aliyun_qwen_tts").strip(),
        "providerDescription": str(descriptor.description or "").strip(),
        "selectedModel": selected_model,
        "modelCapabilities": model_capabilities,
        "supportedVoices": supported_voices,
        "supportedLanguages": [
            {
                "languageType": str(option.value or "").strip(),
                "label": str(option.label or option.value or "").strip(),
                "description": str(option.description or option.label or "").strip(),
            }
            for option in ALIYUN_QWEN_TTS_LANGUAGE_OPTIONS
            if str(option.value or "").strip()
        ],
        "instructionGuidance": instruction_guidance,
        "cueSchemaGuidance": cue_schema_guidance,
        "modelNotes": model_notes,
        "generationGuidance": generation_guidance,
    }


def _normalize_aliyun_language_type(language_type: str | None) -> str | None:
    normalized = str(language_type or "").strip()
    if not normalized:
        return None
    return _ALIYUN_LANGUAGE_TYPE_ALIASES.get(normalized.lower(), normalized)


def _utf8_size(text: str) -> int:
    return len(str(text).encode("utf-8"))


def _hard_split_aliyun_qwen_tts_text(text: str, *, max_bytes: int) -> list[str]:
    chunks: list[str] = []
    current = ""
    for char in text:
        candidate = f"{current}{char}"
        if _utf8_size(candidate) <= max_bytes:
            current = candidate
            continue
        if current:
            chunks.append(current)
        current = char
    if current:
        chunks.append(current)
    return chunks


def _split_aliyun_qwen_tts_text(text: str, *, max_bytes: int) -> list[str]:
    normalized = str(text or "").strip()
    if not normalized:
        return []
    if _utf8_size(normalized) <= max_bytes:
        return [normalized]

    parts: list[str] = []
    paragraphs = [item.strip() for item in re.split(r"\n\s*\n+", normalized) if item.strip()]
    if not paragraphs:
        paragraphs = [normalized]

    for paragraph in paragraphs:
        if _utf8_size(paragraph) <= max_bytes:
            parts.append(paragraph)
            continue
        sentences = [item.strip() for item in _SENTENCE_SPLIT_RE.split(paragraph) if item.strip()]
        if len(sentences) <= 1:
            parts.extend(_hard_split_aliyun_qwen_tts_text(paragraph, max_bytes=max_bytes))
            continue

        current = ""
        for sentence in sentences:
            candidate = sentence if not current else f"{current}{sentence}"
            if _utf8_size(candidate) <= max_bytes:
                current = candidate
                continue
            if current:
                parts.append(current)
            if _utf8_size(sentence) <= max_bytes:
                current = sentence
            else:
                parts.extend(_hard_split_aliyun_qwen_tts_text(sentence, max_bytes=max_bytes))
                current = ""
        if current:
            parts.append(current)

    collapsed: list[str] = []
    current = ""
    for part in parts:
        candidate = part if not current else f"{current}\n\n{part}"
        if _utf8_size(candidate) <= max_bytes:
            current = candidate
            continue
        if current:
            collapsed.append(current)
        current = part
    if current:
        collapsed.append(current)
    return collapsed or [normalized[: max(1, max_bytes // 3)]]


async def _aliyun_qwen_tts_synthesize_single_chunk(
    *,
    api_key: str,
    text: str,
    base_url: str,
    model: str,
    voice: str,
    language_type: str | None = None,
    instructions: str | None = None,
    optimize_instructions: bool = False,
    stream: bool = True,
    request_overrides: object | None = None,
    timeout_seconds: float = 60,
) -> bytes:
    parameters: dict[str, object] = {}
    normalized_instructions = str(instructions or "").strip()
    if normalized_instructions:
        parameters["instructions"] = normalized_instructions
        parameters["optimize_instructions"] = bool(optimize_instructions)

    payload: dict[str, object] = {
        "model": model,
        "input": {
            "text": text,
            "voice": voice,
        },
    }
    normalized_language_type = _normalize_aliyun_language_type(language_type)
    if normalized_language_type:
        payload["input"]["language_type"] = normalized_language_type  # type: ignore[index]
    if parameters:
        payload["parameters"] = parameters
    payload = deep_merge(
        payload,
        normalize_object_overrides(request_overrides, label="阿里百炼 Qwen TTS requestOverrides"),
    )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if stream:
        headers["Accept"] = "text/event-stream"
        headers["X-DashScope-SSE"] = "enable"

    audio_chunks: list[bytes] = []
    final_audio_url = ""

    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds), follow_redirects=True) as client:
        try:
            if stream:
                async with client.stream("POST", base_url, headers=headers, json=payload) as response:
                    if response.status_code >= 400:
                        body = (await response.aread()).decode("utf-8", errors="ignore")
                        raise BusinessError(
                            message=f"阿里百炼 Qwen TTS 返回错误（HTTP {response.status_code}）",
                            details={"body": body[:2000]},
                        )

                    async for event in iter_sse_json(response):
                        if not isinstance(event, dict):
                            continue
                        output = event.get("output")
                        if not isinstance(output, dict):
                            continue
                        audio = output.get("audio")
                        if isinstance(audio, dict):
                            data = audio.get("data")
                            if isinstance(data, str) and data.strip():
                                audio_chunks.append(decode_base64_audio(data))
                            url = audio.get("url")
                            if isinstance(url, str) and url.strip():
                                final_audio_url = url.strip()
                        if output.get("finish_reason") == "stop":
                            break
            else:
                response = await client.post(base_url, headers=headers, json=payload)
                if response.status_code >= 400:
                    raise BusinessError(
                        message=f"阿里百炼 Qwen TTS 返回错误（HTTP {response.status_code}）",
                        details={"body": response.text[:2000]},
                    )

                payload_json = response.json()
                base64_audio = extract_first_base64(payload_json, ["data", "audioBase64", "audio_base64"])
                if base64_audio:
                    audio_chunks.append(decode_base64_audio(base64_audio))
                final_audio_url = extract_first_url(payload_json, ["url", "audioUrl", "audio_url"])
        except httpx.HTTPError as exc:
            raise BusinessError(message="阿里百炼 Qwen TTS 请求失败", details={"error": str(exc)}) from exc
        except json.JSONDecodeError as exc:
            raise BusinessError(message="阿里百炼 Qwen TTS 返回不是合法 JSON", details={"error": str(exc)}) from exc

        if not audio_chunks and final_audio_url:
            try:
                asset_response = await client.get(
                    final_audio_url,
                    headers={"Authorization": f"Bearer {api_key}"},
                )
            except httpx.HTTPError as exc:
                raise BusinessError(message="阿里百炼 Qwen TTS 下载音频失败", details={"error": str(exc)}) from exc
            if asset_response.status_code >= 400:
                raise BusinessError(
                    message=f"阿里百炼 Qwen TTS 获取音频返回错误（HTTP {asset_response.status_code}）",
                    details={"url": final_audio_url},
                )
            media_type, _ = media_type_and_ext_from_content_type(asset_response.headers.get("content-type"))
            if media_type == "application/octet-stream":
                media_type = "audio/wav"
            if media_type != "audio/wav":
                raise BusinessError(
                    message="阿里百炼 Qwen TTS 返回了不支持直接拼接的音频格式",
                    details={"mediaType": media_type},
                )
            return asset_response.content

    audio_bytes = b"".join(audio_chunks)
    if not audio_bytes:
        raise BusinessError(message="阿里百炼 Qwen TTS 未返回音频数据")
    return wrap_pcm16_as_wav_if_needed(audio_bytes=audio_bytes, sample_rate=24000)


async def aliyun_qwen_tts_synthesize_stream(
    *,
    api_key: str,
    text: str,
    base_url: str,
    model: str,
    voice: str,
    language_type: str | None = None,
    instructions: str | None = None,
    optimize_instructions: bool = False,
    stream: bool = True,
    request_overrides: object | None = None,
    timeout_seconds: float = 60,
) -> SpeechAudioStream:
    normalized_base_url = str(base_url or "").strip()
    normalized_model = str(model or "").strip()
    normalized_voice = str(voice or "").strip()
    normalized_text = str(text or "").strip()
    if not normalized_base_url:
        raise BusinessError(message="阿里百炼 Qwen TTS 缺少 baseUrl")
    if not str(api_key or "").strip():
        raise BusinessError(message="阿里百炼 Qwen TTS 缺少 apiKey")
    if not normalized_model:
        raise BusinessError(message="阿里百炼 Qwen TTS 缺少 model")
    if not normalized_voice:
        raise BusinessError(message="阿里百炼 Qwen TTS 缺少 voice")
    if not normalized_text:
        raise BusinessError(message="阿里百炼 Qwen TTS 缺少文本")

    text_chunks = _split_aliyun_qwen_tts_text(
        normalized_text,
        max_bytes=min(ALIYUN_QWEN_TTS_SAFE_INPUT_BYTES, ALIYUN_QWEN_TTS_MAX_INPUT_BYTES),
    )
    wav_segments: list[bytes] = []
    for text_chunk in text_chunks:
        wav_segments.append(
            await _aliyun_qwen_tts_synthesize_single_chunk(
                api_key=api_key,
                text=text_chunk,
                base_url=normalized_base_url,
                model=normalized_model,
                voice=normalized_voice,
                language_type=language_type,
                instructions=instructions,
                optimize_instructions=optimize_instructions,
                stream=stream,
                request_overrides=request_overrides,
                timeout_seconds=timeout_seconds,
            )
        )

    wav_bytes = concat_wav_audio_segments(audio_segments=wav_segments, sample_rate=24000, channels=1)
    return bytes_to_stream(data=wav_bytes, media_type="audio/wav", ext="wav")
