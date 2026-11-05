"""
AOJU Backend - Speech Config Endpoints

租户级语音配置（TTS / STT）：
- 提供可选 provider 列表与字段 schema（用于前端动态渲染配置项）
- 读写租户当前选择的 provider 与配置（密钥脱敏）

同时提供最小可用的「演示接口」：
- TTS: 基于租户配置合成音频（支持 edge_tts / gemini_tts / glm_tts / openai_tts / azure_tts / doubao_tts / custom_http_tts；system_tts 为前端能力）
- STT: 基于租户配置语音转文字（支持 openai_whisper / glm_asr / gemini_asr / azure_stt / doubao_asr / doubao_stream_asr / custom_http_stt；funasr_local 需本地部署暂不接入演示）
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse

from app.api.deps import CurrentTenantAdmin, DBSession, TenantCtx
from app.core.exceptions import BusinessError
from app.core.logger import get_logger
from app.core.response import SuccessResponse
from app.core.schemas import ResponseBase
from app.domain.credits.service import CreditService
from app.domain.speech.billing import charge_speech_text_credits
from app.domain.speech.providers.aliyun_qwen_tts import (
    DEFAULT_ALIYUN_QWEN_TTS_BASE_URL,
    DEFAULT_ALIYUN_QWEN_TTS_MODEL,
    DEFAULT_ALIYUN_QWEN_TTS_VOICE,
    aliyun_qwen_tts_synthesize_stream,
)
from app.domain.speech.providers.aliyun_qwen_tts_realtime_sdk import (
    DEFAULT_ALIYUN_QWEN_TTS_REALTIME_MODEL,
    DEFAULT_ALIYUN_QWEN_TTS_REALTIME_WS_URL,
    aliyun_qwen_tts_realtime_sdk_synthesize_stream,
)
from app.domain.speech.providers.common import SpeechAudioStream, bytes_to_stream
from app.domain.speech.providers.xiaomi_mimo import (
    DEFAULT_XIAOMI_MIMO_AUDIO_FORMAT,
    DEFAULT_XIAOMI_MIMO_BASE_URL,
    DEFAULT_XIAOMI_MIMO_MODEL,
    xiaomi_mimo_tts_synthesize_stream,
)
from app.domain.speech.registry import normalize_provider_id
from app.domain.speech.runtime import (
    azure_stt_transcribe,
    azure_tts_synthesize_stream,
    custom_http_stt_transcribe,
    custom_http_tts_synthesize_stream,
    doubao_asr_transcribe,
    doubao_tts_synthesize_stream,
    edge_tts_synthesize_stream,
    gemini_asr_transcribe,
    gemini_tts_synthesize_wav,
    glm_asr_transcribe,
    glm_tts_synthesize_stream,
    openai_tts_synthesize_stream,
    openai_whisper_transcribe,
)
from app.domain.speech.schemas import (
    SpeechSttDemoResponse,
    SpeechTenantConfigUpsertRequest,
    SpeechTenantConfigView,
    SpeechTtsDemoRequest,
)
from app.domain.speech.service import SpeechConfigService
from app.domain.speech.voice_clone_schemas import (
    SpeechVoiceClonePreviewRequest,
    SpeechVoiceCloneWorkspaceItemView,
    SpeechVoiceCloneWorkspacePayload,
)
from app.domain.speech.voice_clone_service import SpeechVoiceCloneService
from app.infrastructure.cache.base_runtime_keys import (
    SPEECH_CONFIG_TTL_SECONDS,
    SPEECH_PROVIDERS_CACHE_KEY,
    SPEECH_PROVIDERS_TTL_SECONDS,
    build_speech_config_cache_key,
    invalidate_speech_runtime_cache,
)
from app.infrastructure.cache.runtime_cache import remember_json

logger = get_logger(__name__)

router = APIRouter()


def _serialize_speech_config_view(data: SpeechTenantConfigView) -> dict[str, Any]:
    return data.model_dump(by_alias=True)


async def _collect_audio_stream(stream: SpeechAudioStream) -> bytes:
    chunks: list[bytes] = []
    async for chunk in stream.iterator:
        if chunk:
            chunks.append(bytes(chunk))
    return b"".join(chunks)


async def _bill_speech_tts_text(
    *,
    db: DBSession,
    tenant_id: int,
    user_id: int | None,
    text: str,
    reference_type: str,
    reference_id: int | None = None,
    provider_id: str | None = None,
    model: str | None = None,
    voice: str | None = None,
) -> None:
    await charge_speech_text_credits(
        credit_service=CreditService(db),
        tenant_id=tenant_id,
        user_id=user_id,
        text=text,
        reference_type=reference_type,
        reference_id=reference_id,
        provider_id=provider_id,
        model=model,
        voice=voice,
        operator_id=user_id,
        extra={"source": "speech_endpoint"},
    )


def _billable_streaming_response(
    *,
    audio_bytes: bytes,
    media_type: str,
    file_ext: str,
    filename: str = "tts-demo",
) -> StreamingResponse:
    stream = bytes_to_stream(data=audio_bytes, media_type=media_type, ext=file_ext)
    return StreamingResponse(
        stream.iterator,
        media_type=stream.media_type,
        headers={"Content-Disposition": f'inline; filename="{filename}.{stream.file_ext}"'},
    )


async def _finalize_tts_stream_response(
    *,
    db: DBSession,
    tenant_id: int,
    user_id: int | None,
    text: str,
    reference_type: str,
    stream: SpeechAudioStream,
    provider_id: str | None = None,
    model: str | None = None,
    voice: str | None = None,
    reference_id: int | None = None,
    filename: str = "tts-demo",
) -> StreamingResponse:
    audio_bytes = await _collect_audio_stream(stream)
    await _bill_speech_tts_text(
        db=db,
        tenant_id=tenant_id,
        user_id=user_id,
        text=text,
        reference_type=reference_type,
        reference_id=reference_id,
        provider_id=provider_id,
        model=model,
        voice=voice,
    )
    return _billable_streaming_response(
        audio_bytes=audio_bytes,
        media_type=stream.media_type,
        file_ext=stream.file_ext,
        filename=filename,
    )


@router.get("/providers", response_model=ResponseBase[dict])
async def list_speech_providers(
    current_user: CurrentTenantAdmin,
    tenant_ctx: TenantCtx,
) -> dict[str, Any]:
    _ = current_user, tenant_ctx

    async def _load_providers() -> dict[str, Any]:
        providers = SpeechConfigService.list_providers()
        return {
            "tts": [p.model_dump(by_alias=True) for p in providers if p.category == "tts"],
            "stt": [p.model_dump(by_alias=True) for p in providers if p.category == "stt"],
        }

    payload = await remember_json(
        SPEECH_PROVIDERS_CACHE_KEY,
        ttl_seconds=SPEECH_PROVIDERS_TTL_SECONDS,
        loader=_load_providers,
    )
    return SuccessResponse(data=payload)


@router.get("/config", response_model=ResponseBase[SpeechTenantConfigView])
async def get_speech_config(
    current_user: CurrentTenantAdmin,
    tenant_ctx: TenantCtx,
    db: DBSession,
) -> dict[str, Any]:
    cache_key = build_speech_config_cache_key(tenant_ctx.tenant_id)

    async def _load_speech_config() -> dict[str, Any]:
        service = SpeechConfigService(db)
        view = await service.get_view(tenant_id=tenant_ctx.tenant_id)
        return _serialize_speech_config_view(view)

    payload = await remember_json(
        cache_key,
        ttl_seconds=SPEECH_CONFIG_TTL_SECONDS,
        loader=_load_speech_config,
    )
    logger.info("speech_config_retrieved", user_id=current_user.id, tenant_id=tenant_ctx.tenant_id)
    return SuccessResponse(data=payload)


@router.put("/config", response_model=ResponseBase[SpeechTenantConfigView])
async def upsert_speech_config(
    data: SpeechTenantConfigUpsertRequest,
    current_user: CurrentTenantAdmin,
    tenant_ctx: TenantCtx,
    db: DBSession,
) -> dict[str, Any]:
    service = SpeechConfigService(db)
    cfg = await service.upsert(tenant_id=tenant_ctx.tenant_id, data=data)
    view = service.to_view(cfg)
    await invalidate_speech_runtime_cache(tenant_ctx.tenant_id)
    logger.info("speech_config_updated", user_id=current_user.id, tenant_id=tenant_ctx.tenant_id)
    return SuccessResponse(data=_serialize_speech_config_view(view), message="语音配置已更新")


@router.get("/voice-clones/workspace", response_model=ResponseBase[SpeechVoiceCloneWorkspacePayload])
async def get_speech_voice_clone_workspace(
    current_user: CurrentTenantAdmin,
    tenant_ctx: TenantCtx,
    db: DBSession,
) -> dict[str, Any]:
    payload = await SpeechVoiceCloneService(db).list_workspace(tenant_id=tenant_ctx.tenant_id, user_id=current_user.id)
    logger.info("speech_voice_clone_workspace_retrieved", user_id=current_user.id, tenant_id=tenant_ctx.tenant_id)
    return SuccessResponse(data=payload.model_dump(by_alias=True, mode="json"))


@router.post("/voice-clones", response_model=ResponseBase[SpeechVoiceCloneWorkspaceItemView])
async def create_speech_voice_clone(
    current_user: CurrentTenantAdmin,
    tenant_ctx: TenantCtx,
    db: DBSession,
    file: UploadFile = File(...),
    display_name: str | None = Form(None, alias="displayName"),
    transcript_text: str | None = Form(None, alias="transcriptText"),
    language_type: str | None = Form(None, alias="languageType"),
    source_duration_ms: int | None = Form(None, alias="sourceDurationMs"),
) -> dict[str, Any]:
    audio_bytes = await file.read()
    item = await SpeechVoiceCloneService(db).create_voice_clone(
        tenant_id=tenant_ctx.tenant_id,
        created_by_user_id=current_user.id,
        file_name=file.filename or "voice-sample",
        content_type=file.content_type or "application/octet-stream",
        audio_bytes=audio_bytes,
        display_name=display_name,
        transcript_text=transcript_text,
        language_type=language_type,
        source_duration_ms=source_duration_ms,
    )
    logger.info("speech_voice_clone_created", user_id=current_user.id, tenant_id=tenant_ctx.tenant_id)
    return SuccessResponse(
        data=item.model_dump(by_alias=True, mode="json"),
        message="声音已加入复刻音色库",
    )


@router.post("/voice-clones/{clone_id}/preview-tts")
async def preview_speech_voice_clone(
    clone_id: int,
    data: SpeechVoiceClonePreviewRequest,
    current_user: CurrentTenantAdmin,
    tenant_ctx: TenantCtx,
    db: DBSession,
) -> Response:
    stream = await SpeechVoiceCloneService(db).synthesize_clone_preview(
        tenant_id=tenant_ctx.tenant_id,
        clone_id=clone_id,
        text=data.text,
        user_id=current_user.id,
    )
    logger.info(
        "speech_voice_clone_preview_generated",
        user_id=current_user.id,
        tenant_id=tenant_ctx.tenant_id,
        clone_id=clone_id,
    )
    audio_bytes = await _collect_audio_stream(stream)
    await _bill_speech_tts_text(
        db=db,
        tenant_id=tenant_ctx.tenant_id,
        user_id=current_user.id,
        text=data.text,
        reference_type="speech_voice_clone_preview",
        reference_id=clone_id,
    )
    return Response(content=audio_bytes, media_type=stream.media_type)


@router.get("/voice-clones/assets/{asset_id}/source")
async def stream_speech_voice_clone_asset_source(
    asset_id: int,
    current_user: CurrentTenantAdmin,
    tenant_ctx: TenantCtx,
    db: DBSession,
):
    _ = current_user
    file_path, asset = await SpeechVoiceCloneService(db).read_asset_audio(
        tenant_id=tenant_ctx.tenant_id,
        asset_id=asset_id,
        user_id=current_user.id,
    )
    return FileResponse(
        path=file_path,
        media_type=str(asset.source_content_type or "").strip() or "application/octet-stream",
        filename=str(asset.source_file_name or "").strip() or f"voice-asset-{asset.id}",
    )


@router.delete("/voice-clones/{clone_id}", response_model=ResponseBase[dict])
async def delete_speech_voice_clone(
    clone_id: int,
    current_user: CurrentTenantAdmin,
    tenant_ctx: TenantCtx,
    db: DBSession,
) -> dict[str, Any]:
    await SpeechVoiceCloneService(db).delete_clone(
        tenant_id=tenant_ctx.tenant_id,
        clone_id=clone_id,
        user_id=current_user.id,
    )
    logger.info("speech_voice_clone_deleted", user_id=current_user.id, tenant_id=tenant_ctx.tenant_id, clone_id=clone_id)
    return SuccessResponse(
        data={"id": clone_id},
        message="复刻音色已删除",
    )


# ===================== Demo / Playground =====================


@router.post("/demo/tts")
async def demo_tts(
    data: SpeechTtsDemoRequest,
    current_user: CurrentTenantAdmin,
    tenant_ctx: TenantCtx,
    db: DBSession,
):
    """
    TTS 演示：返回音频流（用于前端播放）。

    说明：
    - 默认使用租户已配置的 TTS provider；未配置则回退 edge_tts
    - 可通过 providerId/settings 覆盖（不写入 DB）
    """

    service = SpeechConfigService(db)
    cfg = await service.get_or_create(tenant_id=tenant_ctx.tenant_id)

    config = cfg.config or {}
    secrets = cfg.secrets or {}

    section = (config.get("tts") or {}) if isinstance(config, dict) else {}
    tenant_provider_id = normalize_provider_id(section.get("providerId")) if isinstance(section, dict) else None
    provider_id = normalize_provider_id(data.provider_id or tenant_provider_id or "edge_tts") or "edge_tts"

    # system_tts 是前端能力，后端演示接口无法直接返回“系统语音”
    if normalize_provider_id(data.provider_id) == "system_tts":
        raise BusinessError(message="system_tts 为前端系统语音能力，请在浏览器端进行播放")
    if provider_id == "system_tts":
        provider_id = "edge_tts"

    tenant_settings = service._pick_settings(section, provider_id=provider_id)
    merged_settings = {**(tenant_settings or {}), **(data.settings or {})}

    secrets_with_profiles = dict(secrets) if isinstance(secrets, dict) else {}
    secrets_with_profiles["__config_tts_profiles"] = config.get("ttsProfiles") if isinstance(config, dict) else []
    secrets_map = service.resolve_tts_provider_secrets(
        secrets=secrets_with_profiles,
        provider_id=provider_id,
        default_provider_id=tenant_provider_id,
    )
    secrets_map = service._merge_secret_values(secrets_map, data.secrets or {})

    if provider_id == "xiaomi_mimo":
        api_key = (secrets_map.get("apiKey") or "").strip()
        if not api_key:
            raise BusinessError(message="请先配置并保存 Xiaomi MiMo 的 API Key（密钥不会回显）")

        base_url = str(merged_settings.get("baseUrl") or DEFAULT_XIAOMI_MIMO_BASE_URL)
        model = str(merged_settings.get("model") or DEFAULT_XIAOMI_MIMO_MODEL)
        voice = str(merged_settings.get("voice") or "default_zh")
        style = str(merged_settings.get("style") or "")
        text_injection_mode = str(merged_settings.get("textInjectionMode") or "plain")
        audio_format = (
            data.output_format
            or merged_settings.get("audioFormat")
            or merged_settings.get("format")
            or DEFAULT_XIAOMI_MIMO_AUDIO_FORMAT
        )
        request_overrides = merged_settings.get("requestOverrides")
        timeout_seconds = float(merged_settings.get("timeoutSeconds") or 60)

        stream = await xiaomi_mimo_tts_synthesize_stream(
            api_key=api_key,
            text=data.text,
            base_url=base_url,
            model=model,
            voice=voice,
            style=style or None,
            text_injection_mode=text_injection_mode or None,
            audio_format=str(audio_format),
            request_overrides=request_overrides,
            timeout_seconds=timeout_seconds,
        )

        logger.info(
            "speech_demo_tts",
            tenant_id=tenant_ctx.tenant_id,
            user_id=current_user.id,
            provider_id=provider_id,
            voice=voice,
        )
        return await _finalize_tts_stream_response(
            db=db,
            tenant_id=tenant_ctx.tenant_id,
            user_id=current_user.id,
            text=data.text,
            reference_type="speech_tts",
            stream=stream,
            provider_id=provider_id,
            model=model,
            voice=voice,
        )

    if provider_id == "aliyun_qwen_tts":
        api_key = (secrets_map.get("apiKey") or "").strip()
        if not api_key:
            raise BusinessError(message="请先配置并保存阿里百炼 Qwen TTS 的 API Key（密钥不会回显）")

        base_url = str(merged_settings.get("baseUrl") or DEFAULT_ALIYUN_QWEN_TTS_BASE_URL)
        model = str(merged_settings.get("model") or DEFAULT_ALIYUN_QWEN_TTS_MODEL)
        voice = str(merged_settings.get("voice") or DEFAULT_ALIYUN_QWEN_TTS_VOICE)
        language_type = str(merged_settings.get("languageType") or "").strip() or None
        instructions = str(merged_settings.get("instructions") or "").strip() or None
        optimize_instructions = bool(merged_settings.get("optimizeInstructions") or False)
        request_overrides = merged_settings.get("requestOverrides")
        stream_enabled = bool(merged_settings.get("stream") if merged_settings.get("stream") is not None else True)
        timeout_seconds = float(merged_settings.get("timeoutSeconds") or 60)

        stream = await aliyun_qwen_tts_synthesize_stream(
            api_key=api_key,
            text=data.text,
            base_url=base_url,
            model=model,
            voice=voice,
            language_type=language_type,
            instructions=instructions,
            optimize_instructions=optimize_instructions,
            stream=stream_enabled,
            request_overrides=request_overrides,
            timeout_seconds=timeout_seconds,
        )

        logger.info(
            "speech_demo_tts",
            tenant_id=tenant_ctx.tenant_id,
            user_id=current_user.id,
            provider_id=provider_id,
            voice=voice,
        )
        return await _finalize_tts_stream_response(
            db=db,
            tenant_id=tenant_ctx.tenant_id,
            user_id=current_user.id,
            text=data.text,
            reference_type="speech_tts",
            stream=stream,
            provider_id=provider_id,
            model=model,
            voice=voice,
        )

    if provider_id == "aliyun_qwen_tts_realtime_sdk":
        api_key = (secrets_map.get("apiKey") or "").strip()
        if not api_key:
            raise BusinessError(message="请先配置并保存阿里百炼 Qwen Realtime TTS 的 API Key（密钥不会回显）")

        base_url = str(merged_settings.get("baseUrl") or DEFAULT_ALIYUN_QWEN_TTS_REALTIME_WS_URL)
        model = str(merged_settings.get("model") or DEFAULT_ALIYUN_QWEN_TTS_REALTIME_MODEL)
        voice = str(merged_settings.get("voice") or DEFAULT_ALIYUN_QWEN_TTS_VOICE)
        language_type = str(merged_settings.get("languageType") or "").strip() or None
        instructions = str(merged_settings.get("instructions") or "").strip() or None
        optimize_instructions = bool(merged_settings.get("optimizeInstructions") or False)
        timeout_seconds = float(merged_settings.get("timeoutSeconds") or 60)
        stream = await aliyun_qwen_tts_realtime_sdk_synthesize_stream(
            api_key=api_key,
            text=data.text,
            base_url=base_url,
            model=model,
            voice=voice,
            language_type=language_type,
            instructions=instructions,
            optimize_instructions=optimize_instructions,
            timeout_seconds=timeout_seconds,
        )
        return await _finalize_tts_stream_response(
            db=db,
            tenant_id=tenant_ctx.tenant_id,
            user_id=current_user.id,
            text=data.text,
            reference_type="speech_tts",
            stream=stream,
            provider_id=provider_id,
            model=model,
            voice=voice,
        )

    if provider_id == "edge_tts":
        model = None
        voice = str(merged_settings.get("voice") or "zh-CN-XiaoxiaoNeural")
        rate = merged_settings.get("rate")
        volume = merged_settings.get("volume")
        pitch = merged_settings.get("pitch")
        output_format = data.output_format or merged_settings.get("outputFormat") or merged_settings.get("format")

        stream = await edge_tts_synthesize_stream(
            text=data.text,
            voice=voice,
            rate=rate,
            volume=volume,
            pitch=pitch,
            output_format=str(output_format) if output_format is not None else None,
        )

        logger.info(
            "speech_demo_tts",
            tenant_id=tenant_ctx.tenant_id,
            user_id=current_user.id,
            provider_id=provider_id,
            voice=voice,
        )
        return await _finalize_tts_stream_response(
            db=db,
            tenant_id=tenant_ctx.tenant_id,
            user_id=current_user.id,
            text=data.text,
            reference_type="speech_tts",
            stream=stream,
            provider_id=provider_id,
            model=model,
            voice=voice,
        )

    if provider_id == "gemini_tts":
        api_key = (secrets_map.get("apiKey") or "").strip()
        if not api_key:
            raise BusinessError(message="请先配置并保存 TTS Provider 的 API Key（密钥不会回显）")

        base_url = str(merged_settings.get("baseUrl") or "https://generativelanguage.googleapis.com/")
        model = str(merged_settings.get("model") or "gemini-2.5-flash-preview-tts")
        voice = str(merged_settings.get("voice") or "Zephyr")

        wav_bytes = await gemini_tts_synthesize_wav(
            api_key=api_key,
            base_url=base_url,
            model=model,
            text=data.text,
            voice=voice,
        )

        stream = bytes_to_stream(data=wav_bytes, media_type="audio/wav", ext="wav")

        logger.info(
            "speech_demo_tts",
            tenant_id=tenant_ctx.tenant_id,
            user_id=current_user.id,
            provider_id=provider_id,
            voice=voice,
        )
        return await _finalize_tts_stream_response(
            db=db,
            tenant_id=tenant_ctx.tenant_id,
            user_id=current_user.id,
            text=data.text,
            reference_type="speech_tts",
            stream=stream,
            provider_id=provider_id,
            model=model,
            voice=voice,
        )

    if provider_id == "openai_tts":
        api_key = (secrets_map.get("apiKey") or "").strip()
        if not api_key:
            raise BusinessError(message="请先配置并保存 TTS Provider 的 API Key（密钥不会回显）")

        base_url = str(merged_settings.get("baseUrl") or "https://api.openai.com/v1/audio/speech")
        model = str(merged_settings.get("model") or "tts-1")
        voice = str(merged_settings.get("voice") or "alloy")
        fmt = data.output_format or merged_settings.get("format") or merged_settings.get("outputFormat") or "wav"
        speed = merged_settings.get("speed")
        timeout_seconds = float(merged_settings.get("timeoutSeconds") or 60)

        stream = await openai_tts_synthesize_stream(
            base_url=base_url,
            api_key=api_key,
            model=model,
            text=data.text,
            voice=voice,
            response_format=str(fmt),
            speed=speed,
            timeout_seconds=timeout_seconds,
        )

        logger.info(
            "speech_demo_tts",
            tenant_id=tenant_ctx.tenant_id,
            user_id=current_user.id,
            provider_id=provider_id,
            voice=voice,
        )
        return await _finalize_tts_stream_response(
            db=db,
            tenant_id=tenant_ctx.tenant_id,
            user_id=current_user.id,
            text=data.text,
            reference_type="speech_tts",
            stream=stream,
            provider_id=provider_id,
            model=model,
            voice=voice,
        )

    if provider_id == "glm_tts":
        api_key = (secrets_map.get("apiKey") or "").strip()
        if not api_key:
            raise BusinessError(message="请先配置并保存 TTS Provider 的 API Key（密钥不会回显）")

        base_url = str(merged_settings.get("baseUrl") or "https://open.bigmodel.cn/api/paas/v4/audio/speech")
        model = str(merged_settings.get("model") or "glm-tts")
        voice = str(merged_settings.get("voice") or "female")
        response_format = str(merged_settings.get("responseFormat") or "pcm")
        encode_format = str(merged_settings.get("encodeFormat") or "base64")
        stream_flag = merged_settings.get("stream")
        stream_flag = True if stream_flag is None else bool(stream_flag)
        speed = merged_settings.get("speed")
        volume = merged_settings.get("volume")
        timeout_seconds = float(merged_settings.get("timeoutSeconds") or 60)

        stream = await glm_tts_synthesize_stream(
            base_url=base_url,
            api_key=api_key,
            model=model,
            text=data.text,
            voice=voice,
            response_format=response_format,
            encode_format=encode_format,
            stream=stream_flag,
            speed=speed,
            volume=volume,
            timeout_seconds=timeout_seconds,
        )

        logger.info(
            "speech_demo_tts",
            tenant_id=tenant_ctx.tenant_id,
            user_id=current_user.id,
            provider_id=provider_id,
            voice=voice,
        )
        return await _finalize_tts_stream_response(
            db=db,
            tenant_id=tenant_ctx.tenant_id,
            user_id=current_user.id,
            text=data.text,
            reference_type="speech_tts",
            stream=stream,
            provider_id=provider_id,
            model=model,
            voice=voice,
        )

    if provider_id == "azure_tts":
        model = None
        region = str(merged_settings.get("region") or "")
        subscription_key = str(secrets_map.get("subscriptionKey") or "").strip()
        voice = str(merged_settings.get("voice") or "")
        output_format = str(merged_settings.get("outputFormat") or "audio-16khz-32kbitrate-mono-mp3")
        timeout_seconds = float(merged_settings.get("timeoutSeconds") or 60)

        stream = await azure_tts_synthesize_stream(
            region=region,
            subscription_key=subscription_key,
            text=data.text,
            voice=voice,
            output_format=output_format,
            timeout_seconds=timeout_seconds,
        )

        logger.info(
            "speech_demo_tts",
            tenant_id=tenant_ctx.tenant_id,
            user_id=current_user.id,
            provider_id=provider_id,
            voice=voice,
        )
        return await _finalize_tts_stream_response(
            db=db,
            tenant_id=tenant_ctx.tenant_id,
            user_id=current_user.id,
            text=data.text,
            reference_type="speech_tts",
            stream=stream,
            provider_id=provider_id,
            model=model,
            voice=voice,
        )

    if provider_id == "doubao_tts":
        model = None
        appid = str(merged_settings.get("appid") or "")
        access_token = str(secrets_map.get("accessToken") or "").strip()
        cluster = str(merged_settings.get("cluster") or "")
        api_url = str(merged_settings.get("apiUrl") or "")
        authorization_prefix = str(merged_settings.get("authorization") or "Bearer ")
        voice = str(merged_settings.get("voice") or "")
        fmt = str(data.output_format or merged_settings.get("format") or "wav")

        speed_ratio = float(merged_settings.get("speedRatio") or 1.0)
        volume_ratio = float(merged_settings.get("volumeRatio") or 1.0)
        pitch_ratio = float(merged_settings.get("pitchRatio") or 1.0)
        timeout_seconds = float(merged_settings.get("timeoutSeconds") or 60)

        stream = await doubao_tts_synthesize_stream(
            api_url=api_url,
            authorization_prefix=authorization_prefix,
            appid=appid,
            access_token=access_token,
            cluster=cluster,
            text=data.text,
            voice=voice,
            audio_format=fmt,
            speed_ratio=speed_ratio,
            volume_ratio=volume_ratio,
            pitch_ratio=pitch_ratio,
            timeout_seconds=timeout_seconds,
        )

        logger.info(
            "speech_demo_tts",
            tenant_id=tenant_ctx.tenant_id,
            user_id=current_user.id,
            provider_id=provider_id,
            voice=voice,
        )
        return await _finalize_tts_stream_response(
            db=db,
            tenant_id=tenant_ctx.tenant_id,
            user_id=current_user.id,
            text=data.text,
            reference_type="speech_tts",
            stream=stream,
            provider_id=provider_id,
            model=model,
            voice=voice,
        )

    if provider_id == "custom_http_tts":
        model = None
        voice = str(merged_settings.get("voice") or "")
        endpoint = str(merged_settings.get("endpoint") or "")
        headers_template = merged_settings.get("headers")
        payload_template = merged_settings.get("payloadTemplate")
        secret_key1 = str(secrets_map.get("secretKey1") or "").strip() or None
        secret_key2 = str(secrets_map.get("secretKey2") or "").strip() or None
        fmt = str(data.output_format or merged_settings.get("outputFormat") or merged_settings.get("format") or "mp3")
        timeout_seconds = float(merged_settings.get("timeoutSeconds") or 60)

        stream = await custom_http_tts_synthesize_stream(
            endpoint=endpoint,
            text=data.text,
            headers_template=headers_template,
            payload_template=payload_template,
            secret_key1=secret_key1,
            secret_key2=secret_key2,
            output_format=fmt,
            timeout_seconds=timeout_seconds,
        )

        logger.info(
            "speech_demo_tts",
            tenant_id=tenant_ctx.tenant_id,
            user_id=current_user.id,
            provider_id=provider_id,
            voice=str(merged_settings.get("voice") or ""),
        )
        return await _finalize_tts_stream_response(
            db=db,
            tenant_id=tenant_ctx.tenant_id,
            user_id=current_user.id,
            text=data.text,
            reference_type="speech_tts",
            stream=stream,
            provider_id=provider_id,
            model=model,
            voice=voice,
        )

    raise BusinessError(message=f"暂不支持该 TTS provider 的演示：{provider_id}")


@router.post("/demo/stt", response_model=ResponseBase[SpeechSttDemoResponse])
async def demo_stt(
    current_user: CurrentTenantAdmin,
    tenant_ctx: TenantCtx,
    db: DBSession,
    file: UploadFile = File(...),
    provider_id: str | None = Form(None, alias="providerId"),
    language: str | None = Form(None),
    settings: str | None = Form(None),
    secret_payload: str | None = Form(None, alias="secrets"),
) -> dict[str, Any]:
    """
    STT 演示：上传音频文件 → 返回转写文本。

    说明：
    - 默认使用租户已配置的 STT provider
    - 可通过 providerId/settings 覆盖部分非密钥参数（不会写入数据库）
    - 支持：openai_whisper / glm_asr / gemini_asr / azure_stt / doubao_asr / doubao_stream_asr / custom_http_stt
    - funasr_local 需本地部署模型，演示接口暂不接入
    """

    service = SpeechConfigService(db)
    cfg = await service.get_or_create(tenant_id=tenant_ctx.tenant_id)
    config = cfg.config or {}
    secrets = cfg.secrets or {}

    section = (config.get("stt") or {}) if isinstance(config, dict) else {}
    tenant_provider_id = section.get("providerId") if isinstance(section, dict) else None
    selected_provider_id = provider_id or tenant_provider_id
    if not selected_provider_id:
        raise BusinessError(message="请先在「语音配置」里选择 STT Provider")

    # system_stt 是前端能力，后端演示接口不支持
    if provider_id == "system_stt":
        raise BusinessError(message="system_stt 为前端系统语音识别能力，请在浏览器端进行识别")
    if selected_provider_id == "system_stt":
        raise BusinessError(message="当前租户 STT Provider 为 system_stt，请在浏览器端进行识别")

    tenant_settings = service._pick_settings(section, provider_id=selected_provider_id)
    demo_settings: dict[str, Any] = {}
    if isinstance(settings, str) and settings.strip():
        try:
            raw = json.loads(settings)
        except Exception:
            raise BusinessError(message="settings 不是合法 JSON")
        if not isinstance(raw, dict):
            raise BusinessError(message="settings 必须是 JSON 对象")
        demo_settings = raw
    merged_settings = {**(tenant_settings or {}), **(demo_settings or {})}

    section_secrets_raw = secrets.get("stt") if isinstance(secrets, dict) else None
    secrets_map = service._pick_secrets(
        section_secrets_raw, provider_id=selected_provider_id, selected_provider_id=tenant_provider_id
    )
    demo_secrets: dict[str, Any] = {}
    if isinstance(secret_payload, str) and secret_payload.strip():
        try:
            raw_secrets = json.loads(secret_payload)
        except Exception:
            raise BusinessError(message="secrets 不是合法 JSON")
        if not isinstance(raw_secrets, dict):
            raise BusinessError(message="secrets 必须是 JSON 对象")
        demo_secrets = raw_secrets
    secrets_map = service._merge_secret_values(secrets_map, demo_secrets)

    audio_bytes = await file.read()
    filename = file.filename or "audio"
    content_type = file.content_type or "application/octet-stream"

    lang = language or merged_settings.get("language")
    model = None
    text: str

    if selected_provider_id == "openai_whisper":
        api_key = (secrets_map.get("apiKey") or "").strip()
        if not api_key:
            raise BusinessError(message="请先配置并保存 STT Provider 的 API Key（密钥不会回显）")

        base_url = str(merged_settings.get("baseUrl") or "https://api.openai.com/v1/audio/transcriptions")
        model = str(merged_settings.get("model") or "whisper-1")
        timeout_seconds = float(merged_settings.get("timeoutSeconds") or 60)

        text = await openai_whisper_transcribe(
            base_url=base_url,
            api_key=api_key,
            audio_bytes=audio_bytes,
            filename=filename,
            content_type=content_type,
            model=model,
            language=str(lang) if lang else None,
            timeout_seconds=timeout_seconds,
        )
    elif selected_provider_id == "glm_asr":
        api_key = (secrets_map.get("apiKey") or "").strip()
        if not api_key:
            raise BusinessError(message="请先配置并保存 STT Provider 的 API Key（密钥不会回显）")

        base_url = str(merged_settings.get("baseUrl") or "https://open.bigmodel.cn/api/paas/v4/audio/transcriptions")
        model = str(merged_settings.get("model") or "glm-asr-2512")
        stream_flag = merged_settings.get("stream")
        stream_flag = True if stream_flag is None else bool(stream_flag)
        timeout_seconds = float(merged_settings.get("timeoutSeconds") or 60)

        text = await glm_asr_transcribe(
            base_url=base_url,
            api_key=api_key,
            model=model,
            audio_bytes=audio_bytes,
            filename=filename,
            content_type=content_type,
            stream=stream_flag,
            language=str(lang) if lang else None,
            timeout_seconds=timeout_seconds,
        )
    elif selected_provider_id == "gemini_asr":
        api_key = (secrets_map.get("apiKey") or "").strip()
        if not api_key:
            raise BusinessError(message="请先配置并保存 STT Provider 的 API Key（密钥不会回显）")

        base_url = str(merged_settings.get("baseUrl") or "https://generativelanguage.googleapis.com/")
        model = str(merged_settings.get("model") or "gemini-2.5-flash")
        extra_prompt = merged_settings.get("extraPrompt")
        timeout_seconds = float(merged_settings.get("timeoutSeconds") or 60)

        text = await gemini_asr_transcribe(
            api_key=api_key,
            base_url=base_url,
            model=model,
            audio_bytes=audio_bytes,
            mime_type=content_type,
            language=str(lang) if lang else None,
            extra_prompt=str(extra_prompt) if isinstance(extra_prompt, str) and extra_prompt.strip() else None,
            timeout_seconds=timeout_seconds,
        )
    elif selected_provider_id == "azure_stt":
        region = str(merged_settings.get("region") or "")
        subscription_key = str(secrets_map.get("subscriptionKey") or "").strip()
        if not subscription_key:
            raise BusinessError(message="请先配置并保存 STT Provider 的 Subscription Key（密钥不会回显）")

        language_ = str(lang or "zh-CN")
        timeout_seconds = float(merged_settings.get("timeoutSeconds") or 60)

        text = await azure_stt_transcribe(
            region=region,
            subscription_key=subscription_key,
            audio_bytes=audio_bytes,
            content_type=content_type,
            language=language_,
            timeout_seconds=timeout_seconds,
        )
        lang = language_
    elif selected_provider_id in {"doubao_asr", "doubao_stream_asr"}:
        appid = str(merged_settings.get("appid") or "")
        access_token = str(secrets_map.get("accessToken") or "").strip()
        if not access_token:
            raise BusinessError(message="请先配置并保存 STT Provider 的 Access Token（密钥不会回显）")

        cluster = str(merged_settings.get("cluster") or "")
        api_url = str(merged_settings.get("apiUrl") or "")
        authorization_prefix = str(merged_settings.get("authorization") or "Bearer ")
        timeout_seconds = float(merged_settings.get("timeoutSeconds") or 60)

        extra: dict[str, object] = {}
        if selected_provider_id == "doubao_asr":
            boosting = merged_settings.get("boostingTableName")
            correct = merged_settings.get("correctTableName")
            if boosting:
                extra["boostingTableName"] = str(boosting)
            if correct:
                extra["correctTableName"] = str(correct)
        else:
            enable_multilingual = merged_settings.get("enableMultilingual")
            workflow = merged_settings.get("workflow")
            language_setting = merged_settings.get("language")
            if enable_multilingual is not None:
                extra["enable_multilingual"] = bool(enable_multilingual)
            if workflow:
                extra["workflow"] = str(workflow)
            if language_setting:
                extra["language"] = str(language_setting)

        text = await doubao_asr_transcribe(
            api_url=api_url,
            authorization_prefix=authorization_prefix,
            appid=appid,
            access_token=access_token,
            cluster=cluster,
            audio_bytes=audio_bytes,
            mime_type=content_type,
            timeout_seconds=timeout_seconds,
            extra=extra or None,
        )
    elif selected_provider_id == "custom_http_stt":
        endpoint = str(merged_settings.get("endpoint") or "")
        headers_template = merged_settings.get("headers")
        payload_template = merged_settings.get("payloadTemplate")
        secret_key1 = str(secrets_map.get("secretKey1") or "").strip() or None
        secret_key2 = str(secrets_map.get("secretKey2") or "").strip() or None
        timeout_seconds = float(merged_settings.get("timeoutSeconds") or 60)

        text = await custom_http_stt_transcribe(
            endpoint=endpoint,
            audio_bytes=audio_bytes,
            mime_type=content_type,
            headers_template=headers_template,
            payload_template=payload_template,
            secret_key1=secret_key1,
            secret_key2=secret_key2,
            timeout_seconds=timeout_seconds,
        )
    elif selected_provider_id == "funasr_local":
        raise BusinessError(message="funasr_local 演示暂未接入：需要在后端安装 FunASR 并部署模型后才能使用")
    else:
        raise BusinessError(message=f"暂不支持该 STT provider 的演示：{selected_provider_id}")

    logger.info(
        "speech_demo_stt",
        tenant_id=tenant_ctx.tenant_id,
        user_id=current_user.id,
        provider_id=selected_provider_id,
        model=model,
    )
    return SuccessResponse(
        data=SpeechSttDemoResponse(
            text=text,
            providerId=selected_provider_id,
            model=model,
            language=str(lang) if lang else None,
        ).model_dump(by_alias=True)
    )
