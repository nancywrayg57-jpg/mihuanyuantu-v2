from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core import verification
from app.core.exceptions import BusinessError
from app.core.provider_secrets import encrypt_provider_secret
from app.infrastructure.messaging import smtp_config as smtp_config_module
from app.infrastructure.messaging.smtp_config import (
    SmtpConfig,
    resolve_smtp_config,
    smtp_config_from_settings,
    tenant_smtp_mode,
)


def _system_settings(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "SMTP_HOST": "system.smtp.example",
        "SMTP_PORT": 587,
        "SMTP_USERNAME": "system-user",
        "SMTP_PASSWORD": "system-password",
        "SMTP_FROM_EMAIL": "system@example.com",
        "SMTP_FROM_NAME": "System Mail",
        "SMTP_USE_TLS": True,
        "SMTP_USE_SSL": False,
        "SMTP_TIMEOUT_SECONDS": 12.5,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _override_smtp(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "host": "tenant.smtp.example",
        "port": 465,
        "senderEmail": "tenant@example.com",
        "security": "ssl",
        "timeoutSeconds": 8,
    }
    values.update(overrides)
    return values


def test_inherit_uses_typed_system_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(smtp_config_module, "settings", _system_settings())

    resolved = resolve_smtp_config({"messaging": {"email": {"mode": "inherit"}}})

    assert resolved == SmtpConfig(
        host="system.smtp.example",
        port=587,
        username="system-user",
        password="system-password",
        sender_email="system@example.com",
        sender_name="System Mail",
        security="starttls",
        timeout_seconds=12.5,
    )
    assert tenant_smtp_mode({}) == "inherit"


def test_override_decrypts_tenant_password_and_never_uses_system(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(smtp_config_module, "settings", _system_settings())
    encrypted = encrypt_provider_secret("tenant-password")

    resolved = resolve_smtp_config(
        {
            "messaging": {
                "email": {
                    "mode": "override",
                    "smtp": _override_smtp(
                        username="tenant-user",
                        passwordEncrypted=encrypted,
                    ),
                }
            }
        }
    )

    assert resolved is not None
    assert resolved.host == "tenant.smtp.example"
    assert resolved.username == "tenant-user"
    assert resolved.password == "tenant-password"
    assert tenant_smtp_mode({"messaging": {"email": {"mode": "override"}}}) == "override"


def test_disabled_returns_none_without_reading_system(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_if_called() -> None:
        raise AssertionError("system fallback must not be attempted")

    monkeypatch.setattr(smtp_config_module, "smtp_config_from_settings", fail_if_called)
    config = {"messaging": {"email": {"mode": "disabled", "smtp": _override_smtp()}}}

    assert resolve_smtp_config(config) is None
    assert tenant_smtp_mode(config) == "disabled"


@pytest.mark.parametrize(
    ("host", "sender", "username"),
    [
        ("", "system@example.com", "system-user"),
        ("system.smtp.example", "", ""),
    ],
)
def test_unconfigured_system_smtp_returns_none(
    monkeypatch: pytest.MonkeyPatch,
    host: str,
    sender: str,
    username: str,
) -> None:
    monkeypatch.setattr(
        smtp_config_module,
        "settings",
        _system_settings(
            SMTP_HOST=host,
            SMTP_FROM_EMAIL=sender,
            SMTP_USERNAME=username or None,
            SMTP_PASSWORD="system-password" if username else None,
        ),
    )
    assert smtp_config_from_settings() is None
    assert resolve_smtp_config({}) is None


def test_incomplete_override_raises_instead_of_falling_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(smtp_config_module, "settings", _system_settings())
    tenant = {
        "messaging": {
            "email": {
                "mode": "override",
                "smtp": {"host": "tenant.smtp.example"},
            }
        }
    }

    with pytest.raises(BusinessError) as exc_info:
        resolve_smtp_config(tenant)

    assert exc_info.value.code == "EMAIL_SMTP_INCOMPLETE"


def test_override_decryption_failure_raises_without_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(smtp_config_module, "settings", _system_settings())
    tenant = {
        "messaging": {
            "email": {
                "mode": "override",
                "smtp": _override_smtp(
                    username="tenant-user",
                    passwordEncrypted="gAAAAA-invalid-ciphertext",
                ),
            }
        }
    }

    with pytest.raises(BusinessError) as exc_info:
        resolve_smtp_config(tenant)

    assert exc_info.value.code == "EMAIL_SMTP_INVALID"
    assert "system" not in exc_info.value.message.lower()


def test_override_rejects_plaintext_password() -> None:
    tenant = {
        "messaging": {
            "email": {
                "mode": "override",
                "smtp": _override_smtp(username="tenant-user", password="plaintext"),
            }
        }
    }
    with pytest.raises(BusinessError) as exc_info:
        resolve_smtp_config(tenant)
    assert exc_info.value.code == "EMAIL_SMTP_INVALID"


def test_use_tls_and_use_ssl_conflict_is_rejected() -> None:
    tenant = {
        "messaging": {
            "email": {
                "mode": "override",
                "smtp": _override_smtp(security=None, useTls=True, useSsl=True),
            }
        }
    }
    with pytest.raises(BusinessError) as exc_info:
        resolve_smtp_config(tenant)
    assert exc_info.value.code == "EMAIL_SMTP_INVALID"


@pytest.mark.parametrize(
    ("smtp", "sender_email", "security"),
    [
        ({"host": "smtp.example", "from": "from@example.com", "useTls": True}, "from@example.com", "starttls"),
        (
            {"host": "smtp.example", "sender_email": "snake@example.com", "use_tls": False},
            "snake@example.com",
            "plain",
        ),
        (
            {"host": "smtp.example", "senderEmail": "camel@example.com", "useSsl": True},
            "camel@example.com",
            "ssl",
        ),
        (
            {"host": "smtp.example", "senderEmail": "camel@example.com", "use_ssl": True},
            "camel@example.com",
            "ssl",
        ),
        (
            {"host": "smtp.example", "senderEmail": "camel@example.com", "useSsl": False},
            "camel@example.com",
            "starttls",
        ),
    ],
)
def test_tenant_aliases_are_normalized(
    smtp: dict[str, object],
    sender_email: str,
    security: str,
) -> None:
    resolved = resolve_smtp_config(
        {"messaging": {"email": {"mode": "override", "smtp": smtp}}}
    )
    assert resolved is not None
    assert resolved.sender_email == sender_email
    assert resolved.security == security


def test_legacy_verification_email_smtp_is_an_override() -> None:
    tenant = {"verification": {"email": {"smtp": _override_smtp()}}}

    resolved = resolve_smtp_config(tenant)

    assert tenant_smtp_mode(tenant) == "override"
    assert resolved is not None
    assert resolved.host == "tenant.smtp.example"


@pytest.mark.asyncio
async def test_production_email_verification_fails_closed_without_smtp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        smtp_config_module,
        "settings",
        _system_settings(
            SMTP_HOST="",
            SMTP_FROM_EMAIL="",
            SMTP_USERNAME=None,
            SMTP_PASSWORD=None,
        ),
    )
    monkeypatch.setattr(verification.settings, "DEBUG", False)
    monkeypatch.setattr(verification.settings, "ENV", "production")

    with pytest.raises(BusinessError) as exc_info:
        await verification.send_verification_code(
            channel="email",
            target="person@example.com",
            code="123456",
            tenant_name="Demo",
            tenant_config={},
            purpose="register",
        )

    assert exc_info.value.code == "EMAIL_NOT_CONFIGURED"
