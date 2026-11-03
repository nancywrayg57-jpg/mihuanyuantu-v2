"""
AOJU Backend - Messaging Senders

This module abstracts outbound delivery (SMS/Email) behind a simple interface,
so upstream code only needs to build a `Message` and choose a provider.
"""

from __future__ import annotations

import ssl
import smtplib
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import formataddr
from typing import Any, Literal, Protocol

import anyio
import httpx

from app.core.exceptions import BusinessError
from app.core.logger import get_logger
from app.infrastructure.messaging.smtp_config import SmtpConfig

logger = get_logger(__name__)

Channel = Literal["sms", "email"]


@dataclass(frozen=True)
class Message:
    channel: Channel
    to: str
    content: str
    subject: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SendResult:
    debug_code: str | None = None


class MessageSender(Protocol):
    async def send(self, message: Message) -> SendResult: ...


@dataclass(frozen=True)
class WebhookConfig:
    url: str
    headers: dict[str, str] = field(default_factory=dict)


class MockSender:
    def __init__(self, *, debug_return_code: bool):
        self._debug_return_code = debug_return_code

    async def send(self, message: Message) -> SendResult:
        code = str(message.meta.get("code") or "")
        purpose = message.meta.get("purpose")
        tenant_name = message.meta.get("tenantName")
        ttl_minutes = message.meta.get("ttlMinutes")

        if self._debug_return_code:
            logger.info(
                "message_send_mock",
                channel=message.channel,
                target=message.to,
                purpose=purpose,
                tenant=tenant_name,
                ttl_minutes=ttl_minutes,
                code=code or None,
            )
            return SendResult(debug_code=code or None)

        logger.info(
            "message_send_mock",
            channel=message.channel,
            target="***",
            purpose=purpose,
            tenant=tenant_name,
            ttl_minutes=ttl_minutes,
        )
        return SendResult()


class WebhookSender:
    def __init__(self, cfg: WebhookConfig, *, timeout_seconds: float = 10):
        self._cfg = cfg
        self._timeout_seconds = timeout_seconds

    async def send(self, message: Message) -> SendResult:
        payload: dict[str, Any] = {
            "channel": message.channel,
            "to": message.to,
            "content": message.content,
        }
        if message.subject is not None:
            payload["subject"] = message.subject
        # Keep a flat payload for compatibility with simple webhook handlers,
        # while still allowing arbitrary metadata.
        payload.update(message.meta or {})

        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            resp = await client.post(
                self._cfg.url,
                json=payload,
                headers=dict(self._cfg.headers or {}),
            )
            if resp.status_code >= 400:
                code = "SMS_SEND_FAILED" if message.channel == "sms" else "EMAIL_SEND_FAILED"
                raise BusinessError(
                    message="Send failed",
                    code=code,
                    details={"status": resp.status_code, "body": resp.text[:500]},
                )
        return SendResult()


class SmtpEmailSender:
    def __init__(self, cfg: SmtpConfig):
        self._cfg = cfg

    async def send(self, message: Message) -> SendResult:
        if message.channel != "email":
            raise BusinessError(message="SMTP sender only supports email", code="EMAIL_PROVIDER_UNSUPPORTED")

        if not self._cfg.host or not self._cfg.sender_email:
            raise BusinessError(message="Email SMTP is not configured", code="EMAIL_NOT_CONFIGURED")
        if bool(self._cfg.username) != bool(self._cfg.password):
            raise BusinessError(
                message="SMTP username and password must be configured together",
                code="EMAIL_SMTP_INVALID",
            )

        msg = EmailMessage()
        msg["Subject"] = message.subject or ""
        msg["From"] = (
            formataddr((self._cfg.sender_name, self._cfg.sender_email))
            if self._cfg.sender_name
            else self._cfg.sender_email
        )
        msg["To"] = message.to
        msg.set_content(message.content)

        def _send_sync() -> None:
            context = ssl.create_default_context()
            if self._cfg.security == "ssl":
                smtp_client = smtplib.SMTP_SSL(
                    self._cfg.host,
                    self._cfg.port,
                    timeout=self._cfg.timeout_seconds,
                    context=context,
                )
            else:
                smtp_client = smtplib.SMTP(
                    self._cfg.host,
                    self._cfg.port,
                    timeout=self._cfg.timeout_seconds,
                )
            with smtp_client as smtp:
                if self._cfg.security == "starttls":
                    smtp.starttls(context=context)
                if self._cfg.username and self._cfg.password:
                    smtp.login(self._cfg.username, self._cfg.password)
                smtp.send_message(msg)

        try:
            await anyio.to_thread.run_sync(_send_sync)
        except smtplib.SMTPResponseException as exc:
            status = int(exc.smtp_code)
            retryable = 400 <= status < 500
            raise BusinessError(
                message="SMTP delivery was temporarily rejected" if retryable else "SMTP configuration was rejected",
                code="EMAIL_SEND_RETRYABLE" if retryable else "EMAIL_SMTP_CONFIGURATION_ERROR",
                details={"smtpStatus": status, "retryable": retryable},
            ) from None
        except (TimeoutError, OSError):
            raise BusinessError(
                message="SMTP delivery is temporarily unavailable",
                code="EMAIL_SEND_RETRYABLE",
                details={"retryable": True},
            ) from None
        except smtplib.SMTPException:
            raise BusinessError(
                message="SMTP delivery failed",
                code="EMAIL_SEND_FAILED",
                details={"retryable": False},
            ) from None
        return SendResult()


def create_sender(
    *,
    channel: Channel,
    provider: str,
    webhook_url: str | None = None,
    webhook_headers: dict[str, str] | None = None,
    smtp: SmtpConfig | None = None,
    debug_return_code: bool = False,
) -> MessageSender:
    provider_key = (provider or "").strip().lower()

    if provider_key == "mock":
        return MockSender(debug_return_code=debug_return_code)

    if provider_key == "webhook":
        if not webhook_url:
            code = "SMS_NOT_CONFIGURED" if channel == "sms" else "EMAIL_NOT_CONFIGURED"
            label = "SMS" if channel == "sms" else "Email"
            raise BusinessError(message=f"{label} webhookUrl is not configured", code=code)
        return WebhookSender(WebhookConfig(url=webhook_url, headers=dict(webhook_headers or {})))

    if provider_key == "smtp":
        if channel != "email":
            raise BusinessError(message=f"Unsupported SMS provider: {provider}", code="SMS_PROVIDER_UNSUPPORTED")

        if smtp is None:
            raise BusinessError(message="Email SMTP is not configured", code="EMAIL_NOT_CONFIGURED")
        if not isinstance(smtp, SmtpConfig):
            raise BusinessError(message="Email SMTP config must be typed", code="EMAIL_SMTP_INVALID")
        if bool(smtp.username) != bool(smtp.password):
            raise BusinessError(
                message="SMTP username and password must be configured together",
                code="EMAIL_SMTP_INVALID",
            )
        return SmtpEmailSender(smtp)

    if channel == "sms":
        raise BusinessError(message=f"Unsupported SMS provider: {provider}", code="SMS_PROVIDER_UNSUPPORTED")
    raise BusinessError(message=f"Unsupported email provider: {provider}", code="EMAIL_PROVIDER_UNSUPPORTED")
