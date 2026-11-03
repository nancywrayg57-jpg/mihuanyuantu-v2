"""
AOJU Backend - Speech Schemas

配置项（而非运行态）DTO：
- Provider 元数据（用于前端动态渲染配置表单）
- 租户级 Speech 配置读写
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, computed_field


SpeechProviderCategory = Literal["tts", "stt"]


class SpeechFieldType(str, Enum):
    STRING = "string"
    SECRET = "secret"
    NUMBER = "number"
    BOOLEAN = "boolean"
    SELECT = "select"
    MULTISELECT = "multiselect"
    JSON = "json"
    TEXTAREA = "textarea"


class SpeechFieldOption(BaseModel):
    """Select/multiselect option"""

    value: str = Field(..., description="Option value")
    label: str = Field(..., description="Option label")
    description: str | None = Field(None, description="Optional help text")


class SpeechProviderFieldSchema(BaseModel):
    """Provider config field schema for UI rendering"""

    key: str = Field(..., description="Config key")
    label: str = Field(..., description="Field label")
    type: SpeechFieldType = Field(..., description="Field type")
    required: bool = Field(False, description="Is required")
    description: str | None = Field(None, description="Help text")
    placeholder: str | None = Field(None, description="Placeholder")
    default: Any | None = Field(None, description="Default value")
    options: list[SpeechFieldOption] = Field(default_factory=list, description="Select options (if applicable)")
    ui: dict[str, Any] | None = Field(
        default=None,
        description="Optional UI metadata (e.g., slider range, allowCreate for selects).",
    )


class SpeechProviderCapabilities(BaseModel):
    """Runtime capabilities (for routing/UX hints)"""

    supports_voices_list: bool = Field(False, alias="supportsVoicesList")
    supports_tts_stream_audio: bool = Field(False, alias="supportsTtsStreamAudio")
    supports_tts_stream_text: bool = Field(False, alias="supportsTtsStreamText")
    supports_asr_stream: bool = Field(False, alias="supportsAsrStream")
    supports_cancel: bool = Field(False, alias="supportsCancel")
    supports_voice_clone: bool = Field(False, alias="supportsVoiceClone")

    model_config = ConfigDict(populate_by_name=True)


class SpeechProviderDescriptor(BaseModel):
    """Provider descriptor for UI + routing"""

    id: str = Field(..., description="Provider id (stable key)")
    category: SpeechProviderCategory = Field(..., description="tts | stt")
    name: str = Field(..., description="Display name")
    description: str | None = Field(None, description="Provider description")
    capabilities: SpeechProviderCapabilities = Field(default_factory=SpeechProviderCapabilities)
    fields: list[SpeechProviderFieldSchema] = Field(default_factory=list, description="Config fields")


class SpeechProviderSelection(BaseModel):
    """Tenant-selected provider (non-secret settings only)"""

    provider_id: str = Field(..., alias="providerId")
    settings: dict[str, Any] = Field(default_factory=dict, description="Non-secret settings")

    model_config = ConfigDict(populate_by_name=True)


class SpeechProviderProfileView(BaseModel):
    id: str
    label: str
    provider_id: str = Field(..., alias="providerId")
    settings: dict[str, Any] = Field(default_factory=dict)
    is_default: bool = Field(False, alias="isDefault")
    allow_voice_clone: bool = Field(False, alias="allowVoiceClone")
    secrets_set: dict[str, bool] = Field(default_factory=dict, alias="secretsSet")

    model_config = ConfigDict(populate_by_name=True)


class SpeechProviderSelectionUpsert(BaseModel):
    """
    Tenant provider selection update payload.

    - settings: non-secret parameters
    - secrets: secret parameters (stored but never returned in clear text)
    """

    provider_id: str | None = Field(..., alias="providerId")
    settings: dict[str, Any] = Field(default_factory=dict)
    secrets: dict[str, Any] | None = None

    model_config = ConfigDict(populate_by_name=True)


class SpeechProviderProfileUpsert(BaseModel):
    id: str | None = None
    label: str | None = None
    provider_id: str | None = Field(..., alias="providerId")
    settings: dict[str, Any] = Field(default_factory=dict)
    secrets: dict[str, Any] | None = None
    is_default: bool | None = Field(default=None, alias="isDefault")
    allow_voice_clone: bool | None = Field(default=None, alias="allowVoiceClone")

    model_config = ConfigDict(populate_by_name=True)


class SpeechBargeInConfig(BaseModel):
    """Barge-in / interrupt configuration (optional, future runtime)"""

    enabled: bool = True
    mode: Literal["vad_onset", "asr_text", "stop_words", "client_abort"] = Field(
        "vad_onset",
        description="Interrupt trigger strategy",
    )
    stop_words: list[str] = Field(default_factory=list, alias="stopWords")
    wake_words: list[str] = Field(default_factory=list, alias="wakeWords")

    model_config = ConfigDict(populate_by_name=True)


class SpeechTenantConfigView(BaseModel):
    """Speech config returned to client (secrets masked)"""

    enabled: bool = True
    status: str = "active"
    tts: SpeechProviderSelection | None = None
    tts_profiles: list[SpeechProviderProfileView] = Field(default_factory=list, alias="ttsProfiles")
    default_tts_profile_id: str | None = Field(None, alias="defaultTtsProfileId")
    stt: SpeechProviderSelection | None = Field(default=None, validation_alias=AliasChoices("stt", "asr"))
    barge_in: SpeechBargeInConfig | None = Field(default=None, alias="bargeIn")

    secrets_set: dict[str, Any] = Field(default_factory=dict, alias="secretsSet")

    model_config = ConfigDict(populate_by_name=True)

    @computed_field(alias="isActive", return_type=bool)
    @property
    def is_active(self) -> bool:
        return bool(self.enabled)


class SpeechTenantConfigUpsertRequest(BaseModel):
    """Upsert speech tenant config"""

    enabled: bool | None = Field(default=None, validation_alias=AliasChoices("enabled", "isActive"))
    status: str | None = None
    tts: SpeechProviderSelectionUpsert | None = None
    tts_profiles: list[SpeechProviderProfileUpsert] | None = Field(default=None, alias="ttsProfiles")
    default_tts_profile_id: str | None = Field(default=None, alias="defaultTtsProfileId")
    stt: SpeechProviderSelectionUpsert | None = Field(default=None, validation_alias=AliasChoices("stt", "asr"))
    barge_in: SpeechBargeInConfig | None = Field(default=None, alias="bargeIn")

    model_config = ConfigDict(populate_by_name=True)


# ===================== Demo / Playground =====================


class SpeechTtsDemoRequest(BaseModel):
    """
    TTS 演示请求。

    - 默认使用租户已配置的 TTS provider；若未配置，则回退到 edge_tts
    - 可通过 providerId/settings 覆盖（不写入数据库）
    """

    text: str = Field(..., min_length=1, max_length=2000)
    provider_id: str | None = Field(None, alias="providerId")
    settings: dict[str, Any] = Field(default_factory=dict)
    secrets: dict[str, Any] = Field(default_factory=dict)
    output_format: str | None = Field(None, alias="outputFormat", description="mp3/wav/opus (best-effort)")

    model_config = ConfigDict(populate_by_name=True)


class SpeechSttDemoResponse(BaseModel):
    """STT 演示响应（文字结果 + 运行信息）"""

    text: str
    provider_id: str = Field(..., alias="providerId")
    model: str | None = None
    language: str | None = None

    model_config = ConfigDict(populate_by_name=True)
