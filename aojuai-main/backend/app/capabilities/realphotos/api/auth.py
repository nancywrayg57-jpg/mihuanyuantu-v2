"""Captcha challenge + login (S0 / FR-001). Cookie session aligned with platform login."""

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Request
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DBSession, snapshot_current_user
from app.capabilities.realphotos.constants import ACCESS_TOKEN_MINUTES, SESSION_ABSOLUTE_DAYS
from app.capabilities.realphotos.schemas.auth import ChallengeCreate, LoginRequest, RegisterRequest
from app.capabilities.realphotos.services.auth_service import RealphotosAuthService
from app.core.auth_cookies import set_auth_cookies, should_use_secure_auth_cookie
from app.core.config import settings
from app.core.response import SuccessResponse
from app.domain.users.models import User
from app.domain.users.service import UserService

router = APIRouter(prefix="/auth")


async def _build_cookie_session_payload(*, db: DBSession, user: Any, expires: datetime | None) -> dict[str, Any]:
    """Mirror platform login session fields without importing api.v1.endpoints.auth (circular)."""
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
    # expires 必须是 ISO 字符串：前端 createCookieBackedSession 只接受非空 string
    expires_iso = expires.isoformat() if expires is not None else None
    return {
        "avatar": user.avatar or "",
        "username": user.username,
        "nickname": user.nickname or user.username,
        "roles": list(roles or []),
        "permissions": list(permissions or []),
        "isSuperuser": actor.is_superuser,
        "mustCompleteProfile": must_complete_profile,
        "expires": expires_iso,
        "authMode": "cookie",
    }


@router.post("/challenges")
async def create_challenge(
    db: DBSession,
    body: ChallengeCreate | None = None,
) -> dict[str, Any]:
    payload = body or ChallengeCreate()
    data = await RealphotosAuthService(db).create_challenge(client_key=payload.client_key)
    await db.commit()
    return SuccessResponse(data=data)


@router.post("/register")
async def register(
    body: RegisterRequest,
    db: DBSession,
) -> dict[str, Any]:
    """商家自助开户：验证码 + 用户名密码 → 新建租户与 rp_merchant（架构 §9.2 / FR-001）。"""
    data = await RealphotosAuthService(db).register(
        username=body.username,
        password=body.password,
        nickname=body.nickname,
        challenge_id=body.challenge_id,
        challenge_code=body.challenge_code,
    )
    await db.commit()
    return SuccessResponse(data=data, message="注册成功，请登录")


@router.post("/login")
async def login(
    body: LoginRequest,
    http_request: Request,
    db: DBSession,
) -> dict[str, Any]:
    """Web 登录：用户名 + 密码 + 验证码；写入与平台一致的 cookie 会话（绝对 30 天 refresh）。"""
    token_data = await RealphotosAuthService(db).login(
        username=body.username,
        password=body.password,
        challenge_id=body.challenge_id,
        challenge_code=body.challenge_code,
    )
    user_id = int(token_data["user"]["id"])
    user = (
        await db.execute(
            select(User)
            .options(selectinload(User.roles))
            .where(User.id == user_id, User.deleted_at.is_(None))
        )
    ).scalar_one()
    expires = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_MINUTES)
    session_payload = await _build_cookie_session_payload(db=db, user=user, expires=expires)
    access_token = str(token_data["accessToken"])
    refresh_token = str(token_data["refreshToken"])
    # 保证根级 expires 与 session_payload 同为 ISO 字符串，避免前端 Invalid cookie-backed session payload
    api_response = SuccessResponse(
        data={
            **session_payload,
            "accessToken": access_token,
            "refreshToken": refresh_token,
            "expires": session_payload["expires"],
            "absoluteSessionDays": SESSION_ABSOLUTE_DAYS,
            "user": token_data["user"],
        }
    )
    set_auth_cookies(
        api_response,
        request=http_request,
        access_token=access_token,
        refresh_token=refresh_token,
    )
    refresh_max_age = SESSION_ABSOLUTE_DAYS * 24 * 60 * 60
    secure = should_use_secure_auth_cookie(http_request)
    cookie_domain = str(settings.AUTH_COOKIE_DOMAIN or "").strip() or None
    api_response.set_cookie(
        key=settings.AUTH_REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=refresh_max_age,
        expires=refresh_max_age,
        path="/api/v1/auth",
        domain=cookie_domain,
        secure=secure,
        httponly=True,
        samesite=settings.AUTH_COOKIE_SAMESITE,
    )
    await db.commit()
    return api_response
