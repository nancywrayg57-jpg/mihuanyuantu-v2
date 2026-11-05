"""
AOJU Backend - Authentication Endpoints
"""
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.api.deps import CurrentUser, DBSession, OptionalCurrentUser, snapshot_current_user
from app.core.auth_cookies import clear_auth_cookies, get_access_cookie, get_refresh_cookie, set_auth_cookies
from app.core.config import settings
from app.core.exceptions import BusinessError, UnauthorizedError
from app.core.logger import get_logger
from app.core.response import ErrorResponse, SuccessResponse
from app.core.schemas import ResponseBase
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_invite_code,
    decode_token,
    get_token_expiry,
    verify_password,
)
from app.domain.auth.schemas import get_registration_basic_fields_config
from app.domain.auth.service import TenantService
from app.domain.invitations.schemas import InvitationConfig, get_invitation_config
from app.domain.invitations.service import InvitationService
from app.domain.roles.service import RoleService
from app.domain.users.models import RegisterSource, UserStatus
from app.domain.users.profile_schema import UserProfileCompletionState, UserProfileFieldsConfig, get_user_profile_config
from app.domain.users.schemas import UserRegister
from app.domain.users.service import UserService
from app.domain.verification.service import VerificationService

router = APIRouter()
logger = get_logger(__name__)


# ============== Schemas ==============


class LoginRequest(BaseModel):
    """Login request"""

    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1)


class TokenData(BaseModel):
    """Token response data"""

    avatar: str = ""
    username: str
    nickname: str = ""
    roles: list[str] = []
    permissions: list[str] = []
    is_superuser: bool = Field(False, alias="isSuperuser")
    must_complete_profile: bool = Field(False, alias="mustCompleteProfile")
    access_token: str = Field(alias="accessToken")
    refresh_token: str = Field(alias="refreshToken")
    expires: datetime

    model_config = ConfigDict(populate_by_name=True)


class LoginResponse(ResponseBase[TokenData]):
    """Login response"""

    pass


class RefreshRequest(BaseModel):
    """Refresh token request"""

    refresh_token: str = Field(alias="refreshToken")

    model_config = ConfigDict(populate_by_name=True)


class RefreshData(TokenData):
    """Refresh response data, including current RBAC metadata."""

    pass


class RefreshResponse(ResponseBase[RefreshData]):
    """Refresh response"""

    pass


class UserInfoData(BaseModel):
    """User info data"""

    avatar: str = ""
    username: str
    nickname: str = ""
    email: str = ""
    phone: str = ""
    description: str = ""
    profile: dict[str, Any] = {}
    profile_meta: UserProfileCompletionState = Field(default_factory=UserProfileCompletionState, alias="profileMeta")
    profile_schema: UserProfileFieldsConfig = Field(default_factory=UserProfileFieldsConfig, alias="profileSchema")
    must_complete_profile: bool = Field(False, alias="mustCompleteProfile")

    model_config = ConfigDict(populate_by_name=True)


class UserInfoResponse(ResponseBase[UserInfoData]):
    """User info response"""

    pass


class AuthSessionData(BaseModel):
    avatar: str = ""
    username: str
    nickname: str = ""
    roles: list[str] = []
    permissions: list[str] = []
    is_superuser: bool = Field(False, alias="isSuperuser")
    must_complete_profile: bool = Field(False, alias="mustCompleteProfile")
    expires: datetime | None = None
    auth_mode: str = Field("cookie", alias="authMode")

    model_config = ConfigDict(populate_by_name=True)


class AuthSessionResponse(ResponseBase[AuthSessionData]):
    pass


class UpdateProfileRequest(BaseModel):
    """Update profile request"""

    avatar: str | None = None
    nickname: str | None = Field(None, max_length=50)
    profile: dict[str, Any] | None = None


class SendPhoneCodeRequest(BaseModel):
    """Send SMS code for binding phone"""

    phone: str = Field(..., min_length=7, max_length=32)


class BindPhoneRequest(BaseModel):
    """Bind phone with SMS verification code"""

    phone: str = Field(..., min_length=7, max_length=32)
    code: str = Field(..., min_length=4, max_length=16)


class SendEmailCodeRequest(BaseModel):
    """Send email code for binding email"""

    email: EmailStr


class BindEmailRequest(BaseModel):
    """Bind email with verification code"""

    email: EmailStr
    code: str = Field(..., min_length=4, max_length=16)


class ChangePasswordRequest(BaseModel):
    """Change password request"""

    old_password: str = Field(..., alias="oldPassword")
    new_password: str = Field(..., min_length=8, max_length=50, alias="newPassword")

    model_config = ConfigDict(populate_by_name=True)


# ============== Endpoints ==============

_REGISTRATION_REQUIRED_FIELD_LABELS: dict[str, str] = {
    "nickname": "昵称",
    "email": "邮箱",
    "phone": "手机号",
}


def _normalize_host_candidate(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""

    parsed = urlparse(raw if "://" in raw else f"//{raw}")
    host = parsed.hostname or raw
    return host.strip().lower()


def _resolve_request_hostname(request: Request) -> str:
    for candidate in (
        request.headers.get("x-forwarded-host"),
        request.headers.get("x-original-host"),
        request.headers.get("origin"),
        request.headers.get("referer"),
        request.url.hostname,
    ):
        normalized = _normalize_host_candidate(candidate)
        if normalized:
            return normalized
    return ""


def _resolve_request_access_token(http_request: Request) -> str | None:
    authorization = str(http_request.headers.get("authorization") or "").strip()
    if authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        if token:
            return token
    return get_access_cookie(http_request)


async def _build_auth_session_payload(*, db: DBSession, user: Any, expires: datetime | None) -> dict[str, Any]:
    actor = snapshot_current_user(user)
    user_service = UserService(db)
    profile_config = await user_service.get_tenant_profile_config(actor.tenant_id)
    _, profile_state = user_service.build_user_profile_state(user, profile_config)
    must_complete_profile = bool(
        profile_config.enabled and profile_config.enforce_after_login and not profile_state.completed
    )
    permissions = sorted(await user_service.get_user_permissions(actor.user_id, tenant_id=actor.tenant_id))
    roles = await user_service.get_user_role_codes(actor.user_id, tenant_id=actor.tenant_id)
    if actor.is_superuser and not roles:
        roles = ["superuser"]

    return {
        "avatar": user.avatar or "",
        "username": user.username,
        "nickname": user.nickname or user.username,
        "roles": roles,
        "permissions": permissions,
        "isSuperuser": actor.is_superuser,
        "mustCompleteProfile": must_complete_profile,
        "expires": expires,
        "authMode": "cookie",
    }


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    http_request: Request,
    db: DBSession,
) -> dict[str, Any]:
    """
    User login with username and password.
    Returns JWT tokens.
    """
    # Get client IP
    client_ip = http_request.client.host if http_request.client else "unknown"

    # Use UserService to find user by username (global lookup for login)
    user_service = UserService(db)
    user = await user_service.get_one(username=request.username)

    if not user:
        logger.warning(
            "login_failed_user_not_found",
            username=request.username,
            ip=client_ip,
        )
        raise UnauthorizedError(message="Invalid username or password")

    # Verify password
    if not verify_password(request.password, user.password_hash):
        # Record login failure using service method
        await user_service.record_login_failure(user)
        if user.failed_login_count >= 5:
            logger.warning(
                "user_account_locked",
                user_id=user.id,
                username=user.username,
                failed_attempts=user.failed_login_count,
                ip=client_ip,
            )
        else:
            logger.warning(
                "login_failed_invalid_password",
                user_id=user.id,
                username=user.username,
                failed_attempts=user.failed_login_count,
                ip=client_ip,
            )
        # 必须在抛出异常前提交，否则事务回滚会导致登录失败次数不被记录
        await db.commit()
        raise UnauthorizedError(message="Invalid username or password")

    # Check if user is active
    if user.status == UserStatus.PENDING:
        logger.warning(
            "login_failed_pending_approval",
            user_id=user.id,
            username=user.username,
            ip=client_ip,
        )
        raise UnauthorizedError(message="Your registration is pending approval")
    if user.status == UserStatus.REJECTED:
        logger.warning(
            "login_failed_rejected",
            user_id=user.id,
            username=user.username,
            ip=client_ip,
        )
        raise UnauthorizedError(message="Your registration was rejected")
    if not user.is_active:
        logger.warning(
            "login_failed_account_disabled",
            user_id=user.id,
            username=user.username,
            ip=client_ip,
        )
        raise UnauthorizedError(message="User account is disabled or locked")

    # Record successful login using service method
    await user_service.record_login_success(user)

    try:
        await InvitationService(db).process_due_rewards(tenant_id=user.tenant_id, user_id=user.id)
    except Exception as exc:
        logger.warning(
            "invite_reward_process_failed_on_login",
            tenant_id=user.tenant_id,
            user_id=user.id,
            error=str(exc),
        )

    # Create tokens
    expires = datetime.now(UTC) + timedelta(
        minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    )
    access_token = create_access_token(
        subject=user.id,
        extra_data={"tenant_id": user.tenant_id},
    )
    refresh_token = create_refresh_token(subject=user.id)
    session_payload = await _build_auth_session_payload(db=db, user=user, expires=expires)

    # Log successful login
    logger.info(
        "login_success",
        user_id=user.id,
        username=user.username,
        tenant_id=user.tenant_id,
        is_superuser=user.is_superuser,
        roles=session_payload["roles"],
        ip=client_ip,
    )

    api_response = SuccessResponse(
        data={
            **session_payload,
            "accessToken": access_token,
            "refreshToken": refresh_token,
            "expires": expires,
        }
    )
    set_auth_cookies(
        api_response,
        request=http_request,
        access_token=access_token,
        refresh_token=refresh_token,
    )
    return api_response


@router.post("/refresh-token", response_model=RefreshResponse)
async def refresh_token(
    http_request: Request,
    db: DBSession,
    request: RefreshRequest | None = None,
) -> dict[str, Any]:
    """
    Refresh access token using refresh token.
    """
    refresh_token_value = request.refresh_token if request else None
    if not refresh_token_value:
        refresh_token_value = get_refresh_cookie(http_request)
    if not refresh_token_value:
        raise UnauthorizedError(message="Missing refresh token")

    # Decode refresh token
    payload = decode_token(refresh_token_value)

    if payload.get("type") != "refresh":
        raise UnauthorizedError(message="Invalid refresh token")

    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError(message="Invalid token payload")

    # Use UserService to verify user exists and is active
    user_service = UserService(db)
    user = await user_service.get_user_by_id_any_tenant(int(user_id))

    if not user or not user.is_active:
        raise UnauthorizedError(message="User not found or inactive")

    # Create new tokens
    expires = datetime.now(UTC) + timedelta(
        minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    )
    new_access_token = create_access_token(
        subject=user.id,
        extra_data={"tenant_id": user.tenant_id},
    )
    new_refresh_token = create_refresh_token(subject=user.id)
    session_payload = await _build_auth_session_payload(db=db, user=user, expires=expires)

    api_response = SuccessResponse(
        data={
            **session_payload,
            "accessToken": new_access_token,
            "refreshToken": new_refresh_token,
            "expires": expires,
        }
    )
    set_auth_cookies(
        api_response,
        request=http_request,
        access_token=new_access_token,
        refresh_token=new_refresh_token,
    )
    return api_response


@router.get("/mine", response_model=UserInfoResponse)
async def get_current_user_info(
    current_user: CurrentUser,
    db: DBSession,
) -> dict[str, Any]:
    """
    Get current user information.
    """
    actor = snapshot_current_user(current_user)
    user_service = UserService(db)
    profile_config = await user_service.get_tenant_profile_config(actor.tenant_id)
    profile, profile_state = user_service.build_user_profile_state(current_user, profile_config)
    must_complete_profile = bool(
        profile_config.enabled and profile_config.enforce_after_login and not profile_state.completed
    )

    return SuccessResponse(
        data={
            "avatar": current_user.avatar or "",
            "username": current_user.username,
            "nickname": current_user.nickname or "",
            "email": current_user.email or "",
            "phone": current_user.phone or "",
            "description": current_user.description or "",
            "profile": profile,
            "profileMeta": profile_state.model_dump(by_alias=True),
            "profileSchema": profile_config.model_dump(by_alias=True),
            "mustCompleteProfile": must_complete_profile,
        }
    )


@router.post("/logout")
async def logout(
    http_request: Request,
    current_user: OptionalCurrentUser,
) -> dict[str, Any]:
    """
    Logout current user.
    Always clears auth cookies so stale sessions can exit cleanly.
    """
    if current_user:
        actor = snapshot_current_user(current_user)
        logger.info(
            "logout_success",
            user_id=actor.user_id,
            username=actor.username,
            tenant_id=actor.tenant_id,
        )
    api_response = SuccessResponse(message="Logged out successfully")
    clear_auth_cookies(api_response, request=http_request)
    return api_response


@router.get("/session", response_model=AuthSessionResponse)
async def get_auth_session(
    current_user: CurrentUser,
    http_request: Request,
    db: DBSession,
) -> dict[str, Any]:
    expires = None
    access_token = _resolve_request_access_token(http_request)
    if access_token:
        try:
            expires = get_token_expiry(access_token)
        except UnauthorizedError:
            expires = None

    payload = await _build_auth_session_payload(db=db, user=current_user, expires=expires)
    return SuccessResponse(data=payload)


@router.put("/profile")
async def update_profile(
    request: UpdateProfileRequest,
    current_user: CurrentUser,
    db: DBSession,
) -> dict[str, Any]:
    """
    Update current user profile (avatar, nickname).
    """
    actor = snapshot_current_user(current_user)
    user_service = UserService(db)
    update_data = {}
    if request.avatar is not None:
        update_data["avatar"] = request.avatar
    if request.nickname is not None:
        update_data["nickname"] = request.nickname
    if request.profile is not None:
        profile, profile_state, profile_config = await user_service.prepare_user_profile(
            tenant_id=actor.tenant_id,
            raw_profile=request.profile,
            existing_extra=current_user.extra,
            source=current_user.register_source or RegisterSource.SELF,
        )
        update_data["extra"] = user_service.build_user_extra_with_profile(
            existing_extra=current_user.extra,
            profile=profile,
            profile_state=profile_state,
        )
    else:
        profile_config = await user_service.get_tenant_profile_config(actor.tenant_id)

    if update_data:
        await user_service.update(current_user, update_data)

    profile, profile_state = user_service.build_user_profile_state(current_user, profile_config)
    must_complete_profile = bool(
        profile_config.enabled and profile_config.enforce_after_login and not profile_state.completed
    )

    return SuccessResponse(
        data={
            "avatar": current_user.avatar or "",
            "nickname": current_user.nickname or "",
            "profile": profile,
            "profileMeta": profile_state.model_dump(by_alias=True),
            "profileSchema": profile_config.model_dump(by_alias=True),
            "mustCompleteProfile": must_complete_profile,
        },
        message="Profile updated successfully",
    )


@router.post("/phone/send-code")
async def send_bind_phone_code(
    request: SendPhoneCodeRequest,
    current_user: CurrentUser,
    db: DBSession,
) -> dict[str, Any]:
    """Send SMS verification code to bind phone."""
    actor = snapshot_current_user(current_user)
    tenant_service = TenantService(db)
    tenant = await tenant_service.get_by_id(actor.tenant_id)
    if not tenant:
        raise BusinessError(message="Tenant not found")

    service = VerificationService(db)
    result = await service.send_bind_phone_code(user=current_user, tenant=tenant, phone=request.phone)

    data: dict[str, Any] = {
        "cooldownSeconds": result.get("cooldownSeconds"),
        "ttlSeconds": result.get("ttlSeconds"),
    }
    if result.get("debugCode"):
        data["debugCode"] = result.get("debugCode")

    return SuccessResponse(data=data, message="Verification code sent")


@router.post("/phone/bind")
async def bind_phone(
    request: BindPhoneRequest,
    current_user: CurrentUser,
    db: DBSession,
) -> dict[str, Any]:
    """Verify code and bind phone to current user."""
    actor = snapshot_current_user(current_user)
    tenant_service = TenantService(db)
    tenant = await tenant_service.get_by_id(actor.tenant_id)
    if not tenant:
        raise BusinessError(message="Tenant not found")

    service = VerificationService(db)
    user = await service.verify_and_bind_phone(user=current_user, tenant=tenant, phone=request.phone, code=request.code)

    return SuccessResponse(
        data={
            "phone": user.phone or "",
        },
        message="Phone bound successfully",
    )


@router.post("/email/send-code")
async def send_bind_email_code(
    request: SendEmailCodeRequest,
    current_user: CurrentUser,
    db: DBSession,
) -> dict[str, Any]:
    """Send email verification code to bind email."""
    actor = snapshot_current_user(current_user)
    tenant_service = TenantService(db)
    tenant = await tenant_service.get_by_id(actor.tenant_id)
    if not tenant:
        raise BusinessError(message="Tenant not found")

    service = VerificationService(db)
    result = await service.send_bind_email_code(user=current_user, tenant=tenant, email=str(request.email))

    data: dict[str, Any] = {
        "cooldownSeconds": result.get("cooldownSeconds"),
        "ttlSeconds": result.get("ttlSeconds"),
    }
    if result.get("debugCode"):
        data["debugCode"] = result.get("debugCode")

    return SuccessResponse(data=data, message="Verification code sent")


@router.post("/email/bind")
async def bind_email(
    request: BindEmailRequest,
    current_user: CurrentUser,
    db: DBSession,
) -> dict[str, Any]:
    """Verify code and bind email to current user."""
    actor = snapshot_current_user(current_user)
    tenant_service = TenantService(db)
    tenant = await tenant_service.get_by_id(actor.tenant_id)
    if not tenant:
        raise BusinessError(message="Tenant not found")

    service = VerificationService(db)
    user = await service.verify_and_bind_email(user=current_user, tenant=tenant, email=str(request.email), code=request.code)

    return SuccessResponse(
        data={
            "email": user.email or "",
        },
        message="Email bound successfully",
    )


@router.put("/password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: CurrentUser,
    db: DBSession,
) -> dict[str, Any]:
    """
    Change current user password.
    """
    from app.domain.users.schemas import PasswordChange

    actor = snapshot_current_user(current_user)
    user_service = UserService(db)
    await user_service.change_password(
        user_id=actor.user_id,
        tenant_id=actor.tenant_id,
        data=PasswordChange(
            old_password=request.old_password,
            new_password=request.new_password,
        ),
    )
    return SuccessResponse(message="Password changed successfully")


@router.post("/register")
async def register(
    data: UserRegister,
    request: Request,
    db: DBSession,
) -> dict[str, Any]:
    """
    User self-registration.

    Registration behavior depends on tenant configuration:
    - If registration is disabled, returns error
    - If require_audit is true, user status is PENDING
    - If require_audit is false, user is immediately active
    """
    tenant_code = (data.tenant_code or "").strip()
    invite_code = (data.invite_code or "").strip()
    invitation_service = InvitationService(db)
    db_invite_code = None

    # Resolve tenant:
    # 1) explicit tenantCode (e.g. invite/link/route derived)
    # 2) current domain (suffix based)
    # 3) system default tenant
    tenant_service = TenantService(db)
    if invite_code:
        invite_context = await invitation_service.resolve_code_context(invite_code, for_update=True)
        if invite_context:
            db_invite_code, tenant, _ = invite_context
        else:
            invite_tenant_code = decode_invite_code(invite_code)
            if not invite_tenant_code:
                raise BusinessError(message="Invalid or expired invite code")
            tenant = await tenant_service.get_one(code=invite_tenant_code, is_active=True)
            if not tenant:
                raise BusinessError(message="Invalid or expired invite code")
    elif tenant_code:
        tenant = await tenant_service.get_one(code=tenant_code, is_active=True)
        if not tenant:
            raise BusinessError(message="Invalid tenant code")
    else:
        hostname = _resolve_request_hostname(request)
        tenant = await tenant_service.get_one(domain=hostname, is_active=True) if hostname else None
        if not tenant:
            tenant = await tenant_service.get_one(code=settings.DEFAULT_TENANT_CODE, is_active=True)
        if not tenant:
            raise BusinessError(message="Default tenant is not configured")

    invitation_config = get_invitation_config(tenant.config)
    if invite_code:
        if not invitation_config.enabled:
            raise BusinessError(message="当前租户未启用邀请注册")
    elif not tenant.registration_enabled:
        raise BusinessError(message="Registration is not allowed for this tenant")

    basic_fields = get_registration_basic_fields_config(tenant.config)
    sanitized_updates: dict[str, Any] = {}
    for field_key in ("nickname", "email", "phone"):
        field_config = getattr(basic_fields, field_key)
        raw_value = getattr(data, field_key, None)
        normalized_value = str(raw_value or "").strip()
        if not field_config.enabled:
            sanitized_updates[field_key] = None
            continue
        if field_config.required and not normalized_value:
            raise BusinessError(message=f"当前租户要求填写{_REGISTRATION_REQUIRED_FIELD_LABELS[field_key]}")
        sanitized_updates[field_key] = normalized_value or None
    if sanitized_updates:
        data = data.model_copy(update=sanitized_updates)

    # Check if username exists
    user_service = UserService(db)
    existing = await user_service.get_by_username_global(data.username)
    if existing:
        raise BusinessError(message=f"Username '{data.username}' already exists")

    # Determine user status based on tenant config
    require_audit = tenant.registration_require_audit

    # Create user
    user = await user_service.register_user(
        data,
        tenant.id,
        register_source=RegisterSource.INVITE if db_invite_code else RegisterSource.SELF,
    )

    # If no audit required, directly activate and assign default role
    if not require_audit:
        user.status = UserStatus.ENABLED
        # Use RoleService to get default role
        role_service = RoleService(db)
        default_role_code = tenant.registration_default_role
        default_role = await role_service.get_by_code(default_role_code, tenant.id)
        if not default_role and default_role_code != "user":
            default_role = await role_service.get_by_code("user", tenant.id)
        if default_role:
            from app.domain.users.models import UserRole
            user_role = UserRole(
                user_id=user.id,
                role_id=default_role.id,
                tenant_id=tenant.id,
            )
            db.add(user_role)
        await db.flush()
        await db.refresh(user)

    if db_invite_code:
        await invitation_service.create_registration_from_code(
            invite_code=db_invite_code,
            tenant=tenant,
            invited_user=user,
        )

    return SuccessResponse(
        data={
            "id": user.id,
            "username": user.username,
            "status": user.status,
            "requireAudit": require_audit,
        },
        message="Registration submitted. Pending approval." if require_audit else "Registration successful.",
    )


@router.get("/registration-config")
async def get_registration_config(
    db: DBSession,
    request: Request,
    tenant_code: str | None = None,
) -> dict[str, Any]:
    """
    Get tenant registration configuration (public endpoint).
    Used by frontend to determine if registration is available.
    """
    # Use TenantService to get tenant
    tenant_service = TenantService(db)
    normalized_tenant_code = (tenant_code or "").strip()
    tenant_bound = False
    tenant_source = "none"
    if normalized_tenant_code:
        tenant = await tenant_service.get_one(code=normalized_tenant_code, is_active=True)
        tenant_bound = tenant is not None
        tenant_source = "query"
    else:
        hostname = _resolve_request_hostname(request)
        tenant = await tenant_service.get_one(domain=hostname, is_active=True) if hostname else None
        if tenant:
            tenant_bound = True
            tenant_source = "domain"
        if not tenant:
            tenant = await tenant_service.get_one(code=settings.DEFAULT_TENANT_CODE, is_active=True)
            tenant_source = "default" if tenant else "none"

    if not tenant:
        return SuccessResponse(
            data={
                "enabled": False,
                "requireAudit": True,
                "defaultRole": "user",
                "basicFields": get_registration_basic_fields_config({}).model_dump(by_alias=True),
                "invitation": InvitationConfig().model_dump(by_alias=True),
                "userProfileFields": UserProfileFieldsConfig().model_dump(by_alias=True),
                "tenantBound": False,
                "tenantSource": "none",
            }
        )

    return SuccessResponse(
        data={
            "enabled": tenant.registration_enabled,
            "requireAudit": tenant.registration_require_audit,
            "defaultRole": tenant.registration_default_role,
            "basicFields": get_registration_basic_fields_config(tenant.config).model_dump(by_alias=True),
            "invitation": get_invitation_config(tenant.config).model_dump(by_alias=True),
            "userProfileFields": get_user_profile_config(tenant.config).model_dump(by_alias=True),
            "tenantCode": tenant.code,
            "tenantName": tenant.name,
            "tenantBound": tenant_bound,
            "tenantSource": tenant_source,
        }
    )


@router.get("/parse-invite")
async def parse_invite_code(
    db: DBSession,
    code: str,
) -> dict[str, Any]:
    """
    Parse invite code and return tenant info (public endpoint).
    Used by frontend to auto-fill tenant on registration page.
    """
    invitation_service = InvitationService(db)
    tenant_service = TenantService(db)
    invite_context = await invitation_service.resolve_code_context(code)
    inviter_data: dict[str, Any] = {}

    if invite_context:
        _, tenant, inviter = invite_context
        inviter_data = {
            "inviterUsername": inviter.username,
            "inviterNickname": inviter.nickname or inviter.username,
        }
    else:
        tenant_code = decode_invite_code(code)
        if not tenant_code:
            return ErrorResponse(
                message="Invalid or expired invite code",
                code="INVALID_INVITE_CODE",
            )
        tenant = await tenant_service.get_one(code=tenant_code, is_active=True)

    if not tenant:
        return ErrorResponse(
            message="Tenant not found",
            code="NOT_FOUND",
        )

    if not get_invitation_config(tenant.config).enabled:
        return ErrorResponse(
            message="Invitation registration is disabled for this tenant",
            code="INVITATION_DISABLED",
        )

    return SuccessResponse(
        data={
            "tenantCode": tenant.code,
            "tenantName": tenant.name,
            "requireAudit": tenant.registration_require_audit,
            "basicFields": get_registration_basic_fields_config(tenant.config).model_dump(by_alias=True),
            "invitation": get_invitation_config(tenant.config).model_dump(by_alias=True),
            "userProfileFields": get_user_profile_config(tenant.config).model_dump(by_alias=True),
            "tenantBound": True,
            "tenantSource": "invite",
            **inviter_data,
        }
    )


@router.get("/resolve-domain")
async def resolve_domain(
    db: DBSession,
    domain: str,
) -> dict[str, Any]:
    """
    Resolve domain to tenant (public endpoint).
    Used by frontend to auto-detect tenant from current domain.
    """
    # Use TenantService to get tenant by domain
    tenant_service = TenantService(db)
    tenant = await tenant_service.get_one(domain=domain, is_active=True)

    if not tenant:
        return ErrorResponse(
            message="No tenant found for this domain",
            code="NOT_FOUND",
        )

    return SuccessResponse(
        data={
            "tenantCode": tenant.code,
            "tenantName": tenant.name,
            "requireAudit": tenant.registration_require_audit,
            "registrationEnabled": tenant.registration_enabled,
        }
    )
