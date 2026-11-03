"""
AOJU Backend - User Schemas
"""
from datetime import datetime
from typing import Any

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import settings
from app.domain.users.profile_schema import UserProfileCompletionState


PASSWORD_MAX_LENGTH = 50
PASSWORD_MIN_LENGTH = int(getattr(settings, "PASSWORD_MIN_LENGTH", 8) or 8)
PASSWORD_RULE_MESSAGE = (
    f"密码格式应为{PASSWORD_MIN_LENGTH}-{PASSWORD_MAX_LENGTH}位数字、字母、符号的任意两种组合"
)
_PASSWORD_CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")


def _validate_password_strength(password: str) -> str:
    if _PASSWORD_CHINESE_RE.search(password):
        raise ValueError("密码不能包含中文")

    has_digit = bool(re.search(r"\d", password))
    has_alpha = bool(re.search(r"[a-zA-Z]", password))
    has_symbol = bool(re.search(r"[^a-zA-Z0-9]", password))

    if (has_digit + has_alpha + has_symbol) < 2:
        raise ValueError(PASSWORD_RULE_MESSAGE)
    return password


class UserBase(BaseModel):
    """Base user schema"""
    username: str = Field(..., min_length=2, max_length=50)
    nickname: str | None = None
    email: str | None = None
    phone: str | None = None
    sex: int = Field(0, ge=0, le=2)
    description: str | None = Field(None, max_length=200)
    organization_id: int | None = Field(None, alias="organizationId")
    remark: str | None = Field(None, max_length=200)

    model_config = ConfigDict(populate_by_name=True)


class UserCreate(UserBase):
    """Create user schema (admin creates user)"""
    password: str = Field(..., min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)
    profile: dict[str, Any] | None = None
    role_ids: list[int] = Field(default_factory=list, alias="roleIds")
    group_ids: list[int] = Field(default_factory=list, alias="groupIds")
    team_ids: list[int] = Field(default_factory=list, alias="teamIds")
    status: int = Field(1, ge=0, le=3)
    # 系统管理员可以指定租户ID，租户管理员使用自己的租户
    tenant_id: int | None = Field(None, alias="tenantId")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password_strength(v)


class UserRegister(BaseModel):
    """User self-registration schema"""
    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)
    nickname: str | None = None
    email: str | None = None
    phone: str | None = None
    profile: dict[str, Any] | None = None
    tenant_code: str | None = Field(None, alias="tenantCode")
    invite_code: str | None = Field(None, alias="inviteCode")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not v.isalnum() and "_" not in v:
            raise ValueError("Username can only contain letters, numbers and underscores")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password_strength(v)


class UserUpdate(BaseModel):
    """Update user schema"""
    nickname: str | None = None
    email: str | None = None
    phone: str | None = None
    profile: dict[str, Any] | None = None
    sex: int | None = Field(None, ge=0, le=2)
    description: str | None = Field(None, max_length=200)
    organization_id: int | None = Field(None, alias="organizationId")
    status: int | None = Field(None, ge=0, le=3)
    remark: str | None = Field(None, max_length=200)
    role_ids: list[int] | None = Field(None, alias="roleIds")
    group_ids: list[int] | None = Field(None, alias="groupIds")
    team_ids: list[int] | None = Field(None, alias="teamIds")

    model_config = ConfigDict(populate_by_name=True)


class UserAudit(BaseModel):
    """Audit user registration schema"""
    approved: bool = Field(..., description="True=approve, False=reject")
    remark: str | None = Field(None, max_length=200, description="Audit remark")


class UserResponse(BaseModel):
    """User response schema"""
    id: int
    username: str
    nickname: str | None = None
    avatar: str | None = None
    email: str | None = None
    phone: str | None = None
    sex: int = 0
    status: int = 1
    description: str | None = None
    register_source: str | None = Field(None, alias="registerSource")
    organization_id: int | None = Field(None, alias="organizationId")
    remark: str | None = None
    created_at: datetime | None = Field(None, alias="createdAt")
    last_login_at: datetime | None = Field(None, alias="lastLoginAt")
    roles: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []
    organization: dict[str, Any] | None = None
    teams: list[dict[str, Any]] = []
    profile: dict[str, Any] = {}
    profile_meta: UserProfileCompletionState = Field(default_factory=UserProfileCompletionState, alias="profileMeta")
    must_complete_profile: bool = Field(False, alias="mustCompleteProfile")
    invited_by_user_id: int | None = Field(None, alias="invitedByUserId")
    invited_by_username: str | None = Field(None, alias="invitedByUsername")
    invited_by_nickname: str | None = Field(None, alias="invitedByNickname")
    invited_via_invite_code: str | None = Field(None, alias="invitedViaInviteCode")
    invited_at: datetime | None = Field(None, alias="invitedAt")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class UserListItem(BaseModel):
    """User list item schema"""
    id: int
    username: str
    nickname: str | None = None
    avatar: str | None = None
    email: str | None = None
    phone: str | None = None
    sex: int = 0
    status: int = 1
    register_source: str | None = Field(None, alias="registerSource")
    tenant_id: int | None = Field(None, alias="tenantId")
    tenant_name: str | None = Field(None, alias="tenantName")
    organization: dict[str, Any] | None = None
    teams: list[dict[str, Any]] = []
    roles: list[str] = []
    remark: str | None = None
    profile: dict[str, Any] = {}
    profile_meta: UserProfileCompletionState = Field(default_factory=UserProfileCompletionState, alias="profileMeta")
    created_at: datetime | None = Field(None, alias="createdAt")
    invited_by_user_id: int | None = Field(None, alias="invitedByUserId")
    invited_by_username: str | None = Field(None, alias="invitedByUsername")
    invited_by_nickname: str | None = Field(None, alias="invitedByNickname")
    invited_via_invite_code: str | None = Field(None, alias="invitedViaInviteCode")
    invited_at: datetime | None = Field(None, alias="invitedAt")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class PasswordChange(BaseModel):
    """Password change schema"""
    old_password: str = Field(..., alias="oldPassword")
    new_password: str = Field(
        ...,
        min_length=PASSWORD_MIN_LENGTH,
        max_length=PASSWORD_MAX_LENGTH,
        alias="newPassword",
    )

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        return _validate_password_strength(v)


class PasswordReset(BaseModel):
    """Password reset by admin"""
    new_password: str = Field(
        ...,
        min_length=PASSWORD_MIN_LENGTH,
        max_length=PASSWORD_MAX_LENGTH,
        alias="newPassword",
    )

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        return _validate_password_strength(v)
