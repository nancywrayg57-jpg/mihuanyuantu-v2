from __future__ import annotations

import base64
import hashlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core import provider_secrets
from app.infrastructure.database import session as session_module


def test_provider_secret_key_prefers_explicit_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(provider_secrets.settings, "PROVIDER_SECRET_KEY", "provider-secret", raising=False)
    monkeypatch.setattr(provider_secrets.settings, "JWT_SECRET_KEY", "jwt-secret", raising=False)

    expected = base64.urlsafe_b64encode(hashlib.sha256(b"provider-secret").digest())
    assert provider_secrets._provider_secret_key() == expected


class _FakeSessionContext:
    def __init__(self, session: SimpleNamespace) -> None:
        self._session = session

    async def __aenter__(self) -> SimpleNamespace:
        return self._session

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


@pytest.mark.asyncio
async def test_get_db_context_allows_manual_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_session = SimpleNamespace(
        commit=AsyncMock(),
        rollback=AsyncMock(),
        close=AsyncMock(),
    )
    monkeypatch.setattr(session_module, "async_session_factory", lambda: _FakeSessionContext(fake_session))

    async with session_module.get_db_context() as db:
        await db.commit()

    assert fake_session.commit.await_count == 2
    fake_session.rollback.assert_not_awaited()
    fake_session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_db_context_rolls_back_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_session = SimpleNamespace(
        commit=AsyncMock(),
        rollback=AsyncMock(),
        close=AsyncMock(),
    )
    monkeypatch.setattr(session_module, "async_session_factory", lambda: _FakeSessionContext(fake_session))

    with pytest.raises(RuntimeError, match="boom"):
        async with session_module.get_db_context():
            raise RuntimeError("boom")

    fake_session.commit.assert_not_awaited()
    fake_session.rollback.assert_awaited_once()
    fake_session.close.assert_awaited_once()
