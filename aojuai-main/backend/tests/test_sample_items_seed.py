from __future__ import annotations

from collections.abc import Mapping

import pytest

from app.capabilities.sample_items import seed
from app.capabilities.sample_items.permissions import CREATE, DELETE
from app.domain.menus.reconciler import (
    MenuRecord,
    MenuState,
    RoleDefaults,
    RoleRecord,
    apply_menu_declaration,
)

TENANT_ID = 31


class MemoryStore:
    def __init__(self) -> None:
        self.state = MenuState(roles={1: RoleRecord(id=1, tenant_id=TENANT_ID, code="admin")})
        self.next_id = 10

    async def load_state(self, tenant_id: int) -> MenuState:
        assert tenant_id == TENANT_ID
        return self.state

    async def create_menu(self, tenant_id: int, values: Mapping[str, object]) -> MenuRecord:
        menu = MenuRecord(id=self.next_id, tenant_id=tenant_id, **dict(values))
        self.next_id += 1
        return menu

    async def update_menu(self, menu_id: int, values: Mapping[str, object]) -> None:
        return None

    async def merge_menu(self, tenant_id: int, duplicate_id: int, canonical_id: int) -> None:
        return None

    async def create_role(
        self,
        tenant_id: int,
        code: str,
        defaults: RoleDefaults,
    ) -> RoleRecord:
        role = RoleRecord(id=1000 + self.next_id, tenant_id=tenant_id, code=code)
        self.next_id += 1
        return role

    async def add_grant(self, tenant_id: int, role_id: int, menu_id: int) -> None:
        return None


def semantic_snapshot(store: MemoryStore) -> tuple[tuple[object, ...], tuple[object, ...]]:
    menu_identity = {
        menu_id: (menu.path, menu.perms, menu.title, menu.menu_type) for menu_id, menu in store.state.menus.items()
    }
    menus = tuple(sorted(menu_identity.values(), key=repr))
    grant_values = [
        (
            store.state.roles[role_id].code,
            menu_identity[menu_id],
        )
        for role_id, menu_id in store.state.grants
        if role_id in store.state.roles and menu_id in menu_identity
    ]
    grants = tuple(sorted(grant_values, key=repr))
    return menus, grants


@pytest.mark.asyncio
async def test_seed_is_idempotent_and_repairs_missing_button_and_grant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = MemoryStore()

    async def reconcile_in_memory(db, *, tenant_id, declaration, role_id_overrides=None):  # noqa: ANN001
        return await apply_menu_declaration(
            store,
            tenant_id=tenant_id,
            declaration=declaration,
            role_id_overrides=role_id_overrides,
        )

    monkeypatch.setattr(seed, "reconcile_menu_declaration", reconcile_in_memory)

    first = await seed.provision(object(), tenant_id=TENANT_ID)
    expected = semantic_snapshot(store)
    second = await seed.provision(object(), tenant_id=TENANT_ID)
    assert first.changed is True
    assert second.changed is False
    assert semantic_snapshot(store) == expected

    delete_button = next(menu for menu in store.state.menus.values() if menu.perms == DELETE)
    store.state.menus.pop(delete_button.id)
    store.state.grants = {grant for grant in store.state.grants if grant[1] != delete_button.id}
    create_button = next(menu for menu in store.state.menus.values() if menu.perms == CREATE)
    store.state.grants.remove((1, create_button.id))

    with pytest.raises(AssertionError):
        assert semantic_snapshot(store) == expected

    repaired = await seed.reconcile(object(), tenant_id=TENANT_ID)
    assert repaired.changed is True
    assert semantic_snapshot(store) == expected
