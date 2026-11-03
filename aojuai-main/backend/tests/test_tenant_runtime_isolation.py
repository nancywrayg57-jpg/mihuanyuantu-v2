from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from starlette.requests import Request

from app.api import deps as deps_mod
from app.api.deps import TenantScopedUser, get_tenant_context
from app.api.v1.endpoints import assistant as assistant_mod
from app.api.v1.endpoints import menus as menus_mod
from app.core.data_permission import get_user_data_scope
from app.infrastructure.cache.base_runtime_keys import build_async_routes_cache_key


def _make_request(
    *,
    path: str,
    headers: dict[str, str] | None = None,
    query_string: str = "",
    host: str = "testserver",
) -> Request:
    raw_headers = [
        (key.lower().encode("utf-8"), str(value).encode("utf-8"))
        for key, value in (headers or {}).items()
    ]
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "query_string": query_string.encode("utf-8"),
        "headers": raw_headers,
        "server": (host, 80),
        "client": ("127.0.0.1", 12345),
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_get_current_user_scopes_superuser_to_target_tenant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stored_user = SimpleNamespace(
        id=1,
        username="admin",
        tenant_id=1,
        is_superuser=True,
        is_active=True,
        deleted_at=None,
    )
    result = Mock()
    result.scalar_one_or_none.return_value = stored_user

    db = AsyncMock()
    db.execute.return_value = result

    monkeypatch.setattr(deps_mod, "decode_token", lambda _: {"type": "access", "sub": "1"})
    monkeypatch.setattr(deps_mod, "_enforce_module_switch_for_request", AsyncMock(return_value=None))

    current_user = await deps_mod.get_current_user(
        db=db,
        credentials=SimpleNamespace(scheme="Bearer", credentials="token"),
        request=_make_request(path="/api/v1/users", headers={"X-Tenant-Id": "2"}),
    )

    assert isinstance(current_user, TenantScopedUser)
    assert current_user.id == 1
    assert current_user.tenant_id == 2
    assert current_user.user_tenant_id == 1
    assert current_user.is_superuser is True


@pytest.mark.asyncio
async def test_get_current_user_ignores_cross_tenant_header_for_regular_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stored_user = SimpleNamespace(
        id=7,
        username="member",
        tenant_id=1,
        is_superuser=False,
        is_active=True,
        deleted_at=None,
    )
    result = Mock()
    result.scalar_one_or_none.return_value = stored_user

    db = AsyncMock()
    db.execute.return_value = result

    monkeypatch.setattr(deps_mod, "decode_token", lambda _: {"type": "access", "sub": "7"})
    monkeypatch.setattr(deps_mod, "_enforce_module_switch_for_request", AsyncMock(return_value=None))

    current_user = await deps_mod.get_current_user(
        db=db,
        credentials=SimpleNamespace(scheme="Bearer", credentials="token"),
        request=_make_request(path="/api/v1/users", headers={"X-Tenant-Id": "2"}),
    )

    assert current_user is stored_user
    assert current_user.tenant_id == 1


@pytest.mark.asyncio
async def test_get_tenant_context_preserves_original_tenant_on_superuser_switch() -> None:
    current_user = TenantScopedUser(
        _user=SimpleNamespace(id=1, tenant_id=1, is_superuser=True),
        tenant_id=2,
        user_tenant_id=1,
    )

    tenant_ctx = await get_tenant_context(
        current_user=current_user,
        x_tenant_id=None,
        tenant_id=None,
        tenant_id_camel=None,
    )

    assert tenant_ctx.tenant_id == 2
    assert tenant_ctx.user_tenant_id == 1
    assert tenant_ctx.is_cross_tenant is True


def test_async_routes_cache_key_changes_with_effective_tenant() -> None:
    base_user = SimpleNamespace(id=1, tenant_id=1, is_superuser=True, roles=[])
    switched_user = TenantScopedUser(
        _user=base_user,
        tenant_id=2,
        user_tenant_id=1,
    )

    assert build_async_routes_cache_key(base_user) != build_async_routes_cache_key(switched_user)


@pytest.mark.asyncio
async def test_assistant_team_lookup_is_tenant_scoped() -> None:
    result = Mock()
    result.scalars.return_value.all.return_value = [11, 12]

    db = AsyncMock()
    db.execute.return_value = result

    team_ids = await assistant_mod._get_user_team_ids(db, tenant_id=2, user_id=9)

    assert team_ids == [11, 12]
    stmt = db.execute.await_args.args[0]
    sql = str(stmt)
    assert "user_teams.tenant_id" in sql
    assert "user_teams.user_id" in sql


@pytest.mark.asyncio
async def test_menu_user_role_lookup_avoids_soft_delete_filters_on_association_tables() -> None:
    result = Mock()
    result.scalars.return_value.all.return_value = [11, 12, None]

    db = AsyncMock()
    db.execute.return_value = result

    menu_ids = await menus_mod._load_user_menu_ids(db=db, tenant_id=2, user_id=9)

    assert menu_ids == {11, 12}
    sql = str(db.execute.await_args.args[0])
    assert "user_roles.tenant_id" in sql
    assert "user_roles.user_id" in sql
    assert "user_roles.deleted_at" not in sql
    assert "role_menus.deleted_at" not in sql
    assert "roles.deleted_at" in sql


@pytest.mark.asyncio
async def test_data_scope_relation_reload_is_tenant_scoped() -> None:
    result = Mock()
    result.scalar_one_or_none.return_value = SimpleNamespace(
        id=9,
        tenant_id=2,
        roles=[],
        teams=[],
        is_superuser=False,
    )

    db = AsyncMock()
    db.execute.return_value = result

    scope = await get_user_data_scope(
        db=db,
        user=SimpleNamespace(id=9, tenant_id=2, is_superuser=False),
        load_relations=True,
    )

    assert scope.user_id == 9
    stmt = db.execute.await_args.args[0]
    sql = str(stmt)
    assert "users.id" in sql
    assert "users.tenant_id" in sql
