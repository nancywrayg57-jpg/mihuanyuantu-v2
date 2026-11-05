"""AOJU Backend - Tenant Assistant Config Bridge

Store a lightweight tenant-scoped assistant config inside ``tenant.config.assistant``.
The base branch only keeps the generic assistant foundation and does not embed
business-module-specific prompt presets.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domain.assistant.module_skill_governance import (
    build_assistant_module_skill_catalog,
    build_default_module_skill_governance,
    merge_module_skill_governance,
)

DEFAULT_ASSISTANT_PROMPTS: dict[str, Any] = {
    "assistant": {
        "system": (
            "你是 AOJUAI 的统一 AI 助手。先基于上下文理解用户目标，再给出务实、可执行的下一步。"
        ),
        "writeGuard": (
            "若回答涉及新增、修改、删除或外部写入动作，先明确风险与确认点，不要假设已经执行。"
        ),
    },
    "modules": {
        "default": {
            "chat": "优先输出结构清晰、可直接执行的建议，避免空泛总结。",
        },
    },
}

DEFAULT_ASSISTANT_CAPABILITIES: dict[str, Any] = {
    "skillBindings": [
        {"id": "core.context_reader", "enabled": True, "instruction": ""},
        {"id": "core.permission_boundary", "enabled": True, "instruction": ""},
        {"id": "core.form_collection", "enabled": True, "instruction": ""},
        {"id": "core.write_confirmation", "enabled": True, "instruction": ""},
    ],
    "toolBindings": [
        {"id": "time.now", "enabled": True, "instruction": ""},
        {"id": "time.range.resolve", "enabled": True, "instruction": ""},
        {"id": "session.scope.inspect", "enabled": True, "instruction": ""},
        {"id": "page.context.refresh", "enabled": True, "instruction": ""},
    ],
    "importedTools": [],
    "memory": {
        "workingSummary": "",
        "profile": {
            "preferredStyle": "",
            "avoidedPhrases": [],
            "preferredDomains": [],
        },
        "episodic": [],
    },
    "policy": {
        "requireConfirmationForWrites": True,
        "exposeModuleCapabilityManifest": True,
        "allowImportedToolsInChat": False,
        "maxVisibleTools": 8,
    },
    "moduleSkillGovernance": build_default_module_skill_governance(),
}


DEFAULT_ASSISTANT_CONFIG: dict[str, Any] = {
    "enabled": False,
    "deductCredits": False,
    "creditsPerCall": 1,
    "pointsTokenRatio": 1000,
    "baseUrl": "",
    "model": "",
    "temperature": 0.7,
    "maxTokens": 2048,
    "stream": True,
    "apiKey": "",
    "prompts": deepcopy(DEFAULT_ASSISTANT_PROMPTS),
    "capabilities": deepcopy(DEFAULT_ASSISTANT_CAPABILITIES),
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = dict(base)
    for key, override_value in override.items():
        base_value = result.get(key)
        if isinstance(base_value, dict) and isinstance(override_value, dict):
            result[key] = _deep_merge(base_value, override_value)
        else:
            result[key] = override_value
    return result


def _first_nonempty_string(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _nonempty_string(value: Any) -> bool:
    return bool(str(value or "").strip())


def _mask_api_key(value: str | None) -> str | None:
    if not value:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    if len(normalized) <= 8:
        return "*" * len(normalized)
    return normalized[:4] + "*" * (len(normalized) - 8) + normalized[-4:]


def _extract_provider(source: dict[str, Any]) -> dict[str, Any]:
    provider = source.get("provider")
    return provider if isinstance(provider, dict) else {}


def _extract_secrets(source: dict[str, Any]) -> dict[str, Any]:
    secrets = source.get("secrets")
    return secrets if isinstance(secrets, dict) else {}


def _extract_prompts(source: dict[str, Any]) -> dict[str, Any]:
    prompts_source = source.get("prompts")
    if not isinstance(prompts_source, dict):
        return deepcopy(DEFAULT_ASSISTANT_PROMPTS)
    return _deep_merge(deepcopy(DEFAULT_ASSISTANT_PROMPTS), prompts_source)


def _extract_capabilities(source: dict[str, Any]) -> dict[str, Any]:
    capabilities_source = source.get("capabilities")
    if not isinstance(capabilities_source, dict):
        return deepcopy(DEFAULT_ASSISTANT_CAPABILITIES)
    return _deep_merge(deepcopy(DEFAULT_ASSISTANT_CAPABILITIES), capabilities_source)


def _read_numeric_value(primary: dict[str, Any], secondary: dict[str, Any], key: str) -> Any:
    if key in primary:
        return primary.get(key)
    return secondary.get(key)


def _assign_string_field(
    stored: dict[str, Any],
    payload: dict[str, Any],
    provider_payload: dict[str, Any],
    *,
    key: str,
    snake_key: str | None = None,
) -> None:
    normalized_snake = snake_key or key.replace("-", "_")
    if key in payload or normalized_snake in payload:
        stored[key] = str(payload.get(key, payload.get(normalized_snake)) or "")
        return
    if key in provider_payload or normalized_snake in provider_payload:
        stored[key] = str(provider_payload.get(key, provider_payload.get(normalized_snake)) or "")


def normalize_assistant_stored_config(raw: Any) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    normalized = deepcopy(DEFAULT_ASSISTANT_CONFIG)

    for key in ("enabled", "deductCredits"):
        value = source.get(key)
        if isinstance(value, bool):
            normalized[key] = value

    credits_per_call = source.get("creditsPerCall")
    if isinstance(credits_per_call, int) and credits_per_call >= 0:
        normalized["creditsPerCall"] = credits_per_call

    points_token_ratio = source.get("pointsTokenRatio")
    if isinstance(points_token_ratio, int | float) and float(points_token_ratio) >= 0:
        normalized["pointsTokenRatio"] = float(points_token_ratio)

    provider_source = _extract_provider(source)
    secrets_source = _extract_secrets(source)

    normalized["baseUrl"] = _first_nonempty_string(
        source.get("baseUrl"),
        source.get("base_url"),
        provider_source.get("baseUrl"),
        provider_source.get("base_url"),
    )
    normalized["model"] = _first_nonempty_string(
        source.get("model"),
        provider_source.get("model"),
    )

    temperature = _read_numeric_value(source, provider_source, "temperature")
    if isinstance(temperature, int | float) and 0 <= float(temperature) <= 2:
        normalized["temperature"] = float(temperature)

    max_tokens = _read_numeric_value(source, provider_source, "maxTokens")
    if isinstance(max_tokens, int) and 1 <= max_tokens <= 8192:
        normalized["maxTokens"] = max_tokens

    stream = source.get("stream") if "stream" in source else provider_source.get("stream")
    if isinstance(stream, bool):
        normalized["stream"] = stream

    normalized["apiKey"] = _first_nonempty_string(
        source.get("apiKey"),
        source.get("api_key"),
        secrets_source.get("apiKey"),
        secrets_source.get("api_key"),
    )
    normalized["prompts"] = _extract_prompts(source)
    normalized["capabilities"] = _extract_capabilities(source)

    return normalized


def assistant_config_to_view(raw: Any) -> dict[str, Any]:
    stored = normalize_assistant_stored_config(raw)
    view = deepcopy(stored)
    api_key = str(view.pop("apiKey", "") or "").strip()
    view["isEnabled"] = bool(view.get("enabled"))
    view["apiKeyMasked"] = _mask_api_key(api_key)
    view["apiKeySet"] = bool(api_key)
    view["moduleSkillCatalog"] = build_assistant_module_skill_catalog()
    return view


def merge_assistant_config(raw: Any, incoming: Any) -> dict[str, Any]:
    stored = normalize_assistant_stored_config(raw)
    payload = incoming if isinstance(incoming, dict) else {}
    provider_payload = _extract_provider(payload)
    secrets_payload = _extract_secrets(payload)

    for key in ("enabled", "deductCredits"):
        if key in payload and isinstance(payload.get(key), bool):
            stored[key] = bool(payload.get(key))

    if "creditsPerCall" in payload:
        credits_per_call = payload.get("creditsPerCall")
        if isinstance(credits_per_call, int) and credits_per_call >= 0:
            stored["creditsPerCall"] = credits_per_call

    if "pointsTokenRatio" in payload:
        points_token_ratio = payload.get("pointsTokenRatio")
        if isinstance(points_token_ratio, int | float) and float(points_token_ratio) >= 0:
            stored["pointsTokenRatio"] = float(points_token_ratio)

    _assign_string_field(stored, payload, provider_payload, key="baseUrl", snake_key="base_url")
    _assign_string_field(stored, payload, provider_payload, key="model")

    if "temperature" in payload or "temperature" in provider_payload:
        temperature = payload.get("temperature") if "temperature" in payload else provider_payload.get("temperature")
        if isinstance(temperature, int | float) and 0 <= float(temperature) <= 2:
            stored["temperature"] = float(temperature)

    if "maxTokens" in payload or "maxTokens" in provider_payload:
        max_tokens = payload.get("maxTokens") if "maxTokens" in payload else provider_payload.get("maxTokens")
        if isinstance(max_tokens, int) and 1 <= max_tokens <= 8192:
            stored["maxTokens"] = max_tokens

    if "stream" in payload or "stream" in provider_payload:
        stream = payload.get("stream") if "stream" in payload else provider_payload.get("stream")
        if isinstance(stream, bool):
            stored["stream"] = stream

    if "apiKey" in payload or "api_key" in payload:
        stored["apiKey"] = str(payload.get("apiKey", payload.get("api_key")) or "")
    elif "apiKey" in secrets_payload or "api_key" in secrets_payload:
        stored["apiKey"] = str(secrets_payload.get("apiKey", secrets_payload.get("api_key")) or "")

    prompts_payload = payload.get("prompts")
    if isinstance(prompts_payload, dict):
        stored["prompts"] = _deep_merge(stored["prompts"], prompts_payload)

    capabilities_payload = payload.get("capabilities")
    if isinstance(capabilities_payload, dict):
        current_governance = (
            deepcopy(stored["capabilities"].get("moduleSkillGovernance"))
            if isinstance(stored.get("capabilities"), dict)
            else None
        )
        stored["capabilities"] = _deep_merge(stored["capabilities"], capabilities_payload)
        if isinstance(capabilities_payload.get("moduleSkillGovernance"), dict):
            stored["capabilities"]["moduleSkillGovernance"] = merge_module_skill_governance(
                current_governance,
                capabilities_payload.get("moduleSkillGovernance"),
            )

    return stored


def resolve_assistant_provider_runtime(raw: Any) -> dict[str, Any] | None:
    stored = normalize_assistant_stored_config(raw)
    api_key = str(stored.get("apiKey") or "").strip()

    if not stored["enabled"]:
        return None
    if not _nonempty_string(stored.get("baseUrl")):
        return None
    if not _nonempty_string(stored.get("model")):
        return None
    if not api_key:
        return None

    return {
        "base_url": str(stored.get("baseUrl") or "").strip(),
        "api_key": api_key,
        "model": str(stored.get("model") or "").strip(),
        "temperature": float(stored.get("temperature") or 0.7),
        "max_tokens": int(stored.get("maxTokens") or 2048),
        "stream": bool(stored.get("stream", True)),
        "timeout_seconds": 600,
    }


def resolve_assistant_prompt_stack(
    raw: Any,
    *,
    assistant_key: str = "default",
    module_code: str = "default",
) -> dict[str, str]:
    stored = normalize_assistant_stored_config(raw)
    prompts = stored.get("prompts") if isinstance(stored.get("prompts"), dict) else {}

    assistant_prompts = prompts.get("assistant") if isinstance(prompts.get("assistant"), dict) else {}
    modules = prompts.get("modules") if isinstance(prompts.get("modules"), dict) else {}

    module_prompt_sources: list[dict[str, Any]] = []
    normalized_key = str(assistant_key or "").strip()
    if normalized_key and isinstance(modules.get(normalized_key), dict):
        module_prompt_sources.append(modules[normalized_key])
    if module_code and isinstance(modules.get(module_code), dict):
        module_prompt_sources.append(modules[module_code])
    if isinstance(modules.get("default"), dict):
        module_prompt_sources.append(modules["default"])

    module_chat = ""
    for item in module_prompt_sources:
        candidate = str(item.get("chat") or "").strip()
        if candidate:
            module_chat = candidate
            break

    return {
        "system": str(assistant_prompts.get("system") or DEFAULT_ASSISTANT_PROMPTS["assistant"]["system"]).strip(),
        "writeGuard": str(
            assistant_prompts.get("writeGuard") or DEFAULT_ASSISTANT_PROMPTS["assistant"]["writeGuard"]
        ).strip(),
        "moduleChat": module_chat or str(DEFAULT_ASSISTANT_PROMPTS["modules"]["default"]["chat"]).strip(),
    }
