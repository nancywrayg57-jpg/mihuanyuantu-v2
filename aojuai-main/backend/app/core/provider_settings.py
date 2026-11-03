"""
AOJU Backend - Internal provider-settings helpers.

This module defines a minimal normalized contract for OpenAI-compatible
provider settings shared by assistant runtime and legacy module-local AI
configs, without forcing an immediate schema merge.

Ownership guidance:
- `assistant_tenant_configs` is the canonical provider source for new
  assistant-backed modules and future plugins.
- `tenant_ai_configs` remains the legacy provider source for OKR/coaching
  flows until those modules are migrated explicitly.
"""
from __future__ import annotations

from typing import Any

from app.core.provider_secrets import mask_provider_secret


DEFAULT_OPENAI_PROVIDER_MODEL = "gpt-3.5-turbo"
DEFAULT_OPENAI_PROVIDER_TEMPERATURE = 0.7
DEFAULT_OPENAI_PROVIDER_MAX_TOKENS = 2048
DEFAULT_OPENAI_PROVIDER_STREAM = True


def normalize_provider_text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def normalize_provider_base_url(value: Any) -> str | None:
    normalized = normalize_provider_text(value)
    if not normalized:
        return None
    return normalized.rstrip("/")


def _normalize_provider_float(value: Any, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _normalize_provider_int(value: Any, *, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return int(default)
    return parsed if parsed > 0 else int(default)


def _normalize_optional_provider_int(value: Any) -> int | None:
    try:
        parsed = int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _normalize_provider_api_mode(value: Any) -> str:
    mode = str(value or "").strip().lower()
    if mode in {"responses", "response", "responses_api"}:
        return "responses"
    return "chat_completions"


def normalize_openai_provider_config(
    *,
    base_url: Any,
    model: Any,
    temperature: Any,
    max_tokens: Any,
    stream: Any | None = None,
    api_mode: Any | None = None,
    default_model: str = DEFAULT_OPENAI_PROVIDER_MODEL,
    default_temperature: float = DEFAULT_OPENAI_PROVIDER_TEMPERATURE,
    default_max_tokens: int = DEFAULT_OPENAI_PROVIDER_MAX_TOKENS,
    default_stream: bool = DEFAULT_OPENAI_PROVIDER_STREAM,
) -> dict[str, Any]:
    return {
        "base_url": normalize_provider_base_url(base_url),
        "model": normalize_provider_text(model) or default_model,
        "temperature": _normalize_provider_float(temperature, default=default_temperature),
        # max_tokens 留空 = 不下发（跟随模型默认）。历史上空值会落到 default，
        # 现在空/非法一律 None——固定上限既可能截断大输出，实测也不是时延主因。
        "max_tokens": _normalize_optional_provider_int(max_tokens),
        "stream": default_stream if stream is None else bool(stream),
        "api_mode": _normalize_provider_api_mode(api_mode),
    }


def build_openai_provider_settings(
    *,
    base_url: Any,
    api_key: Any,
    model: Any,
    temperature: Any,
    max_tokens: Any,
    stream: Any | None = None,
    api_mode: Any | None = None,
    default_model: str = DEFAULT_OPENAI_PROVIDER_MODEL,
    default_temperature: float = DEFAULT_OPENAI_PROVIDER_TEMPERATURE,
    default_max_tokens: int = DEFAULT_OPENAI_PROVIDER_MAX_TOKENS,
    default_stream: bool = DEFAULT_OPENAI_PROVIDER_STREAM,
) -> dict[str, Any] | None:
    provider_config = normalize_openai_provider_config(
        base_url=base_url,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=stream,
        api_mode=api_mode,
        default_model=default_model,
        default_temperature=default_temperature,
        default_max_tokens=default_max_tokens,
        default_stream=default_stream,
    )
    normalized_api_key = normalize_provider_text(api_key)

    if not provider_config["base_url"] or not normalized_api_key:
        return None

    return {
        **provider_config,
        "api_key": normalized_api_key,
    }


def build_openai_provider_view(
    *,
    base_url: Any,
    api_key: Any,
    model: Any,
    temperature: Any,
    max_tokens: Any,
    stream: Any | None = None,
    default_model: str = DEFAULT_OPENAI_PROVIDER_MODEL,
    default_temperature: float = DEFAULT_OPENAI_PROVIDER_TEMPERATURE,
    default_max_tokens: int = DEFAULT_OPENAI_PROVIDER_MAX_TOKENS,
    default_stream: bool = DEFAULT_OPENAI_PROVIDER_STREAM,
) -> dict[str, Any]:
    provider_config = normalize_openai_provider_config(
        base_url=base_url,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=stream,
        default_model=default_model,
        default_temperature=default_temperature,
        default_max_tokens=default_max_tokens,
        default_stream=default_stream,
    )
    normalized_api_key = normalize_provider_text(api_key)

    return {
        **provider_config,
        "api_key_masked": mask_provider_secret(normalized_api_key),
        "api_key_set": bool(normalized_api_key),
    }
