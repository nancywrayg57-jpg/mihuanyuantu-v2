"""Session login with captcha challenge (dev captcha allowed)."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.realphotos.constants import (
    ACCESS_TOKEN_MINUTES,
    CHALLENGE_CODE_LENGTH,
    CHALLENGE_TTL_SECONDS,
    MAX_FAILED_LOGINS,
    SESSION_ABSOLUTE_DAYS,
    allow_dev_captcha,
)
from app.capabilities.realphotos.models import (
    RealphotosAuthChallenge,
    RealphotosAuthGuard,
    RealphotosMerchantProfile,
)
from app.core.exceptions import BusinessError, UnauthorizedError
from app.core.security import create_access_token, create_refresh_token, verify_password
from app.domain.users.models import User, UserStatus


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _normalize_username(username: str) -> str:
    return str(username or "").strip().lower()


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


class RealphotosAuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_challenge(self, *, client_key: str | None = None) -> dict:
        code = "".join(secrets.choice("0123456789") for _ in range(CHALLENGE_CODE_LENGTH))
        public_id = secrets.token_urlsafe(18)
        row = RealphotosAuthChallenge(
            challenge_public_id=public_id,
            code_hash=_hash_code(code),
            client_key=(client_key or None),
            expires_at=_utcnow() + timedelta(seconds=CHALLENGE_TTL_SECONDS),
        )
        self.db.add(row)
        await self.db.flush()
        payload = {
            "challengeId": public_id,
            "expiresAt": row.expires_at.isoformat(),
            "ttlSeconds": CHALLENGE_TTL_SECONDS,
        }
        if allow_dev_captcha():
            # 开发验证码可：明文仅在显式开发/测试开关下返回
            payload["devCode"] = code
        return payload

    async def _consume_challenge(self, challenge_id: str, code: str) -> None:
        result = await self.db.execute(
            select(RealphotosAuthChallenge).where(
                RealphotosAuthChallenge.challenge_public_id == challenge_id,
                RealphotosAuthChallenge.deleted_at.is_(None),
            )
        )
        challenge = result.scalar_one_or_none()
        if challenge is None:
            raise BusinessError(message="验证码无效", code="INPUT_INVALID")
        if challenge.consumed_at is not None:
            raise BusinessError(message="验证码已使用", code="INPUT_INVALID")
        expires = challenge.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if expires < _utcnow():
            raise BusinessError(message="验证码已过期", code="INPUT_INVALID")
        if not secrets.compare_digest(challenge.code_hash, _hash_code(str(code or "").strip())):
            raise BusinessError(message="验证码错误", code="INPUT_INVALID")
        challenge.consumed_at = _utcnow()
        await self.db.flush()

    async def _get_or_create_guard(self, username_normalized: str) -> RealphotosAuthGuard:
        result = await self.db.execute(
            select(RealphotosAuthGuard).where(
                RealphotosAuthGuard.username_normalized == username_normalized,
                RealphotosAuthGuard.deleted_at.is_(None),
            )
        )
        guard = result.scalar_one_or_none()
        if guard is None:
            guard = RealphotosAuthGuard(username_normalized=username_normalized)
            self.db.add(guard)
            await self.db.flush()
        return guard

    async def login(
        self,
        *,
        username: str,
        password: str,
        challenge_id: str,
        challenge_code: str,
    ) -> dict:
        await self._consume_challenge(challenge_id, challenge_code)

        username_normalized = _normalize_username(username)
        if not username_normalized:
            raise UnauthorizedError(message="Invalid username or password")

        guard = await self._get_or_create_guard(username_normalized)
        if guard.locked_until is not None:
            locked_until = guard.locked_until
            if locked_until.tzinfo is None:
                locked_until = locked_until.replace(tzinfo=UTC)
            if locked_until > _utcnow():
                raise BusinessError(message="账号已锁定，请联系客服", code="ACCOUNT_LOCKED")

        result = await self.db.execute(
            select(User).where(
                User.username == username.strip(),
                User.deleted_at.is_(None),
            )
        )
        user = result.scalar_one_or_none()
        if user is None or not verify_password(password, user.password_hash):
            guard.failed_count = int(guard.failed_count or 0) + 1
            guard.last_failure_at = _utcnow()
            if guard.failed_count >= MAX_FAILED_LOGINS:
                guard.locked_until = _utcnow() + timedelta(minutes=30)
            await self.db.flush()
            raise UnauthorizedError(message="Invalid username or password")

        if int(user.status) != int(UserStatus.ENABLED):
            raise UnauthorizedError(message="Account disabled")

        guard.failed_count = 0
        guard.locked_until = None
        guard.user_id = int(user.id)
        await self.db.flush()

        # 确保商家档案存在（客服/管理员也可有档案行，pre_review_frozen 默认 false）
        profile_result = await self.db.execute(
            select(RealphotosMerchantProfile).where(
                RealphotosMerchantProfile.tenant_id == int(user.tenant_id),
                RealphotosMerchantProfile.user_id == int(user.id),
                RealphotosMerchantProfile.deleted_at.is_(None),
            )
        )
        profile = profile_result.scalar_one_or_none()
        if profile is None:
            profile = RealphotosMerchantProfile(
                tenant_id=int(user.tenant_id),
                user_id=int(user.id),
                display_name=user.nickname or user.username,
            )
            self.db.add(profile)
            await self.db.flush()

        access_token = create_access_token(
            subject=user.id,
            expires_delta=timedelta(minutes=ACCESS_TOKEN_MINUTES),
            extra_data={
                "tenant_id": int(user.tenant_id),
                "rp_session": True,
                "rp_abs_exp": int(
                    (_utcnow() + timedelta(days=SESSION_ABSOLUTE_DAYS)).timestamp()
                ),
            },
        )
        refresh_token = create_refresh_token(
            subject=user.id,
            expires_delta=timedelta(days=SESSION_ABSOLUTE_DAYS),
        )
        role_codes = sorted(
            {str(getattr(role, "code", "") or "") for role in (user.roles or []) if getattr(role, "code", None)}
        )
        return {
            "accessToken": access_token,
            "refreshToken": refresh_token,
            "expiresIn": ACCESS_TOKEN_MINUTES * 60,
            "absoluteSessionDays": SESSION_ABSOLUTE_DAYS,
            "user": {
                "id": str(int(user.id)),
                "username": user.username,
                "nickname": user.nickname,
                "tenantId": str(int(user.tenant_id)),
                "roleCodes": role_codes,
                "preReviewFrozen": bool(profile.pre_review_frozen),
            },
        }
