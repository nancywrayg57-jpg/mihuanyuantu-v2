from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from starlette.responses import JSONResponse

from app.api.v1.endpoints import message_channels as channel_endpoints
from app.api.v1.endpoints import message_gateways as gateway_endpoints
from app.api.v1.endpoints.message_channels import _generate_unique_bind_code
from app.core.exceptions import AOJUException, TooManyRequestsError, UnauthorizedError
from app.domain.notifications import gateway_service as gateway_service_mod
from app.domain.notifications.gateway_service import (
    InboundGatewayAuthContext,
    MessageGatewayAccountService,
    _sanitized_feishu_event_header,
    authenticate_inbound_gateway_request,
    build_gateway_inbound_signature,
    extract_bind_token,
)
from app.domain.notifications.message_channels import UserMessageChannelService
from app.infrastructure.database import get_db

_NOW = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
_BODY = b'{"event":{"message":"hello"}}'
_SECRET = "runtime-test-secret"
_ACCOUNT_ID = "bot-1"
_NONCE = "nonce-1234567890abcdef"


class _Result:
    def __init__(self, value=None, *, scalars_value=None) -> None:  # noqa: ANN001
        self.value = value
        self.scalars_value = scalars_value

    def scalar_one_or_none(self):  # noqa: ANN201
        return self.value

    def scalar_one(self):  # noqa: ANN201
        return self.value

    def scalars(self):  # noqa: ANN201
        value = self.scalars_value

        class _Scalars:
            def first(self):  # noqa: ANN201
                return value

        return _Scalars()


class _AuthDB:
    def __init__(self, *, nonce_insert_id: int | None = 11) -> None:
        self.nonce_insert_id = nonce_insert_id
        self.statements: list[object] = []

    async def execute(self, statement):  # noqa: ANN001, ANN201
        self.statements.append(statement)
        if getattr(statement, "__visit_name__", "") == "insert":
            return _Result(self.nonce_insert_id)
        return _Result()


@pytest.mark.asyncio
async def test_new_binding_codes_have_eight_digits_and_legacy_codes_remain_in_flight_compatible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = SimpleNamespace(get_one=AsyncMock(return_value=None))
    monkeypatch.setattr(channel_endpoints.secrets, "randbelow", lambda _limit: 42)

    code = await _generate_unique_bind_code(service)  # type: ignore[arg-type]

    assert code == "10000042"
    assert extract_bind_token(code) == code
    assert extract_bind_token("123456") == "123456"
    assert extract_bind_token("1234567") is None


@pytest.mark.asyncio
async def test_feishu_upsert_scrubs_legacy_plaintext_callback_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing = SimpleNamespace(
        extra={
            "verificationToken": "legacy-value",
            "encryptKey": "legacy-value",
            "preserved": "yes",
        }
    )
    service = MessageGatewayAccountService(object())  # type: ignore[arg-type]
    service._clear_defaults = AsyncMock()  # type: ignore[method-assign]
    service.get_one = AsyncMock(return_value=existing)  # type: ignore[method-assign]
    service.update = AsyncMock(return_value=existing)  # type: ignore[method-assign]
    monkeypatch.setattr(gateway_service_mod, "encrypt_provider_secret", lambda _value: "encrypted")

    await service.upsert_feishu_account(
        name="feishu",
        app_id="app-id",
        app_secret="app-secret",
        domain="feishu",
    )

    values = service.update.await_args.args[1]
    assert values["token_encrypted"] == "encrypted"
    assert values["extra"]["preserved"] == "yes"
    assert "verificationToken" not in values["extra"]
    assert "encryptKey" not in values["extra"]


def test_feishu_callback_credentials_are_removed_before_business_json_storage() -> None:
    sanitized = _sanitized_feishu_event_header(
        {
            "event_type": "im.message.receive_v1",
            "token": "callback-value",
            "verificationToken": "callback-value",
            "encrypt_key": "callback-value",
            "signature": "callback-value",
            "authorization": "callback-value",
        }
    )

    assert sanitized == {"event_type": "im.message.receive_v1"}


def _headers(*, missing: str | None = None) -> dict[str, str]:
    timestamp = str(int(_NOW.timestamp()))
    values = {
        "account_id": _ACCOUNT_ID,
        "timestamp": timestamp,
        "nonce": _NONCE,
        "signature": build_gateway_inbound_signature(
            secret=_SECRET,
            channel_type="wecom",
            account_id=_ACCOUNT_ID,
            timestamp=timestamp,
            nonce=_NONCE,
            body=_BODY,
        ),
    }
    if missing:
        values[missing] = ""
    return values


def _install_account_service(
    monkeypatch: pytest.MonkeyPatch,
    *,
    account: object | None = None,
) -> None:
    resolved = account if account is not None else SimpleNamespace(id=7, token_encrypted="encrypted")

    class _AccountService:
        def __init__(self, _db) -> None:  # noqa: ANN001
            pass

        async def get_active_by_account_id(self, channel_type: str, account_id: str):  # noqa: ANN201
            assert channel_type == "wecom"
            assert account_id == _ACCOUNT_ID
            return resolved

    monkeypatch.setattr(gateway_service_mod, "MessageGatewayAccountService", _AccountService)
    monkeypatch.setattr(gateway_service_mod, "decrypt_provider_secret_or_plain", lambda _value: _SECRET)


@pytest.mark.asyncio
async def test_signed_gateway_request_uses_constant_time_compare_and_records_nonce(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_account_service(monkeypatch)
    db = _AuthDB()
    headers = _headers()

    context = await authenticate_inbound_gateway_request(
        db,  # type: ignore[arg-type]
        channel_type="wecom",
        body=_BODY,
        allow_unsigned=False,
        now=_NOW,
        **headers,
    )

    assert context == InboundGatewayAuthContext(gateway_account_id=7, signed=True)
    assert any(getattr(stmt, "__visit_name__", "") == "insert" for stmt in db.statements)


@pytest.mark.asyncio
async def test_compare_digest_mutation_makes_valid_signature_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mutation check: replacing compare_digest with a false result must make this test red."""
    _install_account_service(monkeypatch)
    compare_calls: list[tuple[str, str]] = []

    def _mutated_compare(left: str, right: str) -> bool:
        compare_calls.append((left, right))
        return False

    monkeypatch.setattr(gateway_service_mod.hmac, "compare_digest", _mutated_compare)

    with pytest.raises(UnauthorizedError):
        await authenticate_inbound_gateway_request(
            _AuthDB(),  # type: ignore[arg-type]
            channel_type="wecom",
            body=_BODY,
            allow_unsigned=False,
            now=_NOW,
            **_headers(),
        )

    assert len(compare_calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", [None, "account_id", "timestamp", "nonce", "signature"])
async def test_missing_gateway_auth_material_is_fail_closed_even_during_transition(
    monkeypatch: pytest.MonkeyPatch,
    missing: str | None,
) -> None:
    """Mutation check for both legacy ``expected and incoming`` fail-open branches."""
    _install_account_service(monkeypatch)
    values = dict.fromkeys(_headers(), "") if missing is None else _headers(missing=missing)

    with pytest.raises(UnauthorizedError):
        await authenticate_inbound_gateway_request(
            _AuthDB(),  # type: ignore[arg-type]
            channel_type="wecom",
            body=_BODY,
            allow_unsigned=(missing is not None),
            now=_NOW,
            **values,
        )


@pytest.mark.asyncio
async def test_transition_accepts_only_fully_unsigned_and_emits_critical_security_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[tuple[str, dict[str, object]]] = []

    class _Logger:
        def critical(self, event: str, **fields: object) -> None:
            events.append((event, fields))

    monkeypatch.setattr(gateway_service_mod, "logger", _Logger())
    context = await authenticate_inbound_gateway_request(
        _AuthDB(),  # type: ignore[arg-type]
        channel_type="feishu",
        account_id=None,
        timestamp=None,
        nonce=None,
        signature=None,
        body=_BODY,
        allow_unsigned=True,
        now=_NOW,
    )

    assert context == InboundGatewayAuthContext(gateway_account_id=None, signed=False)
    assert events == [
        (
            "message_gateway_unsigned_inbound_accepted",
            {
                "security_event": "gateway_authentication_bypass",
                "auth_result": "transition_unsigned_accepted",
                "migration_mode": True,
                "channel_type": "feishu",
                "action_required": "upgrade_gateway_runtime_and_disable_transition",
            },
        )
    ]


@pytest.mark.asyncio
async def test_configured_headers_still_fail_when_account_secret_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_account_service(monkeypatch, account=SimpleNamespace(id=7, token_encrypted=None))
    monkeypatch.setattr(gateway_service_mod, "decrypt_provider_secret_or_plain", lambda _value: "")

    with pytest.raises(UnauthorizedError):
        await authenticate_inbound_gateway_request(
            _AuthDB(),  # type: ignore[arg-type]
            channel_type="wecom",
            body=_BODY,
            allow_unsigned=True,
            now=_NOW,
            **_headers(),
        )


@pytest.mark.asyncio
async def test_stale_timestamp_and_reused_nonce_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_account_service(monkeypatch)
    stale = _headers()
    stale["timestamp"] = str(int(_NOW.timestamp()) - 301)

    with pytest.raises(UnauthorizedError):
        await authenticate_inbound_gateway_request(
            _AuthDB(),  # type: ignore[arg-type]
            channel_type="wecom",
            body=_BODY,
            allow_unsigned=False,
            now=_NOW,
            **stale,
        )

    with pytest.raises(UnauthorizedError):
        await authenticate_inbound_gateway_request(
            _AuthDB(nonce_insert_id=None),  # type: ignore[arg-type]
            channel_type="wecom",
            body=_BODY,
            allow_unsigned=False,
            now=_NOW,
            **_headers(),
        )


@pytest.mark.asyncio
async def test_all_public_inbound_routes_authenticate_before_business_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def _deny(_db, *, channel_type: str, **_kwargs):  # noqa: ANN001, ANN003, ANN201
        calls.append(channel_type)
        raise UnauthorizedError(message="denied by mutation sentinel")

    monkeypatch.setattr(gateway_endpoints, "authenticate_inbound_gateway_request", _deny)
    monkeypatch.setattr(channel_endpoints, "authenticate_inbound_gateway_request", _deny)

    app = FastAPI()
    app.include_router(gateway_endpoints.router, prefix="/api/v1/message-gateways")
    app.include_router(channel_endpoints.router, prefix="/api/v1/message-channels")

    @app.exception_handler(AOJUException)
    async def _handle_exception(_request, exc: AOJUException):  # noqa: ANN001, ANN201
        return JSONResponse(status_code=exc.status_code, content={"code": exc.code})

    async def _db_override():  # noqa: ANN202
        yield object()

    app.dependency_overrides[get_db] = _db_override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        responses = [
            await client.post("/api/v1/message-gateways/wecom/events", json={}),
            await client.post("/api/v1/message-gateways/feishu/events", json={"challenge": "challenge"}),
            await client.post(
                "/api/v1/message-channels/bind/inbound",
                json={
                    "bindingCode": "12345678",
                    "channelType": "wecom",
                    "externalUserId": "external-user",
                },
            ),
        ]

    assert [response.status_code for response in responses] == [401, 401, 401]
    assert calls == ["wecom", "feishu", "wecom"]


@pytest.mark.asyncio
async def test_invalid_binding_code_records_a_failed_attempt() -> None:
    class _BindDB:
        async def execute(self, _statement):  # noqa: ANN001, ANN201
            return _Result(None)

    service = UserMessageChannelService(_BindDB())  # type: ignore[arg-type]
    service._enforce_bind_rate_limit = AsyncMock()  # type: ignore[method-assign]
    service._record_failed_bind_attempt = AsyncMock()  # type: ignore[method-assign]

    channel = await service.bind_inbound_message(
        bind_token="12345678",
        channel_type="wecom",
        external_user_id="external-user",
        conversation_id=None,
        context_token=None,
    )

    assert channel is None
    service._record_failed_bind_attempt.assert_awaited_once()


@pytest.mark.asyncio
async def test_blocked_binding_subject_is_rejected_before_code_lookup() -> None:
    blocked = SimpleNamespace(
        guard_key="a" * 64,
        failure_count=5,
        blocked_until=_NOW,
    )

    class _BindDB:
        def __init__(self) -> None:
            self.calls = 0

        async def execute(self, _statement):  # noqa: ANN001, ANN201
            self.calls += 1
            return _Result(scalars_value=blocked if self.calls == 2 else None)

    service = UserMessageChannelService(_BindDB())  # type: ignore[arg-type]

    with pytest.raises(TooManyRequestsError):
        await service._enforce_bind_rate_limit(channel_type="wecom", guard_keys=["a" * 64])
