from __future__ import annotations

import ast
import copy
import json
from collections.abc import Mapping
from pathlib import Path

import pytest

from app.domain.menus.reconciler import (
    MENU_VALUE_FIELDS,
    ReconcileResult,
    MenuDeclaration,
    MenuNodeSpec,
    MenuRecord,
    MenuState,
    RoleDefaults,
    RoleGrantSpec,
    RoleRecord,
    apply_menu_declaration,
    inspect_menu_declaration,
)

TENANT_ID = 7
DECLARATION = MenuDeclaration(
    roots=(
        MenuNodeSpec(
            key="root",
            title="内容管理",
            path="/content",
            menu_type="0",
            meta={"section": "content"},
            children=(
                MenuNodeSpec(
                    key="page",
                    title="页面管理",
                    path="/content/pages",
                    component="views/content/pages",
                    menu_type="1",
                    perms="content:page:read",
                    meta={"feature": "pages"},
                    children=(
                        MenuNodeSpec(
                            key="button",
                            title="编辑页面",
                            menu_type="2",
                            perms="content:page:update",
                            is_visible=False,
                        ),
                    ),
                ),
            ),
        ),
    ),
    roles=(
        RoleGrantSpec(code="admin", grant_all=True),
        RoleGrantSpec(
            code="editor",
            menu_keys=("button",),
            create=RoleDefaults(name="Editor", description="Edits content", sort_order=2),
        ),
    ),
)


class MemoryStore:
    def __init__(self) -> None:
        self.state = MenuState(roles={100: RoleRecord(id=100, tenant_id=TENANT_ID, code="admin")})
        self.next_id = 1
        self.operations: list[tuple[object, ...]] = []

    async def load_state(self, tenant_id: int) -> MenuState:
        assert tenant_id == TENANT_ID
        return self.state

    async def create_menu(self, tenant_id: int, values: Mapping[str, object]) -> MenuRecord:
        menu = MenuRecord(id=self.next_id, tenant_id=tenant_id, **dict(values))
        self.next_id += 1
        self.operations.append(("create_menu", menu.id))
        return menu

    async def update_menu(self, menu_id: int, values: Mapping[str, object]) -> None:
        self.operations.append(("update_menu", menu_id, tuple(sorted(values))))

    async def merge_menu(self, tenant_id: int, duplicate_id: int, canonical_id: int) -> None:
        assert tenant_id == TENANT_ID
        self.operations.append(("merge_menu", duplicate_id, canonical_id))

    async def create_role(self, tenant_id: int, code: str, defaults: RoleDefaults) -> RoleRecord:
        role = RoleRecord(id=1000 + self.next_id, tenant_id=tenant_id, code=code)
        self.operations.append(("create_role", role.id, defaults.name))
        return role

    async def add_grant(self, tenant_id: int, role_id: int, menu_id: int) -> None:
        assert tenant_id == TENANT_ID
        self.operations.append(("add_grant", role_id, menu_id))


def _identity(state: MenuState, menu: MenuRecord) -> tuple[str, str | None, str | None]:
    parent = state.menus.get(menu.parent_id) if menu.parent_id is not None else None
    parent_identity = (parent.path or parent.perms or parent.title) if parent else None
    return (menu.path or menu.perms or menu.title, parent_identity, menu.menu_type)


def _semantic_snapshot(store: MemoryStore) -> tuple[object, ...]:
    state = store.state
    menus = []
    for menu in state.menus.values():
        values = []
        for field_name in MENU_VALUE_FIELDS:
            if field_name == "parent_id":
                continue
            value = getattr(menu, field_name)
            values.append(json.dumps(value, sort_keys=True) if field_name == "meta" else value)
        menus.append((_identity(state, menu), tuple(values)))
    menus.sort(key=repr)

    grants = []
    for role_id, menu_id in state.grants:
        role = state.roles.get(role_id)
        menu = state.menus.get(menu_id)
        if role is not None and menu is not None:
            grants.append((role.code, _identity(state, menu)))
    grants.sort(key=repr)
    return tuple(menus), tuple(grants), tuple(sorted(role.code for role in state.roles.values()))


async def _clean_store() -> MemoryStore:
    store = MemoryStore()
    result = await apply_menu_declaration(store, tenant_id=TENANT_ID, declaration=DECLARATION)
    assert result.changed
    return store


@pytest.mark.asyncio
async def test_reconciler_second_apply_is_a_noop() -> None:
    store = await _clean_store()
    store.operations.clear()

    second = await apply_menu_declaration(store, tenant_id=TENANT_ID, declaration=DECLARATION)

    assert second.changed is False
    assert store.operations == []


def _damage_missing_submenu(store: MemoryStore) -> None:
    page = next(menu for menu in store.state.menus.values() if menu.path == "/content/pages")
    store.state.menus.pop(page.id)


def _damage_missing_button(store: MemoryStore) -> None:
    button = next(menu for menu in store.state.menus.values() if menu.perms == "content:page:update")
    store.state.menus.pop(button.id)
    store.state.grants = {grant for grant in store.state.grants if grant[1] != button.id}


def _damage_missing_grant(store: MemoryStore) -> None:
    page = next(menu for menu in store.state.menus.values() if menu.path == "/content/pages")
    store.state.grants.remove((100, page.id))


def _damage_path_and_meta(store: MemoryStore) -> None:
    page = next(menu for menu in store.state.menus.values() if menu.path == "/content/pages")
    page.path = "/old/pages"
    page.meta = {"feature": "legacy"}


def _damage_duplicate(store: MemoryStore) -> None:
    page = next(menu for menu in store.state.menus.values() if menu.path == "/content/pages")
    duplicate = copy.deepcopy(page)
    duplicate.id = store.next_id
    store.next_id += 1
    store.state.menus[duplicate.id] = duplicate
    store.state.grants.add((100, duplicate.id))


@pytest.mark.parametrize(
    "damage",
    [
        _damage_missing_submenu,
        _damage_missing_button,
        _damage_missing_grant,
        _damage_path_and_meta,
        _damage_duplicate,
    ],
    ids=["missing-submenu", "missing-button", "missing-grant", "path-and-meta-drift", "duplicate-row"],
)
@pytest.mark.asyncio
async def test_partial_states_converge_to_the_same_terminal_state(damage) -> None:  # noqa: ANN001
    reference = await _clean_store()
    expected = _semantic_snapshot(reference)
    damaged = await _clean_store()
    damage(damaged)

    result = await apply_menu_declaration(damaged, tenant_id=TENANT_ID, declaration=DECLARATION)

    assert result.changed
    assert _semantic_snapshot(damaged) == expected


@pytest.mark.asyncio
async def test_child_grant_adds_all_parent_grants() -> None:
    store = await _clean_store()
    editor = next(role for role in store.state.roles.values() if role.code == "editor")
    editor_menu_ids = {menu_id for role_id, menu_id in store.state.grants if role_id == editor.id}

    assert editor_menu_ids == set(store.state.menus)


@pytest.mark.asyncio
async def test_read_only_inspection_reports_all_seed_state_issue_classes() -> None:
    store = await _clean_store()
    root = next(menu for menu in store.state.menus.values() if menu.path == "/content")
    page = next(menu for menu in store.state.menus.values() if menu.path == "/content/pages")
    duplicate = copy.deepcopy(page)
    duplicate.id = store.next_id
    store.state.menus[duplicate.id] = duplicate
    page.meta = {"feature": "legacy"}
    store.state.grants.remove((100, page.id))
    editor = next(role for role in store.state.roles.values() if role.code == "editor")
    store.state.grants.remove((editor.id, root.id))

    issues = inspect_menu_declaration(store.state, tenant_id=TENANT_ID, declaration=DECLARATION)

    assert {issue.kind for issue in issues} == {
        "duplicate_menu",
        "missing_grant",
        "parent_closure",
        "drift",
    }


def test_runtime_seed_tenant_creation_and_repair_share_reconciler() -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    source_paths = (
        backend_dir / "scripts" / "seed_cms.py",
        backend_dir / "app" / "domain" / "auth" / "service.py",
        backend_dir / "scripts" / "repair_menu_state.py",
    )
    for source_path in source_paths:
        source = source_path.read_text(encoding="utf-8")
        assert "reconcile_menu_declaration(" in source
    seed_source = source_paths[0].read_text(encoding="utf-8")
    assert "path='/cms'" not in seed_source
    assert "CMS_SUBMENUS" not in seed_source

    auth_tree = ast.parse(source_paths[1].read_text(encoding="utf-8"))
    create_function = next(
        node
        for node in ast.walk(auth_tree)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "create_tenant_with_admin"
    )
    admin_role_assignment = next(
        node
        for node in ast.walk(create_function)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "admin_role" for target in node.targets)
    )
    reconcile_call = next(
        node
        for node in ast.walk(create_function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "reconcile_menu_declaration"
    )
    flushes_before_reconcile = [
        node
        for node in ast.walk(create_function)
        if isinstance(node, ast.Await)
        and node.lineno < reconcile_call.lineno
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Attribute)
        and node.value.func.attr == "flush"
    ]
    assert admin_role_assignment.lineno < reconcile_call.lineno
    assert flushes_before_reconcile


def test_cms_migration_has_frozen_local_snapshot_and_single_parent() -> None:
    migration_path = (
        Path(__file__).resolve().parents[1] / "alembic" / "versions" / "base_20260808_cms_menu_reconcile.py"
    )
    source = migration_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = {
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    snapshot_assignment = next(
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "CMS_MENU_SNAPSHOT" for target in node.targets)
    )

    assert not any(module.startswith("app.") for module in imported_modules)
    assert "domain.cms.access" not in source
    assert isinstance(ast.literal_eval(snapshot_assignment.value), tuple)
    assert 'down_revision: str | None = "base_20260622_cms_languages"' in source
    assert "IS DISTINCT FROM" in source
    assert "ON CONFLICT (role_id, menu_id) DO NOTHING" in source


@pytest.mark.asyncio
async def test_reconcile_invalidates_menu_routes_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """写了菜单就必须让菜单缓存失效。

    `/menus/routes` 的响应按 menu_version 缓存。真机验证时踩到过：
    seed / 建租户 / repair 把菜单写进库了，接口却继续吐旧树，
    看起来就像"修了没用"。所有单测都直接调 reconciler，绕过了缓存层，
    所以这条必须显式锁住。
    """
    from app.domain.menus import reconciler as reconciler_module

    calls: list[int] = []

    async def fake_bump() -> int:
        calls.append(1)
        return len(calls)

    monkeypatch.setattr(
        "app.infrastructure.cache.bump_menu_structure_cache_version", fake_bump
    )

    async def fake_apply(*_args: object, **_kwargs: object) -> ReconcileResult:
        return ReconcileResult(added_grants=1)

    monkeypatch.setattr(reconciler_module, "apply_menu_declaration", fake_apply)
    monkeypatch.setattr(reconciler_module, "SQLAlchemyMenuStateStore", lambda db: db)

    await reconciler_module.reconcile_menu_declaration(
        object(), tenant_id=1, declaration=DECLARATION
    )
    assert calls == [1], "有变更时必须 bump 菜单缓存版本"

    async def fake_apply_unchanged(*_args: object, **_kwargs: object) -> ReconcileResult:
        return ReconcileResult()

    monkeypatch.setattr(reconciler_module, "apply_menu_declaration", fake_apply_unchanged)
    await reconciler_module.reconcile_menu_declaration(
        object(), tenant_id=1, declaration=DECLARATION
    )
    assert calls == [1], "无变更时不该白白让全租户的菜单缓存失效"


def test_menus_domain_owns_no_module_declaration() -> None:
    """菜单内核只提供对账机制与 spec 类型，**不许持有任何模块的菜单声明**。

    判据同架构文档：把 app/domain/menus/ 整个拷进一个空基座应该能直接跑。
    CMS 的声明属于 CMS（app/domain/cms/access.py），能力包的属于包自己
    （app/capabilities/<code>/access.py）。这条不写成检查的话，
    下一个模块又会顺手塞回 domain/menus/。
    """
    menus_dir = Path(__file__).resolve().parents[1] / "app" / "domain" / "menus"
    allowed = {"__init__.py", "models.py", "reconciler.py", "service.py"}
    actual = {p.name for p in menus_dir.glob("*.py")}

    assert actual <= allowed, (
        f"domain/menus 里出现了不属于菜单内核的文件：{sorted(actual - allowed)}；"
        "模块的菜单声明应放在该模块自己的目录下"
    )

    for path in menus_dir.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "app.domain.cms" not in source, f"{path.name} 不该认识 CMS"
        assert "app.capabilities" not in source, f"{path.name} 不该认识能力包"
