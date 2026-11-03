"""系统菜单声明的完整性，以及"菜单必须显式指定租户"这条不变量。

端到端的正确性（声明建出来的 == seed 建出来的）由
`python -m scripts.check_scenario_parity` 证明——那需要真 PostgreSQL。
这里只锁不依赖数据库、但一旦破掉就会静默出错的几条。
"""

from __future__ import annotations

import inspect

from app.core.system_menus import SYSTEM_MENU_DECLARATION
from app.domain.menus.reconciler import MenuNodeSpec
from app.domain.menus.service import MenuService


def _walk(nodes: tuple[MenuNodeSpec, ...]):
    for node in nodes:
        yield node
        yield from _walk(node.children)


def test_declaration_covers_the_three_system_roots() -> None:
    roots = {node.key for node in SYSTEM_MENU_DECLARATION.roots}
    assert roots == {"personal", "system", "tenant"}, (
        "系统声明必须覆盖个人中心/系统管理/租户管理三棵树；少一棵，新建租户就少一块菜单"
    )


def test_declaration_keys_are_unique() -> None:
    """key 重复会让 reconciler 把两个节点当成同一个，静默丢菜单。"""
    keys = [node.key for node in _walk(SYSTEM_MENU_DECLARATION.roots)]
    duplicates = sorted({key for key in keys if keys.count(key) > 1})
    assert not duplicates, f"声明里有重复 key：{duplicates}"


def test_role_grants_reference_declared_keys() -> None:
    """授权引用了不存在的 key 会静默失效——租户建完看起来正常，实则少授权。"""
    declared = {node.key for node in _walk(SYSTEM_MENU_DECLARATION.roots)}
    for role in SYSTEM_MENU_DECLARATION.roles:
        unknown = sorted(set(role.menu_keys) - declared)
        assert not unknown, f"角色 {role.code} 授权了未声明的菜单：{unknown}"


def test_admin_and_user_roles_are_declared() -> None:
    """建租户时只显式创建 admin/user 两个角色，其余角色靠声明里的 create 补齐。

    admin 必须拿到全部系统菜单，user 至少要有个人中心——否则新租户的普通用户
    登录后菜单是空的（2026-08-09 实测过的真实故障）。
    """
    by_code = {role.code: role for role in SYSTEM_MENU_DECLARATION.roles}
    assert "admin" in by_code and "user" in by_code

    all_keys = {node.key for node in _walk(SYSTEM_MENU_DECLARATION.roots)}
    assert set(by_code["admin"].menu_keys) == all_keys, "admin 必须覆盖全部系统菜单"

    user_keys = set(by_code["user"].menu_keys)
    assert user_keys, "user 角色不能一条授权都没有"
    assert any(key.startswith("personal") for key in user_keys), "user 至少要有个人中心"


def test_menu_crud_is_tenant_scoped() -> None:
    """列表/更新/删除都必须要求显式租户。

    菜单行逐租户一份；少一处租户条件，超管就能列出、编辑、删除**别的租户**的菜单。
    这几条原来的注释还写着"菜单是系统级配置，不区分租户"，与 reconciler 的
    实际行为相反——注释错了整整一层，所以这里用签名把语义钉死。
    """
    for name in ("list_menus_paginated", "update_menu", "delete_menu"):
        method = getattr(MenuService, name)
        param = inspect.signature(method).parameters.get("tenant_id")
        assert param is not None, f"{name} 必须接受 tenant_id"
        assert param.kind is inspect.Parameter.KEYWORD_ONLY, f"{name} 的 tenant_id 应为关键字参数"
        assert param.default is inspect.Parameter.empty, f"{name} 的 tenant_id 不许有默认值"


def test_create_menu_requires_an_explicit_tenant() -> None:
    """`MenuService.create_menu` 不许有 tenant_id 默认值。

    它原来写死 `tenant_id=1`，导致超管在别的租户下建的菜单落进 1 号租户。
    菜单行是逐租户的，租户必须由调用方显式给出——给默认值就等于把那个 bug 请回来。
    """
    signature = inspect.signature(MenuService.create_menu)
    tenant_param = signature.parameters.get("tenant_id")
    assert tenant_param is not None, "create_menu 必须接受 tenant_id"
    assert tenant_param.kind is inspect.Parameter.KEYWORD_ONLY, "tenant_id 应为关键字参数，避免位置传错"
    assert tenant_param.default is inspect.Parameter.empty, "tenant_id 不许有默认值"
