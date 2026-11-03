"""Alibaba Bailian Qwen TTS Realtime provider via DashScope Python SDK."""

from __future__ import annotations

import asyncio
import ast
import json
import re
import ssl
import threading
import time
from typing import Any
from urllib.parse import urlsplit

from app.core.exceptions import BusinessError
from app.domain.speech.providers.aliyun_qwen_tts import (
    ALIYUN_QWEN_TTS_LANGUAGE_OPTIONS,
    ALIYUN_QWEN_TTS_MAX_INPUT_BYTES,
    ALIYUN_QWEN_TTS_SAFE_INPUT_BYTES,
    ALIYUN_QWEN_TTS_VOICE_OPTIONS,
    _field,
    _split_aliyun_qwen_tts_text,
    build_aliyun_qwen_tts_prompt_context,
)
from app.domain.speech.providers.common import (
    SpeechAudioStream,
    bytes_to_stream,
    concat_wav_audio_segments,
    decode_base64_audio,
)
from app.domain.speech.schemas import (
    SpeechFieldOption,
    SpeechFieldType,
    SpeechProviderCapabilities,
    SpeechProviderDescriptor,
)

DEFAULT_ALIYUN_QWEN_TTS_REALTIME_WS_URL = "wss://dashscope.aliyuncs.com/api-ws/v1/realtime"
DEFAULT_ALIYUN_QWEN_TTS_REALTIME_WS_URL_INTL = "wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime"
DEFAULT_ALIYUN_QWEN_TTS_REALTIME_MODEL = "qwen3-tts-instruct-flash-realtime"
_DASHSCOPE_SDK_LOCK = threading.Lock()
_REALTIME_HANDSHAKE_STATUS_RE = re.compile(r"Handshake status\s+(\d+)")

try:  # pragma: no cover - import is validated by runtime smoke
    import certifi
    import dashscope
    import websocket
    from dashscope.audio.qwen_tts_realtime import AudioFormat, QwenTtsRealtime, QwenTtsRealtimeCallback
except Exception:  # pragma: no cover
    certifi = None
    dashscope = None
    websocket = None
    AudioFormat = None
    QwenTtsRealtime = None
    QwenTtsRealtimeCallback = object

_QWEN_TTS_REALTIME_BASE = QwenTtsRealtime if QwenTtsRealtime is not None else object


class _RealtimeCollectorCallback(QwenTtsRealtimeCallback):  # type: ignore[misc]
    def __init__(self) -> None:
        self.done = threading.Event()
        self.audio_chunks: list[bytes] = []
        self.error_payload: dict[str, Any] | None = None
        self.close_status_code: Any = None
        self.close_message: Any = None

    def on_open(self) -> None:
        return None

    def on_close(self, close_status_code, close_msg) -> None:
        self.close_status_code = close_status_code
        self.close_message = close_msg
        if close_status_code not in (None, 1000) and self.error_payload is None:
            self.error_payload = {
                "message": "Qwen TTS Realtime 连接已关闭",
                "closeStatusCode": close_status_code,
                "closeMessage": close_msg,
            }
        self.done.set()

    def on_error(self, error: Any) -> None:
        if self.error_payload is None:
            self.error_payload = _build_realtime_error_payload(error)
        self.done.set()

    def on_event(self, message: str) -> None:
        payload: Any = message
        if isinstance(message, str):
            try:
                payload = json.loads(message)
            except json.JSONDecodeError:
                self.error_payload = {"message": "Qwen TTS Realtime 返回了无法解析的事件"}
                self.done.set()
                return
        if not isinstance(payload, dict):
            return

        event_type = str(payload.get("type") or "").strip()
        if event_type == "response.audio.delta":
            delta = _extract_audio_delta(payload)
            if delta:
                self.audio_chunks.append(decode_base64_audio(delta))
            return

        if event_type in {"error", "response.error"}:
            self.error_payload = payload
            self.done.set()
            return

        if event_type == "response.done":
            response = payload.get("response") if isinstance(payload.get("response"), dict) else {}
            status = str(response.get("status") or "").strip().lower()
            if status in {"failed", "cancelled"} and self.error_payload is None:
                self.error_payload = payload
            self.done.set()


class _ObservedQwenTtsRealtime(_QWEN_TTS_REALTIME_BASE):  # type: ignore[misc]
    def on_error(self, ws, error):  # pragma: no cover - exercised through provider smoke
        try:
            self.callback.on_error(error)
        finally:
            return None


class _CertAwareQwenTtsRealtime(_ObservedQwenTtsRealtime):  # type: ignore[misc]
    def __init__(
        self,
        *args,
        connect_timeout_seconds: float = 15.0,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.connect_timeout_seconds = max(float(connect_timeout_seconds or 5.0), 5.0)

    def connect(self) -> None:  # pragma: no cover - exercised through provider smoke
        if websocket is None or certifi is None:
            raise BusinessError(message="websocket-client 或 certifi 缺失，无法建立 realtime 连接")
        self.ws = websocket.WebSocketApp(
            self.url,
            header=self._get_websocket_header(),
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
        )
        self.thread = threading.Thread(
            target=self.ws.run_forever,
            kwargs={
                "sslopt": {
                    "cert_reqs": ssl.CERT_REQUIRED,
                    "ca_certs": certifi.where(),
                    "check_hostname": True,
                }
            },
        )
        self.thread.daemon = True
        self.thread.start()
        timeout = self.connect_timeout_seconds
        start_time = time.time()
        while not (self.ws.sock and self.ws.sock.connected) and (time.time() - start_time) < timeout:
            time.sleep(0.1)
        if not (self.ws.sock and self.ws.sock.connected):
            raise TimeoutError(
                f"websocket connection could not established within {timeout:.0f}s. "
                "Please check your network connection, firewall settings, or server status.",
            )
        self.callback.on_open()


def _extract_audio_delta(payload: dict[str, Any]) -> str:
    direct = payload.get("delta")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    audio = payload.get("audio")
    if isinstance(audio, dict):
        audio_delta = audio.get("delta")
        if isinstance(audio_delta, str) and audio_delta.strip():
            return audio_delta.strip()

    response = payload.get("response")
    if isinstance(response, dict):
        response_delta = response.get("delta")
        if isinstance(response_delta, str) and response_delta.strip():
            return response_delta.strip()
        response_audio = response.get("audio")
        if isinstance(response_audio, dict):
            response_audio_delta = response_audio.get("delta")
            if isinstance(response_audio_delta, str) and response_audio_delta.strip():
                return response_audio_delta.strip()

    return ""


def _extract_error_message(payload: dict[str, Any] | None) -> str:
    source = payload if isinstance(payload, dict) else {}
    error = source.get("error")
    if isinstance(error, dict):
        message = str(error.get("message") or error.get("code") or "").strip()
        if message:
            return message
    for key in ("message", "msg", "detail", "code", "type"):
        value = source.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "Qwen TTS Realtime 返回错误"


def _build_realtime_error_payload(error: Any) -> dict[str, Any]:
    raw_message = str(error or "Qwen TTS Realtime WebSocket 连接失败").strip() or "Qwen TTS Realtime WebSocket 连接失败"
    payload: dict[str, Any] = {
        "message": raw_message,
        "rawError": raw_message,
    }

    status_match = _REALTIME_HANDSHAKE_STATUS_RE.search(raw_message)
    if status_match:
        payload["statusCode"] = int(status_match.group(1))

    body_literal = ""
    for prefix in ("b'", 'b"'):
        start = raw_message.rfind(prefix)
        if start >= 0:
            body_literal = raw_message[start:]
            break

    if body_literal:
        try:
            body_bytes = ast.literal_eval(body_literal)
            if isinstance(body_bytes, bytes):
                body_text = body_bytes.decode("utf-8", errors="ignore").strip()
                if body_text:
                    payload["responseBody"] = body_text
                    try:
                        parsed = json.loads(body_text)
                    except json.JSONDecodeError:
                        parsed = None
                    if isinstance(parsed, dict):
                        payload["error"] = parsed
                        message = str(parsed.get("message") or parsed.get("code") or "").strip()
                        if message:
                            payload["message"] = message
        except Exception:
            pass

    return payload


def _normalize_realtime_ws_url(base_url: str | None) -> str:
    normalized = str(base_url or "").strip()
    if not normalized:
        return DEFAULT_ALIYUN_QWEN_TTS_REALTIME_WS_URL

    parsed = urlsplit(normalized)
    scheme = parsed.scheme.lower().strip()
    hostname = (parsed.hostname or "").lower().strip()

    if scheme in {"ws", "wss"}:
        base_path = normalized.split("?", 1)[0].rstrip("/")
        return base_path or DEFAULT_ALIYUN_QWEN_TTS_REALTIME_WS_URL

    if scheme in {"http", "https"}:
        if "dashscope-intl.aliyuncs.com" in hostname:
            return DEFAULT_ALIYUN_QWEN_TTS_REALTIME_WS_URL_INTL
        if "dashscope.aliyuncs.com" in hostname:
            return DEFAULT_ALIYUN_QWEN_TTS_REALTIME_WS_URL
        raise BusinessError(message="Qwen TTS Realtime SDK 需要 WebSocket URL（wss://...），当前 baseUrl 不是 DashScope 地址")

    raise BusinessError(message="Qwen TTS Realtime SDK 的 baseUrl 必须是 ws:// 或 wss:// 地址")


def _build_realtime_connect_failure(
    *,
    callback: _RealtimeCollectorCallback,
    attempt_errors: list[str],
) -> BusinessError | None:
    if callback.error_payload is None and callback.close_status_code in (None, 1000):
        return None

    details = dict(callback.error_payload or {})
    if callback.close_status_code not in (None, 1000):
        details.setdefault("closeStatusCode", callback.close_status_code)
        details.setdefault("closeMessage", callback.close_message)
    if attempt_errors:
        details["attempts"] = list(attempt_errors)

    return BusinessError(
        message=f"Qwen TTS Realtime SDK 握手失败：{_extract_error_message(details)}",
        details=details,
    )


def build_aliyun_qwen_tts_realtime_sdk_provider_descriptor() -> SpeechProviderDescriptor:
    model_options = [
        SpeechFieldOption(value=DEFAULT_ALIYUN_QWEN_TTS_REALTIME_MODEL, label=DEFAULT_ALIYUN_QWEN_TTS_REALTIME_MODEL),
        SpeechFieldOption(value="qwen3-tts-flash-realtime", label="qwen3-tts-flash-realtime"),
    ]
    return SpeechProviderDescriptor(
        id="aliyun_qwen_tts_realtime_sdk",
        category="tts",
        name="Alibaba Bailian Qwen TTS Realtime (SDK)",
        description=(
            "通过 DashScope Python SDK 接入 Qwen TTS Realtime。当前先聚合单次 realtime 会话的音频后再返回，"
            "用于验证 SDK 链路，不替换现有 HTTP provider。"
        ),
        capabilities=SpeechProviderCapabilities(
            supports_voices_list=True,
            supports_tts_stream_audio=False,
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
                label="WebSocket URL",
                field_type=SpeechFieldType.STRING,
                default=DEFAULT_ALIYUN_QWEN_TTS_REALTIME_WS_URL,
                description="默认北京地域 realtime WebSocket 接入点。",
            ),
            _field(
                key="model",
                label="Model",
                field_type=SpeechFieldType.SELECT,
                default=DEFAULT_ALIYUN_QWEN_TTS_REALTIME_MODEL,
                options=model_options,
                description="建议优先使用 instruct realtime 系列，便于沿用 instructions 控制语气和语速。",
                ui={"allowCreate": True, "filterable": True},
            ),
            _field(
                key="voice",
                label="Voice",
                field_type=SpeechFieldType.SELECT,
                default="Cherry",
                options=ALIYUN_QWEN_TTS_VOICE_OPTIONS,
                description="当前沿用 Qwen TTS 官方音色列表。",
                ui={"allowCreate": True, "filterable": True},
            ),
            _field(
                key="languageType",
                label="Language Type",
                field_type=SpeechFieldType.SELECT,
                default="Chinese",
                options=ALIYUN_QWEN_TTS_LANGUAGE_OPTIONS,
                description="建议与实际文本语种一致。",
                ui={"allowCreate": True, "filterable": True},
            ),
            _field(
                key="instructions",
                label="Instructions",
                field_type=SpeechFieldType.TEXTAREA,
                description="instruct realtime 模型可用。用自然语言描述语速、语气、情绪与角色氛围。",
            ),
            _field(
                key="previewText",
                label="Preview Text",
                field_type=SpeechFieldType.TEXTAREA,
                description="当前渠道声音试听的默认文案。留空时系统会按当前租户品牌名和 SEO 简介自动生成。",
                placeholder="例如：这里是你的品牌语音，正在试听当前声音，语气自然，适合长时间收听。",
            ),
            _field(
                key="optimizeInstructions",
                label="Optimize Instructions",
                field_type=SpeechFieldType.BOOLEAN,
                default=False,
                description="开启后先优化 instructions，再交给 realtime instruct 模型执行。",
            ),
            _field(
                key="volume",
                label="Volume",
                field_type=SpeechFieldType.NUMBER,
                default=50,
                ui={"component": "slider", "min": 0, "max": 100, "step": 1, "showInput": True},
            ),
            _field(
                key="speechRate",
                label="Speech Rate",
                field_type=SpeechFieldType.NUMBER,
                default=1.0,
                ui={"component": "slider", "min": 0.5, "max": 2.0, "step": 0.05, "showInput": True},
            ),
            _field(
                key="pitchRate",
                label="Pitch Rate",
                field_type=SpeechFieldType.NUMBER,
                default=1.0,
                ui={"component": "slider", "min": 0.5, "max": 2.0, "step": 0.05, "showInput": True},
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


def build_aliyun_qwen_tts_realtime_sdk_prompt_context(
    *,
    model: str | None = None,
) -> dict[str, Any]:
    descriptor = build_aliyun_qwen_tts_realtime_sdk_provider_descriptor()
    selected_model = str(model or DEFAULT_ALIYUN_QWEN_TTS_REALTIME_MODEL).strip() or DEFAULT_ALIYUN_QWEN_TTS_REALTIME_MODEL
    context = build_aliyun_qwen_tts_prompt_context(model=selected_model)
    instruction_guidance = list(context.get("instructionGuidance") or [])
    model_capabilities = (
        context.get("modelCapabilities")
        if isinstance(context.get("modelCapabilities"), dict)
        else {}
    )
    selected_model = str(context.get("selectedModel") or selected_model).strip()
    if selected_model.endswith("-realtime"):
        model_capabilities = {
            **model_capabilities,
            "selectedModel": selected_model,
            "supportsVoiceClone": False,
            "supportsInstructions": False,
            "supportsOptimizeInstructions": False,
            "supportsStyle": False,
            "supportsLanguageType": True,
            "supportsRequestOverrides": False,
            "voiceSelectionMode": "official_or_custom",
            "allowedCueFields": ["voice", "languageType"],
        }
        instruction_guidance = [
            "当前 realtime model 不走 instruct 通道，内容生成不要输出 instructions / optimizeInstructions。",
            "如果需要稳定声音人格，请优先通过 voice 选择来完成，不要把 style 或长 instructions 硬塞给 realtime flash 模型。",
        ]
        generation_guidance = [
            "内容生成时把 realtime flash 当成轻量 voice 通道，优先用 voice 选择音色，只在必要时补 languageType。",
            "当前 realtime 模型不要输出 style / instructions / requestOverrides，避免生成出无效字段。",
        ]
    else:
        generation_guidance = list(context.get("generationGuidance") or [])
    context.update(
        {
            "providerName": str(descriptor.name or "aliyun_qwen_tts_realtime_sdk").strip(),
            "providerDescription": str(descriptor.description or "").strip(),
            "selectedModel": selected_model,
            "modelCapabilities": model_capabilities,
            "instructionGuidance": [
                "当前通过 DashScope Python SDK 接入 realtime，会在服务端聚合单次会话的音频后统一返回。",
                *instruction_guidance,
            ],
            "generationGuidance": generation_guidance,
        }
    )
    return context


def _synthesize_single_realtime_chunk_sync(
    *,
    api_key: str,
    text: str,
    base_url: str | None,
    model: str,
    voice: str,
    language_type: str | None = None,
    instructions: str | None = None,
    optimize_instructions: bool = False,
    volume: int | None = None,
    speech_rate: float | None = None,
    pitch_rate: float | None = None,
    timeout_seconds: float = 60,
) -> bytes:
    if dashscope is None or QwenTtsRealtime is None or AudioFormat is None:
        raise BusinessError(message="未安装 dashscope，无法使用 Qwen TTS Realtime SDK provider")

    normalized_api_key = str(api_key or "").strip()
    normalized_model = str(model or DEFAULT_ALIYUN_QWEN_TTS_REALTIME_MODEL).strip()
    normalized_voice = str(voice or "").strip()
    normalized_text = str(text or "").strip()
    normalized_base_url = str(base_url or DEFAULT_ALIYUN_QWEN_TTS_REALTIME_WS_URL).strip()
    if not normalized_api_key:
        raise BusinessError(message="Qwen TTS Realtime SDK 缺少 API Key")
    if not normalized_model:
        raise BusinessError(message="Qwen TTS Realtime SDK 缺少 Model")
    if not normalized_voice:
        raise BusinessError(message="Qwen TTS Realtime SDK 缺少 Voice")
    if not normalized_text:
        raise BusinessError(message="Qwen TTS Realtime SDK 缺少文本")
    normalized_base_url = _normalize_realtime_ws_url(base_url)

    with _DASHSCOPE_SDK_LOCK:
        dashscope.api_key = normalized_api_key
        attempt_errors: list[str] = []
        connect_failure: BusinessError | None = None
        for use_cert_aware in (True, False):
            callback = _RealtimeCollectorCallback()
            synthesizer = (
                _CertAwareQwenTtsRealtime(
                    model=normalized_model,
                    callback=callback,
                    url=normalized_base_url or None,
                    connect_timeout_seconds=min(max(float(timeout_seconds or 15.0), 5.0), 30.0),
                )
                if use_cert_aware
                else _ObservedQwenTtsRealtime(
                    model=normalized_model,
                    callback=callback,
                    url=normalized_base_url or None,
                )
            )
            try:
                try:
                    synthesizer.connect()
                except TimeoutError as exc:
                    connect_failure = _build_realtime_connect_failure(
                        callback=callback,
                        attempt_errors=attempt_errors,
                    )
                    if connect_failure is not None:
                        attempt_errors.append(
                            f"{'cert' if use_cert_aware else 'sdk'} handshake failure: {connect_failure}"
                        )
                    else:
                        attempt_errors.append(f"{'cert' if use_cert_aware else 'sdk'} connect timeout: {exc}")
                    continue
                synthesizer.update_session(
                    voice=normalized_voice,
                    response_format=AudioFormat.PCM_24000HZ_MONO_16BIT,
                    mode="commit",
                    language_type=str(language_type or "").strip() or None,
                    instructions=str(instructions or "").strip() or None,
                    optimize_instructions=bool(optimize_instructions),
                    volume=volume,
                    speech_rate=speech_rate,
                    pitch_rate=pitch_rate,
                )
                synthesizer.append_text(normalized_text)
                synthesizer.commit()
                if not callback.done.wait(timeout=max(float(timeout_seconds), 5.0)):
                    raise BusinessError(message="Qwen TTS Realtime SDK 合成超时")
                if callback.error_payload is not None:
                    raise BusinessError(
                        message=f"Qwen TTS Realtime SDK 返回错误：{_extract_error_message(callback.error_payload)}",
                        details=callback.error_payload,
                    )
                pcm_bytes = b"".join(callback.audio_chunks)
                if not pcm_bytes:
                    raise BusinessError(message="Qwen TTS Realtime SDK 未返回音频数据")
                return pcm_bytes
            except BusinessError as exc:
                attempt_errors.append(str(exc))
            finally:
                try:
                    synthesizer.finish()
                except Exception:
                    pass
                try:
                    synthesizer.close()
                except Exception:
                    pass

    if connect_failure is not None:
        failure_details = dict(connect_failure.details or {})
        failure_details["attempts"] = attempt_errors or failure_details.get("attempts") or ["unknown"]
        raise BusinessError(message=connect_failure.message, details=failure_details)

    raise BusinessError(
        message="Qwen TTS Realtime SDK 连接失败",
        details={"attempts": attempt_errors or ["unknown"]},
    )


async def aliyun_qwen_tts_realtime_sdk_synthesize_stream(
    *,
    api_key: str,
    text: str,
    base_url: str | None = None,
    model: str | None = None,
    voice: str | None = None,
    language_type: str | None = None,
    instructions: str | None = None,
    optimize_instructions: bool = False,
    volume: int | None = None,
    speech_rate: float | None = None,
    pitch_rate: float | None = None,
    timeout_seconds: float = 60,
) -> SpeechAudioStream:
    normalized_text = str(text or "").strip()
    if not normalized_text:
        raise BusinessError(message="Qwen TTS Realtime SDK 缺少文本")

    text_chunks = _split_aliyun_qwen_tts_text(
        normalized_text,
        max_bytes=min(ALIYUN_QWEN_TTS_SAFE_INPUT_BYTES, ALIYUN_QWEN_TTS_MAX_INPUT_BYTES),
    )
    wav_segments: list[bytes] = []
    for text_chunk in text_chunks:
        pcm_bytes = await asyncio.to_thread(
            _synthesize_single_realtime_chunk_sync,
            api_key=api_key,
            text=text_chunk,
            base_url=base_url,
            model=str(model or DEFAULT_ALIYUN_QWEN_TTS_REALTIME_MODEL).strip(),
            voice=str(voice or "Cherry").strip(),
            language_type=language_type,
            instructions=instructions,
            optimize_instructions=optimize_instructions,
            volume=volume,
            speech_rate=speech_rate,
            pitch_rate=pitch_rate,
            timeout_seconds=timeout_seconds,
        )
        wav_segments.append(pcm_bytes)

    wav_bytes = concat_wav_audio_segments(audio_segments=wav_segments, sample_rate=24000, channels=1)
    return bytes_to_stream(data=wav_bytes, media_type="audio/wav", ext="wav")
