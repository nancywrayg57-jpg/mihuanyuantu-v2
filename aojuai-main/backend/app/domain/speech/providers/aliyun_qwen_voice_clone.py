"""Alibaba Bailian Qwen voice cloning helpers."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.exceptions import BusinessError

DEFAULT_ALIYUN_QWEN_VOICE_CLONE_BASE_URL = "https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization"
DEFAULT_ALIYUN_QWEN_VOICE_ENROLLMENT_MODEL = "qwen-voice-enrollment"
DEFAULT_ALIYUN_QWEN_VOICE_CLONE_TARGET_MODEL = "qwen3-tts-vc-2026-01-22"

_ALIYUN_VOICE_CLONE_LANGUAGE_ALIASES = {
    "zh": "zh",
    "zh-cn": "zh",
    "zh_cn": "zh",
    "chinese": "zh",
    "中文": "zh",
    "普通话": "zh",
    "cn": "zh",
    "en": "en",
    "en-us": "en",
    "en_us": "en",
    "english": "en",
    "英语": "en",
}


@dataclass(slots=True)
class AliyunQwenVoiceCloneResult:
    voice: str
    request_id: str | None = None
    count: int = 1
    raw_response: dict[str, Any] | None = None


def resolve_aliyun_qwen_voice_clone_base_url(base_url: str | None = None) -> str:
    normalized = str(base_url or "").strip().rstrip("/")
    if not normalized:
        return DEFAULT_ALIYUN_QWEN_VOICE_CLONE_BASE_URL
    if "/api/v1/services/audio/tts/customization" in normalized:
        return normalized
    if "dashscope-intl.aliyuncs.com" in normalized:
        return "https://dashscope-intl.aliyuncs.com/api/v1/services/audio/tts/customization"
    if "dashscope.aliyuncs.com" in normalized:
        return DEFAULT_ALIYUN_QWEN_VOICE_CLONE_BASE_URL
    return normalized


def _normalize_clone_language(language: str | None) -> str:
    normalized = str(language or "").strip()
    if not normalized:
        return "zh"
    alias_key = normalized.lower().replace("_", "-")
    return _ALIYUN_VOICE_CLONE_LANGUAGE_ALIASES.get(alias_key, normalized)


def _build_audio_data_url(audio_bytes: bytes, content_type: str) -> str:
    media_type = str(content_type or "").strip() or "application/octet-stream"
    encoded = base64.b64encode(audio_bytes).decode("ascii")
    return f"data:{media_type};base64,{encoded}"


async def aliyun_qwen_create_voice_clone(
    *,
    api_key: str,
    audio_bytes: bytes,
    content_type: str,
    preferred_name: str,
    text: str | None = None,
    language: str | None = None,
    base_url: str | None = None,
    model: str = DEFAULT_ALIYUN_QWEN_VOICE_ENROLLMENT_MODEL,
    target_model: str = DEFAULT_ALIYUN_QWEN_VOICE_CLONE_TARGET_MODEL,
    count: int = 1,
    timeout_seconds: float = 120,
) -> AliyunQwenVoiceCloneResult:
    normalized_api_key = str(api_key or "").strip()
    if not normalized_api_key:
        raise BusinessError(message="阿里云声音复刻缺少 API Key")
    if not audio_bytes:
        raise BusinessError(message="声音复刻缺少音频数据")
    normalized_name = str(preferred_name or "").strip()
    if not normalized_name:
        raise BusinessError(message="声音复刻缺少音色名称")

    input_payload: dict[str, Any] = {
        "action": "create",
        "target_model": str(target_model or DEFAULT_ALIYUN_QWEN_VOICE_CLONE_TARGET_MODEL).strip()
        or DEFAULT_ALIYUN_QWEN_VOICE_CLONE_TARGET_MODEL,
        "preferred_name": normalized_name,
        "audio": {
            "data": _build_audio_data_url(audio_bytes, content_type),
        },
    }
    normalized_language = str(language or "").strip()
    if normalized_language:
        input_payload["language"] = _normalize_clone_language(normalized_language)

    payload = {
        "model": str(model or DEFAULT_ALIYUN_QWEN_VOICE_ENROLLMENT_MODEL).strip()
        or DEFAULT_ALIYUN_QWEN_VOICE_ENROLLMENT_MODEL,
        "input": input_payload,
    }
    normalized_text = str(text or "").strip()
    if normalized_text:
        payload["input"]["text"] = normalized_text

    headers = {
        "Authorization": f"Bearer {normalized_api_key}",
        "Content-Type": "application/json",
    }
    normalized_base_url = resolve_aliyun_qwen_voice_clone_base_url(base_url)

    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds), follow_redirects=True) as client:
        try:
            response = await client.post(normalized_base_url, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            raise BusinessError(
                message="阿里云声音复刻请求失败，请检查 DashScope 地址、API Key 与模型开通状态",
                details={
                    "error": str(exc),
                    "baseUrl": normalized_base_url,
                    "model": payload["model"],
                    "targetModel": payload["input"]["target_model"],
                },
            ) from exc

    if response.status_code >= 400:
        response_message = f"阿里云声音复刻返回错误（HTTP {response.status_code}）"
        try:
            response_json = response.json()
        except json.JSONDecodeError:
            response_json = None
        if isinstance(response_json, dict):
            request_id = str(response_json.get("request_id") or "").strip()
            error_payload = response_json.get("error")
            if isinstance(error_payload, dict):
                detail_message = str(error_payload.get("message") or error_payload.get("code") or "").strip()
                if detail_message:
                    response_message = f"阿里云声音复刻失败：{detail_message}"
            elif request_id:
                response_message = f"阿里云声音复刻返回错误（request_id={request_id}）"
        raise BusinessError(
            message=response_message,
            details={"body": response.text[:2000], "baseUrl": normalized_base_url},
        )

    try:
        payload_json = response.json()
    except json.JSONDecodeError as exc:
        raise BusinessError(message="阿里云声音复刻返回不是合法 JSON", details={"error": str(exc)}) from exc

    output = payload_json.get("output") if isinstance(payload_json.get("output"), dict) else {}
    voice = str(output.get("voice") or "").strip()
    if not voice:
        raise BusinessError(message="阿里云声音复刻未返回 voice 标识", details={"response": payload_json})

    return AliyunQwenVoiceCloneResult(
        voice=voice,
        request_id=str(payload_json.get("request_id") or "").strip() or None,
        count=max(
            int(
                output.get("count")
                or (payload_json.get("usage") if isinstance(payload_json.get("usage"), dict) else {}).get("count")
                or count
                or 1
            ),
            1,
        ),
        raw_response=payload_json if isinstance(payload_json, dict) else None,
    )


async def aliyun_qwen_delete_voice_clone(
    *,
    api_key: str,
    voice: str,
    base_url: str | None = None,
    timeout_seconds: float = 60,
) -> None:
    normalized_api_key = str(api_key or "").strip()
    normalized_voice = str(voice or "").strip()
    if not normalized_api_key or not normalized_voice:
        return

    headers = {
        "Authorization": f"Bearer {normalized_api_key}",
        "Content-Type": "application/json",
    }
    normalized_base_url = resolve_aliyun_qwen_voice_clone_base_url(base_url)
    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds), follow_redirects=True) as client:
        try:
            response = await client.post(
                normalized_base_url,
                headers=headers,
                json={
                    "model": DEFAULT_ALIYUN_QWEN_VOICE_ENROLLMENT_MODEL,
                    "input": {
                        "action": "delete",
                        "voice": normalized_voice,
                    },
                },
            )
        except httpx.HTTPError as exc:
            raise BusinessError(message="阿里云声音复刻删除请求失败", details={"error": str(exc)}) from exc

    if response.status_code in {404, 410}:
        return
    if response.status_code >= 400:
        raise BusinessError(
            message=f"阿里云声音复刻删除失败（HTTP {response.status_code}）",
            details={"body": response.text[:2000], "voice": normalized_voice},
        )
