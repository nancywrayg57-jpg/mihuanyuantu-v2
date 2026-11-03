from __future__ import annotations

from collections.abc import AsyncIterator, Iterator, Mapping
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient

from app.api import v1
from app.api.deps import get_current_user
from app.core.capability_runtime import provision_installed_capabilities
from app.capabilities.sample_items import seed as sample_seed
from app.core import feature_switches
from app.domain.menus.reconciler import (
    MenuRecord,
    MenuState,
    RoleDefaults,
    RoleRecord,
    apply_menu_declaration,
)
from app.infrastructure.database import get_db

TENANT_ID = 7


class MemoryStore:
    def __init__(self) -> None:
        self.state = MenuState(roles={100: RoleRecord(id=100, tenant_id=TENANT_ID, code="admin")})
        self.next_id = 1

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
        return RoleRecord(id=1000 + self.next_id, tenant_id=tenant_id, code=code)

    async def add_grant(self, tenant_id: int, role_id: int, menu_id: int) -> None:
        return None


class EmptyScalars:
    def all(self) -> list[object]:
        return []


class EmptyResult:
    def scalars(self) -> EmptyScalars:
        return EmptyScalars()

    def scalar(self) -> int:
        # RepositoryBase.get_list 走 count 查询时会读它
        return 0


class EmptyDB:
    async def scalar(self, statement):  # noqa: ANN001
        return 0

    async def execute(self, statement):  # noqa: ANN001
        return EmptyResult()


@contextmanager
def installation(value: str) -> Iterator[None]:
    original = feature_switches.settings.AOJ_ENABLED_MODULES
    feature_switches.settings.AOJ_ENABLED_MODULES = value
    feature_switches.clear_module_install_caches()
    try:
        yield
    finally:
        feature_switches.settings.AOJ_ENABLED_MODULES = original
        feature_switches.clear_module_install_caches()


async def build_app(monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    target = APIRouter()
    monkeypatch.setattr(v1, "api_router", target)
    v1.register_discovered_capability_routers()

    app = FastAPI()
    app.include_router(target, prefix="/api/v1")
    fake_db = EmptyDB()

    async def current_user():
        return SimpleNamespace(
            id=1,
            tenant_id=TENANT_ID,
            user_tenant_id=TENANT_ID,
            username="root",
            is_superuser=True,
        )

    async def database() -> AsyncIterator[EmptyDB]:
        yield fake_db

    app.dependency_overrides[get_current_user] = current_user
    app.dependency_overrides[get_db] = database
    return app


@pytest.mark.parametrize(
    ("installed_value", "status_code", "in_openapi", "menu_present"),
    [
        ("none", 404, False, False),
        ("sample_items", 200, True, True),
    ],
)
@pytest.mark.asyncio
async def test_sample_items_installation_controls_route_openapi_and_menu(
    monkeypatch: pytest.MonkeyPatch,
    installed_value: str,
    status_code: int,
    in_openapi: bool,
    menu_present: bool,
) -> None:
    store = MemoryStore()

    async def reconcile_in_memory(db, *, tenant_id, declaration, role_id_overrides=None):  # noqa: ANN001
        return await apply_menu_declaration(
            store,
            tenant_id=tenant_id,
            declaration=declaration,
            role_id_overrides=role_id_overrides,
        )

    monkeypatch.setattr(sample_seed, "reconcile_menu_declaration", reconcile_in_memory)

    with installation(installed_value):
        app = await build_app(monkeypatch)
        await provision_installed_capabilities(object(), tenant_id=TENANT_ID)
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/sample-items")

        paths = app.openapi()["paths"]
        menu_paths = {menu.path for menu in store.state.menus.values()}

    assert response.status_code == status_code
    assert ("/api/v1/sample-items" in paths) is in_openapi
    assert ("/sample-items" in menu_paths) is menu_present
