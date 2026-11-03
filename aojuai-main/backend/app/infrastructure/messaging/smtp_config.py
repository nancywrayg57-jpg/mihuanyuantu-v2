"""Typed SMTP configuration and tenant-aware resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.core.config import settings
from app.core.exceptions import BusinessError
from app.core.provider_secrets import decrypt_provider_secret, normalize_provider_secret_text
from app.core.tenant_config_namespaces import safe_tenant_config_dict

SmtpSecurity = Literal["plain", "starttls", "ssl"]
TenantSmtpMode = Literal["inherit", "override", "disabled"]


@dataclass(frozen=True)
class SmtpConfig:
    host: str
    port: int
    username: str | None
    password: str | None
    sender_email: str
    sender_name: str | None
    security: SmtpSecurity
    timeout_seconds: float


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _invalid(message: str) -> BusinessError:
    return BusinessError(message=message, code="EMAIL_SMTP_INVALID")


def _coerce_bool(value: Any, *, field: str, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off", ""}:
            return False
    raise _invalid(f"SMTP {field} must be a boolean")


def _coerce_port(value: Any, *, default: int) -> int:
    if value in (None, ""):
        return default
    try:
        port = int(value)
    except (TypeError, ValueError) as exc:
        raise _invalid("SMTP port must be a number") from exc
    if isinstance(value, bool) or port < 1 or port > 65535:
        raise _invalid("SMTP port must be between 1 and 65535")
    return port


def _coerce_timeout(value: Any, *, default: float) -> float:
    if value in (None, ""):
        return default
    try:
        timeout = float(value)
    except (TypeError, ValueError) as exc:
        raise _invalid("SMTP timeoutSeconds must be a number") from exc
    if isinstance(value, bool) or timeout <= 0:
        raise _invalid("SMTP timeoutSeconds must be greater than 0")
    return timeout


def _security_from_mapping(smtp: dict[str, Any]) -> SmtpSecurity:
    raw_security = _clean_text(smtp.get("security"))
    use_ssl = _coerce_bool(
        smtp.get("useSsl", smtp.get("use_ssl")),
        field="useSsl",
        default=False,
    )
    use_tls = _coerce_bool(
        smtp.get("useTls", smtp.get("use_tls")),
        field="useTls",
        default=False if raw_security is not None else not use_ssl,
    )
    if use_tls and use_ssl:
        raise _invalid("SMTP useTls and useSsl cannot both be enabled")

    if raw_security is not None:
        security = raw_security.lower()
        if security not in {"plain", "starttls", "ssl"}:
            raise _invalid("SMTP security must be plain, starttls, or ssl")
        if use_tls and security != "starttls":
            raise _invalid("SMTP security conflicts with useTls")
        if use_ssl and security != "ssl":
            raise _invalid("SMTP security conflicts with useSsl")
        return security  # type: ignore[return-value]

    if use_ssl:
        return "ssl"
    if use_tls:
        return "starttls"
    return "plain"


def smtp_config_from_settings() -> SmtpConfig | None:
    """Build system SMTP configuration exclusively from application Settings."""
    host = _clean_text(settings.SMTP_HOST)
    username = _clean_text(settings.SMTP_USERNAME)
    sender_email = _clean_text(settings.SMTP_FROM_EMAIL) or username
    if not host or not sender_email:
        return None

    use_tls = bool(settings.SMTP_USE_TLS)
    use_ssl = bool(settings.SMTP_USE_SSL)
    if use_tls and use_ssl:
        raise _invalid("System SMTP_USE_TLS and SMTP_USE_SSL cannot both be enabled")
    security: SmtpSecurity = "ssl" if use_ssl else "starttls" if use_tls else "plain"

    password = settings.SMTP_PASSWORD
    normalized_password = str(password) if password not in (None, "") else None
    if bool(username) != bool(normalized_password):
        raise _invalid("System SMTP username and password must be configured together")

    return SmtpConfig(
        host=host,
        port=_coerce_port(settings.SMTP_PORT, default=465 if security == "ssl" else 587),
        username=username,
        password=normalized_password,
        sender_email=sender_email,
        sender_name=_clean_text(settings.SMTP_FROM_NAME),
        security=security,
        timeout_seconds=_coerce_timeout(settings.SMTP_TIMEOUT_SECONDS, default=10.0),
    )


def _email_transport(tenant_config: Any) -> tuple[TenantSmtpMode, dict[str, Any] | None]:
    config = safe_tenant_config_dict(tenant_config)
    messaging = config.get("messaging")
    if isinstance(messaging, dict) and "email" in messaging:
        raw_email = messaging.get("email")
        if raw_email is not None and not isinstance(raw_email, dict):
            raise _invalid("messaging.email must be an object")
        email = safe_tenant_config_dict(raw_email)
        raw_mode = _clean_text(email.get("mode")) or "inherit"
        mode = raw_mode.lower()
        if mode not in {"inherit", "override", "disabled"}:
            raise _invalid("SMTP mode must be inherit, override, or disabled")
        return mode, safe_tenant_config_dict(email.get("smtp")) or None  # type: ignore[return-value]

    verification = safe_tenant_config_dict(config.get("verification"))
    legacy_email = safe_tenant_config_dict(verification.get("email"))
    if isinstance(legacy_email.get("smtp"), dict):
        return "override", safe_tenant_config_dict(legacy_email.get("smtp"))
    return "inherit", None


def tenant_smtp_mode(tenant_config: Any) -> TenantSmtpMode:
    """Return the effective tenant SMTP mode, including legacy-path compatibility."""
    mode, _ = _email_transport(tenant_config)
    return mode


def _tenant_override_config(smtp: dict[str, Any] | None) -> SmtpConfig:
    if not smtp:
        raise BusinessError(
            message="Tenant SMTP override is incomplete",
            code="EMAIL_SMTP_INCOMPLETE",
        )
    if normalize_provider_secret_text(smtp.get("password")):
        raise _invalid("Tenant SMTP password must be stored as passwordEncrypted")

    security = _security_from_mapping(smtp)
    host = _clean_text(smtp.get("host"))
    sender_email = _clean_text(
        smtp.get("senderEmail") or smtp.get("sender_email") or smtp.get("from")
    )
    if not host or not sender_email:
        raise BusinessError(
            message="Tenant SMTP override requires host and senderEmail",
            code="EMAIL_SMTP_INCOMPLETE",
        )

    username = _clean_text(smtp.get("username"))
    encrypted_password = normalize_provider_secret_text(smtp.get("passwordEncrypted"))
    password: str | None = None
    if encrypted_password:
        try:
            password = decrypt_provider_secret(encrypted_password)
        except Exception:
            raise _invalid("Tenant SMTP password could not be decrypted") from None
    if bool(username) != bool(password):
        raise BusinessError(
            message="Tenant SMTP username and passwordEncrypted must be configured together",
            code="EMAIL_SMTP_INCOMPLETE",
        )

    return SmtpConfig(
        host=host,
        port=_coerce_port(smtp.get("port"), default=465 if security == "ssl" else 587),
        username=username,
        password=password,
        sender_email=sender_email,
        sender_name=_clean_text(smtp.get("senderName") or smtp.get("sender_name")),
        security=security,
        timeout_seconds=_coerce_timeout(
            smtp.get("timeoutSeconds", smtp.get("timeout_seconds")),
            default=10.0,
        ),
    )


def resolve_smtp_config(tenant_config: Any) -> SmtpConfig | None:
    """Resolve SMTP once; delivery failures never trigger transport fallback."""
    mode, smtp = _email_transport(tenant_config)
    if mode == "disabled":
        return None
    if mode == "inherit":
        return smtp_config_from_settings()
    return _tenant_override_config(smtp)
