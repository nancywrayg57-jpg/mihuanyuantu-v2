"""
AOJU Backend - Contact Verification Utilities

Provides:
- Normalization helpers for phone/email
- Verification code generation + hashing
- Unified send function (SMS/Email) with tenant-configurable providers
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from typing import Any, Literal

from app.core.config import settings
from app.core.exceptions import BusinessError, ValidationError
from app.core.feature_switches import is_capability_enabled
from app.core.tenant_config_namespaces import get_tenant_config_namespace, safe_tenant_config_dict
from app.infrastructure.messaging import Message, create_sender
from app.infrastructure.messaging.smtp_config import SmtpConfig, resolve_smtp_config

VerificationChannel = Literal["sms", "email"]

_PHONE_RE = re.compile(r"^\+?\d{7,20}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_phone(phone: str) -> str:
    value = (phone or "").strip()
    if not value:
        raise ValidationError(message="Phone is required")

    # keep digits, allow leading '+'
    value = "+" + re.sub(r"\D", "", value[1:]) if value.startswith("+") else re.sub(r"\D", "", value)

    if not _PHONE_RE.match(value):
        raise ValidationError(message="Invalid phone format")
    return value


def normalize_email(email: str) -> str:
    value = (email or "").strip().lower()
    if not value:
        raise ValidationError(message="Email is required")
    if len(value) > 200 or not _EMAIL_RE.fullmatch(value):
        raise ValidationError(message="Invalid email format")
    return value


def generate_numeric_code(length: int) -> str:
    if length < 4 or length > 8:
        raise ValidationError(message="Invalid verification code length")
    # cryptographically strong, numeric only
    alphabet = "0123456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_salt(length: int = 16) -> str:
    # hex length is 2x bytes
    return secrets.token_hex(max(1, length // 2))


def hash_verification_code(code: str, *, salt: str) -> str:
    """
    Hash verification code using HMAC-SHA256 with server secret.

    Note: We include salt to avoid precomputed rainbow tables and to make
    identical codes hash differently per record.
    """
    payload = f"{salt}:{code}".encode()
    return hmac.new(
        settings.JWT_SECRET_KEY.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()


@dataclass(frozen=True)
class VerificationRuntimeConfig:
    length: int = 6
    ttl_seconds: int = 600
    cooldown_seconds: int = 60
    max_attempts: int = 5
    sms_provider: str = "mock"
    sms_enabled: bool = True
    sms_template: str = "验证码：{code}，{ttlMinutes}分钟内有效。"
    sms_webhook_url: str | None = None
    sms_webhook_headers: dict[str, str] | None = None
    email_provider: str = "mock"
    email_enabled: bool = True
    email_subject: str = "验证码"
    email_template: str = "您的验证码是：{code}，{ttlMinutes}分钟内有效。"
    email_smtp: SmtpConfig | None = None
    email_webhook_url: str | None = None
    email_webhook_headers: dict[str, str] | None = None

    @staticmethod
    def from_tenant_config(tenant_config: dict[str, Any]) -> VerificationRuntimeConfig:
        config = safe_tenant_config_dict(tenant_config)
        verification = get_tenant_config_namespace(config, ("verification",))
        code_cfg = verification.get("code") or {}
        sms_cfg = verification.get("sms") or {}
        email_cfg = verification.get("email") or {}

        sms_enabled_raw = sms_cfg.get("enabled") if isinstance(sms_cfg, dict) else None
        email_enabled_raw = email_cfg.get("enabled") if isinstance(email_cfg, dict) else None

        email_smtp = resolve_smtp_config(config)
        email_provider = str(email_cfg.get("provider") or ("smtp" if email_smtp else "mock") or "mock")

        return VerificationRuntimeConfig(
            length=int(code_cfg.get("length", 6) or 6),
            ttl_seconds=int(code_cfg.get("ttlSeconds", 600) or 600),
            cooldown_seconds=int(code_cfg.get("cooldownSeconds", 60) or 60),
            max_attempts=int(code_cfg.get("maxAttempts", 5) or 5),
            sms_provider=str(sms_cfg.get("provider", "mock") or "mock"),
            sms_enabled=(
                bool(sms_enabled_raw)
                if sms_enabled_raw is not None
                else is_capability_enabled(config, "verification_sms")
            ),
            sms_template=str(
                sms_cfg.get("template", "验证码：{code}，{ttlMinutes}分钟内有效。")
                or "验证码：{code}，{ttlMinutes}分钟内有效。"
            ),
            sms_webhook_url=sms_cfg.get("webhookUrl") or sms_cfg.get("webhook_url"),
            sms_webhook_headers=sms_cfg.get("webhookHeaders") or sms_cfg.get("webhook_headers"),
            email_provider=email_provider,
            email_enabled=(
                bool(email_enabled_raw)
                if email_enabled_raw is not None
                else is_capability_enabled(config, "verification_email")
            ),
            email_subject=str(email_cfg.get("subject", "验证码") or "验证码"),
            email_template=str(
                email_cfg.get("template", "您的验证码是：{code}，{ttlMinutes}分钟内有效。")
                or "您的验证码是：{code}，{ttlMinutes}分钟内有效。"
            ),
            email_smtp=email_smtp,
            email_webhook_url=email_cfg.get("webhookUrl") or email_cfg.get("webhook_url"),
            email_webhook_headers=email_cfg.get("webhookHeaders") or email_cfg.get("webhook_headers"),
        )

    def ttl_minutes(self) -> int:
        return max(1, int(self.ttl_seconds // 60) or 1)


def render_template(template: str, *, code: str, ttl_minutes: int, tenant_name: str | None = None) -> str:
    try:
        return template.format(code=code, ttlMinutes=ttl_minutes, tenantName=tenant_name or "")
    except Exception:
        # keep it safe: do not break sending because of a template format error
        return f"验证码：{code}，{ttl_minutes}分钟内有效。"


async def send_verification_code(
    *,
    channel: VerificationChannel,
    target: str,
    code: str,
    tenant_name: str | None,
    tenant_config: dict[str, Any],
    purpose: str,
) -> str | None:
    """
    Send verification code through tenant-configured provider.

    Returns:
        debug_code: Only returned for non-production + mock provider.
    """
    cfg = VerificationRuntimeConfig.from_tenant_config(tenant_config)
    ttl_minutes = cfg.ttl_minutes()
    debug_return_code = bool(settings.DEBUG or settings.ENV != "production")

    if channel == "sms":
        if not cfg.sms_enabled:
            raise BusinessError(message="短信验证码功能未启用", code="FEATURE_DISABLED")
        content = render_template(cfg.sms_template, code=code, ttl_minutes=ttl_minutes, tenant_name=tenant_name)
        sender = create_sender(
            channel="sms",
            provider=cfg.sms_provider,
            webhook_url=cfg.sms_webhook_url,
            webhook_headers=cfg.sms_webhook_headers,
            debug_return_code=debug_return_code,
        )
        result = await sender.send(
            Message(
                channel="sms",
                to=target,
                content=content,
                meta={
                    "code": code,
                    "ttlMinutes": ttl_minutes,
                    "tenantName": tenant_name,
                    "purpose": purpose,
                },
            )
        )
        return result.debug_code

    if channel == "email":
        if not cfg.email_enabled:
            raise BusinessError(message="邮箱验证码功能未启用", code="FEATURE_DISABLED")
        if not debug_return_code and cfg.email_provider.strip().lower() == "mock":
            raise BusinessError(
                message="Email SMTP is not configured",
                code="EMAIL_NOT_CONFIGURED",
            )
        subject = cfg.email_subject
        content = render_template(cfg.email_template, code=code, ttl_minutes=ttl_minutes, tenant_name=tenant_name)
        sender = create_sender(
            channel="email",
            provider=cfg.email_provider,
            webhook_url=cfg.email_webhook_url,
            webhook_headers=cfg.email_webhook_headers,
            smtp=cfg.email_smtp,
            debug_return_code=debug_return_code,
        )
        result = await sender.send(
            Message(
                channel="email",
                to=target,
                subject=subject,
                content=content,
                meta={
                    "code": code,
                    "ttlMinutes": ttl_minutes,
                    "tenantName": tenant_name,
                    "purpose": purpose,
                },
            )
        )
        return result.debug_code

    raise ValidationError(message="Invalid channel")
