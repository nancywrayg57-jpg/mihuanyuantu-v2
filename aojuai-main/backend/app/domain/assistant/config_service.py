"""
AOJU Backend - AI Assistant Config Service

租户级 AI 助手配置服务
"""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.provider_secrets import (
    decrypt_provider_secret_or_plain,
    encrypt_provider_secret,
    normalize_provider_secret_text,
)
from app.core.provider_settings import (
    DEFAULT_OPENAI_PROVIDER_MAX_TOKENS,
    DEFAULT_OPENAI_PROVIDER_MODEL,
    DEFAULT_OPENAI_PROVIDER_TEMPERATURE,
    build_openai_provider_settings,
    build_openai_provider_view,
    normalize_openai_provider_config,
)
from app.domain.assistant.config_models import AssistantTenantConfig
from app.domain.assistant.config_schemas import (
    AssistantCapabilityConfig,
    AssistantConfigUpsertRequest,
    AssistantConfigView,
    AssistantPromptConfig,
)
from app.domain.assistant.module_skill_governance import (
    build_assistant_module_skill_catalog,
    build_default_module_skill_governance,
    merge_module_skill_governance,
)
from app.domain.assistant_bridge import (
    assistant_config_to_view,
    normalize_assistant_stored_config,
    resolve_assistant_prompt_stack,
    resolve_assistant_provider_runtime,
)
from app.domain.auth.models import Tenant


def build_default_assistant_prompts() -> dict[str, Any]:
    payload = normalize_assistant_stored_config({})
    prompts = payload.get("prompts")
    if isinstance(prompts, dict):
        return deepcopy(prompts)
    return {
        "assistant": {
            "system": "你是 AOJUAI 的统一 AI 助手。先基于上下文理解用户目标，再给出务实、可执行的下一步。",
            "writeGuard": "若回答涉及新增、修改、删除或外部写入动作，先明确风险与确认点，不要假设已经执行。",
        },
        "modules": {
            "default": {
                "chat": "优先输出结构清晰、可直接执行的建议，避免空泛总结。",
            }
        },
    }


def build_default_assistant_capabilities() -> dict[str, Any]:
    payload = normalize_assistant_stored_config({})
    capabilities = payload.get("capabilities")
    merged = deepcopy(capabilities) if isinstance(capabilities, dict) else {}
    merged["moduleSkillGovernance"] = merge_module_skill_governance(
        build_default_module_skill_governance(),
        merged.get("moduleSkillGovernance"),
    )
    return merged


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = dict(base)
    for key, override_value in override.items():
        base_value = result.get(key)
        if isinstance(base_value, dict) and isinstance(override_value, dict):
            result[key] = _deep_merge(base_value, override_value)
        else:
            result[key] = override_value
    return result


def _is_nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


DEFAULT_ASSISTANT_PROMPTS: dict[str, Any] = build_default_assistant_prompts()


class AssistantConfigService:
    """
    Primary tenant-level provider service for assistant-backed modules.

    `assistant_tenant_configs` 是新的规范化来源。
    `tenant.config.assistant` 保留为兼容兜底，只读优先、写入迁移到新表。
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_db_config(self, tenant_id: int) -> AssistantTenantConfig | None:
        if not callable(getattr(self.db, "execute", None)):
            return None
        result = await self.db.execute(
            select(AssistantTenantConfig).where(
                AssistantTenantConfig.tenant_id == tenant_id,
                AssistantTenantConfig.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def _get_legacy_payload(self, tenant_id: int) -> dict[str, Any] | None:
        if not callable(getattr(self.db, "execute", None)):
            return None
        result = await self.db.execute(
            select(Tenant.config).where(
                Tenant.id == tenant_id,
                Tenant.deleted_at.is_(None),
            )
        )
        config = result.scalar_one_or_none()
        if not isinstance(config, dict):
            return None
        payload = config.get("assistant")
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _legacy_payload_to_effective_config(tenant_id: int, payload: dict[str, Any]) -> SimpleNamespace:
        stored = normalize_assistant_stored_config(payload)
        api_key = str(stored.get("apiKey") or "").strip()
        return SimpleNamespace(
            id=None,
            tenant_id=tenant_id,
            enabled=bool(stored.get("enabled")),
            deduct_credits=bool(stored.get("deductCredits")),
            credits_per_call=int(stored.get("creditsPerCall") or 1),
            config={
                "points_token_ratio": stored.get("pointsTokenRatio", 1000),
                "base_url": stored.get("baseUrl"),
                "model": stored.get("model"),
                "temperature": stored.get("temperature"),
                "max_tokens": stored.get("maxTokens"),
                "stream": stored.get("stream"),
                "prompts": deepcopy(stored.get("prompts") or {}),
                "capabilities": deepcopy(stored.get("capabilities") or {}),
            },
            secrets={"api_key": api_key} if api_key else {},
        )

    async def get_config(self, tenant_id: int) -> AssistantTenantConfig | SimpleNamespace | None:
        config = await self._get_db_config(tenant_id)
        if config:
            return config
        legacy_payload = await self._get_legacy_payload(tenant_id)
        if not legacy_payload:
            return None
        return self._legacy_payload_to_effective_config(tenant_id, legacy_payload)

    @staticmethod
    def _extract_prompts(config: AssistantTenantConfig | SimpleNamespace | None) -> dict[str, Any]:
        defaults = build_default_assistant_prompts()
        if not config:
            return defaults
        cfg = config.config if isinstance(getattr(config, "config", None), dict) else {}
        raw_prompts = cfg.get("prompts")
        if not isinstance(raw_prompts, dict):
            return defaults
        return _deep_merge(defaults, raw_prompts)

    @staticmethod
    def _extract_capabilities(config: AssistantTenantConfig | SimpleNamespace | None) -> dict[str, Any]:
        defaults = build_default_assistant_capabilities()
        if not config:
            return defaults
        cfg = config.config if isinstance(getattr(config, "config", None), dict) else {}
        raw_capabilities = cfg.get("capabilities")
        if not isinstance(raw_capabilities, dict):
            return defaults
        merged = _deep_merge(defaults, raw_capabilities)
        merged["moduleSkillGovernance"] = merge_module_skill_governance(
            defaults.get("moduleSkillGovernance"),
            raw_capabilities.get("moduleSkillGovernance"),
        )
        return merged

    def get_decrypted_api_key(self, config: AssistantTenantConfig | SimpleNamespace | None) -> str | None:
        if not config:
            return None
        secrets = config.secrets if isinstance(getattr(config, "secrets", None), dict) else {}
        return decrypt_provider_secret_or_plain(secrets.get("api_key"))

    def get_provider_config(self, config: AssistantTenantConfig | SimpleNamespace | None) -> dict[str, Any]:
        cfg = config.config if config and isinstance(getattr(config, "config", None), dict) else {}
        return normalize_openai_provider_config(
            base_url=cfg.get("base_url"),
            model=cfg.get("model"),
            temperature=cfg.get("temperature"),
            max_tokens=cfg.get("max_tokens"),
            stream=cfg.get("stream"),
            default_model=DEFAULT_OPENAI_PROVIDER_MODEL,
            default_temperature=DEFAULT_OPENAI_PROVIDER_TEMPERATURE,
            default_max_tokens=DEFAULT_OPENAI_PROVIDER_MAX_TOKENS,
        )

    def get_provider_view(self, config: AssistantTenantConfig | SimpleNamespace | None) -> dict[str, Any]:
        cfg = config.config if config and isinstance(getattr(config, "config", None), dict) else {}
        return build_openai_provider_view(
            base_url=cfg.get("base_url"),
            api_key=self.get_decrypted_api_key(config),
            model=cfg.get("model"),
            temperature=cfg.get("temperature"),
            max_tokens=cfg.get("max_tokens"),
            stream=cfg.get("stream"),
            default_model=DEFAULT_OPENAI_PROVIDER_MODEL,
            default_temperature=DEFAULT_OPENAI_PROVIDER_TEMPERATURE,
            default_max_tokens=DEFAULT_OPENAI_PROVIDER_MAX_TOKENS,
        )

    async def get_config_view(self, tenant_id: int) -> AssistantConfigView:
        config = await self.get_config(tenant_id)
        if config is None:
            payload = assistant_config_to_view({})
            provider_view = build_openai_provider_view(
                base_url=None,
                api_key=None,
                model=None,
                temperature=None,
                max_tokens=None,
                stream=None,
                default_model=DEFAULT_OPENAI_PROVIDER_MODEL,
                default_temperature=DEFAULT_OPENAI_PROVIDER_TEMPERATURE,
                default_max_tokens=DEFAULT_OPENAI_PROVIDER_MAX_TOKENS,
            )
            payload.update(
                {
                    "baseUrl": provider_view["base_url"],
                    "model": provider_view["model"],
                    "temperature": provider_view["temperature"],
                    "maxTokens": provider_view["max_tokens"],
                    "stream": provider_view["stream"],
                    "apiKeyMasked": provider_view["api_key_masked"],
                    "apiKeySet": provider_view["api_key_set"],
                }
            )
            return AssistantConfigView.model_validate(payload)

        cfg = config.config if isinstance(getattr(config, "config", None), dict) else {}
        raw_api_key = normalize_provider_secret_text((config.secrets or {}).get("api_key")) if config else None
        decrypted_api_key = self.get_decrypted_api_key(config)
        provider_view = self.get_provider_view(config)
        api_key_masked = provider_view["api_key_masked"]
        api_key_set = provider_view["api_key_set"]
        if raw_api_key and not decrypted_api_key:
            api_key_masked = "已加密但当前无法解密，请重新填写"
            api_key_set = True

        return AssistantConfigView(
            enabled=bool(config.enabled) if config else False,
            deduct_credits=bool(config.deduct_credits) if config else False,
            credits_per_call=int(config.credits_per_call) if config else 1,
            points_token_ratio=cfg.get("points_token_ratio", 1000),
            base_url=provider_view["base_url"],
            model=provider_view["model"],
            temperature=provider_view["temperature"],
            max_tokens=provider_view["max_tokens"],
            stream=provider_view["stream"],
            api_key_masked=api_key_masked,
            api_key_set=api_key_set,
            prompts=AssistantPromptConfig.model_validate(self._extract_prompts(config)),
            capabilities=AssistantCapabilityConfig.model_validate(self._extract_capabilities(config)),
            module_skill_catalog=build_assistant_module_skill_catalog(),
        )

    async def upsert_config(
        self,
        tenant_id: int,
        request: AssistantConfigUpsertRequest,
    ) -> AssistantTenantConfig:
        config = await self._get_db_config(tenant_id)

        if not config:
            legacy_payload = await self._get_legacy_payload(tenant_id)
            seeded = normalize_assistant_stored_config(legacy_payload or {})
            secrets = {}
            legacy_api_key = str(seeded.get("apiKey") or "").strip()
            if legacy_api_key:
                secrets["api_key"] = encrypt_provider_secret(legacy_api_key)
            config = AssistantTenantConfig(
                tenant_id=tenant_id,
                enabled=bool(seeded.get("enabled")),
                deduct_credits=bool(seeded.get("deductCredits")),
                credits_per_call=int(seeded.get("creditsPerCall") or 1),
                config={
                    "points_token_ratio": seeded.get("pointsTokenRatio", 1000),
                    "base_url": seeded.get("baseUrl"),
                    "model": seeded.get("model"),
                    "temperature": seeded.get("temperature"),
                    "max_tokens": seeded.get("maxTokens"),
                    "stream": seeded.get("stream"),
                    "prompts": deepcopy(seeded.get("prompts") or {}),
                    "capabilities": deepcopy(seeded.get("capabilities") or {}),
                },
                secrets=secrets,
            )
            self.db.add(config)

        if request.enabled is not None:
            config.enabled = request.enabled
        if request.deduct_credits is not None:
            config.deduct_credits = request.deduct_credits
        if request.credits_per_call is not None:
            config.credits_per_call = request.credits_per_call

        cfg = config.config.copy() if config.config else {}
        fields_set = request.model_fields_set
        if request.points_token_ratio is not None:
            cfg["points_token_ratio"] = request.points_token_ratio
        if "base_url" in fields_set:
            cfg["base_url"] = request.base_url
        if "model" in fields_set and request.model is not None:
            cfg["model"] = request.model
        if request.temperature is not None:
            cfg["temperature"] = request.temperature
        if request.max_tokens is not None:
            cfg["max_tokens"] = request.max_tokens
        if request.stream is not None:
            cfg["stream"] = request.stream
        if request.prompts is not None:
            cfg["prompts"] = request.prompts.model_dump(by_alias=True, exclude_none=True)
        if request.capabilities is not None:
            existing_capabilities = cfg.get("capabilities") if isinstance(cfg.get("capabilities"), dict) else {}
            defaults = build_default_assistant_capabilities()
            request_capabilities = request.capabilities.model_dump(by_alias=True, exclude_none=True)
            existing_governance = existing_capabilities.get("moduleSkillGovernance")
            request_governance = request_capabilities.pop("moduleSkillGovernance", None)

            merged_capabilities = _deep_merge(defaults, existing_capabilities)
            merged_capabilities = _deep_merge(merged_capabilities, request_capabilities)
            effective_governance = merge_module_skill_governance(
                defaults.get("moduleSkillGovernance"),
                existing_governance,
            )
            if request_governance is not None:
                effective_governance = merge_module_skill_governance(effective_governance, request_governance)
            merged_capabilities["moduleSkillGovernance"] = effective_governance
            cfg["capabilities"] = merged_capabilities
        config.config = cfg

        if request.api_key is not None:
            secrets = config.secrets.copy() if config.secrets else {}
            secrets["api_key"] = encrypt_provider_secret(request.api_key)
            config.secrets = secrets

        await self.db.commit()
        await self.db.refresh(config)
        return config

    async def get_provider_settings(self, tenant_id: int) -> dict[str, Any] | None:
        config = await self.get_config(tenant_id)
        if config:
            cfg = config.config if isinstance(getattr(config, "config", None), dict) else {}
            return build_openai_provider_settings(
                base_url=cfg.get("base_url"),
                api_key=self.get_decrypted_api_key(config),
                model=cfg.get("model", DEFAULT_OPENAI_PROVIDER_MODEL),
                temperature=cfg.get("temperature", DEFAULT_OPENAI_PROVIDER_TEMPERATURE),
                max_tokens=cfg.get("max_tokens", DEFAULT_OPENAI_PROVIDER_MAX_TOKENS),
                stream=cfg.get("stream", True),
                default_model=DEFAULT_OPENAI_PROVIDER_MODEL,
                default_temperature=DEFAULT_OPENAI_PROVIDER_TEMPERATURE,
                default_max_tokens=DEFAULT_OPENAI_PROVIDER_MAX_TOKENS,
            )

        legacy_payload = await self._get_legacy_payload(tenant_id)
        if not legacy_payload:
            return None
        runtime = resolve_assistant_provider_runtime(legacy_payload)
        if runtime:
            return build_openai_provider_settings(
                base_url=runtime.get("base_url"),
                api_key=runtime.get("api_key"),
                model=runtime.get("model"),
                temperature=runtime.get("temperature"),
                max_tokens=runtime.get("max_tokens"),
                stream=runtime.get("stream", True),
                default_model=DEFAULT_OPENAI_PROVIDER_MODEL,
                default_temperature=DEFAULT_OPENAI_PROVIDER_TEMPERATURE,
                default_max_tokens=DEFAULT_OPENAI_PROVIDER_MAX_TOKENS,
            )
        return None

    async def get_prompt_stack(
        self,
        tenant_id: int,
        module_code: str,
        module_name: str,
        default_module_chat_prompt: str | None = None,
    ) -> dict[str, str]:
        config = await self.get_config(tenant_id)
        if not config:
            return resolve_assistant_prompt_stack({}, assistant_key="default", module_code=module_code)

        prompt_config = self._extract_prompts(config)
        assistant_cfg = prompt_config.get("assistant", {})
        modules_cfg = prompt_config.get("modules", {})
        module_cfg = modules_cfg.get(module_code, {}) if isinstance(modules_cfg, dict) else {}
        default_module_cfg = modules_cfg.get("default", {}) if isinstance(modules_cfg, dict) else {}

        system_prompt = assistant_cfg.get("system")
        write_guard_prompt = assistant_cfg.get("writeGuard")
        module_chat_prompt = None
        if isinstance(module_cfg, dict):
            module_chat_prompt = module_cfg.get("chat")
        if not _is_nonempty(module_chat_prompt) and isinstance(default_module_cfg, dict):
            module_chat_prompt = default_module_cfg.get("chat")
        if not _is_nonempty(module_chat_prompt) and _is_nonempty(default_module_chat_prompt):
            module_chat_prompt = default_module_chat_prompt

        if not _is_nonempty(system_prompt):
            system_prompt = DEFAULT_ASSISTANT_PROMPTS["assistant"]["system"]
        if not _is_nonempty(write_guard_prompt):
            write_guard_prompt = DEFAULT_ASSISTANT_PROMPTS["assistant"]["writeGuard"]
        if not _is_nonempty(module_chat_prompt):
            module_chat_prompt = f"在{module_name}场景下，优先输出按步骤执行的建议。"

        return {
            "system": str(system_prompt).strip(),
            "writeGuard": str(write_guard_prompt).strip(),
            "moduleChat": str(module_chat_prompt).strip(),
        }

    async def is_enabled(self, tenant_id: int) -> bool:
        config = await self.get_config(tenant_id)
        return bool(config and config.enabled)

    async def ensure_enabled(self, tenant_id: int) -> None:
        from app.core.exceptions import FeatureDisabledError

        enabled = await self.is_enabled(tenant_id)
        if not enabled:
            raise FeatureDisabledError(
                feature="assistant",
                message="AI 助手未启用，请联系租户管理员在“系统配置 → AI 配置”中开启",
            )
