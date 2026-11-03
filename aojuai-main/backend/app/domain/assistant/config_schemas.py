"""AOJU Backend - AI Assistant Config Schemas"""

from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, computed_field, field_validator


def _mask_api_key(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 8:
        return "*" * len(value)
    return value[:4] + "*" * (len(value) - 8) + value[-4:]


class AssistantCorePromptConfig(BaseModel):
    """Core prompt set owned by assistant runtime."""

    model_config = ConfigDict(populate_by_name=True)

    system: str | None = Field(default=None, description="统一助手系统提示词")
    write_guard: str | None = Field(default=None, alias="writeGuard", description="写入守卫提示词")


class AssistantModulePromptConfig(BaseModel):
    """Module prompt set provided by adapters."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    chat: str | None = Field(default=None, description="模块对话提示词")


class AssistantPromptConfig(BaseModel):
    """Prompt stack for assistant runtime."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    assistant: AssistantCorePromptConfig | None = None
    modules: dict[str, AssistantModulePromptConfig] = Field(default_factory=dict)


class AssistantSkillBindingConfig(BaseModel):
    """Assistant skill binding."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    enabled: bool = True
    instruction: str = ""


class AssistantToolBindingConfig(BaseModel):
    """Assistant tool binding."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    enabled: bool = True
    instruction: str = ""


class AssistantImportedToolConfig(BaseModel):
    """Imported tool / MCP descriptor."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    label: str
    description: str | None = None
    transport_type: str | None = Field(default=None, alias="transportType")
    endpoint_url: str | None = Field(default=None, alias="endpointUrl")
    command: str | None = None
    auth_mode: str | None = Field(default=None, alias="authMode")
    visibility: str | None = None
    allowlisted_tools: list[str] = Field(default_factory=list, alias="allowlistedTools")
    allowlisted_resources: list[str] = Field(default_factory=list, alias="allowlistedResources")
    allowlisted_prompts: list[str] = Field(default_factory=list, alias="allowlistedPrompts")


class AssistantMemoryProfileConfig(BaseModel):
    """Profile memory config."""

    model_config = ConfigDict(populate_by_name=True)

    preferred_style: str | None = Field(default=None, alias="preferredStyle")
    avoided_phrases: list[str] = Field(default_factory=list, alias="avoidedPhrases")
    preferred_domains: list[str] = Field(default_factory=list, alias="preferredDomains")


class AssistantMemoryConfig(BaseModel):
    """Assistant memory config."""

    model_config = ConfigDict(populate_by_name=True)

    working_summary: str | None = Field(default=None, alias="workingSummary")
    profile: AssistantMemoryProfileConfig = Field(default_factory=AssistantMemoryProfileConfig)
    episodic: list[dict[str, Any]] = Field(default_factory=list)


class AssistantCapabilityPolicyConfig(BaseModel):
    """Capability policy config."""

    model_config = ConfigDict(populate_by_name=True)

    require_confirmation_for_writes: bool = Field(True, alias="requireConfirmationForWrites")
    expose_module_capability_manifest: bool = Field(True, alias="exposeModuleCapabilityManifest")
    allow_imported_tools_in_chat: bool = Field(False, alias="allowImportedToolsInChat")
    max_visible_tools: int = Field(8, alias="maxVisibleTools", ge=1, le=20)


class AssistantModuleSkillRuleConfig(BaseModel):
    """Module skill rule config."""

    model_config = ConfigDict(populate_by_name=True)

    skill_id: str = Field(..., alias="skillId")
    enabled: bool = True
    rank: int = Field(0, ge=0, le=999)


class AssistantModuleSkillGovernanceModuleConfig(BaseModel):
    """Module skill governance config."""

    model_config = ConfigDict(populate_by_name=True)

    module_code: str = Field(..., alias="moduleCode")
    skill_rules: list[AssistantModuleSkillRuleConfig] = Field(default_factory=list, alias="skillRules")


class AssistantModuleSkillGovernanceConfig(BaseModel):
    """Tenant module skill governance."""

    model_config = ConfigDict(populate_by_name=True)

    modules: list[AssistantModuleSkillGovernanceModuleConfig] = Field(default_factory=list)


class AssistantModuleSkillCatalogItem(BaseModel):
    """Module skill catalog item."""

    model_config = ConfigDict(populate_by_name=True)

    skill_id: str = Field(..., alias="skillId")
    label: str
    description: str = ""
    default_rank: int = Field(0, alias="defaultRank", ge=0, le=999)
    scope_ids: list[str] = Field(default_factory=list, alias="scopeIds")


class AssistantModuleSkillCatalogModule(BaseModel):
    """Module skill catalog module."""

    model_config = ConfigDict(populate_by_name=True)

    module_code: str = Field(..., alias="moduleCode")
    module_name: str = Field(..., alias="moduleName")
    skills: list[AssistantModuleSkillCatalogItem] = Field(default_factory=list)


class AssistantCapabilityConfig(BaseModel):
    """Capability framework config."""

    model_config = ConfigDict(populate_by_name=True)

    skill_bindings: list[AssistantSkillBindingConfig] = Field(default_factory=list, alias="skillBindings")
    tool_bindings: list[AssistantToolBindingConfig] = Field(default_factory=list, alias="toolBindings")
    imported_tools: list[AssistantImportedToolConfig] = Field(default_factory=list, alias="importedTools")
    memory: AssistantMemoryConfig = Field(default_factory=AssistantMemoryConfig)
    policy: AssistantCapabilityPolicyConfig = Field(default_factory=AssistantCapabilityPolicyConfig)
    module_skill_governance: AssistantModuleSkillGovernanceConfig = Field(
        default_factory=AssistantModuleSkillGovernanceConfig,
        alias="moduleSkillGovernance",
    )


class AssistantProviderConfig(BaseModel):
    """AI Provider 配置"""

    base_url: str = Field(..., alias="baseUrl", description="API Base URL")
    model: str = Field(..., description="模型名称")
    temperature: float = Field(0.7, ge=0, le=2, description="温度参数")
    max_tokens: int = Field(2048, alias="maxTokens", ge=1, description="最大token数")
    stream: bool = Field(True, description="是否启用流式输出")

    model_config = ConfigDict(populate_by_name=True)


class AssistantProviderSecrets(BaseModel):
    """AI Provider 密钥配置"""

    api_key: str = Field(..., alias="apiKey", description="API Key")

    model_config = ConfigDict(populate_by_name=True)


class AssistantConfigView(BaseModel):
    """Tenant-scoped assistant config view with masked secrets."""

    enabled: bool = Field(False, description="是否启用 AI 助手")
    deduct_credits: bool = Field(False, alias="deductCredits", description="是否扣除积分")
    credits_per_call: int = Field(1, alias="creditsPerCall", description="每次调用扣除积分")
    points_token_ratio: float = Field(1000, alias="pointsTokenRatio", description="Token / 积分 比例")
    base_url: str | None = Field(None, alias="baseUrl")
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = Field(None, alias="maxTokens")
    stream: bool = True
    api_key_masked: str | None = Field(None, alias="apiKeyMasked")
    api_key_set: bool = Field(False, alias="apiKeySet")
    prompts: AssistantPromptConfig = Field(default_factory=AssistantPromptConfig)
    capabilities: AssistantCapabilityConfig = Field(default_factory=AssistantCapabilityConfig)
    module_skill_catalog: list[AssistantModuleSkillCatalogModule] = Field(
        default_factory=list,
        alias="moduleSkillCatalog",
    )

    model_config = ConfigDict(populate_by_name=True)

    @computed_field(alias="isEnabled", return_type=bool)
    @property
    def is_enabled(self) -> bool:
        return bool(self.enabled)


class AssistantConfigUpsertRequest(BaseModel):
    """Update config request."""

    enabled: bool | None = Field(
        None,
        validation_alias=AliasChoices("enabled", "isEnabled", "is_enabled"),
    )
    deduct_credits: bool | None = Field(None, alias="deductCredits")
    credits_per_call: int | None = Field(None, alias="creditsPerCall", ge=0)
    points_token_ratio: float | None = Field(None, alias="pointsTokenRatio", ge=0)
    base_url: str | None = Field(None, alias="baseUrl")
    model: str | None = None
    temperature: float | None = Field(None, ge=0, le=2)
    max_tokens: int | None = Field(None, alias="maxTokens", ge=1)
    stream: bool | None = None
    api_key: str | None = Field(None, alias="apiKey")
    prompts: AssistantPromptConfig | None = None
    capabilities: AssistantCapabilityConfig | None = None

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("api_key")
    @classmethod
    def _normalize_api_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("base_url", "model")
    @classmethod
    def _normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None
