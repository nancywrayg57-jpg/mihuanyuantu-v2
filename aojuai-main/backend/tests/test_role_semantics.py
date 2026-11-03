from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.role_semantics import has_tenant_admin_role, is_tenant_admin_role_code
from app.domain.roles import service as roles_service
from app.domain.roles.service import RoleService


def test_is_tenant_admin_role_code_accepts_both_aliases() -> None:
    assert is_tenant_admin_role_code("tenant_admin")
    assert is_tenant_admin_role_code(" admin ")


def test_has_tenant_admin_role_handles_empty_and_non_admin_roles() -> None:
    assert has_tenant_admin_role(["user", "tenant_admin"]) is True
    assert has_tenant_admin_role(["user", "guest"]) is False
    assert has_tenant_admin_role(None) is False


@pytest.mark.asyncio
async def test_role_menu_assignment_includes_expanded_ancestor_menus(monkeypatch: pytest.MonkeyPatch) -> None:
    added_menu_ids: list[int] = []

    class FakeRepository:
        def __init__(self, db, model):  # noqa: ANN001
            self.db = db
            self.model = model

        async def get_list(self, **kwargs):  # noqa: ANN003
            _ = kwargs
            return [SimpleNamespace(id=1), SimpleNamespace(id=2)]

    class FakeDb:
        def add(self, item):  # noqa: ANN001
            added_menu_ids.append(item.menu_id)

    async def fake_expand_menu_ids_with_ancestors(db, menu_ids):  # noqa: ANN001
        assert menu_ids == [2]
        return [1, 2]

    monkeypatch.setattr(roles_service, "RepositoryBase", FakeRepository)
    monkeypatch.setattr(roles_service, "expand_menu_ids_with_ancestors", fake_expand_menu_ids_with_ancestors)

    service = RoleService(FakeDb())
    await service._assign_menus(SimpleNamespace(id=10), [2], tenant_id=3)

    assert added_menu_ids == [1, 2]
