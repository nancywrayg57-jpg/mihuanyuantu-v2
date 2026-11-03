"""
AOJU Backend - Verification Service

Handles sending and verifying codes for binding user phone/email.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessError, ConflictError, ValidationError
from app.core.tenant_config_namespaces import safe_tenant_config_dict
from app.core.verification import (
    VerificationRuntimeConfig,
    generate_numeric_code,
    generate_salt,
    hash_verification_code,
    normalize_email,
    normalize_phone,
    send_verification_code,
)
from app.domain.auth.models import Tenant
from app.domain.users.models import User
from app.domain.users.service import UserService
from app.domain.verification.models import VerificationCode
from app.infrastructure.repository import RepositoryBase


VerificationChannel = Literal["sms", "email"]


class VerificationService(RepositoryBase[VerificationCode]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, VerificationCode)

    async def send_bind_phone_code(self, *, user: User, tenant: Tenant, phone: str) -> dict[str, Any]:
        target = normalize_phone(phone)
        await self._ensure_phone_available(user=user, phone=target)

        tenant_config = safe_tenant_config_dict(tenant.config)
        cfg = VerificationRuntimeConfig.from_tenant_config(tenant_config)
        await self._ensure_cooldown_ok(
            tenant_id=user.tenant_id,
            user_id=user.id,
            channel="sms",
            purpose="bind_phone",
            target=target,
            cooldown_seconds=cfg.cooldown_seconds,
        )

        now = datetime.now(timezone.utc)
        code = generate_numeric_code(cfg.length)
        salt = generate_salt()
        code_hash = hash_verification_code(code, salt=salt)

        await self.create(
            {
                "tenant_id": user.tenant_id,
                "user_id": user.id,
                "channel": "sms",
                "purpose": "bind_phone",
                "target": target,
                "code_hash": code_hash,
                "salt": salt,
                "expires_at": now + timedelta(seconds=cfg.ttl_seconds),
                "used_at": None,
                "attempts": 0,
            }
        )

        debug_code = await send_verification_code(
            channel="sms",
            target=target,
            code=code,
            tenant_name=tenant.name,
            tenant_config=tenant_config,
            purpose="bind_phone",
        )

        return {"cooldownSeconds": cfg.cooldown_seconds, "ttlSeconds": cfg.ttl_seconds, "debugCode": debug_code}

    async def send_bind_email_code(self, *, user: User, tenant: Tenant, email: str) -> dict[str, Any]:
        target = normalize_email(email)
        await self._ensure_email_available(user=user, email=target)

        tenant_config = safe_tenant_config_dict(tenant.config)
        cfg = VerificationRuntimeConfig.from_tenant_config(tenant_config)
        await self._ensure_cooldown_ok(
            tenant_id=user.tenant_id,
            user_id=user.id,
            channel="email",
            purpose="bind_email",
            target=target,
            cooldown_seconds=cfg.cooldown_seconds,
        )

        now = datetime.now(timezone.utc)
        code = generate_numeric_code(cfg.length)
        salt = generate_salt()
        code_hash = hash_verification_code(code, salt=salt)

        await self.create(
            {
                "tenant_id": user.tenant_id,
                "user_id": user.id,
                "channel": "email",
                "purpose": "bind_email",
                "target": target,
                "code_hash": code_hash,
                "salt": salt,
                "expires_at": now + timedelta(seconds=cfg.ttl_seconds),
                "used_at": None,
                "attempts": 0,
            }
        )

        debug_code = await send_verification_code(
            channel="email",
            target=target,
            code=code,
            tenant_name=tenant.name,
            tenant_config=tenant_config,
            purpose="bind_email",
        )

        return {"cooldownSeconds": cfg.cooldown_seconds, "ttlSeconds": cfg.ttl_seconds, "debugCode": debug_code}

    async def verify_and_bind_phone(self, *, user: User, tenant: Tenant, phone: str, code: str) -> User:
        target = normalize_phone(phone)
        tenant_config = safe_tenant_config_dict(tenant.config)
        await self._verify_code(
            tenant_id=user.tenant_id,
            user_id=user.id,
            channel="sms",
            purpose="bind_phone",
            target=target,
            code=code,
            tenant_config=tenant_config,
        )

        # Ensure uniqueness again (race-safe before update)
        await self._ensure_phone_available(user=user, phone=target)

        user_service = UserService(self.db)
        await user_service.update(user, {"phone": target})
        return user

    async def verify_and_bind_email(self, *, user: User, tenant: Tenant, email: str, code: str) -> User:
        target = normalize_email(email)
        tenant_config = safe_tenant_config_dict(tenant.config)
        await self._verify_code(
            tenant_id=user.tenant_id,
            user_id=user.id,
            channel="email",
            purpose="bind_email",
            target=target,
            code=code,
            tenant_config=tenant_config,
        )

        await self._ensure_email_available(user=user, email=target)

        user_service = UserService(self.db)
        await user_service.update(user, {"email": target})
        return user

    async def _ensure_phone_available(self, *, user: User, phone: str) -> None:
        if user.phone and user.phone == phone:
            return
        user_service = UserService(self.db)
        existing = await user_service.get_one(where=[User.phone == phone, User.id != user.id])
        if existing:
            raise ConflictError(message="Phone already exists")

    async def _ensure_email_available(self, *, user: User, email: str) -> None:
        if user.email and user.email.lower() == email:
            return
        user_service = UserService(self.db)
        existing = await user_service.get_one(where=[func.lower(User.email) == email, User.id != user.id])
        if existing:
            raise ConflictError(message="Email already exists")

    async def _ensure_cooldown_ok(
        self,
        *,
        tenant_id: int,
        user_id: int,
        channel: VerificationChannel,
        purpose: str,
        target: str,
        cooldown_seconds: int,
    ) -> None:
        if cooldown_seconds <= 0:
            return

        stmt = (
            select(VerificationCode)
            .where(
                VerificationCode.tenant_id == tenant_id,
                VerificationCode.user_id == user_id,
                VerificationCode.channel == channel,
                VerificationCode.purpose == purpose,
                VerificationCode.target == target,
                VerificationCode.deleted_at.is_(None),
            )
            .order_by(VerificationCode.created_at.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        last = result.scalar_one_or_none()
        if not last:
            return

        now = datetime.now(timezone.utc)
        if (now - last.created_at).total_seconds() < cooldown_seconds:
            raise BusinessError(message="Please wait before requesting another code", code="TOO_MANY_REQUESTS")

    async def _verify_code(
        self,
        *,
        tenant_id: int,
        user_id: int,
        channel: VerificationChannel,
        purpose: str,
        target: str,
        code: str,
        tenant_config: dict[str, Any],
    ) -> None:
        cfg = VerificationRuntimeConfig.from_tenant_config(tenant_config)
        max_attempts = max(1, int(cfg.max_attempts) or 1)

        stmt = (
            select(VerificationCode)
            .where(
                VerificationCode.tenant_id == tenant_id,
                VerificationCode.user_id == user_id,
                VerificationCode.channel == channel,
                VerificationCode.purpose == purpose,
                VerificationCode.target == target,
                VerificationCode.deleted_at.is_(None),
            )
            .order_by(VerificationCode.created_at.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        record = result.scalar_one_or_none()
        if not record:
            raise BusinessError(message="Verification code not found", code="VERIFICATION_CODE_NOT_FOUND")

        now = datetime.now(timezone.utc)
        if record.used_at is not None:
            raise BusinessError(message="Verification code already used", code="VERIFICATION_CODE_USED")
        if record.expires_at < now:
            raise BusinessError(message="Verification code expired", code="VERIFICATION_CODE_EXPIRED")
        if record.attempts >= max_attempts:
            raise BusinessError(message="Too many attempts", code="VERIFICATION_CODE_LOCKED")

        code_value = (code or "").strip()
        if not code_value or len(code_value) > 16:
            raise ValidationError(message="Invalid verification code")

        expected = record.code_hash
        actual = hash_verification_code(code_value, salt=record.salt)
        if not hmac_compare(actual, expected):
            record.attempts += 1
            await self.db.flush()
            raise BusinessError(message="Invalid verification code", code="VERIFICATION_CODE_INVALID")

        record.used_at = now
        await self.db.flush()


def hmac_compare(a: str, b: str) -> bool:
    try:
        import hmac

        return hmac.compare_digest(a, b)
    except Exception:
        return a == b
