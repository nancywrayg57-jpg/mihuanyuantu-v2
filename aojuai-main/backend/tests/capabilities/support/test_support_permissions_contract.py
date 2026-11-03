"""权限码与路由守卫的一一对应。

这条是"覆盖率"类检查：今天恰好每条路由都挂了 PermissionChecker，明天加一条忘了挂
就破了，而且破了没有任何征兆——所以按 dependency graph 静态遍历，不逐条人工核对。
"""

from __future__ import annotations

from fastapi.routing import APIRoute

from app.api.deps import PermissionChecker
from app.capabilities.support import api as support_api
from app.capabilities.support.access import ACCESS
from app.capabilities.support.permissions import ALL_PERMISSIONS, CREATE, MANAGE, READ

#: 唯一允许匿名的路由；它自己的防护（主机解析 + 蜜罐 + fail-closed 限流）
#: 由 test_support_public_intake.py 覆盖。
PUBLIC_PATHS = {"/public/tickets"}


def _routes() -> list[APIRoute]:
    return [route for route in support_api.router.routes if isinstance(route, APIRoute)]


def _required_permissions(route: APIRoute) -> set[str]:
    found: set[str] = set()
    for dependency in route.dependant.dependencies:
        call = dependency.call
        if isinstance(call, PermissionChecker):
            found |= set(call.required_permissions)
    return found


def test_permission_codes_use_the_module_prefix() -> None:
    assert set(ALL_PERMISSIONS) == {"support:read", "support:create", "support:manage"}
    assert all(code.startswith("support:") for code in ALL_PERMISSIONS)


def test_every_non_public_route_declares_a_permission() -> None:
    unguarded = [
        route.path
        for route in _routes()
        if route.path not in PUBLIC_PATHS and not _required_permissions(route)
    ]
    assert not unguarded, f"这些路由没有 PermissionChecker：{unguarded}"


def test_admin_routes_require_the_manage_permission() -> None:
    for route in _routes():
        if route.path.startswith("/admin"):
            assert _required_permissions(route) == {MANAGE}, route.path


def test_self_service_routes_never_require_manage() -> None:
    for route in _routes():
        if route.path.startswith("/admin") or route.path in PUBLIC_PATHS:
            continue
        permissions = _required_permissions(route)
        assert MANAGE not in permissions, route.path
        assert permissions <= {READ, CREATE}, route.path


def test_public_route_is_the_only_anonymous_surface() -> None:
    anonymous = {route.path for route in _routes() if not _required_permissions(route)}
    assert anonymous == PUBLIC_PATHS


def test_declared_buttons_cover_every_permission_code() -> None:
    """声明里的按钮权限码必须覆盖全部权限——漏一个就等于那个能力永远授不出去。"""

    def walk(nodes):
        for node in nodes:
            yield node
            yield from walk(node.children)

    declared = {node.perms for node in walk(ACCESS.roots) if node.perms}
    assert declared == set(ALL_PERMISSIONS)


def test_route_permissions_all_exist_in_the_declaration() -> None:
    used: set[str] = set()
    for route in _routes():
        used |= _required_permissions(route)
    assert used <= set(ALL_PERMISSIONS)
