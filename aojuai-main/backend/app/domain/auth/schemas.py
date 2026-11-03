"""
AOJU Backend - Tenant Schemas
"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.tenant_config_namespaces import get_tenant_config_namespace, safe_tenant_config_dict
from app.domain.invitations.schemas import InvitationConfig
from app.domain.users.profile_schema import UserProfileFieldsConfig


def _default_feature_switches() -> dict[str, Any]:
    from app.core.feature_switches import build_default_feature_switches

    return build_default_feature_switches()


class RegistrationBasicFieldConfig(BaseModel):
    enabled: bool = Field(True, description="Whether the field is shown on the registration page")
    required: bool = Field(False, description="Whether the field is required on the registration page")

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def normalize_required_enabled(self) -> "RegistrationBasicFieldConfig":
        if self.required and not self.enabled:
            self.enabled = True
        return self


class RegistrationBasicFieldsConfig(BaseModel):
    nickname: RegistrationBasicFieldConfig = Field(
        default_factory=lambda: RegistrationBasicFieldConfig(enabled=False, required=False)
    )
    email: RegistrationBasicFieldConfig = Field(
        default_factory=lambda: RegistrationBasicFieldConfig(enabled=True, required=False)
    )
    phone: RegistrationBasicFieldConfig = Field(
        default_factory=lambda: RegistrationBasicFieldConfig(enabled=True, required=False)
    )

    model_config = ConfigDict(populate_by_name=True)


def get_registration_basic_fields_config(raw_config: Any) -> RegistrationBasicFieldsConfig:
    source = getattr(raw_config, "config", raw_config)
    config = safe_tenant_config_dict(source)
    registration = get_tenant_config_namespace(config, ("registration",))
    basic_fields = safe_tenant_config_dict(registration.get("basicFields"))
    return RegistrationBasicFieldsConfig.model_validate(basic_fields or {})


class RegistrationConfig(BaseModel):
    """Registration configuration"""
    enabled: bool = Field(True, description="Allow self-registration")
    require_audit: bool = Field(True, alias="requireAudit", description="Require audit for new registrations")
    default_role: str = Field("user", alias="defaultRole", description="Default role for new users")
    basic_fields: RegistrationBasicFieldsConfig = Field(
        default_factory=RegistrationBasicFieldsConfig,
        alias="basicFields",
        description="Visibility and required rules for built-in registration fields",
    )
    invitation: InvitationConfig = Field(default_factory=InvitationConfig, description="Invitation registration config")
    user_profile_fields: UserProfileFieldsConfig = Field(
        default_factory=UserProfileFieldsConfig,
        alias="userProfileFields",
        description="Tenant configurable custom profile fields",
    )

    model_config = ConfigDict(populate_by_name=True)


class SeoConfig(BaseModel):
    """Site SEO configuration"""
    title: str | None = Field(None, description="Site title (suffix in page title)")
    keywords: str | None = Field(None, description="Meta keywords (comma-separated)")
    description: str | None = Field(None, description="Meta description")


class TenantConfig(BaseModel):
    """Tenant configuration"""
    theme: str = "default"
    logo: str | None = None
    timezone: str = Field("UTC", description="Tenant timezone (IANA)")
    features: list[str] = []
    branding: dict[str, Any] = {}
    ai: dict[str, Any] = Field(default_factory=dict)
    seo: SeoConfig = Field(default_factory=SeoConfig)
    registration: RegistrationConfig = Field(default_factory=RegistrationConfig)
    verification: dict[str, Any] = Field(default_factory=dict)
    feature_switches: dict[str, Any] = Field(default_factory=_default_feature_switches, alias="featureSwitches")

    model_config = ConfigDict(populate_by_name=True)


class TenantQuota(BaseModel):
    """Tenant quota limits"""
    max_users: int = Field(100, alias="maxUsers")
    max_ai_apps: int = Field(10, alias="maxAiApps")
    max_ai_calls_per_month: int = Field(10000, alias="maxAiCallsPerMonth")
    storage_gb: int = Field(50, alias="storageGb")

    model_config = ConfigDict(populate_by_name=True)


class TenantBase(BaseModel):
    """Base tenant schema"""
    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=50)
    domain: str | None = None
    description: str | None = None
    contact_name: str | None = Field(None, alias="contactName")
    contact_phone: str | None = Field(None, alias="contactPhone")
    contact_email: str | None = Field(None, alias="contactEmail")

    model_config = ConfigDict(populate_by_name=True)


class TenantCreate(TenantBase):
    """Create tenant schema"""
    config: TenantConfig = Field(default_factory=TenantConfig)
    quota: TenantQuota = Field(default_factory=TenantQuota)
    is_active: bool = Field(True, alias="isActive")
    expires_at: datetime | None = Field(None, alias="expiresAt")

    model_config = ConfigDict(populate_by_name=True)


class TenantUpdate(BaseModel):
    """Update tenant schema"""
    name: str | None = Field(None, min_length=1, max_length=100)
    domain: str | None = None
    description: str | None = None
    contact_name: str | None = Field(None, alias="contactName")
    contact_phone: str | None = Field(None, alias="contactPhone")
    contact_email: str | None = Field(None, alias="contactEmail")
    config: TenantConfig | None = None
    quota: TenantQuota | None = None
    is_active: bool | None = Field(None, alias="isActive")
    expires_at: datetime | None = Field(None, alias="expiresAt")

    model_config = ConfigDict(populate_by_name=True)


class TenantResponse(BaseModel):
    """Tenant response schema"""
    id: int
    name: str
    code: str
    domain: str | None = None
    description: str | None = None
    is_active: bool = Field(True, alias="isActive")
    expires_at: datetime | None = Field(None, alias="expiresAt")
    config: dict[str, Any] = {}
    quota: dict[str, Any] = {}
    contact_name: str | None = Field(None, alias="contactName")
    contact_phone: str | None = Field(None, alias="contactPhone")
    contact_email: str | None = Field(None, alias="contactEmail")
    created_at: datetime | None = Field(None, alias="createdAt")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class TenantListItem(BaseModel):
    """Tenant list item"""
    id: int
    name: str
    code: str
    domain: str | None = None
    is_active: bool = Field(True, alias="isActive")
    expires_at: datetime | None = Field(None, alias="expiresAt")
    contact_name: str | None = Field(None, alias="contactName")
    contact_phone: str | None = Field(None, alias="contactPhone")
    contact_email: str | None = Field(None, alias="contactEmail")
    description: str | None = None
    config: dict[str, Any] = {}
    created_at: datetime | None = Field(None, alias="createdAt")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class TenantSimpleItem(BaseModel):
    """Simple tenant item for dropdown select"""
    id: int
    name: str
    code: str

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class RegistrationConfigUpdate(BaseModel):
    """Update registration config only"""
    enabled: bool | None = None
    require_audit: bool | None = Field(None, alias="requireAudit")
    default_role: str | None = Field(None, alias="defaultRole")
    basic_fields: RegistrationBasicFieldsConfig | None = Field(None, alias="basicFields")
    invitation: InvitationConfig | None = None
    user_profile_fields: UserProfileFieldsConfig | None = Field(None, alias="userProfileFields")

    model_config = ConfigDict(populate_by_name=True)


class InitialAdminCreate(BaseModel):
    """Initial admin account when creating tenant"""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=50)
    nickname: str | None = None
    email: str | None = None
    phone: str | None = None

    model_config = ConfigDict(populate_by_name=True)


class TenantCreateWithAdmin(TenantCreate):
    """Create tenant with optional initial admin"""
    initial_admin: InitialAdminCreate | None = Field(None, alias="initialAdmin")

    model_config = ConfigDict(populate_by_name=True)


class TenantUserItem(BaseModel):
    """Tenant user list item"""
    id: int
    username: str
    nickname: str | None = None
    email: str | None = None
    phone: str | None = None
    status: int = 1
    is_admin: bool = Field(False, alias="isAdmin")
    roles: list[str] = []
    created_at: datetime | None = Field(None, alias="createdAt")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)
