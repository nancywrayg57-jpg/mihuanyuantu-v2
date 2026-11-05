"""
AOJU Backend - Speech Runtime Helpers

最小可用的运行态实现（用于演示页面）：
- TTS：edge_tts / gemini_tts / glm_tts / openai_tts / azure_tts / doubao_tts / custom_http_tts
- STT：openai_whisper / gemini_asr / glm_asr / azure_stt / doubao_asr / doubao_stream_asr / custom_http_stt

注意：这是“演示级”实现，后续可演进为 provider 插件体系 + WebSocket 会话层。
"""

from __future__ import annotations

import base64
import html
import io
import json
import re
import uuid
import wave
from collections.abc import AsyncIterator
from dataclasses import dataclass
from urllib.parse import quote

import httpx

from app.core.exceptions import BusinessError
from app.core.logger import get_logger

logger = get_logger(__name__)

try:
    import edge_tts  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    edge_tts = None

try:
    from google import genai  # type: ignore
    from google.genai import types as genai_types  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    genai = None
    genai_types = None


@dataclass(frozen=True)
class SpeechAudioStream:
    media_type: str
    file_ext: str
    iterator: AsyncIterator[bytes]


_PLACEHOLDER_RE = re.compile(r"\$\{([^}]+)\}", re.UNICODE)


def _media_type_and_ext_from_hint(hint: str | None) -> tuple[str, str]:
    fmt = (hint or "").strip().lower()
    if fmt in {"wav", "wave", "pcm"}:
        return ("audio/wav", "wav")
    if fmt in {"mp3", "mpeg"}:
        return ("audio/mpeg", "mp3")
    if fmt in {"ogg", "opus"}:
        return ("audio/ogg", "ogg")
    if fmt in {"aac"}:
        return ("audio/aac", "aac")
    if fmt in {"flac"}:
        return ("audio/flac", "flac")
    if fmt in {"webm"}:
        return ("audio/webm", "webm")
    return ("application/octet-stream", "bin")


def _media_type_and_ext_from_content_type(content_type: str | None) -> tuple[str, str]:
    ct = (content_type or "").split(";", 1)[0].strip().lower()
    if not ct:
        return ("application/octet-stream", "bin")
    if ct == "audio/wav" or ct == "audio/x-wav":
        return ("audio/wav", "wav")
    if ct == "audio/mpeg":
        return ("audio/mpeg", "mp3")
    if ct in {"audio/ogg", "audio/opus"}:
        return ("audio/ogg", "ogg")
    if ct == "audio/webm":
        return ("audio/webm", "webm")
    if ct == "audio/aac":
        return ("audio/aac", "aac")
    if ct == "audio/flac":
        return ("audio/flac", "flac")
    return (ct, "bin")


def _bytes_to_stream(*, data: bytes, media_type: str, ext: str) -> SpeechAudioStream:
    async def gen() -> AsyncIterator[bytes]:
        yield data

    return SpeechAudioStream(media_type=media_type, file_ext=ext, iterator=gen())


async def _iter_sse_json(resp: httpx.Response) -> AsyncIterator[object]:
    """
    Iterate Server-Sent Events (SSE) response and yield parsed JSON payloads from `data:` blocks.

    - Supports multi-line `data:` blocks.
    - Stops on `[DONE]`.
    """

    buf: list[str] = []

    async for line in resp.aiter_lines():
        # SSE events are separated by empty line
        if line == "":
            if not buf:
                continue
            raw = "\n".join(buf).strip()
            buf.clear()
            if not raw:
                continue
            if raw == "[DONE]":
                break
            try:
                yield json.loads(raw)
            except Exception as exc:
                raise BusinessError(message="流式响应解析失败：data 不是合法 JSON") from exc
            continue

        if line.startswith("data:"):
            buf.append(line[len("data:") :].lstrip())
            continue

    # flush tail
    if buf:
        raw = "\n".join(buf).strip()
        if raw and raw != "[DONE]":
            try:
                yield json.loads(raw)
            except Exception as exc:
                raise BusinessError(message="流式响应解析失败：data 不是合法 JSON") from exc


def _render_template(obj: object, variables: dict[str, object]) -> tuple[object, set[str]]:
    missing: set[str] = set()

    def render_str(s: str) -> str:
        def repl(match: re.Match[str]) -> str:
            key = match.group(1)
            if key not in variables:
                missing.add(key)
                return match.group(0)
            val = variables.get(key)
            return "" if val is None else str(val)

        return _PLACEHOLDER_RE.sub(repl, s)

    def walk(value: object) -> object:
        if isinstance(value, str):
            return render_str(value)
        if isinstance(value, list):
            return [walk(v) for v in value]
        if isinstance(value, dict):
            out: dict[object, object] = {}
            for k, v in value.items():
                out[walk(k) if isinstance(k, str) else k] = walk(v)
            return out
        return value

    return walk(obj), missing


def _extract_first_base64(payload: object, keys: list[str]) -> str:
    if isinstance(payload, dict):
        for k in keys:
            v = payload.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        for v in payload.values():
            s = _extract_first_base64(v, keys)
            if s:
                return s
    if isinstance(payload, list):
        for it in payload:
            s = _extract_first_base64(it, keys)
            if s:
                return s
    return ""


def _extract_json_path(payload: object, path: str | None) -> object:
    current = payload
    normalized_path = str(path or "").strip()
    if not normalized_path:
        return current

    for part in [item for item in normalized_path.split(".") if item]:
        if isinstance(current, dict) and part in current:
            current = current[part]
            continue
        raise BusinessError(message=f"响应路径不存在：{normalized_path}")

    return current


def _extract_first_text(payload: object, keys: list[str]) -> str:
    """
    Best-effort extract the first non-empty string under the given keys.
    Useful for streaming ASR payloads that may embed text in different shapes.
    """

    if isinstance(payload, dict):
        for k in keys:
            v = payload.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        for v in payload.values():
            s = _extract_first_text(v, keys)
            if s:
                return s
    if isinstance(payload, list):
        for it in payload:
            s = _extract_first_text(it, keys)
            if s:
                return s
    return ""


def _maybe_decode_base64(data: str) -> bytes:
    cleaned = (data or "").strip()
    if not cleaned:
        return b""
    try:
        return base64.b64decode(cleaned, validate=False)
    except Exception as exc:  # pragma: no cover - defensive
        raise BusinessError(message="返回的 base64 音频数据无法解码") from exc


def _resolve_edge_output_format(output_format: str | None) -> tuple[str, str, str]:
    """
    Map user-friendly output format to Edge service format.

    `edge-tts` uses Azure/Edge format strings such as:
    - audio-24khz-48kbitrate-mono-mp3
    - riff-24khz-16bit-mono-pcm
    - webm-24khz-16bit-mono-opus
    """

    hint = (output_format or "").strip().lower()
    if hint in {"", "mp3"}:
        return ("audio-24khz-48kbitrate-mono-mp3", "audio/mpeg", "mp3")
    if hint in {"wav", "pcm"}:
        return ("riff-24khz-16bit-mono-pcm", "audio/wav", "wav")
    if hint in {"opus", "webm"}:
        return ("webm-24khz-16bit-mono-opus", "audio/webm", "webm")
    # fallback to mp3 for unknown values
    return ("audio-24khz-48kbitrate-mono-mp3", "audio/mpeg", "mp3")


def _format_signed_percent(value: object | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        sign = "+" if value >= 0 else ""
        return f"{sign}{int(value)}%"
    if isinstance(value, str):
        trimmed = value.strip()
        if not trimmed:
            return None
        if trimmed.endswith("%"):
            return trimmed
        try:
            num = float(trimmed)
            sign = "+" if num >= 0 else ""
            return f"{sign}{int(num)}%"
        except ValueError:
            return trimmed
    return None


def _format_signed_hz(value: object | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        sign = "+" if value >= 0 else ""
        return f"{sign}{int(value)}Hz"
    if isinstance(value, str):
        trimmed = value.strip()
        if not trimmed:
            return None
        if trimmed.lower().endswith("hz"):
            return trimmed
        try:
            num = float(trimmed)
            sign = "+" if num >= 0 else ""
            return f"{sign}{int(num)}Hz"
        except ValueError:
            return trimmed
    return None


async def edge_tts_synthesize_stream(
    *,
    text: str,
    voice: str,
    rate: object | None = None,
    volume: object | None = None,
    pitch: object | None = None,
    output_format: str | None = None,
) -> SpeechAudioStream:
    if edge_tts is None:
        raise BusinessError(message="未安装 edge-tts，无法使用 Edge TTS 演示")

    fmt, media_type, ext = _resolve_edge_output_format(output_format)

    rate_str = _format_signed_percent(rate) or "+0%"
    volume_str = _format_signed_percent(volume) or "+0%"
    pitch_str = _format_signed_hz(pitch) or "+0Hz"

    try:
        communicate = edge_tts.Communicate(  # type: ignore[attr-defined]
            text=text,
            voice=voice,
            rate=rate_str,
            volume=volume_str,
            pitch=pitch_str,
            output_format=fmt,
        )
    except TypeError:
        # 兼容旧版 edge-tts 参数签名
        communicate = edge_tts.Communicate(text, voice, rate=rate_str, volume=volume_str, pitch=pitch_str)  # type: ignore[attr-defined]

    async def gen() -> AsyncIterator[bytes]:
        try:
            async for chunk in communicate.stream():
                if chunk.get("type") == "audio":
                    data = chunk.get("data")
                    if data:
                        yield data
        except Exception as exc:
            logger.exception("edge_tts_stream_failed", error=str(exc))
            raise BusinessError(message="Edge TTS 合成失败") from exc

    return SpeechAudioStream(media_type=media_type, file_ext=ext, iterator=gen())


async def openai_whisper_transcribe(
    *,
    base_url: str,
    api_key: str,
    audio_bytes: bytes,
    filename: str,
    content_type: str,
    model: str,
    language: str | None = None,
    timeout_seconds: float = 60.0,
) -> str:
    headers = {"Authorization": f"Bearer {api_key}"}
    data: dict[str, str] = {"model": model}
    if language:
        data["language"] = language

    files = {"file": (filename, audio_bytes, content_type)}

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            resp = await client.post(base_url, headers=headers, data=data, files=files)
    except httpx.HTTPError as exc:
        logger.exception("openai_whisper_request_failed", error=str(exc))
        raise BusinessError(message="Whisper 请求失败") from exc

    if resp.status_code >= 400:
        logger.warning(
            "openai_whisper_http_error",
            status_code=resp.status_code,
            body=resp.text[:2000],
        )
        raise BusinessError(message=f"Whisper 返回错误（HTTP {resp.status_code}）")

    payload = resp.json()
    text = payload.get("text") if isinstance(payload, dict) else None
    if not text:
        raise BusinessError(message="Whisper 未返回 text 字段")
    return str(text)


def _pcm16_to_wav_bytes(*, pcm_data: bytes, sample_rate: int = 24000, channels: int = 1) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()


async def gemini_asr_transcribe(
    *,
    api_key: str,
    base_url: str,
    model: str,
    audio_bytes: bytes,
    mime_type: str,
    language: str | None = None,
    extra_prompt: str | None = None,
    timeout_seconds: float = 60.0,
) -> str:
    if genai is None or genai_types is None:
        raise BusinessError(message="未安装 google-genai，无法使用 Gemini ASR 演示")

    prompt = "请将下面音频转写成文字，只输出转写文本。"
    if language and language.strip():
        prompt = f"请将下面音频转写成 {language.strip()}，只输出转写文本。"
    if extra_prompt and extra_prompt.strip():
        prompt = f"{prompt}\n额外要求：{extra_prompt.strip()}"

    try:
        client = genai.Client(
            api_key=api_key,
            http_options=genai_types.HttpOptions(
                base_url=base_url,
                timeout=int(timeout_seconds * 1000),
            ),
        )
        uploaded_file = genai_types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
        generation_config = genai_types.GenerateContentConfig(
            temperature=0,
            top_p=1,
            top_k=32,
        )
        resp = await client.aio.models.generate_content(
            model=model,
            contents=[prompt, uploaded_file],
            config=generation_config,
        )
    except Exception as exc:
        logger.exception("gemini_asr_failed", error=str(exc))
        raise BusinessError(message="Gemini ASR 转写失败") from exc

    text = getattr(resp, "text", None)
    if not text:
        raise BusinessError(message="Gemini ASR 未返回 text")
    return str(text).strip()


async def glm_asr_transcribe(
    *,
    base_url: str,
    api_key: str,
    model: str,
    audio_bytes: bytes,
    filename: str,
    content_type: str,
    stream: bool = True,
    language: str | None = None,
    timeout_seconds: float = 60.0,
) -> str:
    if not base_url.strip():
        raise BusinessError(message="GLM ASR 缺少 baseUrl")
    if not api_key.strip():
        raise BusinessError(message="GLM ASR 缺少 apiKey")
    if not audio_bytes:
        raise BusinessError(message="GLM ASR 缺少音频数据")

    headers: dict[str, str] = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "text/event-stream" if stream else "application/json",
    }
    data: dict[str, str] = {"model": model, "stream": "true" if stream else "false"}
    if language and language.strip():
        data["language"] = language.strip()

    files = {"file": (filename or "audio", audio_bytes, content_type or "application/octet-stream")}

    text_out = ""

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
            if stream:
                async with client.stream("POST", str(base_url), headers=headers, data=data, files=files) as resp:
                    if resp.status_code >= 400:
                        body = (await resp.aread()).decode("utf-8", errors="ignore")
                        logger.warning("glm_asr_http_error", status_code=resp.status_code, body=body[:2000])
                        raise BusinessError(message=f"GLM ASR 返回错误（HTTP {resp.status_code}）")

                    ct = (resp.headers.get("content-type") or "").lower()
                    if "text/event-stream" in ct:
                        async for payload in _iter_sse_json(resp):
                            if not isinstance(payload, dict):
                                continue

                            # Some providers may send final "text" repeatedly (full text),
                            # while others send delta pieces. Prefer overwrite when "text" exists.
                            direct = payload.get("text")
                            if isinstance(direct, str) and direct.strip():
                                text_out = direct.strip()
                                continue

                            choices = payload.get("choices")
                            if isinstance(choices, list):
                                for choice in choices:
                                    if isinstance(choice, dict) and choice.get("finish_reason") == "stop":
                                        final = text_out.strip()
                                        if not final:
                                            raise BusinessError(message="GLM ASR 未返回识别文本")
                                        return final

                            delta = _extract_first_text(payload, ["content", "transcript", "text"])
                            if delta:
                                text_out += delta
                        final = text_out.strip()
                        if not final:
                            raise BusinessError(message="GLM ASR 未返回识别文本")
                        return final

                    # Non-SSE fallback
                    raw = await resp.aread()
                    payload_json = json.loads(raw.decode("utf-8", errors="ignore"))
            else:
                resp = await client.post(str(base_url), headers=headers, data=data, files=files)
                if resp.status_code >= 400:
                    logger.warning("glm_asr_http_error", status_code=resp.status_code, body=resp.text[:2000])
                    raise BusinessError(message=f"GLM ASR 返回错误（HTTP {resp.status_code}）")
                payload_json = resp.json()

    except httpx.HTTPError as exc:
        logger.exception("glm_asr_request_failed", error=str(exc))
        raise BusinessError(message="GLM ASR 请求失败") from exc
    except json.JSONDecodeError as exc:
        raise BusinessError(message="GLM ASR 返回内容无法解析（不是合法 JSON）") from exc

    # best-effort extract in non-stream mode
    direct = payload_json.get("text") if isinstance(payload_json, dict) else None
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    extracted = _extract_first_text(payload_json, ["text", "transcript", "content"])
    if extracted:
        return extracted.strip()

    raise BusinessError(message="GLM ASR 未返回识别文本")


async def gemini_tts_synthesize_wav(
    *,
    api_key: str,
    base_url: str,
    model: str,
    text: str,
    voice: str,
    sample_rate: int = 24000,
    timeout_seconds: float = 60.0,
) -> bytes:
    if genai is None or genai_types is None:
        raise BusinessError(message="未安装 google-genai，无法使用 Gemini TTS 演示")

    try:
        client = genai.Client(
            api_key=api_key,
            http_options=genai_types.HttpOptions(
                base_url=base_url,
                timeout=int(timeout_seconds * 1000),
            ),
        )

        resp = await client.aio.models.generate_content(
            model=model,
            contents=text,
            config=genai_types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=genai_types.SpeechConfig(
                    voice_config=genai_types.VoiceConfig(
                        prebuilt_voice_config=genai_types.PrebuiltVoiceConfig(voice_name=voice)
                    )
                ),
            ),
        )
    except Exception as exc:
        logger.exception("gemini_tts_failed", error=str(exc))
        raise BusinessError(message="Gemini TTS 合成失败") from exc

    try:
        candidates = getattr(resp, "candidates", None) or []
        part = candidates[0].content.parts[0].inline_data if candidates else None  # type: ignore[attr-defined]
        pcm_data = getattr(part, "data", None) if part else None
        if not pcm_data:
            raise ValueError("empty audio")
    except Exception as exc:
        logger.exception("gemini_tts_parse_failed", error=str(exc))
        raise BusinessError(message="Gemini TTS 未返回有效音频数据") from exc

    return _pcm16_to_wav_bytes(pcm_data=pcm_data, sample_rate=sample_rate, channels=1)


async def openai_tts_synthesize_stream(
    *,
    base_url: str,
    api_key: str,
    model: str,
    text: str,
    voice: str,
    response_format: str | None = None,
    speed: object | None = None,
    timeout_seconds: float = 60.0,
) -> SpeechAudioStream:
    fmt = (response_format or "wav").strip().lower()
    media_type, ext = _media_type_and_ext_from_hint(fmt)

    headers = {"Authorization": f"Bearer {api_key}"}
    payload: dict[str, object] = {
        "model": model,
        "input": text,
        "voice": voice,
        "response_format": fmt,
    }
    if speed is not None:
        payload["speed"] = speed

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            resp = await client.post(str(base_url), headers=headers, json=payload)
    except httpx.HTTPError as exc:
        logger.exception("openai_tts_request_failed", error=str(exc))
        raise BusinessError(message="OpenAI TTS 请求失败") from exc

    if resp.status_code >= 400:
        logger.warning("openai_tts_http_error", status_code=resp.status_code, body=resp.text[:2000])
        raise BusinessError(message=f"OpenAI TTS 返回错误（HTTP {resp.status_code}）")

    # Prefer content-type from server when possible
    ct = resp.headers.get("content-type")
    if ct:
        media_type, ext = _media_type_and_ext_from_content_type(ct)
    return _bytes_to_stream(data=resp.content, media_type=media_type, ext=ext)


async def glm_tts_synthesize_stream(
    *,
    base_url: str,
    api_key: str,
    model: str,
    text: str,
    voice: str,
    response_format: str | None = None,
    encode_format: str | None = None,
    stream: bool = True,
    speed: object | None = None,
    volume: object | None = None,
    timeout_seconds: float = 60.0,
) -> SpeechAudioStream:
    if not base_url.strip():
        raise BusinessError(message="GLM TTS 缺少 baseUrl")
    if not api_key.strip():
        raise BusinessError(message="GLM TTS 缺少 apiKey")
    if not text.strip():
        raise BusinessError(message="GLM TTS 缺少文本")

    fmt = (response_format or "pcm").strip().lower()
    enc = (encode_format or "base64").strip().lower()
    if enc and enc != "base64":
        raise BusinessError(message="GLM TTS 目前仅支持 encode_format=base64")

    headers: dict[str, str] = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream" if stream else "application/json",
    }

    payload: dict[str, object] = {
        "model": model,
        "input": text,
        "voice": voice,
        "response_format": fmt,
        "encode_format": enc or "base64",
        "stream": bool(stream),
    }
    if speed is not None:
        payload["speed"] = speed
    if volume is not None:
        payload["volume"] = volume

    sample_rate = 24000
    audio_chunks: list[bytes] = []

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
            if stream:
                async with client.stream("POST", str(base_url), headers=headers, json=payload) as resp:
                    if resp.status_code >= 400:
                        body = (await resp.aread()).decode("utf-8", errors="ignore")
                        logger.warning("glm_tts_http_error", status_code=resp.status_code, body=body[:2000])
                        raise BusinessError(message=f"GLM TTS 返回错误（HTTP {resp.status_code}）")

                    ct = (resp.headers.get("content-type") or "").lower()
                    if "text/event-stream" in ct:
                        done = False
                        async for event in _iter_sse_json(resp):
                            if not isinstance(event, dict):
                                continue
                            choices = event.get("choices")
                            if not isinstance(choices, list):
                                continue
                            for choice in choices:
                                if not isinstance(choice, dict):
                                    continue
                                if choice.get("finish_reason") == "stop":
                                    done = True
                                    break
                                delta = choice.get("delta")
                                if not isinstance(delta, dict):
                                    continue
                                sr = delta.get("return_sample_rate")
                                if isinstance(sr, int) and sr > 0:
                                    sample_rate = sr
                                content = delta.get("content")
                                if isinstance(content, str) and content.strip():
                                    audio_chunks.append(_maybe_decode_base64(content))
                            if done:
                                break
                    else:
                        raw = await resp.aread()
                        payload_json = json.loads(raw.decode("utf-8", errors="ignore"))
                        b64 = _extract_first_base64(payload_json, ["content", "audio", "audioBase64", "audio_base64", "data"])
                        if b64:
                            audio_chunks.append(_maybe_decode_base64(b64))
            else:
                resp = await client.post(str(base_url), headers=headers, json=payload)
                if resp.status_code >= 400:
                    logger.warning("glm_tts_http_error", status_code=resp.status_code, body=resp.text[:2000])
                    raise BusinessError(message=f"GLM TTS 返回错误（HTTP {resp.status_code}）")

                ct = (resp.headers.get("content-type") or "").lower()
                if ct.split(";", 1)[0].strip().startswith("audio/"):
                    media_type, ext = _media_type_and_ext_from_content_type(ct)
                    return _bytes_to_stream(data=resp.content, media_type=media_type, ext=ext)

                payload_json = resp.json()
                b64 = _extract_first_base64(payload_json, ["content", "audio", "audioBase64", "audio_base64", "data"])
                if b64:
                    audio_chunks.append(_maybe_decode_base64(b64))

    except httpx.HTTPError as exc:
        logger.exception("glm_tts_request_failed", error=str(exc))
        raise BusinessError(message="GLM TTS 请求失败") from exc
    except json.JSONDecodeError as exc:
        raise BusinessError(message="GLM TTS 返回内容无法解析（不是合法 JSON）") from exc

    audio_bytes = b"".join(audio_chunks)
    if not audio_bytes:
        raise BusinessError(message="GLM TTS 未返回音频数据")

    # Most common mode: pcm(base64) -> wrap as wav for easy playback
    if fmt in {"pcm", "pcm16"}:
        wav_bytes = _pcm16_to_wav_bytes(pcm_data=audio_bytes, sample_rate=sample_rate, channels=1)
        return _bytes_to_stream(data=wav_bytes, media_type="audio/wav", ext="wav")

    media_type, ext = _media_type_and_ext_from_hint(fmt)
    return _bytes_to_stream(data=audio_bytes, media_type=media_type, ext=ext)


async def azure_tts_synthesize_stream(
    *,
    region: str,
    subscription_key: str,
    text: str,
    voice: str,
    output_format: str | None = None,
    timeout_seconds: float = 60.0,
) -> SpeechAudioStream:
    if not region.strip():
        raise BusinessError(message="Azure TTS 缺少 region")
    if not subscription_key.strip():
        raise BusinessError(message="Azure TTS 缺少 subscriptionKey")
    if not voice.strip():
        raise BusinessError(message="Azure TTS 缺少 voice")

    fmt = (output_format or "audio-16khz-32kbitrate-mono-mp3").strip()
    media_type = "audio/mpeg" if "mp3" in fmt.lower() else "audio/wav" if "riff" in fmt.lower() else "application/octet-stream"
    ext = "mp3" if "mp3" in fmt.lower() else "wav" if "riff" in fmt.lower() else "bin"

    url = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"
    headers = {
        "Ocp-Apim-Subscription-Key": subscription_key,
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": fmt,
        "User-Agent": "AOJUAI",
    }

    parts = voice.split("-")
    lang = "-".join(parts[:2]) if len(parts) >= 2 else "zh-CN"
    ssml = (
        f"<speak version='1.0' xml:lang='{html.escape(lang)}'>"
        f"<voice name='{html.escape(voice)}'>{html.escape(text)}</voice>"
        f"</speak>"
    )

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            resp = await client.post(url, headers=headers, content=ssml.encode("utf-8"))
    except httpx.HTTPError as exc:
        logger.exception("azure_tts_request_failed", error=str(exc))
        raise BusinessError(message="Azure TTS 请求失败") from exc

    if resp.status_code >= 400:
        logger.warning("azure_tts_http_error", status_code=resp.status_code, body=resp.text[:2000])
        raise BusinessError(message=f"Azure TTS 返回错误（HTTP {resp.status_code}）")

    ct = resp.headers.get("content-type")
    if ct:
        media_type, ext = _media_type_and_ext_from_content_type(ct)
    return _bytes_to_stream(data=resp.content, media_type=media_type, ext=ext)


async def doubao_tts_synthesize_stream(
    *,
    api_url: str,
    authorization_prefix: str,
    appid: str,
    access_token: str,
    cluster: str,
    text: str,
    voice: str,
    audio_format: str = "wav",
    speed_ratio: float = 1.0,
    volume_ratio: float = 1.0,
    pitch_ratio: float = 1.0,
    timeout_seconds: float = 60.0,
) -> SpeechAudioStream:
    if not api_url.strip():
        raise BusinessError(message="Doubao TTS 缺少 apiUrl")
    if not appid.strip():
        raise BusinessError(message="Doubao TTS 缺少 appid")
    if not access_token.strip():
        raise BusinessError(message="Doubao TTS 缺少 accessToken")
    if not cluster.strip():
        raise BusinessError(message="Doubao TTS 缺少 cluster")
    if not voice.strip():
        raise BusinessError(message="Doubao TTS 缺少 voice")

    auth_header = f"{authorization_prefix or ''}{access_token}".strip()
    headers = {"Authorization": auth_header} if auth_header else {}

    fmt = (audio_format or "wav").strip().lower()
    media_type, ext = _media_type_and_ext_from_hint(fmt)

    payload = {
        "app": {"appid": appid, "token": access_token, "cluster": cluster},
        "user": {"uid": "aojuai-demo"},
        "audio": {
            "voice_type": voice,
            "encoding": fmt,
            "speed_ratio": speed_ratio,
            "volume_ratio": volume_ratio,
            "pitch_ratio": pitch_ratio,
        },
        "request": {
            "reqid": str(uuid.uuid4()),
            "text": text,
            "text_type": "plain",
            "operation": "query",
        },
    }

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            resp = await client.post(str(api_url), headers=headers, json=payload)
    except httpx.HTTPError as exc:
        logger.exception("doubao_tts_request_failed", error=str(exc))
        raise BusinessError(message="Doubao TTS 请求失败") from exc

    if resp.status_code >= 400:
        logger.warning("doubao_tts_http_error", status_code=resp.status_code, body=resp.text[:2000])
        raise BusinessError(message=f"Doubao TTS 返回错误（HTTP {resp.status_code}）")

    ct = resp.headers.get("content-type")
    if ct and ct.split(";", 1)[0].strip().lower().startswith("audio/"):
        media_type, ext = _media_type_and_ext_from_content_type(ct)
        return _bytes_to_stream(data=resp.content, media_type=media_type, ext=ext)

    try:
        payload_json = resp.json()
    except Exception:
        raise BusinessError(message="Doubao TTS 返回内容无法解析（既不是音频也不是 JSON）")

    code = payload_json.get("code") if isinstance(payload_json, dict) else None
    message = payload_json.get("message") if isinstance(payload_json, dict) else None
    if code not in (None, 0, 200, 3000, "0", "200", "3000"):
        raise BusinessError(message=f"Doubao TTS 返回错误: {message or code}")

    b64 = _extract_first_base64(payload_json, ["data", "audio", "audioBase64", "audio_base64"])
    audio_bytes = _maybe_decode_base64(b64)
    if not audio_bytes:
        raise BusinessError(message="Doubao TTS 未返回音频数据")
    return _bytes_to_stream(data=audio_bytes, media_type=media_type, ext=ext)


async def custom_http_tts_synthesize_stream(
    *,
    endpoint: str,
    text: str,
    headers_template: object | None,
    payload_template: object | None,
    secret_key1: str | None = None,
    secret_key2: str | None = None,
    output_format: str | None = None,
    timeout_seconds: float = 60.0,
    method: str | None = None,
    response_mode: str | None = None,
    response_path: str | None = None,
    audio_content_type: str | None = None,
) -> SpeechAudioStream:
    if not endpoint.strip():
        raise BusinessError(message="Custom HTTP TTS 缺少 endpoint")

    request_method = str(method or "POST").strip().upper()
    if request_method not in {"POST", "PUT"}:
        raise BusinessError(message="Custom HTTP TTS 仅支持 POST 或 PUT")

    preview_mode = str(response_mode or "").strip().lower()
    if preview_mode and preview_mode not in {"raw_binary", "json_base64", "json_url"}:
        raise BusinessError(message="Custom HTTP TTS responseMode 不受支持")

    variables: dict[str, object] = {
        "text": text,
        "secretKey1": secret_key1,
        "secretKey2": secret_key2,
    }

    rendered_headers, missing_headers = _render_template(headers_template or {}, variables)
    rendered_payload, missing_payload = _render_template(payload_template or {"text": "${text}"}, variables)
    missing = sorted(set(missing_headers) | set(missing_payload))
    if missing:
        raise BusinessError(message=f"Custom HTTP TTS 模板缺少变量: {', '.join(missing)}")

    headers: dict[str, str] = {}
    if isinstance(rendered_headers, dict):
        for k, v in rendered_headers.items():
            if k is None:
                continue
            headers[str(k)] = "" if v is None else str(v)

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
            resp = await client.request(request_method, str(endpoint), headers=headers, json=rendered_payload)
    except httpx.HTTPError as exc:
        logger.exception("custom_http_tts_request_failed", error=str(exc))
        raise BusinessError(message="Custom HTTP TTS 请求失败") from exc

    if resp.status_code >= 400:
        logger.warning("custom_http_tts_http_error", status_code=resp.status_code, body=resp.text[:2000])
        raise BusinessError(message=f"Custom HTTP TTS 返回错误（HTTP {resp.status_code}）")

    ct = resp.headers.get("content-type")
    fallback_media_type, fallback_ext = _media_type_and_ext_from_content_type(audio_content_type)
    if fallback_media_type == "application/octet-stream":
        fallback_media_type, fallback_ext = _media_type_and_ext_from_hint(output_format)

    if preview_mode == "raw_binary":
        if not resp.content:
            raise BusinessError(message="Custom HTTP TTS 未返回音频内容")
        media_type, ext = _media_type_and_ext_from_content_type(ct)
        if media_type == "application/octet-stream":
            media_type, ext = fallback_media_type, fallback_ext
        return _bytes_to_stream(data=resp.content, media_type=media_type, ext=ext)

    if ct and ct.split(";", 1)[0].strip().lower().startswith("audio/") and not preview_mode:
        media_type, ext = _media_type_and_ext_from_content_type(ct)
        return _bytes_to_stream(data=resp.content, media_type=media_type, ext=ext)

    try:
        payload_json = resp.json()
    except Exception:
        if preview_mode:
            raise BusinessError(message="Custom HTTP TTS 返回不是合法 JSON")
        media_type, ext = _media_type_and_ext_from_hint(output_format)
        return _bytes_to_stream(data=resp.content, media_type=media_type, ext=ext)

    if preview_mode == "json_base64":
        extracted = _extract_json_path(payload_json, response_path)
        audio_bytes = _maybe_decode_base64(str(extracted or ""))
        if not audio_bytes:
            raise BusinessError(message="Custom HTTP TTS 未返回可解码的 base64 音频")
        return _bytes_to_stream(data=audio_bytes, media_type=fallback_media_type, ext=fallback_ext)

    if preview_mode == "json_url":
        extracted = _extract_json_path(payload_json, response_path)
        audio_url = str(extracted or "").strip()
        if not audio_url:
            raise BusinessError(message="Custom HTTP TTS 响应中的音频 URL 为空")
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
                fetch = await client.get(
                    audio_url,
                    headers={k: v for k, v in headers.items() if k.lower() != "content-type"},
                )
        except httpx.HTTPError as exc:
            raise BusinessError(message="Custom HTTP TTS 获取 audioUrl 失败") from exc
        if fetch.status_code >= 400:
            raise BusinessError(message=f"Custom HTTP TTS 获取 audioUrl 返回错误（HTTP {fetch.status_code}）")
        media_type, ext = _media_type_and_ext_from_content_type(fetch.headers.get("content-type"))
        if media_type == "application/octet-stream":
            media_type, ext = fallback_media_type, fallback_ext
        return _bytes_to_stream(data=fetch.content, media_type=media_type, ext=ext)

    audio_url = payload_json.get("audioUrl") if isinstance(payload_json, dict) else None
    if isinstance(audio_url, str) and audio_url.strip():
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
                fetch = await client.get(audio_url.strip())
        except httpx.HTTPError as exc:
            raise BusinessError(message="Custom HTTP TTS 获取 audioUrl 失败") from exc
        if fetch.status_code >= 400:
            raise BusinessError(message=f"Custom HTTP TTS 获取 audioUrl 返回错误（HTTP {fetch.status_code}）")
        media_type, ext = _media_type_and_ext_from_content_type(fetch.headers.get("content-type"))
        return _bytes_to_stream(data=fetch.content, media_type=media_type, ext=ext)

    b64 = _extract_first_base64(payload_json, ["audioBase64", "audio_base64", "audio", "data"])
    audio_bytes = _maybe_decode_base64(b64)
    if not audio_bytes:
        raise BusinessError(message="Custom HTTP TTS 未返回音频数据（期望 audio/* 或 JSON(base64)）")

    media_type, ext = _media_type_and_ext_from_hint(output_format)
    ct2 = resp.headers.get("content-type")
    if ct2:
        mt2, ext2 = _media_type_and_ext_from_content_type(ct2)
        if mt2 != "application/octet-stream":
            media_type, ext = mt2, ext2
    return _bytes_to_stream(data=audio_bytes, media_type=media_type, ext=ext)


async def azure_stt_transcribe(
    *,
    region: str,
    subscription_key: str,
    audio_bytes: bytes,
    content_type: str,
    language: str = "zh-CN",
    timeout_seconds: float = 60.0,
) -> str:
    if not region.strip():
        raise BusinessError(message="Azure STT 缺少 region")
    if not subscription_key.strip():
        raise BusinessError(message="Azure STT 缺少 subscriptionKey")
    if not audio_bytes:
        raise BusinessError(message="Azure STT 缺少音频数据")

    url = (
        f"https://{region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1"
        f"?language={quote(language.strip() or 'zh-CN')}"
    )
    headers = {
        "Ocp-Apim-Subscription-Key": subscription_key,
        "Content-Type": content_type or "audio/wav",
    }

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            resp = await client.post(url, headers=headers, content=audio_bytes)
    except httpx.HTTPError as exc:
        logger.exception("azure_stt_request_failed", error=str(exc))
        raise BusinessError(message="Azure STT 请求失败") from exc

    if resp.status_code >= 400:
        logger.warning("azure_stt_http_error", status_code=resp.status_code, body=resp.text[:2000])
        raise BusinessError(message=f"Azure STT 返回错误（HTTP {resp.status_code}）")

    try:
        payload = resp.json()
    except Exception as exc:
        raise BusinessError(message="Azure STT 返回内容无法解析为 JSON") from exc

    if not isinstance(payload, dict):
        raise BusinessError(message="Azure STT 返回内容格式异常")

    text = payload.get("DisplayText") or payload.get("displayText")
    if isinstance(text, str) and text.strip():
        return text.strip()

    nbest = payload.get("NBest")
    if isinstance(nbest, list) and nbest:
        cand = nbest[0] if isinstance(nbest[0], dict) else {}
        for k in ("Display", "display", "Lexical", "lexical", "ITN", "itn", "MaskedITN", "maskedITN"):
            v = cand.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()

    status = payload.get("RecognitionStatus") or payload.get("recognitionStatus") or "Unknown"
    raise BusinessError(message=f"Azure STT 未识别到文本（{status}）")


async def doubao_asr_transcribe(
    *,
    api_url: str,
    authorization_prefix: str,
    appid: str,
    access_token: str,
    cluster: str,
    audio_bytes: bytes,
    mime_type: str,
    timeout_seconds: float = 60.0,
    extra: dict[str, object] | None = None,
) -> str:
    if not api_url.strip():
        raise BusinessError(message="Doubao ASR 缺少 apiUrl")
    if not appid.strip():
        raise BusinessError(message="Doubao ASR 缺少 appid")
    if not access_token.strip():
        raise BusinessError(message="Doubao ASR 缺少 accessToken")
    if not cluster.strip():
        raise BusinessError(message="Doubao ASR 缺少 cluster")

    auth_header = f"{authorization_prefix or ''}{access_token}".strip()
    headers = {"Authorization": auth_header} if auth_header else {}

    fmt = "wav"
    if mime_type:
        lower = mime_type.lower()
        if "mpeg" in lower or "mp3" in lower:
            fmt = "mp3"
        elif "webm" in lower:
            fmt = "webm"
        elif "ogg" in lower or "opus" in lower:
            fmt = "ogg"
        elif "wav" in lower:
            fmt = "wav"

    payload: dict[str, object] = {
        "app": {"appid": appid, "token": access_token, "cluster": cluster},
        "user": {"uid": "aojuai-demo"},
        "audio": {"format": fmt, "data": base64.b64encode(audio_bytes).decode("utf-8")},
        "request": {"reqid": str(uuid.uuid4()), "operation": "query"},
    }
    if extra:
        payload.update(extra)

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            resp = await client.post(str(api_url), headers=headers, json=payload)
    except httpx.HTTPError as exc:
        logger.exception("doubao_asr_request_failed", error=str(exc))
        raise BusinessError(message="Doubao ASR 请求失败") from exc

    if resp.status_code >= 400:
        logger.warning("doubao_asr_http_error", status_code=resp.status_code, body=resp.text[:2000])
        raise BusinessError(message=f"Doubao ASR 返回错误（HTTP {resp.status_code}）")

    try:
        payload_json = resp.json()
    except Exception:
        # Some gateways might return plain text
        txt = resp.text.strip()
        if txt:
            return txt
        raise BusinessError(message="Doubao ASR 返回内容无法解析")

    if not isinstance(payload_json, dict):
        raise BusinessError(message="Doubao ASR 返回内容格式异常")

    code = payload_json.get("code")
    message = payload_json.get("message")
    if code not in (None, 0, 200, 3000, "0", "200", "3000"):
        raise BusinessError(message=f"Doubao ASR 返回错误: {message or code}")

    text = payload_json.get("text") or payload_json.get("result") or payload_json.get("transcript")
    if isinstance(text, str) and text.strip():
        return text.strip()

    # Some responses may nest the result
    nested = payload_json.get("data")
    if isinstance(nested, dict):
        for k in ("text", "result", "transcript"):
            v = nested.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()

    raise BusinessError(message="Doubao ASR 未返回转写文本")


async def custom_http_stt_transcribe(
    *,
    endpoint: str,
    audio_bytes: bytes,
    mime_type: str,
    headers_template: object | None,
    payload_template: object | None,
    secret_key1: str | None = None,
    secret_key2: str | None = None,
    timeout_seconds: float = 60.0,
) -> str:
    if not endpoint.strip():
        raise BusinessError(message="Custom HTTP STT 缺少 endpoint")
    if not audio_bytes:
        raise BusinessError(message="Custom HTTP STT 缺少音频数据")

    variables: dict[str, object] = {
        "audioBase64": base64.b64encode(audio_bytes).decode("utf-8"),
        "mimeType": mime_type,
        "secretKey1": secret_key1,
        "secretKey2": secret_key2,
    }

    rendered_headers, missing_headers = _render_template(headers_template or {}, variables)
    rendered_payload, missing_payload = _render_template(
        payload_template or {"audioBase64": "${audioBase64}", "mimeType": "${mimeType}"},
        variables,
    )
    missing = sorted(set(missing_headers) | set(missing_payload))
    if missing:
        raise BusinessError(message=f"Custom HTTP STT 模板缺少变量: {', '.join(missing)}")

    headers: dict[str, str] = {}
    if isinstance(rendered_headers, dict):
        for k, v in rendered_headers.items():
            if k is None:
                continue
            headers[str(k)] = "" if v is None else str(v)

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
            resp = await client.post(str(endpoint), headers=headers, json=rendered_payload)
    except httpx.HTTPError as exc:
        logger.exception("custom_http_stt_request_failed", error=str(exc))
        raise BusinessError(message="Custom HTTP STT 请求失败") from exc

    if resp.status_code >= 400:
        logger.warning("custom_http_stt_http_error", status_code=resp.status_code, body=resp.text[:2000])
        raise BusinessError(message=f"Custom HTTP STT 返回错误（HTTP {resp.status_code}）")

    ct = (resp.headers.get("content-type") or "").lower()
    if "application/json" not in ct:
        txt = resp.text.strip()
        if txt:
            return txt

    try:
        payload_json = resp.json()
    except Exception:
        txt = resp.text.strip()
        if txt:
            return txt
        raise BusinessError(message="Custom HTTP STT 返回内容无法解析")

    if isinstance(payload_json, dict):
        for k in ("text", "transcript", "result"):
            v = payload_json.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        nested = payload_json.get("data")
        if isinstance(nested, dict):
            for k in ("text", "transcript", "result"):
                v = nested.get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip()

    raise BusinessError(message="Custom HTTP STT 未返回转写文本（期望 text/transcript/result）")
