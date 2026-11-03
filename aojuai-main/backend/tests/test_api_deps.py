from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from starlette.requests import Request

from app.api import deps as deps_module
from app.api.deps import (
    PermissionChecker,
    TenantAdminOrPermissionChecker,
    TenantScopedUser,
    get_current_tenant_admin,
    snapshot_current_user,
)
from app.core.exceptions import UnauthorizedError


@pytest.mark.asyncio
async def test_get_current_tenant_admin_allows_admin_role() -> None:
    current_user = SimpleNamespace(id=1, is_superuser=False)
    role = SimpleNamespace(code="admin", is_active=True, deleted_at=None)
    user_with_roles = SimpleNamespace(roles=[role])

    result = Mock()
    result.scalar_one_or_none.return_value = user_with_roles

    db = AsyncMock()
    db.execute.return_value = result

    user = await get_current_tenant_admin(current_user=current_user, db=db)
    assert user == current_user


@pytest.mark.asyncio
async def test_get_current_tenant_admin_allows_tenant_admin_role() -> None:
    current_user = SimpleNamespace(id=1, is_superuser=False)
    role = SimpleNamespace(code="tenant_admin", is_active=True, deleted_at=None)
    user_with_roles = SimpleNamespace(roles=[role])

    result = Mock()
    result.scalar_one_or_none.return_value = user_with_roles

    db = AsyncMock()
    db.execute.return_value = result

    user = await get_current_tenant_admin(current_user=current_user, db=db)
    assert user == current_user


@pytest.mark.asyncio
async def test_get_current_tenant_admin_rejects_inactive_role() -> None:
    current_user = SimpleNamespace(id=1, is_superuser=False)
    role = SimpleNamespace(code="admin", is_active=False, deleted_at=None)
    user_with_roles = SimpleNamespace(roles=[role])

    result = Mock()
    result.scalar_one_or_none.return_value = user_with_roles

    db = AsyncMock()
    db.execute.return_value = result

    with pytest.raises(UnauthorizedError):
        await get_current_tenant_admin(current_user=current_user, db=db)


@pytest.mark.asyncio
async def test_get_current_user_accepts_access_cookie(monkeypatch: pytest.MonkeyPatch) -> None:
    user = SimpleNamespace(id=1, is_active=True, deleted_at=None)
    result = Mock()
    result.scalar_one_or_none.return_value = user

    db = AsyncMock()
    db.execute.return_value = result

    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/auth/mine",
            "headers": [(b"cookie", b"aoju_access_token=cookie-token")],
        }
    )

    monkeypatch.setattr(deps_module, "decode_token", lambda token: {"type": "access", "sub": "1"})
    enforce_module = AsyncMock()
    monkeypatch.setattr(deps_module, "_enforce_module_switch_for_request", enforce_module)

    current_user = await deps_module.get_current_user(db=db, credentials=None, request=request)

    assert current_user is user
    enforce_module.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_current_user_wraps_superuser_with_effective_tenant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = SimpleNamespace(id=9, tenant_id=1, is_superuser=True, is_active=True, deleted_at=None)
    result = Mock()
    result.scalar_one_or_none.return_value = user

    db = AsyncMock()
    db.execute.return_value = result

    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/auth/session",
            "query_string": b"tenantId=2",
            "headers": [(b"cookie", b"aoju_access_token=cookie-token")],
        }
    )

    monkeypatch.setattr(deps_module, "decode_token", lambda token: {"type": "access", "sub": "9"})
    monkeypatch.setattr(deps_module, "_enforce_module_switch_for_request", AsyncMock())

    current_user = await deps_module.get_current_user(db=db, credentials=None, request=request)

    assert isinstance(current_user, TenantScopedUser)
    assert current_user.tenant_id == 2
    assert current_user.user_tenant_id == 1


@pytest.mark.asyncio
async def test_get_optional_current_user_returns_none_for_invalid_cookie(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/logout",
            "headers": [(b"cookie", b"aoju_access_token=bad-token")],
        }
    )

    def _raise(_: str) -> dict[str, str]:
        raise UnauthorizedError(message="Invalid token")

    monkeypatch.setattr(deps_module, "decode_token", _raise)

    current_user = await deps_module.get_optional_current_user(
        db=AsyncMock(),
        credentials=None,
        request=request,
    )

    assert current_user is None


@pytest.mark.asyncio
async def test_get_optional_current_user_enforces_public_module_gate_without_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/site/cms/settings",
            "headers": [(b"host", b"public.example.test")],
        }
    )
    enforce_module = AsyncMock()
    monkeypatch.setattr(
        deps_module,
        "_enforce_public_module_switch_for_request",
        enforce_module,
    )
    db = AsyncMock()

    current_user = await deps_module.get_optional_current_user(
        db=db,
        credentials=None,
        request=request,
    )

    assert current_user is None
    enforce_module.assert_awaited_once_with(
        db=db,
        request=request,
        current_user=None,
    )


@pytest.mark.asyncio
async def test_get_public_share_viewer_defers_module_gate_until_share_tenant_is_resolved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/agents/public-share-groups/access/group/apps/26/invoke",
            "headers": [],
        }
    )
    enforce_module = AsyncMock()
    monkeypatch.setattr(
        deps_module,
        "_enforce_public_module_switch_for_request",
        enforce_module,
    )

    viewer = await deps_module.get_public_share_viewer(
        db=AsyncMock(),
        credentials=None,
        request=request,
    )

    assert viewer is None
    enforce_module.assert_not_awaited()


@pytest.mark.asyncio
async def test_tenant_admin_or_permission_checker_allows_tenant_admin_role() -> None:
    checker = TenantAdminOrPermissionChecker(["training:project:update"])
    current_user = SimpleNamespace(id=1, tenant_id=7, is_superuser=False)

    result = Mock()
    result.scalar_one_or_none.return_value = 1

    db = AsyncMock()
    db.execute.return_value = result

    await checker(current_user=current_user, db=db)


@pytest.mark.asyncio
async def test_tenant_admin_or_permission_checker_falls_back_to_permissions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checker = TenantAdminOrPermissionChecker(["training:project:update"])
    current_user = SimpleNamespace(id=1, tenant_id=7, is_superuser=False)

    result = Mock()
    result.scalar_one_or_none.return_value = None

    db = AsyncMock()
    db.execute.return_value = result

    fallback = AsyncMock(return_value=None)
    monkeypatch.setattr("app.api.deps.PermissionChecker.__call__", fallback)

    await checker(current_user=current_user, db=db)

    fallback.assert_awaited_once_with(current_user=current_user, db=db)


@pytest.mark.asyncio
async def test_permission_checker_reads_permissions_in_effective_tenant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checker = PermissionChecker(["training:project:update"])
    current_user = SimpleNamespace(id=1, tenant_id=7, is_superuser=False)

    permission_mock = AsyncMock(return_value={"training:project:update"})
    monkeypatch.setattr(
        "app.domain.users.service.UserService.get_user_permissions",
        permission_mock,
    )

    db = AsyncMock()
    db.scalar.return_value = {}

    await checker(current_user=current_user, db=db)

    assert permission_mock.await_args.kwargs["tenant_id"] == 7


def test_snapshot_current_user_preserves_effective_tenant_for_switched_superuser() -> None:
    current_user = TenantScopedUser(
        _user=SimpleNamespace(
            id=9,
            tenant_id=1,
            username="admin",
            nickname="Admin",
            is_superuser=True,
        ),
        tenant_id=2,
        user_tenant_id=1,
    )

    actor = snapshot_current_user(current_user)

    assert actor.user_id == 9
    assert actor.tenant_id == 2
    assert actor.user_tenant_id == 1
    assert actor.username == "admin"
    assert actor.nickname == "Admin"
    assert actor.is_superuser is True


@pytest.mark.asyncio
async def test_anonymous_request_on_module_path_does_not_guess_a_tenant() -> None:
    """匿名请求打到模块路径上时必须 fail closed，不许猜租户。

    曾经的实现是 host → code="default" → **第一个活跃租户**：未知 Host 会拿
    别的租户的开关来判定当前请求。公开端点必须自己声明租户解析
    （app/core/public_site.resolve_public_tenant），没声明就不该被放行。
    """
    from app.api import deps
    from app.core.exceptions import NotFoundError

    class _Req:
        url = SimpleNamespace(path="/api/v1/cms/pages")
        headers: dict[str, str] = {}
        query_params: dict[str, str] = {}

    db = AsyncMock()
    with pytest.raises(NotFoundError):
        await deps._enforce_public_module_switch_for_request(
            db=db, request=_Req(), current_user=None
        )
    # 关键不是"抛了错"，而是**根本没去查租户**：一旦有人重新加回按 Host 猜租户，
    # 这里就会出现数据库调用。
    assert db.mock_calls == [], f"匿名路径不该查库，实际调用：{db.mock_calls}"

    # 同时锁住：那个带跨租户回落的解析器不许再回到内核里。
    from app.core import module_guards

    assert not hasattr(module_guards, "resolve_public_tenant_id"), (
        "resolve_public_tenant_id 的回落链是 host → code=default → 第一个活跃租户，"
        "会让未知 Host 命中别的租户；唯一真源是 app.core.public_site.resolve_public_tenant"
    )


@pytest.mark.asyncio
async def test_anonymous_request_outside_module_paths_is_untouched() -> None:
    """反向用例：不属于任何模块的内核路径（如 /auth）不能被这道门禁误伤。"""
    from app.api import deps

    class _Req:
        url = SimpleNamespace(path="/api/v1/auth/login")
        headers: dict[str, str] = {}
        query_params: dict[str, str] = {}

    await deps._enforce_public_module_switch_for_request(
        db=AsyncMock(), request=_Req(), current_user=None
    )
