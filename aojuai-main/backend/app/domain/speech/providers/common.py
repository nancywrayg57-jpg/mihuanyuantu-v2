"""Shared helpers for provider-backed speech runtimes."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import io
import json
from typing import Any, AsyncIterator
import wave

import httpx

from app.core.exceptions import BusinessError


@dataclass(frozen=True)
class SpeechAudioStream:
    media_type: str
    file_ext: str
    iterator: AsyncIterator[bytes]


def bytes_to_stream(*, data: bytes, media_type: str, ext: str) -> SpeechAudioStream:
    async def gen() -> AsyncIterator[bytes]:
        yield data

    return SpeechAudioStream(media_type=media_type, file_ext=ext, iterator=gen())


def media_type_and_ext_from_hint(hint: str | None) -> tuple[str, str]:
    fmt = str(hint or "").strip().lower()
    if fmt in {"wav", "wave", "pcm"}:
        return ("audio/wav", "wav")
    if fmt in {"mp3", "mpeg"}:
        return ("audio/mpeg", "mp3")
    if fmt in {"ogg", "opus"}:
        return ("audio/ogg", "ogg")
    if fmt == "aac":
        return ("audio/aac", "aac")
    if fmt == "flac":
        return ("audio/flac", "flac")
    if fmt == "webm":
        return ("audio/webm", "webm")
    return ("application/octet-stream", "bin")


def media_type_and_ext_from_content_type(content_type: str | None) -> tuple[str, str]:
    value = str(content_type or "").split(";", 1)[0].strip().lower()
    if value in {"audio/wav", "audio/x-wav", "audio/pcm"}:
        return ("audio/wav", "wav")
    if value in {"audio/mpeg", "audio/mp3"}:
        return ("audio/mpeg", "mp3")
    if value in {"audio/ogg", "audio/opus"}:
        return ("audio/ogg", "ogg")
    if value == "audio/webm":
        return ("audio/webm", "webm")
    if value == "audio/aac":
        return ("audio/aac", "aac")
    if value == "audio/flac":
        return ("audio/flac", "flac")
    return (value or "application/octet-stream", "bin")


def deep_merge(base: object, override: object) -> object:
    if isinstance(base, dict) and isinstance(override, dict):
        merged = dict(base)
        for key, value in override.items():
            if key in merged:
                merged[key] = deep_merge(merged[key], value)
            else:
                merged[key] = value
        return merged
    return override


def normalize_object_overrides(value: object | None, *, label: str) -> dict[str, object]:
    if value in (None, "", {}):
        return {}
    if not isinstance(value, dict):
        raise BusinessError(message=f"{label} 必须是 JSON 对象")
    return dict(value)


async def iter_sse_json(response: httpx.Response) -> AsyncIterator[object]:
    lines: list[str] = []
    event_name = ""

    async for line in response.aiter_lines():
        if line == "":
            if not lines and not event_name:
                continue
            raw = "\n".join(lines).strip()
            lines.clear()
            current_event = event_name.strip().lower()
            event_name = ""
            if not raw or raw == "[DONE]":
                if raw == "[DONE]":
                    break
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise BusinessError(message="流式响应解析失败：data 不是合法 JSON", details={"error": str(exc)}) from exc
            if current_event == "error":
                if isinstance(payload, dict):
                    message = str(payload.get("message") or "流式响应返回错误事件").strip()
                    raise BusinessError(message=message, details=payload)
                raise BusinessError(message="流式响应返回错误事件", details={"payload": payload})
            yield payload
            continue

        if line.startswith("event:"):
            event_name = line[len("event:") :].lstrip()
            continue
        if line.startswith("data:"):
            lines.append(line[len("data:") :].lstrip())

    if lines:
        raw = "\n".join(lines).strip()
        if raw and raw != "[DONE]":
            try:
                yield json.loads(raw)
            except json.JSONDecodeError as exc:
                raise BusinessError(message="流式响应解析失败：data 不是合法 JSON", details={"error": str(exc)}) from exc


def extract_first_base64(payload: object, keys: list[str]) -> str:
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        for value in payload.values():
            match = extract_first_base64(value, keys)
            if match:
                return match
    if isinstance(payload, list):
        for item in payload:
            match = extract_first_base64(item, keys)
            if match:
                return match
    return ""


def extract_first_url(payload: object, keys: list[str]) -> str:
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, str) and value.strip().startswith(("http://", "https://")):
                return value.strip()
        for value in payload.values():
            match = extract_first_url(value, keys)
            if match:
                return match
    if isinstance(payload, list):
        for item in payload:
            match = extract_first_url(item, keys)
            if match:
                return match
    return ""


def decode_base64_audio(value: Any) -> bytes:
    raw = str(value or "").strip()
    if not raw:
        raise BusinessError(message="Base64 音频字段为空")
    if raw.startswith("data:") and "," in raw:
        raw = raw.split(",", 1)[1]
    try:
        return base64.b64decode(raw)
    except Exception as exc:
        raise BusinessError(message="Base64 音频解码失败", details={"error": str(exc)}) from exc


def apply_xiaomi_style(text: str, *, style: str | None, mode: str | None) -> str:
    normalized_mode = str(mode or "").strip()
    normalized_style = str(style or "").strip()
    if normalized_mode in {"audio_tag", "prepend_audio_tag", "prepend_style_tag"} and normalized_style:
        return f"({normalized_style}){text}"
    return text


def pcm16_to_wav_bytes(*, pcm_data: bytes, sample_rate: int = 24000, channels: int = 1) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm_data)
    return buffer.getvalue()


def wrap_pcm16_as_wav_if_needed(*, audio_bytes: bytes, sample_rate: int = 24000) -> bytes:
    if audio_bytes[:4] == b"RIFF":
        return audio_bytes
    return pcm16_to_wav_bytes(pcm_data=audio_bytes, sample_rate=sample_rate, channels=1)


def concat_wav_audio_segments(
    *,
    audio_segments: list[bytes],
    sample_rate: int = 24000,
    channels: int = 1,
) -> bytes:
    if not audio_segments:
        return b""
    if len(audio_segments) == 1:
        return wrap_pcm16_as_wav_if_needed(audio_bytes=audio_segments[0], sample_rate=sample_rate)

    pcm_parts: list[bytes] = []
    for segment in audio_segments:
        wav_bytes = wrap_pcm16_as_wav_if_needed(audio_bytes=segment, sample_rate=sample_rate)
        with wave.open(io.BytesIO(wav_bytes), "rb") as handle:
            pcm_parts.append(handle.readframes(handle.getnframes()))

    return pcm16_to_wav_bytes(pcm_data=b"".join(pcm_parts), sample_rate=sample_rate, channels=channels)
