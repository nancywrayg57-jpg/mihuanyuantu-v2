from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api.v1.endpoints import users as users_mod


@pytest.mark.asyncio
async def test_get_user_list_loads_profile_config_before_serializing_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_user = SimpleNamespace(id=7)
    fake_profile_config = SimpleNamespace(enabled=False)

    async def fake_get_tenant_profile_config(self, tenant_id: int):  # noqa: ANN001
        assert tenant_id == 2
        return fake_profile_config

    async def fake_list_users(self, **kwargs):  # noqa: ANN001
        assert kwargs["tenant_id"] == 2
        assert kwargs["page"] == 1
        assert kwargs["page_size"] == 10
        assert kwargs["team_ids"] is None
        return [fake_user], 1

    async def fake_get_invitation_context_map(self, *, tenant_id: int, user_ids: list[int]):  # noqa: ANN001
        assert tenant_id == 2
        assert user_ids == [7]
        return {7: {"invitedByUsername": "owner"}}

    def fake_to_list_item(  # noqa: ANN001
        user,
        include_tenant=False,
        *,
        profile_config=None,
        invitation_context=None,
    ):
        assert user is fake_user
        assert include_tenant is False
        assert profile_config is fake_profile_config
        assert invitation_context == {"invitedByUsername": "owner"}
        return {"id": user.id, "username": "demo"}

    monkeypatch.setattr(users_mod.UserService, "get_tenant_profile_config", fake_get_tenant_profile_config)
    monkeypatch.setattr(users_mod.UserService, "list_users", fake_list_users)
    monkeypatch.setattr(users_mod.UserService, "get_invitation_context_map", fake_get_invitation_context_map)
    monkeypatch.setattr(users_mod.UserService, "to_list_item", staticmethod(fake_to_list_item))

    response = await users_mod.get_user_list(
        query=users_mod.UserListQuery(currentPage=1, pageSize=10),
        current_user=SimpleNamespace(id=1),
        tenant_ctx=SimpleNamespace(tenant_id=2, is_superuser=False, is_cross_tenant=False),
        data_scope=SimpleNamespace(has_all_read_access=True, read_team_ids=[]),
        db=AsyncMock(),
        _=None,
    )

    payload = json.loads(response.body)

    assert payload["success"] is True
    assert payload["data"]["list"] == [{"id": 7, "username": "demo"}]
    assert payload["data"]["total"] == 1
