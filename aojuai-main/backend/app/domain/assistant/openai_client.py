"""
AOJU Backend - OpenAI Compatible Client

OpenAI兼容API客户端，支持流和非流模式
"""
import asyncio
import contextvars
import hashlib
import json
import os
import random
import re
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import httpx

from app.domain.credits.usage import record_llm_usage

OPENAI_COMPAT_REQUEST_MAX_RETRIES = 8
OPENAI_COMPAT_REQUEST_MAX_ATTEMPTS = OPENAI_COMPAT_REQUEST_MAX_RETRIES + 1
OPENAI_COMPAT_DEFAULT_MAX_CONCURRENT_REQUESTS = 20
OPENAI_COMPAT_MAX_CONCURRENT_REQUESTS = 100
# 凭据级并发限流：默认 0 = 关闭（保持现状，只有全局信号量生效）。
OPENAI_COMPAT_DEFAULT_MAX_CONCURRENT_PER_CREDENTIAL = 0
OPENAI_COMPAT_CREDENTIAL_SEMAPHORE_REGISTRY_MAX_SIZE = 256
_OPENAI_COMPAT_REQUEST_SEMAPHORE: asyncio.Semaphore | None = None
# 凭据级子信号量注册表：key = sha256(base_url + api_key) 前 16 位。
# 当前生产为单实例单 worker 进程，进程内注册表即可满足限流语义；
# 未来多实例部署时需升级为跨进程共享配额（如 Redis）。
_OPENAI_COMPAT_CREDENTIAL_SEMAPHORES: dict[str, tuple[int, asyncio.Semaphore]] = {}

# 每调用独立的请求指标 sink：chat_with_usage_and_metrics 通过 ContextVar 注入
# 单元素列表，_record_request_metrics 同步写入，实现并发 fan-out 下互不覆盖。
_OPENAI_COMPAT_CALL_METRICS_SINK: contextvars.ContextVar[list[dict[str, Any] | None] | None] = contextvars.ContextVar(
    "aoju_openai_compat_call_metrics_sink",
    default=None,
)


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _chat_endpoint(base_url: str) -> str:
    normalized = str(base_url or "").strip().rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    if normalized.endswith("/responses"):
        return normalized[: -len("/responses")] + "/chat/completions"
    return f"{normalized}/chat/completions"


def _responses_endpoint(base_url: str) -> str:
    normalized = str(base_url or "").strip().rstrip("/")
    if normalized.endswith("/responses"):
        return normalized
    if normalized.endswith("/chat/completions"):
        return normalized[: -len("/chat/completions")] + "/responses"
    return f"{normalized}/responses"


def _safe_response_json(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except Exception:
        return {"raw": response.text[:2000]}
    return payload if isinstance(payload, dict) else {"raw": payload}


def _normalize_usage(value: object) -> dict[str, int]:
    payload = value if isinstance(value, dict) else {}

    def _to_int(raw: object) -> int:
        try:
            parsed = int(raw or 0)
        except (TypeError, ValueError):
            return 0
        return max(parsed, 0)

    prompt_tokens = _to_int(payload.get("prompt_tokens") or payload.get("input_tokens"))
    completion_tokens = _to_int(payload.get("completion_tokens") or payload.get("output_tokens"))
    total_tokens = _to_int(payload.get("total_tokens"))

    if total_tokens <= 0:
        total_tokens = prompt_tokens + completion_tokens
    details = payload.get("prompt_tokens_details") or payload.get("input_tokens_details")
    details_payload = details if isinstance(details, dict) else {}
    try:
        cached_tokens = int(details_payload.get("cached_tokens") or 0)
    except (TypeError, ValueError):
        cached_tokens = 0

    reasoning_details = payload.get("completion_tokens_details") or payload.get("output_tokens_details")
    reasoning_payload = reasoning_details if isinstance(reasoning_details, dict) else {}
    try:
        reasoning_tokens = int(reasoning_payload.get("reasoning_tokens") or 0)
    except (TypeError, ValueError):
        reasoning_tokens = 0

    try:
        cache_write_tokens = int(details_payload.get("cache_write_tokens") or 0)
    except (TypeError, ValueError):
        cache_write_tokens = 0

    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "cached_tokens": max(cached_tokens, 0),
        # 缓存写入（部分网关在 input_tokens_details 里给）：已含在 prompt_tokens，按写入价计
        "cache_write_tokens": max(cache_write_tokens, 0),
        # reasoning 是 completion 的子集，只作明细，不参与相加（codex 评审 2026-08-26）
        "reasoning_tokens": max(reasoning_tokens, 0),
    }


def _utc_iso_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def _incremental_content_text(value: Any) -> str:
    """流式增量的内容提取：绝不 strip。

    每个 SSE chunk 的 content 常以空格/换行开头（token 边界），逐 chunk strip 会把
    聚合文本的空格全部吃掉（历史流式 bug 的根因）；首尾清理只能在聚合完成后做。
    """
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
                continue
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if isinstance(text, dict):
                text = text.get("value")
            if text is None:
                text = item.get("content") or item.get("output_text") or item.get("input_text")
            if isinstance(text, str):
                parts.append(text)
        return "".join(parts)
    if isinstance(value, dict):
        return _incremental_content_text(value.get("text") or value.get("content") or value.get("output_text"))
    return "" if value is None else str(value)


def _content_text(value: Any) -> str:
    if isinstance(value, str):
        return _normalize_text(value)
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
                continue
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if isinstance(text, dict):
                text = text.get("value")
            if text is None:
                text = item.get("content") or item.get("output_text") or item.get("input_text")
            if isinstance(text, str):
                parts.append(text)
        return _normalize_text("\n".join(part for part in parts if _normalize_text(part)))
    if isinstance(value, dict):
        return _content_text(value.get("text") or value.get("content") or value.get("output_text"))
    return _normalize_text(value)


def _extract_chat_content(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    items = choices if isinstance(choices, list) else []
    if not items:
        raise ValueError("AI模型未返回 choices")
    first = items[0] if isinstance(items[0], dict) else {}
    message = first.get("message") if isinstance(first.get("message"), dict) else {}
    content = _content_text(message.get("content") or first.get("text") or first.get("content"))
    if not content:
        raise ValueError("AI模型未返回可用内容")
    return content


def _extract_responses_content(payload: dict[str, Any]) -> str:
    output_text = _content_text(payload.get("output_text"))
    if output_text:
        return output_text
    parts: list[str] = []
    output = payload.get("output")
    for item in output if isinstance(output, list) else []:
        if not isinstance(item, dict):
            continue
        text = _content_text(item.get("content") or item.get("text"))
        if text:
            parts.append(text)
    content = _normalize_text("\n".join(parts))
    if content:
        return content
    if "choices" in payload:
        return _extract_chat_content(payload)
    raise ValueError("AI模型未返回可用内容")


def _response_error_message(response: httpx.Response, payload: dict[str, Any]) -> str:
    message = payload.get("error")
    if isinstance(message, dict):
        message = message.get("message")
    return _normalize_text(message) or response.text[:500]


def _truncate_error_text(data: Any) -> str:
    try:
        return json.dumps(data, ensure_ascii=False)[:400]
    except Exception:
        return str(data)[:400]


class _EmptyStreamError(RuntimeError):
    """流式响应完成但没有任何内容增量（通常是网关静默截断）。"""


class _TruncatedStreamError(RuntimeError):
    pass


class _StreamFinishError(RuntimeError):
    pass


def _is_retryable_status(status_code: int) -> bool:
    return status_code == 429 or status_code >= 500


def _openai_compat_max_concurrent_requests() -> int:
    try:
        value = int(os.getenv("AOJU_OPENAI_COMPAT_MAX_CONCURRENT_REQUESTS", str(OPENAI_COMPAT_DEFAULT_MAX_CONCURRENT_REQUESTS)))
    except (TypeError, ValueError):
        value = OPENAI_COMPAT_DEFAULT_MAX_CONCURRENT_REQUESTS
    return max(1, min(OPENAI_COMPAT_MAX_CONCURRENT_REQUESTS, value))


def _openai_compat_request_semaphore() -> asyncio.Semaphore:
    global _OPENAI_COMPAT_REQUEST_SEMAPHORE
    if _OPENAI_COMPAT_REQUEST_SEMAPHORE is None:
        _OPENAI_COMPAT_REQUEST_SEMAPHORE = asyncio.Semaphore(_openai_compat_max_concurrent_requests())
    return _OPENAI_COMPAT_REQUEST_SEMAPHORE


def _openai_compat_max_concurrent_per_credential() -> int:
    try:
        value = int(
            os.getenv(
                "AOJU_OPENAI_COMPAT_MAX_CONCURRENT_PER_CREDENTIAL",
                str(OPENAI_COMPAT_DEFAULT_MAX_CONCURRENT_PER_CREDENTIAL),
            )
        )
    except (TypeError, ValueError):
        value = OPENAI_COMPAT_DEFAULT_MAX_CONCURRENT_PER_CREDENTIAL
    if value <= 0:
        return 0
    return min(OPENAI_COMPAT_MAX_CONCURRENT_REQUESTS, value)


def _credential_semaphore_key(base_url: str, api_key: str) -> str:
    digest = hashlib.sha256(f"{base_url}\n{api_key}".encode()).hexdigest()
    return digest[:16]


def _openai_compat_credential_semaphore(key: str, limit: int) -> asyncio.Semaphore:
    """按凭据键返回子信号量；limit 变化时重建，注册表有大小上限防泄漏。"""
    entry = _OPENAI_COMPAT_CREDENTIAL_SEMAPHORES.get(key)
    if entry is not None and entry[0] == limit:
        return entry[1]
    if entry is None and len(_OPENAI_COMPAT_CREDENTIAL_SEMAPHORES) >= OPENAI_COMPAT_CREDENTIAL_SEMAPHORE_REGISTRY_MAX_SIZE:
        # FIFO 淘汰最早注册的凭据键；被淘汰键上正在等待的请求仍持有旧信号量对象，
        # 只是后续新请求会拿到新对象，短暂放宽限流，不会死锁或泄漏。
        oldest_key = next(iter(_OPENAI_COMPAT_CREDENTIAL_SEMAPHORES))
        _OPENAI_COMPAT_CREDENTIAL_SEMAPHORES.pop(oldest_key, None)
    semaphore = asyncio.Semaphore(limit)
    _OPENAI_COMPAT_CREDENTIAL_SEMAPHORES[key] = (limit, semaphore)
    return semaphore


def _retry_after_seconds(response: httpx.Response | None) -> float | None:
    if response is None:
        return None
    raw = response.headers.get("retry-after") or response.headers.get("Retry-After")
    if not raw:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return max(1.0, min(60.0, value))


def _retry_delay_seconds(attempt: int, *, response: httpx.Response | None = None) -> float:
    if response is not None and response.status_code == 429:
        retry_after = _retry_after_seconds(response)
        if retry_after is not None:
            return retry_after + random.uniform(0, 1.5)
        base = min(45.0, 1.5 * (2 ** max(0, attempt - 1)))
        return base + random.uniform(0, min(5.0, base * 0.25))
    return min(8.0, 0.8 * (2 ** max(0, attempt - 1))) + random.uniform(0, 0.8)


def _payload_after_parameter_error(payload: dict[str, Any], message: str) -> dict[str, Any] | None:
    normalized = _normalize_text(message).lower()
    next_payload = dict(payload)
    changed = False

    if "temperature" in normalized and "temperature" in next_payload:
        next_payload.pop("temperature", None)
        changed = True

    converted_max_tokens = False
    if "max_tokens" in normalized and "max_tokens" in next_payload:
        value = next_payload.pop("max_tokens", None)
        if value and (
            "max_completion_tokens" in normalized
            or "max output tokens" in normalized
            or "completion tokens" in normalized
        ):
            next_payload["max_completion_tokens"] = value
            converted_max_tokens = True
        changed = True

    if "max_completion_tokens" in normalized and "max_completion_tokens" in next_payload and not converted_max_tokens:
        next_payload.pop("max_completion_tokens", None)
        changed = True
    if "max_output_tokens" in normalized and "max_output_tokens" in next_payload:
        next_payload.pop("max_output_tokens", None)
        changed = True

    if re.search(r"(?<![a-z0-9_])stream(?![a-z0-9_])", normalized) and "stream" in next_payload:
        next_payload.pop("stream", None)
        changed = True

    return next_payload if changed and next_payload != payload else None


def _normalize_api_mode(value: Any) -> str:
    mode = _normalize_text(value).lower()
    if mode in {"responses", "response", "responses_api"}:
        return "responses"
    if mode in {"chat", "chat_completions", "chat_completion"}:
        return "chat_completions"
    return "auto"


def _is_gpt_model(model: Any) -> bool:
    return _normalize_text(model).lower().startswith("gpt-")


def _responses_input_from_messages(messages: list[dict[str, Any]]) -> str:
    items: list[str] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = _normalize_text(message.get("role")).lower() or "user"
        if role not in {"system", "developer", "user", "assistant"}:
            role = "user"
        content = _content_text(message.get("content"))
        if content:
            items.append(f"{role.upper()}:\n{content}")
    return "\n\n".join(items)


def build_responses_input_items(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """把 chat messages 转为 responses 结构化 input 项数组。

    原生工具微循环需要在其后逐跳追加 function_call / function_call_output 项
    （网关实测：全量 input 重放即可完成往返，无需 previous_response_id），
    因此不能用 _responses_input_from_messages 的拍平字符串形态。
    """
    items: list[dict[str, Any]] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = _normalize_text(message.get("role")).lower() or "user"
        if role not in {"system", "developer", "user", "assistant"}:
            role = "user"
        content = _content_text(message.get("content"))
        if content:
            items.append({"role": role, "content": content})
    return items


def build_cacheable_responses_input_items(
    messages: list[dict[str, Any]],
    *,
    stable_prefix_messages: int,
) -> list[dict[str, Any]]:
    """Build role-preserving structured Responses items for a primed prefix.

    ``system`` is mapped to the Responses-compatible ``developer`` role because
    the current gateway rejects structured system items.  User/assistant roles
    stay unchanged: project source material must not gain developer priority.
    A caller first sends ``messages[:stable_prefix_messages]`` through the same
    serializer, then sends the full list, creating a strict structured chain.
    """
    boundary = int(stable_prefix_messages or 0)
    if boundary <= 0 or boundary > len(messages):
        raise ValueError("stable_prefix_messages exceeds the message list")
    items: list[dict[str, Any]] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = _normalize_text(message.get("role")).lower() or "user"
        if role == "system":
            role = "developer"
        elif role not in {"developer", "user", "assistant"}:
            role = "user"
        content = _content_text(message.get("content"))
        if content:
            items.append(
                {
                    "type": "message",
                    "role": role,
                    "content": [{"type": "input_text", "text": content}],
                }
            )
    if not items:
        raise ValueError("prompt messages are empty")
    return items


class _PreOutputRetryError(RuntimeError):
    """首字节前的可重试失败（仅 responses_stream_events 内部使用）。"""


def _responses_unsupported(status_code: int, message: str) -> bool:
    normalized = _normalize_text(message).lower()
    if status_code in {404, 405}:
        return True
    if "responses" not in normalized and "/responses" not in normalized:
        return False
    return any(token in normalized for token in ("not found", "unsupported", "not support", "unknown", "invalid endpoint", "no route"))


class _ResponsesUnsupportedError(Exception):
    pass


class OpenAIClient:
    """OpenAI兼容API客户端"""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        timeout_seconds: float = 120,
        timeout: float | None = None,
        api_mode: str = "chat_completions",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout_seconds = float(timeout if timeout is not None else timeout_seconds)
        self.api_mode = _normalize_api_mode(api_mode)
        self.last_request_metrics: dict[str, Any] | None = None
        # 缓存路由键：多上游网关按 user/prompt_cache_key 做粘性路由，缺失时同前缀
        # 请求会被负载均衡到不同节点导致提示词缓存命中变成概率事件。None 不注入。
        self.prompt_cache_scope: str | None = None
        # reasoning 模型的思考预算：None 不注入（跟随模型默认）；"none"/"low"/"high"
        # 等值按端点语义注入（chat: reasoning_effort；responses: reasoning.effort）。
        self.reasoning_effort: str | None = None
        # responses 内置/自定义工具（如 {"type":"web_search"}）。仅注入 responses
        # payload（chat completions 的工具协议不同，由各域自有实现负责）。
        self.tools: list[dict[str, Any]] | None = None

    def _get_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _record_request_metrics(self, metrics: dict[str, Any] | None) -> None:
        """同时写入实例字段（兼容现有读法）与本次调用的独立 metrics sink。

        last_request_metrics 保持"最后一次写入可见"的原有语义；并发 fan-out 场景
        请通过 chat_with_usage_and_metrics 的返回值读取本次调用的独立指标。
        """
        self.last_request_metrics = metrics
        sink = _OPENAI_COMPAT_CALL_METRICS_SINK.get()
        if sink is not None:
            sink[0] = metrics

    @asynccontextmanager
    async def _acquire_request_slots(self):
        """请求并发闸门：先全局信号量、再凭据级信号量（固定获取顺序避免死锁）。

        凭据级限流默认关闭（AOJU_OPENAI_COMPAT_MAX_CONCURRENT_PER_CREDENTIAL=0），
        关闭时语义与仅有全局信号量的现状一致。当前生产为单实例单 worker 进程，
        进程内信号量即可满足限流语义。
        """
        queued_at = _utc_iso_now()
        queued_monotonic = time.perf_counter()
        async with _openai_compat_request_semaphore():
            global_acquired_monotonic = time.perf_counter()
            global_queue_wait_ms = int(round((global_acquired_monotonic - queued_monotonic) * 1000))
            per_credential_limit = _openai_compat_max_concurrent_per_credential()
            if per_credential_limit <= 0:
                yield {
                    "queuedAt": queued_at,
                    "acquiredAt": _utc_iso_now(),
                    "queueWaitMs": global_queue_wait_ms,
                    "globalQueueWaitMs": global_queue_wait_ms,
                    "credentialQueueWaitMs": 0,
                }
                return
            credential_semaphore = _openai_compat_credential_semaphore(
                _credential_semaphore_key(self.base_url, self.api_key),
                per_credential_limit,
            )
            credential_queued_monotonic = time.perf_counter()
            async with credential_semaphore:
                acquired_monotonic = time.perf_counter()
                credential_queue_wait_ms = int(
                    round((acquired_monotonic - credential_queued_monotonic) * 1000)
                )
                yield {
                    "queuedAt": queued_at,
                    "acquiredAt": _utc_iso_now(),
                    "queueWaitMs": int(round((acquired_monotonic - queued_monotonic) * 1000)),
                    "globalQueueWaitMs": global_queue_wait_ms,
                    "credentialQueueWaitMs": credential_queue_wait_ms,
                }

    def _build_payload(
        self,
        messages: list[dict[str, Any]],
        stream: bool = True,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
        }
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        if self.prompt_cache_scope:
            payload["user"] = self.prompt_cache_scope
            payload["prompt_cache_key"] = self.prompt_cache_scope
        if self.reasoning_effort:
            payload["reasoning_effort"] = self.reasoning_effort
        token_limit = max_tokens if max_tokens is not None else self.max_tokens
        if int(token_limit or 0) > 0:
            payload["max_tokens"] = int(token_limit)
        return payload

    def _build_responses_payload(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int | None = None,
        stable_prefix_messages: int | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "input": (
                build_cacheable_responses_input_items(
                    messages,
                    stable_prefix_messages=int(stable_prefix_messages or 0),
                )
                if stable_prefix_messages
                else _responses_input_from_messages(messages)
            ),
            "stream": False,
        }
        if self.prompt_cache_scope:
            payload["user"] = self.prompt_cache_scope
            payload["prompt_cache_key"] = self.prompt_cache_scope
        if self.reasoning_effort:
            payload["reasoning"] = {"effort": self.reasoning_effort}
        if self.tools:
            payload["tools"] = list(self.tools)
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        token_limit = max_tokens if max_tokens is not None else self.max_tokens
        if int(token_limit or 0) > 0:
            payload["max_output_tokens"] = int(token_limit)
        return payload

    def request_fingerprint(self) -> dict[str, Any]:
        """出网请求指纹(顶层设计 2026-08-12):进 metrics 供审计比对,不含密钥/原文。

        任何"两个域行为不一致"的排查先比对指纹,再看 payload。
        注意:指纹描述 client 配置;参数降级/回退后的最终 payload 差异
        以各 attempt metrics 的 apiType/statusCode 佐证(按 attempt 摘要
        属统一收敛蓝图 P1,见 AI_REQUEST_UNIFICATION_20260812)。
        """
        scope = str(self.prompt_cache_scope or "")
        return {
            "fpModel": self.model,
            "fpApiMode": self._selected_api_type(),
            "fpReasoning": self.reasoning_effort,
            "fpCacheKeyHash": hashlib.sha1(scope.encode()).hexdigest()[:10] if scope else None,
            "fpTools": sorted(
                str(tool.get("type") or "") + (":" + str(tool.get("name")) if tool.get("name") else "")
                for tool in (self.tools or [])
            ) or None,
            "fpTemperature": self.temperature is not None,
        }

    def _selected_api_type(self) -> str:
        if self.api_mode == "auto":
            return "responses" if _is_gpt_model(self.model) else "chat_completions"
        return self.api_mode

    def supports_structured_prompt_cache(self) -> bool:
        """Whether a prime/full pair can use structured message boundaries."""
        return self._selected_api_type() == "responses"

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        max_tokens: int | None = None,
        request_max_attempts: int | None = None,
        stable_prefix_messages: int | None = None,
    ) -> str:
        text, _ = await self.chat_with_usage(
            messages,
            stream=False,
            max_tokens=max_tokens,
            request_max_attempts=request_max_attempts,
            stable_prefix_messages=stable_prefix_messages,
        )
        return text

    async def chat_with_usage(
        self,
        messages: list[dict[str, Any]],
        *,
        stream: bool = False,
        max_tokens: int | None = None,
        request_max_attempts: int | None = None,
        stable_prefix_messages: int | None = None,
    ) -> tuple[str, dict[str, int]]:
        if stream:
            # 聚合式流式：SSE 按事件解析、截断校验、断流整次重试、usage 完整返回。
            # 旧 _stream_chat 生成器仅保留给对话式增量 UI 场景。
            if self._selected_api_type() == "responses":
                try:
                    text, meta = await self.responses_stream_collect(
                        messages,
                        max_tokens=max_tokens,
                        request_max_attempts=request_max_attempts,
                        **(
                            {"stable_prefix_messages": stable_prefix_messages}
                            if stable_prefix_messages
                            else {}
                        ),
                    )
                    return text, dict(meta.get("usage") or {})
                except httpx.HTTPStatusError as exc:
                    if self.api_mode != "auto" or not _responses_unsupported(
                        int(exc.response.status_code), str(exc)
                    ):
                        raise
            text, meta = await self.chat_stream_collect(
                messages,
                max_tokens=max_tokens,
                request_max_attempts=request_max_attempts,
            )
            return text, dict(meta.get("usage") or {})

        api_type = self._selected_api_type()
        if api_type == "responses":
            # 实测多网关的 responses 转发只支持 SSE 输出（非流式请求 400/500 或
            # 返回 SSE 文本导致解析失败）。responses 模式下非流式调用统一改走
            # 流式聚合，对调用方保持"一次性完整返回"的语义。
            text, meta = await self.responses_stream_collect(
                messages,
                max_tokens=max_tokens,
                request_max_attempts=request_max_attempts,
                **(
                    {"stable_prefix_messages": stable_prefix_messages}
                    if stable_prefix_messages
                    else {}
                ),
            )
            return text, dict(meta.get("usage") or {})

        payload = self._build_payload(messages, stream=False, max_tokens=max_tokens)
        kwargs = {
            "api_type": api_type,
            "allow_responses_fallback": False,
        }
        if request_max_attempts is not None:
            kwargs["max_attempts"] = request_max_attempts
        return await self._sync_chat_with_usage(
            _chat_endpoint(self.base_url),
            payload,
            **kwargs,
        )

    async def chat_with_usage_and_metrics(
        self,
        messages: list[dict[str, Any]],
        *,
        stream: bool = False,
        max_tokens: int | None = None,
        request_max_attempts: int | None = None,
        stable_prefix_messages: int | None = None,
    ) -> tuple[str, dict[str, int], dict[str, Any] | None]:
        """chat_with_usage 的并发安全变体：额外返回本次调用独立的请求指标副本。

        实例字段 last_request_metrics 行为不变（并发时最后写入者可见）；
        并行 fan-out 请以本方法返回的第三个元素作为本次调用的指标口径。
        """
        sink: list[dict[str, Any] | None] = [None]
        token = _OPENAI_COMPAT_CALL_METRICS_SINK.set(sink)
        try:
            text, usage = await self.chat_with_usage(
                messages,
                stream=stream,
                max_tokens=max_tokens,
                request_max_attempts=request_max_attempts,
                stable_prefix_messages=stable_prefix_messages,
            )
        finally:
            _OPENAI_COMPAT_CALL_METRICS_SINK.reset(token)
        metrics = sink[0]
        return text, usage, dict(metrics) if isinstance(metrics, dict) else None

    async def prime_prompt_cache(
        self,
        messages: list[dict[str, Any]],
        *,
        stream: bool = True,
        max_tokens: int = 16,
        request_max_attempts: int = 1,
    ) -> tuple[dict[str, int], dict[str, Any] | None]:
        """用公共模型入口写入一个可复用的严格提示词前缀。

        GPT-5.6 的默认隐式缓存断点位于最新 user/tool message 末尾。调用方先传
        只到稳定消息边界的 messages，再让真实请求在其后追加动态消息，即可形成
        与多轮助手相同的严格增量链。调用方必须在该稳定消息里约束“无后续任务时
        只返回极短确认”，否则 prime 仍可能产生昂贵输出。

        本方法只编排既有 chat_with_usage 公共入口，不自行拼 HTTP payload；因此
        Responses/Chat Completions、reasoning、scope、重试和指标语义保持完全一致。
        """
        if not messages:
            raise ValueError("prompt cache prime requires at least one message")
        _text, usage, metrics = await self.chat_with_usage_and_metrics(
            messages,
            stream=stream,
            max_tokens=max(1, int(max_tokens or 16)),
            request_max_attempts=max(1, int(request_max_attempts or 1)),
            **(
                {"stable_prefix_messages": len(messages)}
                if self.supports_structured_prompt_cache()
                else {}
            ),
        )
        return usage, metrics

    async def _sync_chat_with_usage(
        self,
        url: str,
        payload: dict[str, Any],
        *,
        api_type: str = "chat_completions",
        allow_responses_fallback: bool = False,
        max_attempts: int | None = None,
    ) -> tuple[str, dict[str, int]]:
        current_payload = dict(payload)
        last_content_error: Exception | None = None
        attempts_limit = OPENAI_COMPAT_REQUEST_MAX_ATTEMPTS
        if max_attempts is not None:
            attempts_limit = max(1, min(OPENAI_COMPAT_REQUEST_MAX_ATTEMPTS, int(max_attempts)))
        self._record_request_metrics(None)
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            for attempt in range(1, attempts_limit + 1):
                started_at = _utc_iso_now()
                started_monotonic = time.perf_counter()
                current_metrics: dict[str, Any] = {
                    **self.request_fingerprint(),
                    "attempt": attempt,
                    "startedAt": started_at,
                    "endedAt": None,
                    "elapsedMs": None,
                    "statusCode": None,
                    "stream": bool(current_payload.get("stream")),
                    "apiType": api_type,
                    "requestMaxTokens": int(current_payload.get("max_tokens") or current_payload.get("max_completion_tokens") or current_payload.get("max_output_tokens") or 0),
                    "usage": _normalize_usage(None),
                    "responseBytes": 0,
                    "responseChars": 0,
                }
                self._record_request_metrics(current_metrics)
                async with self._acquire_request_slots() as slot_metrics:
                    current_metrics.update(slot_metrics)
                    current_metrics["httpStartedAt"] = _utc_iso_now()
                    self._record_request_metrics(current_metrics)
                    http_started_monotonic = time.perf_counter()
                    response = await client.post(
                        url,
                        headers=self._get_headers(),
                        json=current_payload,
                    )
                    current_metrics["responseReceivedAt"] = _utc_iso_now()
                    current_metrics["httpElapsedMs"] = int(
                        round((time.perf_counter() - http_started_monotonic) * 1000)
                    )
                elapsed_ms = int(round((time.perf_counter() - started_monotonic) * 1000))
                ended_at = _utc_iso_now()
                response_payload = _safe_response_json(response)
                usage = _normalize_usage(response_payload.get("usage"))
                current_metrics = {
                    **current_metrics,
                    "endedAt": ended_at,
                    "elapsedMs": elapsed_ms,
                    "statusCode": int(response.status_code),
                    "stream": bool(current_payload.get("stream")),
                    "apiType": api_type,
                    "requestMaxTokens": int(current_payload.get("max_tokens") or current_payload.get("max_completion_tokens") or current_payload.get("max_output_tokens") or 0),
                    "usage": usage,
                    "responseBytes": len(response.content or b""),
                }
                self._record_request_metrics(current_metrics)
                if response.status_code >= 400:
                    message = _response_error_message(response, response_payload)
                    adjusted_payload = _payload_after_parameter_error(current_payload, message)
                    current_metrics["errorMessage"] = message[:300]
                    self._record_request_metrics(current_metrics)
                    if adjusted_payload is not None and attempt < attempts_limit:
                        current_payload = adjusted_payload
                        await asyncio.sleep(0)
                        continue
                    if (
                        api_type == "responses"
                        and allow_responses_fallback
                        and response.status_code not in {401, 403}
                        and (400 <= response.status_code < 500 or _responses_unsupported(response.status_code, message))
                    ):
                        raise _ResponsesUnsupportedError(message)
                    if _is_retryable_status(response.status_code) and attempt < attempts_limit:
                        await asyncio.sleep(_retry_delay_seconds(attempt, response=response))
                        continue
                    response.raise_for_status()

                try:
                    content = _extract_responses_content(response_payload) if api_type == "responses" else _extract_chat_content(response_payload)
                    # 就地更新本次调用的 metrics 字典；实例字段与 sink 持有同一对象。
                    current_metrics["responseChars"] = len(content)
                    # 计量层：成功返回即上报本次调用用量（无收集器时静默）
                    record_llm_usage(model=self.model, usage=usage, api_type=api_type, source="openai_client")
                    return content, usage
                except ValueError as exc:
                    last_content_error = exc
                    if attempt >= attempts_limit:
                        raise
                    await asyncio.sleep(_retry_delay_seconds(attempt))

        if last_content_error is not None:
            raise last_content_error
        raise ValueError("AI模型未返回可用内容")

    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        *,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[str, None]:
        # 流式路径同样落指纹 metrics(codex:UI 主链路不可豁免审计)
        self._record_request_metrics(
            {**self.request_fingerprint(), "stream": True, "startedAt": _utc_iso_now()}
        )
        # responses 模式（或声明了 responses 内置工具，如 web_search）走 responses
        # SSE 逐增量流；否则保持 chat completions 流。调用方无感。
        # 部分模型×网关组合的 responses 端点不可用（如 deepseek-v4-pro 明示改用
        # flash）——首字节前失败则自动回退 chat 流式（web_search 随之失效但对话可用）。
        if self._selected_api_type() == "responses" or self.tools:
            responses_failed_before_output = False
            try:
                got_output = False
                async for chunk in self.responses_chat_stream(messages, max_tokens=max_tokens):
                    got_output = True
                    yield chunk
                if got_output:
                    return
                responses_failed_before_output = True
            except httpx.HTTPStatusError:
                responses_failed_before_output = True
            if not responses_failed_before_output:
                return
        url = _chat_endpoint(self.base_url)
        payload = self._build_payload(messages, stream=True, max_tokens=max_tokens)
        async for chunk in self._stream_chat(url, payload):
            yield chunk

    async def responses_chat_stream(
        self,
        messages: list[dict[str, Any]],
        *,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[str, None]:
        """responses 端点的逐增量流（打字机用）：yield output_text.delta。

        内置工具（web_search 等）由模型按意图自主调用——不注入任何提示词；
        搜索期间没有文本增量属正常（搜索完成后模型继续输出）。
        """
        _ = max_tokens  # responses 端点不下发输出上限（多网关拒绝该参数）
        url = _responses_endpoint(self.base_url)
        payload: dict[str, Any] = {
            "model": self.model,
            "input": _responses_input_from_messages(messages),
            "stream": True,
        }
        if self.prompt_cache_scope:
            payload["user"] = self.prompt_cache_scope
            payload["prompt_cache_key"] = self.prompt_cache_scope
        if self.reasoning_effort:
            payload["reasoning"] = {"effort": self.reasoning_effort}
        if self.tools:
            payload["tools"] = list(self.tools)
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client, self._acquire_request_slots():
            async with client.stream(
                "POST",
                url,
                headers=self._get_headers(),
                json=payload,
            ) as response:
                if response.status_code >= 400:
                    await response.aread()
                    response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(data, dict):
                        continue
                    if data.get("type") == "response.output_text.delta":
                        delta = data.get("delta")
                        if isinstance(delta, str) and delta:
                            yield delta
                    elif data.get("type") == "response.completed":
                        # response.completed is the terminal Responses event. Some
                        # compatible gateways keep the HTTP connection alive after it;
                        # do not turn that transport keepalive into application latency.
                        return

    async def responses_stream_events(
        self,
        input_items: list[dict[str, Any]],
        *,
        extra_tools: list[dict[str, Any]] | None = None,
        request_max_attempts: int | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """responses 端点 typed 事件流（原生工具微循环用）。

        与 responses_chat_stream 的差异：
        - input 为结构化项数组（role 消息 + function_call/function_call_output），
          由调用方经 build_responses_input_items 构造并逐跳追加工具往返项；
        - 解析 function_call 项并在 arguments 齐备时产出 function_call 事件；
        - 纯工具调用轮没有正文属正常，不触发空流错误；
        - 不做 responses→chat 静默降级：失败直接抛出，由微循环层决定回退。
        事件契约：
          {"type": "text_delta", "delta": str}
          {"type": "function_call", "callId": str, "name": str, "arguments": str}
          {"type": "web_search", "status": "searching"|"completed"}
          {"type": "completed", "status": str, "usage": dict,
           "webSearchCalls": int, "functionCallCount": int, "hasText": bool}
        重试语义：首字节前的可重试失败按既有退避重试；首字节后失败直接抛出
        （工具可能已执行，重放由上层以 callId 去重决策）。
        """
        url = _responses_endpoint(self.base_url)
        self._record_request_metrics(
            {**self.request_fingerprint(), "stream": True, "apiType": "responses", "startedAt": _utc_iso_now()}
        )
        payload: dict[str, Any] = {
            "model": self.model,
            "input": list(input_items),
            "stream": True,
        }
        if self.prompt_cache_scope:
            payload["user"] = self.prompt_cache_scope
            payload["prompt_cache_key"] = self.prompt_cache_scope
        if self.reasoning_effort:
            payload["reasoning"] = {"effort": self.reasoning_effort}
        merged_tools = [*(self.tools or []), *(extra_tools or [])]
        if merged_tools:
            payload["tools"] = merged_tools
        attempts_limit = OPENAI_COMPAT_REQUEST_MAX_ATTEMPTS
        if request_max_attempts is not None:
            attempts_limit = max(1, min(OPENAI_COMPAT_REQUEST_MAX_ATTEMPTS, int(request_max_attempts)))
        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            for attempt in range(1, attempts_limit + 1):
                text_emitted = False
                downstream_emitted = False
                completed_status = ""
                usage = _normalize_usage(None)
                web_search_calls = 0
                calls_by_item: dict[str, dict[str, Any]] = {}
                emitted_call_count = 0

                def _call_entry(item_id: str) -> dict[str, Any] | None:
                    entry = calls_by_item.get(item_id)
                    if entry is None and len(calls_by_item) == 1:
                        entry = next(iter(calls_by_item.values()))
                    return entry

                try:
                    async with self._acquire_request_slots(), client.stream(
                        "POST",
                        url,
                        headers=self._get_headers(),
                        json=payload,
                    ) as response:
                        if response.status_code >= 400:
                            await response.aread()
                            if _is_retryable_status(response.status_code) and attempt < attempts_limit:
                                raise _PreOutputRetryError(f"HTTP {response.status_code}")
                            response.raise_for_status()
                        async for line in response.aiter_lines():
                            if not line.startswith("data:"):
                                continue
                            try:
                                data = json.loads(line[5:].strip())
                            except json.JSONDecodeError as exc:
                                raise _TruncatedStreamError("responses 流式 data JSON 解析失败") from exc
                            if not isinstance(data, dict):
                                continue
                            event_type = str(data.get("type") or "")
                            if event_type == "response.output_text.delta":
                                delta = data.get("delta")
                                if isinstance(delta, str) and delta:
                                    text_emitted = True
                                    downstream_emitted = True
                                    yield {"type": "text_delta", "delta": delta}
                            elif event_type == "response.output_item.added":
                                item = data.get("item") if isinstance(data.get("item"), dict) else {}
                                if item.get("type") == "function_call":
                                    key = str(item.get("id") or item.get("call_id") or len(calls_by_item))
                                    calls_by_item[key] = {
                                        "callId": str(item.get("call_id") or ""),
                                        "name": str(item.get("name") or ""),
                                        "arguments": str(item.get("arguments") or ""),
                                        "emitted": False,
                                    }
                            elif event_type == "response.function_call_arguments.delta":
                                entry = _call_entry(str(data.get("item_id") or ""))
                                delta = data.get("delta")
                                if entry is not None and isinstance(delta, str):
                                    entry["arguments"] += delta
                            elif event_type == "response.function_call_arguments.done":
                                entry = _call_entry(str(data.get("item_id") or ""))
                                if entry is not None:
                                    final_args = data.get("arguments")
                                    if isinstance(final_args, str) and final_args:
                                        entry["arguments"] = final_args
                                    if not entry["emitted"]:
                                        entry["emitted"] = True
                                        emitted_call_count += 1
                                        downstream_emitted = True
                                        yield {
                                            "type": "function_call",
                                            "callId": entry["callId"],
                                            "name": entry["name"],
                                            "arguments": entry["arguments"],
                                        }
                            elif event_type == "response.output_item.done":
                                # 兜底：个别网关不发 arguments.done，完整项在此补发
                                item = data.get("item") if isinstance(data.get("item"), dict) else {}
                                if item.get("type") == "function_call":
                                    key = str(item.get("id") or item.get("call_id") or "")
                                    entry = calls_by_item.get(key)
                                    if entry is None:
                                        entry = {
                                            "callId": str(item.get("call_id") or ""),
                                            "name": str(item.get("name") or ""),
                                            "arguments": str(item.get("arguments") or ""),
                                            "emitted": False,
                                        }
                                        calls_by_item[key or str(len(calls_by_item))] = entry
                                    elif isinstance(item.get("arguments"), str) and item.get("arguments"):
                                        entry["arguments"] = item["arguments"]
                                    if not entry["emitted"]:
                                        entry["emitted"] = True
                                        emitted_call_count += 1
                                        downstream_emitted = True
                                        yield {
                                            "type": "function_call",
                                            "callId": entry["callId"],
                                            "name": entry["name"],
                                            "arguments": entry["arguments"],
                                        }
                                elif item.get("type") == "web_search_call":
                                    # deepseek 系 responses 不产 url_citation 注解,
                                    # 但 open_page 动作携带真实浏览 URL——按引用下发
                                    action = item.get("action") if isinstance(item.get("action"), dict) else {}
                                    if str(action.get("type") or "") == "open_page":
                                        page_url = str(action.get("url") or "").split("#ws_call_id=")[0].strip()
                                        if page_url:
                                            downstream_emitted = True
                                            yield {
                                                "type": "web_search_citation",
                                                "url": page_url,
                                                "title": "",
                                            }
                                elif item.get("type") == "message":
                                    # 兜底:部分网关不发 annotation.added 独立事件,
                                    # url_citation 注解只随消息项完整体返回
                                    for part in item.get("content") or []:
                                        if not isinstance(part, dict):
                                            continue
                                        for annotation in part.get("annotations") or []:
                                            if (
                                                isinstance(annotation, dict)
                                                and str(annotation.get("type") or "") == "url_citation"
                                                and str(annotation.get("url") or "").strip()
                                            ):
                                                downstream_emitted = True
                                                yield {
                                                    "type": "web_search_citation",
                                                    "url": str(annotation.get("url") or ""),
                                                    "title": str(annotation.get("title") or ""),
                                                }
                            elif event_type in {
                                "response.web_search_call.in_progress",
                                "response.web_search_call.searching",
                            }:
                                downstream_emitted = True
                                yield {"type": "web_search", "status": "searching"}
                            elif event_type == "response.web_search_call.completed":
                                web_search_calls += 1
                                downstream_emitted = True
                                yield {"type": "web_search", "status": "completed"}
                            elif event_type == "response.output_text.annotation.added":
                                # url_citation 注解:联网搜索引用(供深研类调用方收集参考资料;
                                # 不消费该事件的调用方可安全忽略)
                                annotation = (
                                    data.get("annotation") if isinstance(data.get("annotation"), dict) else {}
                                )
                                if str(annotation.get("type") or "") == "url_citation":
                                    downstream_emitted = True
                                    yield {
                                        "type": "web_search_citation",
                                        "url": str(annotation.get("url") or ""),
                                        "title": str(annotation.get("title") or ""),
                                    }
                            elif event_type == "response.completed":
                                response_obj = (
                                    data.get("response") if isinstance(data.get("response"), dict) else {}
                                )
                                completed_status = str(response_obj.get("status") or "completed")
                                if isinstance(response_obj.get("usage"), dict):
                                    usage = _normalize_usage(response_obj.get("usage"))
                                break
                            elif event_type in {"response.failed", "response.incomplete", "error"}:
                                raise _StreamFinishError(
                                    f"responses 流式异常结束（{event_type}）：{_truncate_error_text(data)}"
                                )
                    if not completed_status:
                        raise _TruncatedStreamError("responses 流未收到 response.completed，视为截断")
                    if not text_emitted and emitted_call_count == 0:
                        raise _EmptyStreamError("responses 流式响应未返回内容")
                    record_llm_usage(
                        model=self.model,
                        usage=usage,
                        api_type="responses",
                        source="openai_client",
                        web_search_calls=web_search_calls,
                    )
                    yield {
                        "type": "completed",
                        "status": completed_status,
                        "usage": usage,
                        "webSearchCalls": web_search_calls,
                        "functionCallCount": emitted_call_count,
                        "hasText": text_emitted,
                    }
                    return
                except _PreOutputRetryError as exc:
                    last_error = exc
                    await asyncio.sleep(_retry_delay_seconds(attempt))
                    continue
                except (_TruncatedStreamError, _EmptyStreamError, _StreamFinishError) as exc:
                    # 未向下游产出任何事件时,截断/空流/异常收尾与失败请求等价,可安全重试
                    if not downstream_emitted and attempt < attempts_limit:
                        last_error = exc
                        await asyncio.sleep(_retry_delay_seconds(attempt))
                        continue
                    raise
                except (httpx.TimeoutException, httpx.RequestError) as exc:
                    if not downstream_emitted and attempt < attempts_limit:
                        last_error = exc
                        await asyncio.sleep(_retry_delay_seconds(attempt))
                        continue
                    raise
        raise last_error if last_error else RuntimeError("responses_stream_events exhausted attempts")

    async def responses_stream_collect(
        self,
        messages: list[dict[str, Any]],
        *,
        max_tokens: int | None = None,
        request_max_attempts: int | None = None,
        stable_prefix_messages: int | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """/v1/responses 的流式聚合：(text, meta)。

        实测本网关的 responses 转发只支持 SSE 事件流输出，且请求携带
        temperature / max_output_tokens 会被上游拒绝（400）——这是历史上
        responses 路径必败的根因，因此 payload 只带 model/input/stream。
        正文取 response.output_text.delta 的 delta（不 strip），完成以
        response.completed 为准（usage 也在该事件），未见 completed 视为
        截断整次重做。max_tokens 参数保留签名兼容，但不下发。
        """
        _ = max_tokens
        url = _responses_endpoint(self.base_url)
        payload: dict[str, Any] = {
            "model": self.model,
            "input": (
                build_cacheable_responses_input_items(
                    messages,
                    stable_prefix_messages=int(stable_prefix_messages or 0),
                )
                if stable_prefix_messages
                else _responses_input_from_messages(messages)
            ),
            "stream": True,
        }
        if self.prompt_cache_scope:
            payload["user"] = self.prompt_cache_scope
            payload["prompt_cache_key"] = self.prompt_cache_scope
        if self.reasoning_effort:
            payload["reasoning"] = {"effort": self.reasoning_effort}
        if self.tools:
            payload["tools"] = list(self.tools)
        attempts_limit = OPENAI_COMPAT_REQUEST_MAX_ATTEMPTS
        if request_max_attempts is not None:
            attempts_limit = max(1, min(OPENAI_COMPAT_REQUEST_MAX_ATTEMPTS, int(request_max_attempts)))
        last_error: Exception | None = None
        attempt_history: list[dict[str, Any]] = []
        self._record_request_metrics(None)
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            for attempt in range(1, attempts_limit + 1):
                started_at = _utc_iso_now()
                started_monotonic = time.perf_counter()
                parts: list[str] = []
                usage = _normalize_usage(None)
                completed_status = ""
                response_bytes = 0
                status_code_seen = 0
                first_byte_seen = False
                web_search_calls = 0
                current_metrics: dict[str, Any] = {
                    **self.request_fingerprint(),
                    "attempt": attempt,
                    "startedAt": started_at,
                    "endedAt": None,
                    "elapsedMs": None,
                    "statusCode": None,
                    "stream": True,
                    "apiType": "responses",
                    "requestMaxTokens": 0,
                    "usage": usage,
                    "responseBytes": 0,
                    "responseChars": 0,
                    "previousAttempts": list(attempt_history),
                }
                self._record_request_metrics(current_metrics)
                try:
                    async with self._acquire_request_slots() as slot_metrics:
                        current_metrics.update(slot_metrics)
                        current_metrics["httpStartedAt"] = _utc_iso_now()
                        self._record_request_metrics(current_metrics)
                        http_started_monotonic = time.perf_counter()
                        async with client.stream(
                            "POST",
                            url,
                            headers=self._get_headers(),
                            json=payload,
                        ) as response:
                            status_code_seen = int(response.status_code)
                            current_metrics.update(
                                {
                                    "responseHeadersAt": _utc_iso_now(),
                                    "httpToHeadersMs": int(
                                        round((time.perf_counter() - http_started_monotonic) * 1000)
                                    ),
                                    "statusCode": status_code_seen,
                                }
                            )
                            self._record_request_metrics(current_metrics)
                            if response.status_code >= 400:
                                body = await response.aread()
                                current_metrics = {
                                    **current_metrics,
                                    "endedAt": _utc_iso_now(),
                                    "elapsedMs": int(round((time.perf_counter() - started_monotonic) * 1000)),
                                    "statusCode": status_code_seen,
                                    "responseBytes": len(body or b""),
                                }
                                self._record_request_metrics(current_metrics)
                                if _is_retryable_status(response.status_code) and attempt < attempts_limit:
                                    attempt_history.append(dict(current_metrics))
                                    await asyncio.sleep(_retry_delay_seconds(attempt, response=response))
                                    continue
                                response.raise_for_status()
                            async for line in response.aiter_lines():
                                if not first_byte_seen:
                                    first_byte_seen = True
                                    current_metrics.update(
                                        {
                                            "firstByteAt": _utc_iso_now(),
                                            "timeToFirstByteMs": int(
                                                round((time.perf_counter() - http_started_monotonic) * 1000)
                                            ),
                                        }
                                    )
                                    self._record_request_metrics(current_metrics)
                                if not line:
                                    continue
                                response_bytes += len(line.encode("utf-8", errors="ignore"))
                                if not line.startswith("data:"):
                                    continue
                                data_str = line[5:].strip()
                                try:
                                    data = json.loads(data_str)
                                except json.JSONDecodeError as exc:
                                    raise _TruncatedStreamError("responses 流式 data JSON 解析失败") from exc
                                if not isinstance(data, dict):
                                    continue
                                event_type = str(data.get("type") or "")
                                if event_type == "response.output_text.delta":
                                    delta = data.get("delta")
                                    if isinstance(delta, str):
                                        parts.append(delta)
                                elif event_type == "response.web_search_call.completed":
                                    web_search_calls += 1
                                elif event_type == "response.completed":
                                    response_obj = data.get("response") if isinstance(data.get("response"), dict) else {}
                                    completed_status = str(response_obj.get("status") or "completed")
                                    if isinstance(response_obj.get("usage"), dict):
                                        usage = _normalize_usage(response_obj.get("usage"))
                                    break
                                elif event_type in {"response.failed", "response.incomplete", "error"}:
                                    raise _StreamFinishError(
                                        f"responses 流式异常结束（{event_type}）：{_truncate_error_text(data)}"
                                    )
                    text = "".join(parts)
                    current_metrics = {
                        **current_metrics,
                        "endedAt": _utc_iso_now(),
                        "elapsedMs": int(round((time.perf_counter() - started_monotonic) * 1000)),
                        "statusCode": status_code_seen or 200,
                        "usage": usage,
                        "responseBytes": response_bytes,
                        "responseChars": len(text),
                        "finishReason": completed_status,
                    }
                    self._record_request_metrics(current_metrics)
                    if not completed_status:
                        raise _TruncatedStreamError("responses 流未收到 response.completed，视为截断")
                    if not text.strip():
                        raise _EmptyStreamError("responses 流式响应未返回内容")
                    record_llm_usage(
                        model=self.model,
                        usage=usage,
                        api_type="responses",
                        source="openai_client",
                        web_search_calls=web_search_calls,
                    )
                    return text, {
                        "usage": usage,
                        "finishReason": completed_status,
                        "statusCode": status_code_seen or 200,
                        "elapsedMs": current_metrics["elapsedMs"],
                        "attempt": attempt,
                        "webSearchCalls": web_search_calls,
                    }
                except asyncio.CancelledError:
                    self._record_request_metrics({
                        **current_metrics,
                        "endedAt": _utc_iso_now(),
                        "elapsedMs": int(round((time.perf_counter() - started_monotonic) * 1000)),
                        "responseBytes": response_bytes,
                        "errorType": "CancelledError",
                    })
                    raise
                except (httpx.TimeoutException, httpx.RequestError, _TruncatedStreamError, _EmptyStreamError) as exc:
                    last_error = exc
                    self._record_request_metrics({
                        **current_metrics,
                        "endedAt": _utc_iso_now(),
                        "elapsedMs": int(round((time.perf_counter() - started_monotonic) * 1000)),
                        "responseBytes": response_bytes,
                        "errorType": exc.__class__.__name__,
                    })
                    if attempt < attempts_limit:
                        attempt_history.append(dict(self.last_request_metrics or current_metrics))
                        await asyncio.sleep(_retry_delay_seconds(attempt))
                        continue
                    raise
        raise last_error if last_error else RuntimeError("responses_stream_collect exhausted attempts")

    async def chat_stream_collect(
        self,
        messages: list[dict[str, Any]],
        *,
        max_tokens: int | None = None,
        request_max_attempts: int | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """流式请求但聚合为一次性完整返回：(text, meta)。

        网关（CDN 层）对非流式长响应存在无数据超时断开（524）；SSE 增量持续有字节
        流动可绕开该窗口。与 _stream_chat 生成器不同，本方法在单次 attempt 内部
        聚合全部增量，中途断流时丢弃本次 attempt 的内容并整次重做，不存在增量重复问题。
        最终完整性由调用方 JSON 校验兜底。
        meta 含 usage / finishReason / statusCode / elapsedMs / attempt。
        """
        url = _chat_endpoint(self.base_url)
        payload = self._build_payload(messages, stream=True, max_tokens=max_tokens)
        attempts_limit = OPENAI_COMPAT_REQUEST_MAX_ATTEMPTS
        if request_max_attempts is not None:
            attempts_limit = max(1, min(OPENAI_COMPAT_REQUEST_MAX_ATTEMPTS, int(request_max_attempts)))
        last_error: Exception | None = None
        attempt_history: list[dict[str, Any]] = []
        self._record_request_metrics(None)
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            for attempt in range(1, attempts_limit + 1):
                started_at = _utc_iso_now()
                started_monotonic = time.perf_counter()
                parts: list[str] = []
                usage = _normalize_usage(None)
                finish_reason = ""
                response_bytes = 0
                response_status_code: int | None = None
                saw_done = False
                reasoning_chars = 0
                first_byte_seen = False
                current_metrics: dict[str, Any] = {
                    **self.request_fingerprint(),
                    "attempt": attempt,
                    "startedAt": started_at,
                    "endedAt": None,
                    "elapsedMs": None,
                    "statusCode": None,
                    "stream": True,
                    "apiType": "chat_completions",
                    "requestMaxTokens": int(payload.get("max_tokens") or payload.get("max_completion_tokens") or 0),
                    "usage": usage,
                    "responseBytes": 0,
                    "responseChars": 0,
                    "reasoningChars": 0,
                    "sawDone": False,
                    "finishReason": "",
                    "previousAttempts": list(attempt_history),
                }
                self._record_request_metrics(current_metrics)

                def process_sse_event(data_lines: list[str]) -> None:
                    nonlocal usage, finish_reason, saw_done, reasoning_chars

                    if not data_lines:
                        return

                    data_str = "\n".join(data_lines)
                    if data_str == "[DONE]":
                        saw_done = True
                        return

                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError as exc:
                        raise _TruncatedStreamError("流式响应 SSE data JSON 解析失败") from exc

                    if not isinstance(data, dict):
                        return

                    # usage 常出现在 choices 为空数组的收尾块，必须先于 choices 取用。
                    if isinstance(data.get("usage"), dict):
                        usage = _normalize_usage(data.get("usage"))

                    choices = data.get("choices")
                    if not isinstance(choices, list):
                        return

                    for choice in choices:
                        if not isinstance(choice, dict):
                            continue
                        if int(choice.get("index", 0) or 0) != 0:
                            continue

                        if choice.get("finish_reason"):
                            finish_reason = str(choice.get("finish_reason") or "")

                        delta = choice.get("delta") if isinstance(choice.get("delta"), dict) else {}
                        reasoning_content = delta.get("reasoning_content")
                        if reasoning_content is not None:
                            reasoning_chars += len(_content_text(reasoning_content))

                        # 兼容多上游 chunk 形态：delta.content / choices[].text / message.content
                        message_obj = choice.get("message") if isinstance(choice.get("message"), dict) else {}
                        if "content" in delta:
                            content_value = delta.get("content")
                        elif "text" in choice:
                            content_value = choice.get("text")
                        else:
                            content_value = message_obj.get("content", "")

                        content = _incremental_content_text(content_value)
                        if content:
                            parts.append(content)

                try:
                    async with self._acquire_request_slots() as slot_metrics:
                        current_metrics.update(slot_metrics)
                        current_metrics["httpStartedAt"] = _utc_iso_now()
                        self._record_request_metrics(current_metrics)
                        http_started_monotonic = time.perf_counter()
                        async with client.stream(
                            "POST",
                            url,
                            headers=self._get_headers(),
                            json=payload,
                        ) as response:
                            response_status_code = int(response.status_code)
                            current_metrics.update(
                                {
                                    "responseHeadersAt": _utc_iso_now(),
                                    "httpToHeadersMs": int(
                                        round((time.perf_counter() - http_started_monotonic) * 1000)
                                    ),
                                    "statusCode": response_status_code,
                                }
                            )
                            self._record_request_metrics(current_metrics)
                            if response.status_code >= 400:
                                body = await response.aread()
                                current_metrics = {
                                    **current_metrics,
                                    "endedAt": _utc_iso_now(),
                                    "elapsedMs": int(round((time.perf_counter() - started_monotonic) * 1000)),
                                    "statusCode": response_status_code,
                                    "responseBytes": len(body or b""),
                                    "errorType": "HTTPStatusError",
                                    "sawDone": saw_done,
                                    "finishReason": finish_reason,
                                }
                                self._record_request_metrics(current_metrics)
                                if _is_retryable_status(response.status_code) and attempt < attempts_limit:
                                    attempt_history.append(dict(current_metrics))
                                    await asyncio.sleep(_retry_delay_seconds(attempt, response=response))
                                    continue
                                response.raise_for_status()

                            event_data_lines: list[str] = []
                            async for line in response.aiter_lines():
                                if not first_byte_seen:
                                    first_byte_seen = True
                                    current_metrics.update(
                                        {
                                            "firstByteAt": _utc_iso_now(),
                                            "timeToFirstByteMs": int(
                                                round((time.perf_counter() - http_started_monotonic) * 1000)
                                            ),
                                        }
                                    )
                                    self._record_request_metrics(current_metrics)
                                response_bytes += len(line.encode("utf-8", errors="ignore"))
                                if line == "":
                                    process_sse_event(event_data_lines)
                                    event_data_lines = []
                                    if saw_done:
                                        break
                                    continue
                                if line.startswith(":"):
                                    continue
                                if not line.startswith("data:"):
                                    continue

                                data_line = line[5:]
                                if data_line.startswith(" "):
                                    data_line = data_line[1:]
                                event_data_lines.append(data_line)

                    if not saw_done and not finish_reason:
                        raise _TruncatedStreamError("流式响应自然结束但缺少 [DONE] 与 finish_reason")

                    if finish_reason and finish_reason != "stop":
                        text_chars = len("".join(parts))
                        raise _StreamFinishError(
                            f"流式响应非正常结束（finish_reason={finish_reason}, chars={text_chars}）"
                        )

                    text = "".join(parts)
                    current_metrics = {
                        **current_metrics,
                        "endedAt": _utc_iso_now(),
                        "elapsedMs": int(round((time.perf_counter() - started_monotonic) * 1000)),
                        "statusCode": response_status_code,
                        "usage": usage,
                        "responseBytes": response_bytes,
                        "responseChars": len(text),
                        "reasoningChars": reasoning_chars,
                        "finishReason": finish_reason,
                        "sawDone": saw_done,
                    }
                    self._record_request_metrics(current_metrics)
                    if not text.strip():
                        raise _EmptyStreamError(
                            f"流式响应未返回内容（finish_reason={finish_reason or 'unknown'}, "
                            f"reasoning_chars={reasoning_chars}）"
                        )
                    record_llm_usage(model=self.model, usage=usage, api_type="chat_completions", source="openai_client")
                    return text, {
                        "usage": usage,
                        "finishReason": finish_reason,
                        "statusCode": response_status_code,
                        "elapsedMs": current_metrics["elapsedMs"],
                        "attempt": attempt,
                        "sawDone": saw_done,
                        "reasoningChars": reasoning_chars,
                    }
                except asyncio.CancelledError:
                    current_metrics = {
                        **current_metrics,
                        "endedAt": _utc_iso_now(),
                        "elapsedMs": int(round((time.perf_counter() - started_monotonic) * 1000)),
                        "statusCode": response_status_code,
                        "usage": usage,
                        "responseBytes": response_bytes,
                        "responseChars": len("".join(parts)),
                        "reasoningChars": reasoning_chars,
                        "finishReason": finish_reason,
                        "sawDone": saw_done,
                        "errorType": "CancelledError",
                    }
                    self._record_request_metrics(current_metrics)
                    raise
                except _StreamFinishError as exc:
                    current_metrics = {
                        **current_metrics,
                        "endedAt": _utc_iso_now(),
                        "elapsedMs": int(round((time.perf_counter() - started_monotonic) * 1000)),
                        "statusCode": response_status_code,
                        "usage": usage,
                        "responseBytes": response_bytes,
                        "responseChars": len("".join(parts)),
                        "reasoningChars": reasoning_chars,
                        "finishReason": finish_reason,
                        "sawDone": saw_done,
                        "errorType": exc.__class__.__name__,
                    }
                    self._record_request_metrics(current_metrics)
                    raise
                except (httpx.TimeoutException, httpx.RequestError, _EmptyStreamError, _TruncatedStreamError) as exc:
                    # 中途断流/超时/空响应：本 attempt 的聚合内容整体作废，可安全重试。
                    last_error = exc
                    current_metrics = {
                        **current_metrics,
                        "endedAt": _utc_iso_now(),
                        "elapsedMs": int(round((time.perf_counter() - started_monotonic) * 1000)),
                        "statusCode": response_status_code,
                        "usage": usage,
                        "responseBytes": response_bytes,
                        "responseChars": len("".join(parts)),
                        "reasoningChars": reasoning_chars,
                        "finishReason": finish_reason,
                        "sawDone": saw_done,
                        "errorType": exc.__class__.__name__,
                    }
                    self._record_request_metrics(current_metrics)
                    if attempt < attempts_limit:
                        attempt_history.append(dict(current_metrics))
                        await asyncio.sleep(_retry_delay_seconds(attempt))
                        continue
                    raise
                except Exception as exc:
                    current_metrics = {
                        **current_metrics,
                        "endedAt": _utc_iso_now(),
                        "elapsedMs": int(round((time.perf_counter() - started_monotonic) * 1000)),
                        "statusCode": response_status_code,
                        "usage": usage,
                        "responseBytes": response_bytes,
                        "responseChars": len("".join(parts)),
                        "reasoningChars": reasoning_chars,
                        "finishReason": finish_reason,
                        "sawDone": saw_done,
                        "errorType": exc.__class__.__name__,
                    }
                    self._record_request_metrics(current_metrics)
                    raise
        raise last_error if last_error else RuntimeError("chat_stream_collect exhausted attempts")

    async def _stream_chat(
        self,
        url: str,
        payload: dict[str, Any],
        *,
        max_attempts: int | None = None,
    ) -> AsyncGenerator[str, None]:
        attempts_limit = OPENAI_COMPAT_REQUEST_MAX_ATTEMPTS
        if max_attempts is not None:
            attempts_limit = max(1, min(OPENAI_COMPAT_REQUEST_MAX_ATTEMPTS, int(max_attempts)))
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            for attempt in range(1, attempts_limit + 1):
                started_at = _utc_iso_now()
                started_monotonic = time.perf_counter()
                response_chars = 0
                response_bytes = 0
                first_byte_seen = False
                current_metrics: dict[str, Any] = {
                    **self.request_fingerprint(),
                    "attempt": attempt,
                    "startedAt": started_at,
                    "endedAt": None,
                    "elapsedMs": None,
                    "statusCode": None,
                    "stream": True,
                    "apiType": "chat_completions",
                    "requestMaxTokens": int(payload.get("max_tokens") or payload.get("max_completion_tokens") or 0),
                    "usage": _normalize_usage(None),
                    "responseBytes": 0,
                    "responseChars": 0,
                }
                self._record_request_metrics(current_metrics)
                async with self._acquire_request_slots() as slot_metrics:
                    current_metrics.update(slot_metrics)
                    current_metrics["httpStartedAt"] = _utc_iso_now()
                    self._record_request_metrics(current_metrics)
                    http_started_monotonic = time.perf_counter()
                    async with client.stream(
                        "POST",
                        url,
                        headers=self._get_headers(),
                        json=payload,
                    ) as response:
                        current_metrics.update(
                            {
                                "responseHeadersAt": _utc_iso_now(),
                                "httpToHeadersMs": int(
                                    round((time.perf_counter() - http_started_monotonic) * 1000)
                                ),
                                "statusCode": int(response.status_code),
                            }
                        )
                        self._record_request_metrics(current_metrics)
                        if response.status_code >= 400:
                            body = await response.aread()
                            elapsed_ms = int(round((time.perf_counter() - started_monotonic) * 1000))
                            current_metrics = {
                                **current_metrics,
                                "endedAt": _utc_iso_now(),
                                "elapsedMs": elapsed_ms,
                                "statusCode": int(response.status_code),
                                "responseBytes": len(body or b""),
                            }
                            self._record_request_metrics(current_metrics)
                            if _is_retryable_status(response.status_code) and attempt < attempts_limit:
                                await asyncio.sleep(_retry_delay_seconds(attempt, response=response))
                                continue
                            response.raise_for_status()
                        async for line in response.aiter_lines():
                            if not first_byte_seen:
                                first_byte_seen = True
                                current_metrics.update(
                                    {
                                        "firstByteAt": _utc_iso_now(),
                                        "timeToFirstByteMs": int(
                                            round((time.perf_counter() - http_started_monotonic) * 1000)
                                        ),
                                    }
                                )
                                self._record_request_metrics(current_metrics)
                            if not line:
                                continue
                            response_bytes += len(line.encode("utf-8", errors="ignore"))
                            if not line.startswith("data: "):
                                continue
                            data_str = line[6:].strip()
                            if data_str == "[DONE]":
                                current_metrics = {
                                    **current_metrics,
                                    "endedAt": _utc_iso_now(),
                                    "elapsedMs": int(round((time.perf_counter() - started_monotonic) * 1000)),
                                    "statusCode": int(response.status_code),
                                    "responseBytes": response_bytes,
                                    "responseChars": response_chars,
                                }
                                self._record_request_metrics(current_metrics)
                                return
                            try:
                                data = json.loads(data_str)
                                delta = data["choices"][0].get("delta", {})
                                content = _incremental_content_text(delta.get("content", ""))
                                if content:
                                    response_chars += len(content)
                                    yield content
                            except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                                continue
                        current_metrics = {
                            **current_metrics,
                            "endedAt": _utc_iso_now(),
                            "elapsedMs": int(round((time.perf_counter() - started_monotonic) * 1000)),
                            "statusCode": int(response.status_code),
                            "responseBytes": response_bytes,
                            "responseChars": response_chars,
                        }
                        self._record_request_metrics(current_metrics)
                        return
