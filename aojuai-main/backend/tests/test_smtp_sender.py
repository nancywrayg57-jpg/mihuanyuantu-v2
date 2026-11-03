from __future__ import annotations

from typing import Any

import pytest

from app.core.exceptions import BusinessError
from app.infrastructure.messaging import Message, SmtpConfig, create_sender
from app.infrastructure.messaging import senders


def _config(**overrides: Any) -> SmtpConfig:
    values: dict[str, Any] = {
        "host": "smtp.example.com",
        "port": 587,
        "username": "smtp-user",
        "password": "smtp-password",
        "sender_email": "sender@example.com",
        "sender_name": None,
        "security": "starttls",
        "timeout_seconds": 10.0,
    }
    values.update(overrides)
    return SmtpConfig(**values)


def _install_fake_clients(
    monkeypatch: pytest.MonkeyPatch,
    *,
    send_error: Exception | None = None,
) -> list[tuple[str, Any]]:
    events: list[tuple[str, Any]] = []

    async def run_sync_inline(function: Any) -> Any:
        return function()

    class FakeSmtp:
        def __init__(self, kind: str, host: str, port: int, timeout: float, **kwargs: Any):
            events.append(("connect", (kind, host, port, timeout, set(kwargs))))

        def __enter__(self) -> "FakeSmtp":
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def starttls(self, *, context: Any) -> None:
            events.append(("starttls", context))

        def login(self, username: str, password: str) -> None:
            events.append(("login", (username, password)))

        def send_message(self, message: Any) -> None:
            events.append(("message", message))
            if send_error is not None:
                raise send_error

    def smtp_factory(host: str, port: int, timeout: float) -> FakeSmtp:
        return FakeSmtp("plain", host, port, timeout)

    def smtp_ssl_factory(host: str, port: int, timeout: float, **kwargs: Any) -> FakeSmtp:
        return FakeSmtp("ssl", host, port, timeout, **kwargs)

    monkeypatch.setattr(senders.smtplib, "SMTP", smtp_factory)
    monkeypatch.setattr(senders.smtplib, "SMTP_SSL", smtp_ssl_factory)
    monkeypatch.setattr(senders.anyio.to_thread, "run_sync", run_sync_inline)
    return events


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("security", "expected_client", "expected_starttls"),
    [
        ("plain", "plain", False),
        ("starttls", "plain", True),
        ("ssl", "ssl", False),
    ],
)
async def test_smtp_security_branches(
    monkeypatch: pytest.MonkeyPatch,
    security: str,
    expected_client: str,
    expected_starttls: bool,
) -> None:
    events = _install_fake_clients(monkeypatch)
    smtp = _config(security=security, port=465 if security == "ssl" else 587)
    sender = create_sender(channel="email", provider="smtp", smtp=smtp)

    await sender.send(Message(channel="email", to="to@example.com", subject="Hello", content="Body"))

    connection = next(value for event, value in events if event == "connect")
    assert connection[0] == expected_client
    assert any(event == "starttls" for event, _ in events) is expected_starttls


@pytest.mark.asyncio
async def test_sender_name_builds_rfc_from_header(monkeypatch: pytest.MonkeyPatch) -> None:
    events = _install_fake_clients(monkeypatch)
    smtp = _config(sender_name="Demo, Inc.")
    sender = create_sender(channel="email", provider="smtp", smtp=smtp)

    await sender.send(Message(channel="email", to="to@example.com", content="Body"))

    message = next(value for event, value in events if event == "message")
    assert str(message["From"]) == '"Demo, Inc." <sender@example.com>'


@pytest.mark.parametrize(
    ("username", "password"),
    [("smtp-user", None), (None, "smtp-password")],
)
def test_username_and_password_must_be_configured_together(
    username: str | None,
    password: str | None,
) -> None:
    with pytest.raises(BusinessError) as exc_info:
        create_sender(
            channel="email",
            provider="smtp",
            smtp=_config(username=username, password=password),
        )
    assert exc_info.value.code == "EMAIL_SMTP_INVALID"


def test_create_sender_rejects_untyped_smtp_config() -> None:
    with pytest.raises(BusinessError) as exc_info:
        create_sender(
            channel="email",
            provider="smtp",
            smtp={"host": "smtp.example.com"},  # type: ignore[arg-type]
        )
    assert exc_info.value.code == "EMAIL_SMTP_INVALID"


@pytest.mark.asyncio
async def test_smtp_timeout_is_passed_to_client(monkeypatch: pytest.MonkeyPatch) -> None:
    events = _install_fake_clients(monkeypatch)
    sender = create_sender(
        channel="email",
        provider="smtp",
        smtp=_config(timeout_seconds=27.5),
    )

    await sender.send(Message(channel="email", to="to@example.com", content="Body"))

    connection = next(value for event, value in events if event == "connect")
    assert connection[3] == 27.5


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("smtp_status", "expected_code", "retryable"),
    [
        (451, "EMAIL_SEND_RETRYABLE", True),
        (535, "EMAIL_SMTP_CONFIGURATION_ERROR", False),
    ],
)
async def test_smtp_4xx_and_5xx_are_classified_without_secret_leaks(
    monkeypatch: pytest.MonkeyPatch,
    smtp_status: int,
    expected_code: str,
    retryable: bool,
) -> None:
    secret = "account-password"
    host = "smtp://url-user:url-password@smtp.example.com"
    error = senders.smtplib.SMTPDataError(smtp_status, f"rejected {secret}".encode())
    _install_fake_clients(monkeypatch, send_error=error)
    sender = create_sender(
        channel="email",
        provider="smtp",
        smtp=_config(host=host, password=secret),
    )

    with pytest.raises(BusinessError) as exc_info:
        await sender.send(Message(channel="email", to="to@example.com", content="Body"))

    exc = exc_info.value
    assert exc.code == expected_code
    assert exc.details == {"smtpStatus": smtp_status, "retryable": retryable}
    public_error = f"{exc.message} {exc.details} {exc}"
    assert secret not in public_error
    assert "url-user" not in public_error
    assert "url-password" not in public_error


@pytest.mark.asyncio
async def test_network_timeout_is_retryable(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_clients(monkeypatch, send_error=TimeoutError("smtp-password"))
    sender = create_sender(channel="email", provider="smtp", smtp=_config())

    with pytest.raises(BusinessError) as exc_info:
        await sender.send(Message(channel="email", to="to@example.com", content="Body"))

    assert exc_info.value.code == "EMAIL_SEND_RETRYABLE"
    assert "smtp-password" not in str(exc_info.value)
