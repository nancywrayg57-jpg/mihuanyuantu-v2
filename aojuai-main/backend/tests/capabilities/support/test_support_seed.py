"""菜单/权限三写的对账语义。

seed 不是"根节点在就跳过"：任意残缺状态（删按钮、删授权、改标题）跑一次
reconcile 都要收敛到同一个终态，连跑两次第二次不产生任何变更。
空库（零租户）时 `sync` 是 no-op。

用内存 store 跑纯状态机（`apply_menu_declaration`），不需要数据库。
"""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from app.capabilities.support import seed
from app.capabilities.support.permissions import CREATE, MANAGE, READ
from app.domain.menus.reconciler import (
    MenuRecord,
    MenuState,
    RoleDefaults,
    RoleRecord,
    apply_menu_declaration,
)

TENANT_ID = 4101


class MemoryStore:
    def __init__(self) -> None:
        self.state = MenuState(
            roles={
                1: RoleRecord(id=1, tenant_id=TENANT_ID, code="admin"),
                2: RoleRecord(id=2, tenant_id=TENANT_ID, code="user"),
            }
        )
        self.next_id = 10

    async def load_state(self, tenant_id: int) -> MenuState:
        assert tenant_id == TENANT_ID
        return self.state

    async def create_menu(self, tenant_id: int, values: Mapping[str, object]) -> MenuRecord:
        menu = MenuRecord(id=self.next_id, tenant_id=tenant_id, **dict(values))
        self.state.menus[menu.id] = menu
        self.next_id += 1
        return menu

    async def update_menu(self, menu_id: int, values: Mapping[str, object]) -> None:
        return None

    async def merge_menu(self, tenant_id: int, duplicate_id: int, canonical_id: int) -> None:
        return None

    async def create_role(self, tenant_id: int, code: str, defaults: RoleDefaults) -> RoleRecord:
        role = RoleRecord(id=1000 + self.next_id, tenant_id=tenant_id, code=code)
        self.next_id += 1
        return role

    async def add_grant(self, tenant_id: int, role_id: int, menu_id: int) -> None:
        return None


def snapshot(store: MemoryStore):
    identity = {
        menu_id: (menu.path, menu.perms, menu.title, menu.menu_type)
        for menu_id, menu in store.state.menus.items()
    }
    menus = tuple(sorted(identity.values(), key=repr))
    grants = tuple(
        sorted(
            (
                (store.state.roles[role_id].code, identity[menu_id])
                for role_id, menu_id in store.state.grants
                if role_id in store.state.roles and menu_id in identity
            ),
            key=repr,
        )
    )
    return menus, grants


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch) -> MemoryStore:
    memory = MemoryStore()

    async def reconcile_in_memory(db, *, tenant_id, declaration, role_id_overrides=None):  # noqa: ANN001
        return await apply_menu_declaration(
            memory,
            tenant_id=tenant_id,
            declaration=declaration,
            role_id_overrides=role_id_overrides,
        )

    monkeypatch.setattr(seed, "reconcile_menu_declaration", reconcile_in_memory)
    return memory


@pytest.mark.asyncio
async def test_provision_is_idempotent(store: MemoryStore) -> None:
    first = await seed.provision(object(), tenant_id=TENANT_ID)
    expected = snapshot(store)
    second = await seed.provision(object(), tenant_id=TENANT_ID)

    assert first.changed is True
    assert second.changed is False
    assert snapshot(store) == expected


@pytest.mark.asyncio
async def test_reconcile_repairs_a_deleted_button_and_a_revoked_grant(
    store: MemoryStore,
) -> None:
    await seed.provision(object(), tenant_id=TENANT_ID)
    expected = snapshot(store)

    manage_button = next(
        menu
        for menu in store.state.menus.values()
        if menu.perms == MANAGE and menu.menu_type == "2"
    )
    store.state.menus.pop(manage_button.id)
    store.state.grants = {
        grant for grant in store.state.grants if grant[1] != manage_button.id
    }
    create_button = next(
        menu
        for menu in store.state.menus.values()
        if menu.perms == CREATE and menu.menu_type == "2"
    )
    store.state.grants.discard((2, create_button.id))

    with pytest.raises(AssertionError):
        assert snapshot(store) == expected

    repaired = await seed.reconcile(object(), tenant_id=TENANT_ID)

    assert repaired.changed is True
    assert snapshot(store) == expected


@pytest.mark.asyncio
async def test_plain_user_gets_the_self_service_menus_but_never_the_agent_desk(
    store: MemoryStore,
) -> None:
    await seed.provision(object(), tenant_id=TENANT_ID)

    identity = {
        menu_id: (menu.path, menu.perms) for menu_id, menu in store.state.menus.items()
    }
    user_grants = {identity[menu_id] for role_id, menu_id in store.state.grants if role_id == 2}
    admin_grants = {identity[menu_id] for role_id, menu_id in store.state.grants if role_id == 1}

    assert ("/support/tickets", READ) in user_grants
    assert (None, CREATE) in user_grants
    # 父级闭包：授权子菜单必须同时授权父菜单，否则前端菜单树断层
    assert ("/support", None) in user_grants
    assert ("/support/admin/tickets", MANAGE) not in user_grants
    assert ("/support/admin/tickets", MANAGE) in admin_grants


@pytest.mark.asyncio
async def test_sync_is_a_no_op_on_an_empty_database() -> None:
    class _EmptyDb:
        async def execute(self, statement):  # noqa: ANN001
            class _Result:
                @staticmethod
                def scalars():
                    class _Scalars:
                        @staticmethod
                        def all():
                            return []

                    return _Scalars()

            return _Result()

    assert await seed.sync(_EmptyDb()) == []


def test_every_declared_menu_path_lives_under_the_route_prefix() -> None:
    """页面 path 必须落在包声明的 route_prefixes 下，否则 ModuleRouteGuard 拦不住它。"""
    from app.capabilities.support import CAPABILITY
    from app.capabilities.support.access import ACCESS

    def walk(nodes):
        for node in nodes:
            yield node
            yield from walk(node.children)

    for node in walk(ACCESS.roots):
        if not node.path:
            continue
        assert any(
            node.path == prefix or node.path.startswith(f"{prefix}/")
            for prefix in CAPABILITY.route_prefixes
        ), node.path
