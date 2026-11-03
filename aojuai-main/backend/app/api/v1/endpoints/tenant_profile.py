"""
AOJU Backend - Tenant Profile Endpoints

Tenant self-management endpoints for tenant admins.
These endpoints allow tenant admins to view and update their own tenant settings.
"""
import json
import re
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.api.deps import CurrentTenantAdmin, CurrentUser, DBSession, TenantCtx
from app.core.exceptions import BusinessError, NotFoundError
from app.core.feature_switches import (
    is_module_installed,
    build_feature_catalog_definition,
    merge_feature_switches,
    normalize_feature_switches,
)
from app.core.logger import get_logger
from app.core.provider_secrets import (
    encrypt_provider_secret,
    normalize_provider_secret_text,
)
from app.core.redaction import RedactionPolicy
from app.core.response import ErrorResponse, SuccessResponse
from app.core.schemas import ResponseBase
from app.core.tenant_config_namespaces import (
    get_tenant_config_namespace,
    safe_tenant_config_dict,
    set_tenant_config_namespace,
)
from app.core.tenant_time import (
    DEFAULT_TENANT_TIMEZONE,
    normalize_tenant_timezone,
    validate_tenant_timezone,
)
from app.domain.assistant.config_schemas import AssistantConfigUpsertRequest
from app.domain.assistant_bridge import assistant_config_to_view, merge_assistant_config
from app.domain.ai_redaction import (
    get_active_policy_row,
    list_policy_versions,
    list_scopes,
    load_policy,
    normalize_scope,
    save_policy,
)
from app.domain.auth.config_security import sanitize_tenant_config
from app.domain.auth.schemas import (
    RegistrationConfigUpdate,
    TenantResponse,
    TenantSimpleItem,
    get_registration_basic_fields_config,
)
from app.domain.auth.service import TenantService
from app.domain.invitations.schemas import get_invitation_config
from app.domain.invitations.service import InvitationService
from app.domain.users.profile_schema import get_user_profile_config
from app.infrastructure.cache import (
    bump_site_public_config_cache_version,
    bump_tenant_ui_config_cache_version,
)
from app.infrastructure.cache.base_runtime_keys import (
    TENANT_RUNTIME_CACHE_TTL_SECONDS,
    build_tenant_feature_catalog_cache_key,
    build_tenant_feature_switches_cache_key,
    build_tenant_profile_cache_key,
    build_tenant_settings_cache_key,
    invalidate_tenant_runtime_cache,
)
from app.infrastructure.cache.runtime_cache import remember_json

router = APIRouter()
logger = get_logger(__name__)

EMAIL_TRANSPORT_PATH = ("messaging", "email")
LEGACY_EMAIL_TRANSPORT_PATH = ("verification", "email")
_SIMPLE_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _clean_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _contains_smtp_config(value: Any) -> bool:
    if isinstance(value, list):
        return any(_contains_smtp_config(child) for child in value)
    if not isinstance(value, dict):
        return False
    return any(
        key.lower() == "smtp" or _contains_smtp_config(child)
        for key, child in value.items()
    )


def _effective_email_transport(config: Any) -> dict[str, Any]:
    source = safe_tenant_config_dict(config)
    messaging = safe_tenant_config_dict(source.get("messaging"))
    if "email" in messaging:
        email = safe_tenant_config_dict(messaging.get("email"))
        return {
            "mode": str(email.get("mode") or "inherit").strip().lower(),
            "smtp": safe_tenant_config_dict(email.get("smtp")),
        }

    legacy = get_tenant_config_namespace(source, LEGACY_EMAIL_TRANSPORT_PATH)
    legacy_smtp = legacy.get("smtp")
    if isinstance(legacy_smtp, dict):
        return {"mode": "override", "smtp": dict(legacy_smtp)}
    return {"mode": "inherit", "smtp": {}}


def _smtp_security_for_view(smtp: dict[str, Any]) -> str:
    security = str(smtp.get("security") or "").strip().lower()
    use_ssl = bool(smtp.get("useSsl", smtp.get("use_ssl", False)))
    use_tls = bool(smtp.get("useTls", smtp.get("use_tls", False if security else not use_ssl)))
    if use_tls and use_ssl:
        raise BusinessError(
            message="SMTP useTls and useSsl cannot both be enabled",
            code="EMAIL_SMTP_INVALID",
        )
    if security in {"plain", "starttls", "ssl"}:
        if (use_tls and security != "starttls") or (use_ssl and security != "ssl"):
            raise BusinessError(
                message="SMTP security flags conflict",
                code="EMAIL_SMTP_INVALID",
            )
        return security
    if use_ssl:
        return "ssl"
    return "starttls" if use_tls else "plain"


def _smtp_view(email_transport: Any) -> dict[str, Any]:
    email = safe_tenant_config_dict(email_transport)
    smtp = safe_tenant_config_dict(email.get("smtp"))
    raw_port = smtp.get("port")
    raw_timeout = smtp.get("timeoutSeconds", smtp.get("timeout_seconds"))
    try:
        port = int(raw_port) if raw_port not in (None, "") else None
    except (TypeError, ValueError):
        port = None
    try:
        timeout = float(raw_timeout) if raw_timeout not in (None, "") else None
    except (TypeError, ValueError):
        timeout = None

    password_set = any(
        bool(normalize_provider_secret_text(smtp.get(key)))
        for key in ("passwordEncrypted", "password_encrypted", "password")
    )
    return {
        "mode": str(email.get("mode") or "inherit").strip().lower(),
        "smtp": {
            "host": _clean_optional_text(smtp.get("host")),
            "port": port,
            "username": _clean_optional_text(smtp.get("username")),
            "senderEmail": _clean_optional_text(
                smtp.get("senderEmail") or smtp.get("sender_email") or smtp.get("from")
            ),
            "senderName": _clean_optional_text(smtp.get("senderName") or smtp.get("sender_name")),
            "security": _smtp_security_for_view(smtp),
            "timeoutSeconds": timeout,
            "passwordSet": password_set,
        },
    }


def _canonical_smtp_storage(smtp_value: Any) -> dict[str, Any]:
    smtp = safe_tenant_config_dict(smtp_value)
    canonical: dict[str, Any] = {}
    aliases = {
        "host": smtp.get("host"),
        "port": smtp.get("port"),
        "username": smtp.get("username"),
        "senderEmail": smtp.get("senderEmail") or smtp.get("sender_email") or smtp.get("from"),
        "senderName": smtp.get("senderName") or smtp.get("sender_name"),
        "security": _smtp_security_for_view(smtp),
        "timeoutSeconds": smtp.get("timeoutSeconds", smtp.get("timeout_seconds")),
    }
    for key, value in aliases.items():
        if value not in (None, ""):
            canonical[key] = value

    encrypted = normalize_provider_secret_text(smtp.get("passwordEncrypted"))
    legacy_plaintext = normalize_provider_secret_text(smtp.get("password"))
    if encrypted:
        canonical["passwordEncrypted"] = encrypted
    elif legacy_plaintext:
        canonical["passwordEncrypted"] = encrypt_provider_secret(legacy_plaintext)
    return canonical


def _normalize_tenant_config(raw_config: Any) -> dict[str, Any]:
    config = sanitize_tenant_config(raw_config)
    config["timezone"] = normalize_tenant_timezone(
        config.get("timezone"),
        default=DEFAULT_TENANT_TIMEZONE,
    )
    config["assistant"] = assistant_config_to_view(config.get("assistant"))
    registration = get_tenant_config_namespace(config, ("registration",))
    registration["basicFields"] = get_registration_basic_fields_config(config).model_dump(by_alias=True)
    registration["invitation"] = get_invitation_config(config).model_dump(by_alias=True)
    registration["userProfileFields"] = get_user_profile_config(config).model_dump(by_alias=True)
    config = set_tenant_config_namespace(config, ("registration",), registration)
    feature_switches = normalize_feature_switches(config)
    config["feature_switches"] = feature_switches
    config["featureSwitches"] = feature_switches
    # speech 是可动态卸载的能力：没装就不 import 它、也不渲染它的视图。
    if is_module_installed("speech"):
        from app.domain.speech.service import SpeechConfigService

        config["speech"] = SpeechConfigService.to_legacy_view(config.get("speech"))
    return config


def _build_feature_switch_catalog(config: dict[str, Any] | None) -> dict[str, Any]:
    normalized = normalize_feature_switches(config)
    return {
        **build_feature_catalog_definition(),
        "featureSwitches": normalized,
        "feature_switches": normalized,
    }


# ============== Schemas ==============


class TenantProfileUpdate(BaseModel):
    """Update tenant profile (limited fields for tenant admin)"""
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    contact_name: str | None = Field(None, alias="contactName")
    contact_phone: str | None = Field(None, alias="contactPhone")
    contact_email: str | None = Field(None, alias="contactEmail")

    model_config = ConfigDict(populate_by_name=True)


THEME_PRESET_KEYS = {"indigo", "blue", "cyan", "emerald", "orange", "rose", "violet", "slate"}


class TenantAppearanceUpdate(BaseModel):
    """Tenant appearance settings (theme color etc.)"""
    primary_color: str | None = Field(
        None,
        validation_alias=AliasChoices("primaryColor", "primary_color"),
        serialization_alias="primaryColor",
        max_length=32,
        description="Theme primary color preset key",
    )

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("primary_color")
    @classmethod
    def validate_primary_color(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return value
        normalized = value.strip().lower()
        if normalized not in THEME_PRESET_KEYS:
            raise ValueError(f"primaryColor 仅支持: {', '.join(sorted(THEME_PRESET_KEYS))}")
        return normalized

    default_locale: str | None = Field(
        None,
        validation_alias=AliasChoices("defaultLocale", "default_locale"),
        serialization_alias="defaultLocale",
        max_length=16,
        description="Tenant default UI locale",
    )

    @field_validator("default_locale")
    @classmethod
    def validate_default_locale(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return value
        normalized = value.strip()
        if normalized not in {"zh-CN", "en-US", "es-ES"}:
            raise ValueError("defaultLocale 仅支持: zh-CN, en-US, es-ES")
        return normalized


class TenantSeoUpdate(BaseModel):
    """Tenant site SEO settings"""
    title: str | None = Field(
        None,
        max_length=200,
        description="Site title (suffix in page title)",
    )
    keywords: str | None = Field(
        None,
        max_length=500,
        description="Meta keywords (comma-separated)",
    )
    description: str | None = Field(
        None,
        max_length=1000,
        description="Meta description",
    )


class TenantSettingsUpdate(BaseModel):
    """Update tenant settings (config)"""
    theme: str | None = None
    logo: str | None = None
    timezone: str | None = Field(None, description="Tenant timezone (IANA)")
    registration: RegistrationConfigUpdate | None = None
    assistant: AssistantConfigUpsertRequest | None = None
    speech: dict[str, Any] | None = None
    verification: dict[str, Any] | None = None
    messaging: dict[str, Any] | None = None
    feature_switches: dict[str, Any] | None = Field(None, alias="featureSwitches")
    seo: TenantSeoUpdate | None = None
    appearance: TenantAppearanceUpdate | None = None

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("timezone")
    @classmethod
    def validate_timezone_value(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_tenant_timezone(value)

    @field_validator("verification", "messaging")
    @classmethod
    def reject_generic_smtp_writes(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if _contains_smtp_config(value):
            raise ValueError("SMTP settings must be updated through /email-config")
        return value


class TenantEmailSmtpUpdate(BaseModel):
    """Patch fields for tenant SMTP; plaintext password is write-only."""

    host: str | None = Field(None, max_length=255)
    port: int | None = Field(None, ge=1, le=65535)
    username: str | None = Field(None, max_length=255)
    password: str | None = Field(None, max_length=500)
    sender_email: str | None = Field(
        None,
        validation_alias=AliasChoices("senderEmail", "sender_email", "from"),
        serialization_alias="senderEmail",
        max_length=255,
    )
    sender_name: str | None = Field(
        None,
        validation_alias=AliasChoices("senderName", "sender_name"),
        serialization_alias="senderName",
        max_length=255,
    )
    security: Literal["plain", "starttls", "ssl"] | None = None
    timeout_seconds: float | None = Field(
        None,
        validation_alias=AliasChoices("timeoutSeconds", "timeout_seconds"),
        serialization_alias="timeoutSeconds",
        gt=0,
    )
    use_tls: bool | None = Field(None, validation_alias=AliasChoices("useTls", "use_tls"))
    use_ssl: bool | None = Field(None, validation_alias=AliasChoices("useSsl", "use_ssl"))

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    @field_validator("sender_email")
    @classmethod
    def validate_sender_email(cls, value: str | None) -> str | None:
        normalized = _clean_optional_text(value)
        if normalized and not _SIMPLE_EMAIL_RE.fullmatch(normalized):
            raise ValueError("senderEmail is not a valid email address")
        return value

    @model_validator(mode="after")
    def validate_security_aliases(self) -> "TenantEmailSmtpUpdate":
        if self.use_tls is True and self.use_ssl is True:
            raise ValueError("useTls and useSsl cannot both be enabled")
        if self.security and self.use_tls is True and self.security != "starttls":
            raise ValueError("security conflicts with useTls")
        if self.security and self.use_ssl is True and self.security != "ssl":
            raise ValueError("security conflicts with useSsl")
        return self


class TenantEmailConfigUpdate(BaseModel):
    mode: Literal["inherit", "override", "disabled"] | None = None
    smtp: TenantEmailSmtpUpdate | None = None

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class TenantEmailSmtpView(BaseModel):
    host: str | None = None
    port: int | None = None
    username: str | None = None
    sender_email: str | None = Field(None, alias="senderEmail")
    sender_name: str | None = Field(None, alias="senderName")
    security: Literal["plain", "starttls", "ssl"] = "starttls"
    timeout_seconds: float | None = Field(None, alias="timeoutSeconds")
    password_set: bool = Field(False, alias="passwordSet")

    model_config = ConfigDict(populate_by_name=True)


class TenantEmailConfigView(BaseModel):
    mode: Literal["inherit", "override", "disabled"] = "inherit"
    smtp: TenantEmailSmtpView = Field(default_factory=TenantEmailSmtpView)

    model_config = ConfigDict(populate_by_name=True)


def _merge_email_transport_update(
    existing: dict[str, Any],
    data: TenantEmailConfigUpdate,
) -> dict[str, Any]:
    email = {
        "mode": str(existing.get("mode") or "inherit").strip().lower(),
        "smtp": _canonical_smtp_storage(existing.get("smtp")),
    }
    if data.mode is not None:
        email["mode"] = data.mode

    if data.smtp is None:
        return email

    smtp = safe_tenant_config_dict(email.get("smtp"))
    incoming = data.smtp
    fields_set = incoming.model_fields_set
    text_fields = {
        "host": "host",
        "username": "username",
        "sender_email": "senderEmail",
        "sender_name": "senderName",
    }
    for field_name, stored_key in text_fields.items():
        if field_name not in fields_set:
            continue
        value = _clean_optional_text(getattr(incoming, field_name))
        if value is None:
            smtp.pop(stored_key, None)
        else:
            smtp[stored_key] = value

    if "port" in fields_set:
        if incoming.port is None:
            smtp.pop("port", None)
        else:
            smtp["port"] = incoming.port

    if "timeout_seconds" in fields_set:
        if incoming.timeout_seconds is None:
            smtp.pop("timeoutSeconds", None)
        else:
            smtp["timeoutSeconds"] = incoming.timeout_seconds

    if "security" in fields_set:
        if incoming.security is None:
            smtp.pop("security", None)
        else:
            smtp["security"] = incoming.security
    elif "use_tls" in fields_set or "use_ssl" in fields_set:
        use_tls = bool(incoming.use_tls)
        use_ssl = bool(incoming.use_ssl)
        smtp["security"] = "ssl" if use_ssl else "starttls" if use_tls else "plain"

    if "password" in fields_set:
        password = normalize_provider_secret_text(incoming.password)
        if password:
            smtp["passwordEncrypted"] = encrypt_provider_secret(password)
        else:
            smtp.pop("passwordEncrypted", None)

    email["smtp"] = _canonical_smtp_storage(smtp)
    return email


class TenantSpeechPreviewSecrets(BaseModel):
    api_key: str | None = Field(None, alias="apiKey")
    auth_header_value: str | None = Field(None, alias="authHeaderValue")

    model_config = ConfigDict(populate_by_name=True)


class TenantSpeechPreviewCustomHttpConfig(BaseModel):
    endpoint: str | None = None
    method: str | None = None
    headers_template: str | dict[str, Any] | None = Field(None, alias="headersTemplate")
    body_template: str | dict[str, Any] | None = Field(None, alias="bodyTemplate")
    response_mode: str | None = Field(None, alias="responseMode")
    response_path: str | None = Field(None, alias="responsePath")
    audio_content_type: str | None = Field(None, alias="audioContentType")
    timeout_seconds: float | None = Field(None, alias="timeoutSeconds")
    secrets: TenantSpeechPreviewSecrets | None = None

    model_config = ConfigDict(populate_by_name=True)


class TenantSpeechPreviewTtsConfig(BaseModel):
    mode: str | None = None
    default_voice: str | None = Field(None, alias="defaultVoice")
    custom_http: TenantSpeechPreviewCustomHttpConfig | None = Field(None, alias="customHttp")

    model_config = ConfigDict(populate_by_name=True)


class TenantSpeechPreviewRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    voice: str | None = None
    tts: TenantSpeechPreviewTtsConfig | None = None

    model_config = ConfigDict(populate_by_name=True)


class TenantAIRedactionPolicyUpdate(BaseModel):
    scope: str = "*"
    level: Literal["off", "basic", "standard", "strict", "custom"]
    rules: dict[str, Any] | None = None
    approved_by: str = Field(..., alias="approvedBy", min_length=1, max_length=64)
    note: str = Field(default="", max_length=2000)

    model_config = ConfigDict(populate_by_name=True)


def _compose_ai_redaction_rules(data: TenantAIRedactionPolicyUpdate) -> dict[str, Any]:
    overrides = dict(data.rules or {})
    if data.level == "custom":
        # 签字信息只能来自请求顶层，不能藏在高级 JSON 里覆盖审计字段。
        for key in ("approvedBy", "approvedAt", "note"):
            overrides.pop(key, None)
        overrides["level"] = "custom"
        overrides.setdefault("baseLevel", "standard")
        return RedactionPolicy.from_json(overrides).to_json()

    allowed = {"allowTerms", "fieldRules"}
    disallowed = sorted(set(overrides) - allowed)
    if disallowed:
        raise BusinessError(
            message=(
                f"{data.level} 档只允许覆盖 allowTerms 与 fieldRules；"
                f"不允许的键: {', '.join(disallowed)}"
            )
        )
    payload = RedactionPolicy.preset(data.level).to_json()
    payload.update(overrides)
    return RedactionPolicy.from_json(payload).to_json()


def _ai_redaction_policy_view(
    policy: RedactionPolicy, *, rules: dict[str, Any] | None = None
) -> dict[str, Any]:
    serialized = dict(rules) if rules is not None else policy.to_json()
    return {
        "version": policy.version,
        "level": policy.level,
        "rules": serialized,
        "approvedBy": policy.approved_by,
        "approvedAt": policy.approved_at,
        "note": policy.note,
    }


async def _ai_redaction_settings_payload(
    db: DBSession, *, tenant_id: int, scope: str
) -> dict[str, Any]:
    active_row = await get_active_policy_row(db, tenant_id=tenant_id, scope=scope)
    active = None
    if active_row is not None:
        active_rules = dict(active_row.rules or {})
        active_policy = RedactionPolicy.from_json(active_rules, version=active_row.version)
        active = _ai_redaction_policy_view(active_policy, rules=active_rules)
        active["approvedBy"] = active_row.approved_by
        active["approvedAt"] = str(
            active_rules.get("approvedAt")
            or (active_row.created_at.isoformat() if active_row.created_at else "")
        )
        active["note"] = active_row.note or ""

    effective_policy = await load_policy(db, tenant_id=tenant_id, scope=scope)
    return {
        "scope": scope,
        "scopes": await list_scopes(db, tenant_id=tenant_id),
        "active": active,
        "effective": _ai_redaction_policy_view(effective_policy),
        "presets": {
            level: RedactionPolicy.preset(level).to_json()
            for level in ("basic", "standard", "strict")
        },
    }


def _parse_preview_json_object(value: str | dict[str, Any] | None, *, label: str) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value

    raw = str(value).strip()
    if not raw:
        return {}

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BusinessError(message=f"{label} 不是合法 JSON") from exc

    if not isinstance(payload, dict):
        raise BusinessError(message=f"{label} 必须是 JSON 对象")

    return payload


# ============== Endpoints ==============


@router.get("", response_model=ResponseBase[TenantResponse | TenantSimpleItem])
async def get_tenant_profile(
    current_user: CurrentTenantAdmin,
    tenant_ctx: TenantCtx,
    db: DBSession,
    view: str | None = Query(default=None),
) -> dict[str, Any]:
    """
    Get current tenant profile (tenant admin).
    """
    _ = current_user
    normalized_view = "summary" if str(view or "").strip().lower() == "summary" else "detail"
    cache_key = build_tenant_profile_cache_key(tenant_ctx.tenant_id, view=normalized_view)

    async def _load_profile() -> dict[str, Any]:
        service = TenantService(db)
        tenant = await service.get_by_id(tenant_ctx.tenant_id)

        if not tenant:
            raise BusinessError(message="Tenant not found")

        if normalized_view == "summary":
            return {"id": tenant.id, "name": tenant.name, "code": tenant.code}

        response_data = TenantService.to_response(tenant)
        response_data["config"] = _normalize_tenant_config(response_data.get("config"))
        return response_data

    try:
        payload = await remember_json(
            cache_key,
            ttl_seconds=TENANT_RUNTIME_CACHE_TTL_SECONDS,
            loader=_load_profile,
        )
    except BusinessError:
        return ErrorResponse(message="Tenant not found", code="NOT_FOUND")

    return SuccessResponse(data=payload)


@router.put("", response_model=ResponseBase[TenantResponse])
async def update_tenant_profile(
    data: TenantProfileUpdate,
    current_user: CurrentTenantAdmin,
    tenant_ctx: TenantCtx,
    db: DBSession,
) -> dict[str, Any]:
    """
    Update current tenant profile (tenant admin).

    Tenant admins can update basic info like name, description, contact info.
    """
    service = TenantService(db)
    tenant = await service.get_by_id(tenant_ctx.tenant_id)

    if not tenant:
        return ErrorResponse(message="Tenant not found", code="NOT_FOUND")

    # Update allowed fields using service method
    update_data = data.model_dump(exclude_unset=True)
    tenant = await service.update(tenant, update_data)
    await bump_site_public_config_cache_version()
    await invalidate_tenant_runtime_cache(tenant.id)

    return SuccessResponse(data=TenantService.to_response(tenant))


@router.get("/settings", response_model=ResponseBase[dict])
async def get_tenant_settings(
    current_user: CurrentTenantAdmin,
    tenant_ctx: TenantCtx,
    db: DBSession,
) -> dict[str, Any]:
    """
    Get current tenant settings/config (tenant admin).
    """
    _ = current_user
    cache_key = build_tenant_settings_cache_key(tenant_ctx.tenant_id)

    async def _load_settings() -> dict[str, Any]:
        service = TenantService(db)
        tenant = await service.get_by_id(tenant_ctx.tenant_id)

        if not tenant:
            raise BusinessError(message="Tenant not found")

        return {
            "config": _normalize_tenant_config(tenant.config),
            "quota": tenant.quota,
        }

    try:
        payload = await remember_json(
            cache_key,
            ttl_seconds=TENANT_RUNTIME_CACHE_TTL_SECONDS,
            loader=_load_settings,
        )
    except BusinessError:
        return ErrorResponse(message="Tenant not found", code="NOT_FOUND")

    return SuccessResponse(data=payload)


@router.get("/email-config", response_model=ResponseBase[TenantEmailConfigView])
async def get_tenant_email_config(
    current_user: CurrentTenantAdmin,
    tenant_ctx: TenantCtx,
    db: DBSession,
) -> dict[str, Any]:
    """Get tenant SMTP transport settings without returning a password value."""
    _ = current_user
    service = TenantService(db)
    tenant = await service.get_by_id(tenant_ctx.tenant_id)
    if not tenant:
        return ErrorResponse(message="Tenant not found", code="NOT_FOUND")

    view = TenantEmailConfigView.model_validate(_smtp_view(_effective_email_transport(tenant.config)))
    return SuccessResponse(data=view.model_dump(by_alias=True))


@router.patch("/email-config", response_model=ResponseBase[TenantEmailConfigView])
async def update_tenant_email_config(
    data: TenantEmailConfigUpdate,
    current_user: CurrentTenantAdmin,
    tenant_ctx: TenantCtx,
    db: DBSession,
) -> dict[str, Any]:
    """Safely merge tenant SMTP settings and encrypt a supplied password immediately."""
    _ = current_user
    service = TenantService(db)
    tenant = await service.get_by_id(tenant_ctx.tenant_id)
    if not tenant:
        return ErrorResponse(message="Tenant not found", code="NOT_FOUND")

    config = safe_tenant_config_dict(tenant.config)
    existing = _effective_email_transport(config)
    email_transport = _merge_email_transport_update(existing, data)
    config = set_tenant_config_namespace(config, EMAIL_TRANSPORT_PATH, email_transport)

    tenant = await service.update(tenant, {"config": config})
    await bump_tenant_ui_config_cache_version(tenant_ctx.tenant_id)
    await bump_site_public_config_cache_version()
    await invalidate_tenant_runtime_cache(tenant.id)

    saved_email = get_tenant_config_namespace(
        safe_tenant_config_dict(tenant.config),
        EMAIL_TRANSPORT_PATH,
    )
    view = TenantEmailConfigView.model_validate(_smtp_view(saved_email))
    return SuccessResponse(data=view.model_dump(by_alias=True))


@router.get("/settings/ai-redaction", response_model=ResponseBase[dict[str, Any]])
async def get_tenant_ai_redaction_settings(
    current_user: CurrentTenantAdmin,
    tenant_ctx: TenantCtx,
    db: DBSession,
    scope: str = Query(default="*"),
) -> dict[str, Any]:
    """读取当前租户某个 scope 的显式策略、生效策略和内置预设。"""
    _ = current_user
    normalized_scope = normalize_scope(scope)
    payload = await _ai_redaction_settings_payload(
        db, tenant_id=tenant_ctx.tenant_id, scope=normalized_scope
    )
    return SuccessResponse(data=payload)


@router.put("/settings/ai-redaction", response_model=ResponseBase[dict[str, Any]])
async def update_tenant_ai_redaction_settings(
    data: TenantAIRedactionPolicyUpdate,
    current_user: CurrentTenantAdmin,
    tenant_ctx: TenantCtx,
    db: DBSession,
) -> dict[str, Any]:
    """签字保存一个只追加的新版本；非 custom 档只接受字段规则和允许词覆盖。"""
    scope = normalize_scope(data.scope)
    rules = _compose_ai_redaction_rules(data)
    row = await save_policy(
        db,
        tenant_id=tenant_ctx.tenant_id,
        scope=scope,
        rules=rules,
        approved_by=data.approved_by,
        note=data.note,
    )
    await db.commit()
    logger.info(
        "ai_redaction_policy_updated",
        tenant_id=tenant_ctx.tenant_id,
        user_id=current_user.id,
        scope=scope,
        version=row.version,
        level=rules["level"],
    )
    payload = await _ai_redaction_settings_payload(
        db, tenant_id=tenant_ctx.tenant_id, scope=scope
    )
    return SuccessResponse(data=payload, message="AI 出站脱敏策略已更新")


@router.get("/settings/ai-redaction/versions", response_model=ResponseBase[list[dict[str, Any]]])
async def get_tenant_ai_redaction_versions(
    current_user: CurrentTenantAdmin,
    tenant_ctx: TenantCtx,
    db: DBSession,
    scope: str = Query(default="*"),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    """按版本倒序返回某 scope 的签字历史。"""
    _ = current_user
    rows = await list_policy_versions(
        db,
        tenant_id=tenant_ctx.tenant_id,
        scope=normalize_scope(scope),
        limit=limit,
    )
    versions: list[dict[str, Any]] = []
    for row in rows:
        rules = dict(row.rules or {})
        policy = RedactionPolicy.from_json(rules, version=row.version)
        item = _ai_redaction_policy_view(policy, rules=rules)
        item["approvedBy"] = row.approved_by
        item["approvedAt"] = str(
            rules.get("approvedAt") or (row.created_at.isoformat() if row.created_at else "")
        )
        item["note"] = row.note or ""
        versions.append(item)
    return SuccessResponse(data=versions)


@router.get("/settings/feature-catalog", response_model=ResponseBase[dict])
async def get_tenant_feature_catalog(
    current_user: CurrentTenantAdmin,
    tenant_ctx: TenantCtx,
    db: DBSession,
) -> dict[str, Any]:
    """Get plugin-style feature switch catalog with current tenant values."""
    _ = current_user
    cache_key = build_tenant_feature_catalog_cache_key(tenant_ctx.tenant_id)

    async def _load_feature_catalog() -> dict[str, Any]:
        service = TenantService(db)
        tenant = await service.get_by_id(tenant_ctx.tenant_id)

        if not tenant:
            raise BusinessError(message="Tenant not found")

        tenant_config = _normalize_tenant_config(tenant.config)
        return _build_feature_switch_catalog(tenant_config)

    try:
        payload = await remember_json(
            cache_key,
            ttl_seconds=TENANT_RUNTIME_CACHE_TTL_SECONDS,
            loader=_load_feature_catalog,
        )
    except BusinessError:
        return ErrorResponse(message="Tenant not found", code="NOT_FOUND")

    return SuccessResponse(data=payload)


@router.get("/feature-switches", response_model=ResponseBase[dict])
async def get_runtime_feature_switches(
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    db: DBSession,
) -> dict[str, Any]:
    """Get normalized runtime feature switches for the active target tenant."""
    _ = current_user
    cache_key = build_tenant_feature_switches_cache_key(tenant_ctx.tenant_id)

    async def _load_feature_switches() -> dict[str, Any]:
        service = TenantService(db)
        tenant = await service.get_by_id(tenant_ctx.tenant_id)

        if not tenant:
            raise BusinessError(message="Tenant not found")

        feature_switches = normalize_feature_switches(safe_tenant_config_dict(tenant.config))
        return {
            "tenantId": tenant.id,
            "featureSwitches": feature_switches,
            "feature_switches": feature_switches,
        }

    try:
        payload = await remember_json(
            cache_key,
            ttl_seconds=TENANT_RUNTIME_CACHE_TTL_SECONDS,
            loader=_load_feature_switches,
        )
    except BusinessError:
        return ErrorResponse(message="Tenant not found", code="NOT_FOUND")

    return SuccessResponse(data=payload)


@router.patch("/settings", response_model=ResponseBase[TenantResponse])
@router.put("/settings", response_model=ResponseBase[TenantResponse])
async def update_tenant_settings(
    data: TenantSettingsUpdate,
    current_user: CurrentTenantAdmin,
    tenant_ctx: TenantCtx,
    db: DBSession,
) -> dict[str, Any]:
    """
    Update current tenant settings (tenant admin).

    Tenant admins can update:
    - theme: UI theme
    - logo: Logo URL
    - registration: Registration settings (enabled, requireAudit, defaultRole)
    """
    service = TenantService(db)
    tenant = await service.get_by_id(tenant_ctx.tenant_id)

    if not tenant:
        return ErrorResponse(message="Tenant not found", code="NOT_FOUND")

    # Get current config
    config = safe_tenant_config_dict(tenant.config)
    feature_switches = normalize_feature_switches(config)

    # Update config fields
    if data.theme is not None:
        config["theme"] = data.theme
    if data.logo is not None:
        config["logo"] = data.logo
    if data.timezone is not None:
        try:
            config["timezone"] = validate_tenant_timezone(data.timezone)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    if data.assistant is not None:
        config["assistant"] = merge_assistant_config(
            config.get("assistant"),
            data.assistant.model_dump(by_alias=True, exclude_none=True),
        )

    if data.speech is not None:
        if not is_module_installed("speech"):
            raise NotFoundError()
        from app.domain.speech.service import SpeechConfigService

        config["speech"] = SpeechConfigService.merge(config.get("speech"), data.speech)

    if data.messaging is not None:
        messaging = get_tenant_config_namespace(config, ("messaging",))
        for key, value in data.messaging.items():
            if isinstance(value, dict) and isinstance(messaging.get(key), dict):
                messaging[key] = {**dict(messaging.get(key, {})), **value}
            else:
                messaging[key] = value
        config = set_tenant_config_namespace(config, ("messaging",), messaging)

    # Update registration settings
    if data.registration is not None:
        registration = get_tenant_config_namespace(config, ("registration",))
        incoming_registration = data.registration.model_dump(exclude_unset=True, by_alias=True)
        for key, value in incoming_registration.items():
            registration[key] = value
        config = set_tenant_config_namespace(config, ("registration",), registration)

    # Update module/feature switches
    if data.feature_switches is not None:
        feature_switches = merge_feature_switches(
            config=config,
            incoming=data.feature_switches,
        )

    # Update verification settings (sms/email/code)
    if data.verification is not None:
        verification = get_tenant_config_namespace(config, ("verification",))
        incoming = dict(data.verification)
        for k, v in incoming.items():
            if isinstance(v, dict) and isinstance(verification.get(k), dict):
                verification[k] = {**dict(verification.get(k, {})), **v}
            else:
                verification[k] = v
        config = set_tenant_config_namespace(config, ("verification",), verification)

        sms_cfg = verification.get("sms") if isinstance(verification.get("sms"), dict) else {}
        email_cfg = verification.get("email") if isinstance(verification.get("email"), dict) else {}
        if "enabled" in sms_cfg:
            feature_switches["capabilities"]["verification_sms"] = bool(sms_cfg.get("enabled"))
        if "enabled" in email_cfg:
            feature_switches["capabilities"]["verification_email"] = bool(email_cfg.get("enabled"))

    # Sync capability switches into verification channel config
    verification = get_tenant_config_namespace(config, ("verification",))
    sms_cfg = dict(verification.get("sms") or {})
    email_cfg = dict(verification.get("email") or {})
    sms_cfg["enabled"] = bool(feature_switches["capabilities"].get("verification_sms", True))
    email_cfg["enabled"] = bool(feature_switches["capabilities"].get("verification_email", True))
    verification["sms"] = sms_cfg
    verification["email"] = email_cfg
    config = set_tenant_config_namespace(config, ("verification",), verification)
    config["feature_switches"] = feature_switches
    config["featureSwitches"] = feature_switches

    # Update SEO settings
    if data.seo is not None:
        seo = get_tenant_config_namespace(config, ("seo",))
        incoming = data.seo.model_dump(exclude_unset=True)
        for k, v in incoming.items():
            seo[k] = v
        config = set_tenant_config_namespace(config, ("seo",), seo)

    # Update appearance settings (theme color)
    if data.appearance is not None:
        appearance = get_tenant_config_namespace(config, ("appearance",))
        incoming = data.appearance.model_dump(exclude_unset=True, by_alias=True)
        for k, v in incoming.items():
            if v in (None, ""):
                appearance.pop(k, None)
            else:
                appearance[k] = v
        config = set_tenant_config_namespace(config, ("appearance",), appearance)

    # Use service method to update config
    tenant = await service.update(tenant, {"config": config})
    await bump_tenant_ui_config_cache_version(tenant_ctx.tenant_id)
    await bump_site_public_config_cache_version()
    await invalidate_tenant_runtime_cache(tenant.id)

    response_data = TenantService.to_response(tenant)
    response_data["config"] = _normalize_tenant_config(response_data.get("config"))
    return SuccessResponse(data=response_data)


@router.post("/settings/speech/preview-tts")
async def preview_tenant_speech_tts(
    data: TenantSpeechPreviewRequest,
    current_user: CurrentTenantAdmin,
) -> StreamingResponse:
    _ = current_user
    if not is_module_installed("speech"):
        raise NotFoundError()
    from app.domain.speech.runtime import custom_http_tts_synthesize_stream

    tts = data.tts
    custom_http = tts.custom_http if tts else None
    mode = str(tts.mode or "").strip().lower() if tts else ""
    if mode != "custom_http" or custom_http is None:
        raise BusinessError(message="系统默认 TTS 预览请在前端使用浏览器语音能力")

    secrets = custom_http.secrets
    stream = await custom_http_tts_synthesize_stream(
        endpoint=str(custom_http.endpoint or ""),
        text=data.text,
        headers_template=_parse_preview_json_object(custom_http.headers_template, label="Headers Template"),
        payload_template=_parse_preview_json_object(custom_http.body_template, label="Body Template"),
        secret_key1=(str(secrets.api_key or "").strip() or None) if secrets else None,
        secret_key2=(str(secrets.auth_header_value or "").strip() or None) if secrets else None,
        timeout_seconds=float(custom_http.timeout_seconds or 60),
        method=custom_http.method,
        response_mode=custom_http.response_mode,
        response_path=custom_http.response_path,
        audio_content_type=custom_http.audio_content_type,
    )
    return StreamingResponse(
        stream.iterator,
        media_type=stream.media_type,
        headers={"Content-Disposition": f'inline; filename="speech-preview.{stream.file_ext}"'},
    )


@router.post("/invite-link")
async def generate_invite_link(
    current_user: CurrentTenantAdmin,
    tenant_ctx: TenantCtx,
    db: DBSession,
    expires_days: int = 30,
) -> dict[str, Any]:
    """
    Generate invite link for current tenant (tenant admin).

    The invite link can be shared to allow new users to register
    without manually entering the tenant code.
    """
    service = TenantService(db)
    tenant = await service.get_by_id(tenant_ctx.tenant_id)

    if not tenant:
        return ErrorResponse(message="Tenant not found", code="NOT_FOUND")

    invitation_service = InvitationService(db)
    invite_code = await invitation_service.generate_code(
        tenant=tenant,
        inviter_user=current_user,
        expires_days=expires_days,
    )

    return SuccessResponse(data=invitation_service.to_code_response(invite_code, tenant=tenant, expires_in=expires_days))
