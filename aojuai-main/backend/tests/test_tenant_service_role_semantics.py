from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.domain.auth.service import TenantService


class _DummyScalars:
    def __init__(self, values: list[object]) -> None:
        self._values = list(values)

    def all(self) -> list[object]:
        return list(self._values)


class _DummyResult:
    def __init__(self, *, scalar_value: object | None = None, scalars_values: list[object] | None = None) -> None:
        self._scalar_value = scalar_value
        self._scalars_values = list(scalars_values or [])

    def scalar_one_or_none(self) -> object | None:
        return self._scalar_value

    def scalars(self) -> _DummyScalars:
        return _DummyScalars(self._scalars_values)


@pytest.mark.asyncio
async def test_get_tenant_users_marks_tenant_admin_as_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    user = SimpleNamespace(
        id=2,
        username="u2",
        nickname="U2",
        email=None,
        phone=None,
        status=1,
        created_at=None,
        roles=[SimpleNamespace(code="tenant_admin", is_active=True, deleted_at=None)],
    )
    get_list = AsyncMock(return_value=([user], 1))
    monkeypatch.setattr("app.infrastructure.repository.base.RepositoryBase.get_list", get_list)

    service = TenantService(AsyncMock())
    items, total = await service.get_tenant_users(tenant_id=1, is_admin=True)

    assert total == 1
    assert items[0]["isAdmin"] is True
    assert len(get_list.await_args.kwargs["where"]) == 2


@pytest.mark.asyncio
async def test_set_user_admin_adds_tenant_admin_alias_when_admin_role_missing() -> None:
    existing_user = SimpleNamespace(
        id=2,
        tenant_id=1,
        username="u2",
        nickname="U2",
        roles=[],
    )
    tenant_admin_role = SimpleNamespace(id=99, code="tenant_admin", is_active=True)
    refreshed_user = SimpleNamespace(
        id=2,
        tenant_id=1,
        username="u2",
        nickname="U2",
        roles=[SimpleNamespace(id=99, code="tenant_admin", is_active=True, deleted_at=None)],
    )

    db = AsyncMock()
    db.execute.side_effect = [
        _DummyResult(scalar_value=existing_user),
        _DummyResult(scalars_values=[tenant_admin_role]),
        _DummyResult(scalar_value=refreshed_user),
    ]
    db.add = Mock()
    db.flush = AsyncMock()

    service = TenantService(db)
    payload = await service.set_user_admin(tenant_id=1, user_id=2, is_admin=True)

    added_link = db.add.call_args.args[0]
    assert added_link.role_id == 99
    assert payload["isAdmin"] is True
    assert payload["roles"] == ["tenant_admin"]


@pytest.mark.asyncio
async def test_set_user_admin_removes_tenant_admin_alias_links() -> None:
    existing_role = SimpleNamespace(id=88, code="tenant_admin", is_active=True, deleted_at=None)
    existing_user = SimpleNamespace(
        id=2,
        tenant_id=1,
        username="u2",
        nickname="U2",
        roles=[existing_role],
    )
    user_role_link = SimpleNamespace(role_id=88, user_id=2, tenant_id=1)
    refreshed_user = SimpleNamespace(
        id=2,
        tenant_id=1,
        username="u2",
        nickname="U2",
        roles=[],
    )

    db = AsyncMock()
    db.execute.side_effect = [
        _DummyResult(scalar_value=existing_user),
        _DummyResult(scalars_values=[existing_role]),
        _DummyResult(scalars_values=[user_role_link]),
        _DummyResult(scalar_value=refreshed_user),
    ]
    db.delete = AsyncMock()
    db.flush = AsyncMock()

    service = TenantService(db)
    payload = await service.set_user_admin(tenant_id=1, user_id=2, is_admin=False)

    db.delete.assert_awaited_once_with(user_role_link)
    assert payload["isAdmin"] is False
    assert payload["roles"] == []


def test_tenant_service_response_normalizes_non_object_config() -> None:
    tenant = SimpleNamespace(
        id=1,
        name="Demo",
        code="demo",
        domain=None,
        description=None,
        is_active=True,
        expires_at=None,
        config=[],
        quota={},
        contact_name=None,
        contact_phone=None,
        contact_email=None,
        created_at=None,
    )

    detail = TenantService.to_response(tenant)  # type: ignore[arg-type]
    list_item = TenantService.to_list_item(tenant)  # type: ignore[arg-type]

    assert detail["config"] == {}
    assert list_item["config"] == {}
