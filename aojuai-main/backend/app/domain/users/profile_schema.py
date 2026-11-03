"""
AOJU Backend - Tenant configurable user profile fields.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.tenant_config_namespaces import get_tenant_config_namespace, safe_tenant_config_dict

UserProfileFieldType = Literal["text", "textarea", "number", "select", "multi_select", "date", "boolean"]

_PROFILE_FIELD_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")


def normalize_profile_field_key(value: str | None) -> str:
    raw = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    raw = re.sub(r"_+", "_", raw)
    return raw


class UserProfileFieldOption(BaseModel):
    label: str = Field(..., min_length=1, max_length=100)
    value: str = Field(..., min_length=1, max_length=100)

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("label", "value")
    @classmethod
    def strip_text(cls, value: str) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("选项不能为空")
        return normalized


class UserProfileFieldDefinition(BaseModel):
    key: str = Field(..., min_length=2, max_length=64)
    label: str = Field(..., min_length=1, max_length=100)
    type: UserProfileFieldType = Field("text")
    required: bool = False
    enabled: bool = True
    placeholder: str | None = Field(None, max_length=200)
    help_text: str | None = Field(None, alias="helpText", max_length=500)
    options: list[UserProfileFieldOption] = Field(default_factory=list)
    list_visible: bool = Field(False, alias="listVisible")
    filterable: bool = False
    sort: int = Field(0, ge=0, le=10000)

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("key")
    @classmethod
    def validate_key(cls, value: str) -> str:
        normalized = normalize_profile_field_key(value)
        if not _PROFILE_FIELD_KEY_RE.match(normalized):
            raise ValueError("字段 key 仅支持小写字母、数字、下划线，且必须以字母开头")
        return normalized

    @field_validator("label")
    @classmethod
    def validate_label(cls, value: str) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("字段名称不能为空")
        return normalized

    @field_validator("placeholder", "help_text")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @model_validator(mode="after")
    def validate_options(self) -> "UserProfileFieldDefinition":
        if self.type in {"select", "multi_select"}:
            if not self.options:
                raise ValueError(f"字段 {self.label} 需要至少一个选项")
            seen: set[str] = set()
            for option in self.options:
                if option.value in seen:
                    raise ValueError(f"字段 {self.label} 存在重复选项值: {option.value}")
                seen.add(option.value)
        else:
            self.options = []
        return self


class UserProfileFieldsConfig(BaseModel):
    enabled: bool = Field(False, description="是否启用租户自定义用户资料字段")
    enforce_on_register: bool = Field(True, alias="enforceOnRegister", description="注册时强制填写必填项")
    enforce_after_login: bool = Field(True, alias="enforceAfterLogin", description="登录后强制补齐必填项")
    version: int = Field(1, ge=1, le=100000, description="字段配置版本")
    fields: list[UserProfileFieldDefinition] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("fields")
    @classmethod
    def validate_fields(cls, value: list[UserProfileFieldDefinition]) -> list[UserProfileFieldDefinition]:
        seen: set[str] = set()
        for item in value:
            if item.key in seen:
                raise ValueError(f"存在重复字段 key: {item.key}")
            seen.add(item.key)
        return sorted(value, key=lambda item: (item.sort, item.key))


class UserProfileCompletionState(BaseModel):
    enabled: bool = False
    schema_version: int = Field(1, alias="schemaVersion")
    completed: bool = True
    required_keys: list[str] = Field(default_factory=list, alias="requiredKeys")
    missing_required_keys: list[str] = Field(default_factory=list, alias="missingRequiredKeys")
    last_completed_at: str | None = Field(None, alias="lastCompletedAt")
    source: str | None = None

    model_config = ConfigDict(populate_by_name=True)


def get_user_profile_config(raw_config: Any) -> UserProfileFieldsConfig:
    source = getattr(raw_config, "config", raw_config)
    config = safe_tenant_config_dict(source)
    registration = get_tenant_config_namespace(config, ("registration",))
    raw_profile_fields = safe_tenant_config_dict(registration.get("userProfileFields"))
    return UserProfileFieldsConfig.model_validate(raw_profile_fields or {})


def get_enabled_user_profile_fields(
    config: UserProfileFieldsConfig,
    *,
    list_visible_only: bool = False,
    filterable_only: bool = False,
) -> list[UserProfileFieldDefinition]:
    fields = [field for field in config.fields if field.enabled]
    if list_visible_only:
        fields = [field for field in fields if field.list_visible]
    if filterable_only:
        fields = [field for field in fields if field.filterable]
    return sorted(fields, key=lambda item: (item.sort, item.key))


def build_user_profile_field_map(
    config: UserProfileFieldsConfig,
    *,
    list_visible_only: bool = False,
    filterable_only: bool = False,
) -> dict[str, UserProfileFieldDefinition]:
    return {
        field.key: field
        for field in get_enabled_user_profile_fields(
            config,
            list_visible_only=list_visible_only,
            filterable_only=filterable_only,
        )
    }


def _parse_number(value: Any) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("数值字段不能为布尔值")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else value

    text = str(value).strip()
    if not text:
        return None
    numeric = float(text)
    return int(numeric) if numeric.is_integer() else numeric


def _parse_boolean(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if not text:
        return None
    if text in {"true", "1", "yes", "y", "on"}:
        return True
    if text in {"false", "0", "no", "n", "off"}:
        return False
    raise ValueError("布尔字段仅支持 true/false")


def normalize_user_profile_value(field: UserProfileFieldDefinition, value: Any) -> Any:
    if field.type in {"text", "textarea"}:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    if field.type == "number":
        return _parse_number(value)

    if field.type == "date":
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        date.fromisoformat(text)
        return text

    if field.type == "boolean":
        return _parse_boolean(value)

    if field.type == "select":
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        allowed_values = {option.value for option in field.options}
        if allowed_values and text not in allowed_values:
            raise ValueError("选项不在允许范围内")
        return text

    if field.type == "multi_select":
        raw_items: list[Any]
        if value is None:
            return None
        if isinstance(value, list):
            raw_items = value
        else:
            text = str(value).strip()
            if not text:
                return None
            raw_items = [item.strip() for item in text.split(",")]

        normalized: list[str] = []
        seen: set[str] = set()
        allowed_values = {option.value for option in field.options}
        for item in raw_items:
            text = str(item).strip()
            if not text or text in seen:
                continue
            if allowed_values and text not in allowed_values:
                raise ValueError("选项不在允许范围内")
            seen.add(text)
            normalized.append(text)
        return normalized or None

    raise ValueError(f"Unsupported profile field type: {field.type}")


def is_profile_value_missing(field: UserProfileFieldDefinition, value: Any) -> bool:
    if value is None:
        return True
    if field.type in {"text", "textarea", "select", "date"}:
        return not str(value).strip()
    if field.type == "multi_select":
        return not isinstance(value, list) or len(value) == 0
    return False


def sanitize_user_profile_payload(
    profile: dict[str, Any] | None,
    config: UserProfileFieldsConfig,
) -> tuple[dict[str, Any], list[str]]:
    source = profile if isinstance(profile, dict) else {}
    field_map = build_user_profile_field_map(config)
    sanitized: dict[str, Any] = {}
    errors: list[str] = []

    for key, field in field_map.items():
        if key not in source:
            continue
        try:
            normalized = normalize_user_profile_value(field, source.get(key))
        except ValueError as exc:
            errors.append(f"{field.label}: {exc}")
            continue

        if normalized is not None:
            sanitized[key] = normalized

    return sanitized, errors


def build_user_profile_completion_state(
    config: UserProfileFieldsConfig,
    profile: dict[str, Any] | None,
    *,
    existing_meta: dict[str, Any] | None = None,
    source: str | None = None,
) -> UserProfileCompletionState:
    profile_dict = profile if isinstance(profile, dict) else {}
    required_fields = [field for field in get_enabled_user_profile_fields(config) if field.required]
    required_keys = [field.key for field in required_fields]
    missing_required_keys = [
        field.key
        for field in required_fields
        if is_profile_value_missing(field, profile_dict.get(field.key))
    ]
    completed = len(missing_required_keys) == 0
    meta = safe_tenant_config_dict(existing_meta)
    last_completed_at = meta.get("lastCompletedAt")
    if completed and not last_completed_at:
        last_completed_at = datetime.now(timezone.utc).isoformat()

    return UserProfileCompletionState(
        enabled=config.enabled,
        schemaVersion=config.version,
        completed=completed,
        requiredKeys=required_keys,
        missingRequiredKeys=missing_required_keys,
        lastCompletedAt=last_completed_at,
        source=source or str(meta.get("source") or "").strip() or None,
    )
