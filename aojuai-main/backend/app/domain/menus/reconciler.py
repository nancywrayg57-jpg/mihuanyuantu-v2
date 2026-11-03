"""Declarative menu, permission, and role-grant reconciliation.

The state transition is deliberately separated from the SQLAlchemy adapter so
it can be exercised without a PostgreSQL database.  Runtime callers should use
``reconcile_menu_declaration``; tests and diagnostics can operate on the pure
state model through ``apply_menu_declaration`` and ``inspect_menu_declaration``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.portable_sql import json_column_value, ptext

MENU_TYPES = {"0", "1", "2"}
MENU_VALUE_FIELDS = (
    "title",
    "path",
    "component",
    "redirect",
    "parent_id",
    "level",
    "icon",
    "sort_order",
    "menu_type",
    "perms",
    "is_visible",
    "is_cache",
    "is_frame",
    "frame_src",
    "is_active",
    "no_cache",
    "breadcrumb",
    "affix",
    "no_tags_view",
    "can_to",
    "always_show",
    "meta",
)


@dataclass(frozen=True)
class MenuNodeSpec:
    """One node in a declarative menu tree."""

    key: str
    title: str
    menu_type: str
    path: str | None = None
    component: str | None = None
    redirect: str | None = None
    icon: str | None = None
    sort_order: int = 0
    perms: str | None = None
    is_visible: bool = True
    is_cache: bool = False
    is_frame: bool = False
    frame_src: str | None = None
    is_active: bool = True
    no_cache: bool = False
    breadcrumb: bool = True
    affix: bool = False
    no_tags_view: bool = False
    can_to: bool = False
    always_show: bool = False
    meta: Mapping[str, Any] = field(default_factory=dict)
    children: tuple[MenuNodeSpec, ...] = ()

    def values(self, *, parent_id: int | None, level: int) -> dict[str, Any]:
        return {
            "title": self.title,
            "path": self.path,
            "component": self.component,
            "redirect": self.redirect,
            "parent_id": parent_id,
            "level": level,
            "icon": self.icon,
            "sort_order": self.sort_order,
            "menu_type": self.menu_type,
            "perms": self.perms,
            "is_visible": self.is_visible,
            "is_cache": self.is_cache,
            "is_frame": self.is_frame,
            "frame_src": self.frame_src,
            "is_active": self.is_active,
            "no_cache": self.no_cache,
            "breadcrumb": self.breadcrumb,
            "affix": self.affix,
            "no_tags_view": self.no_tags_view,
            "can_to": self.can_to,
            "always_show": self.always_show,
            "meta": dict(self.meta),
        }


@dataclass(frozen=True)
class RoleDefaults:
    """Role fields used only when a declared role does not exist."""

    name: str
    description: str
    sort_order: int
    is_active: bool = True
    is_system: bool = True
    data_range: int = 0
    data_permissions: int = 3
    extra: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RoleGrantSpec:
    """Minimum grants a role must have within this declaration."""

    code: str
    menu_keys: tuple[str, ...] = ()
    grant_all: bool = False
    create: RoleDefaults | None = None


@dataclass(frozen=True)
class MenuDeclaration:
    roots: tuple[MenuNodeSpec, ...]
    roles: tuple[RoleGrantSpec, ...]


@dataclass
class MenuRecord:
    id: int
    tenant_id: int
    title: str
    menu_type: str
    path: str | None = None
    component: str | None = None
    redirect: str | None = None
    parent_id: int | None = None
    level: int = 1
    icon: str | None = None
    sort_order: int = 0
    perms: str | None = None
    is_visible: bool = True
    is_cache: bool = False
    is_frame: bool = False
    frame_src: str | None = None
    is_active: bool = True
    no_cache: bool = False
    breadcrumb: bool = True
    affix: bool = False
    no_tags_view: bool = False
    can_to: bool = False
    always_show: bool = False
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class RoleRecord:
    id: int
    tenant_id: int
    code: str


@dataclass
class MenuState:
    menus: dict[int, MenuRecord] = field(default_factory=dict)
    roles: dict[int, RoleRecord] = field(default_factory=dict)
    grants: set[tuple[int, int]] = field(default_factory=set)


@dataclass(frozen=True)
class ReconcileResult:
    created_menus: int = 0
    updated_menus: int = 0
    merged_menus: int = 0
    created_roles: int = 0
    added_grants: int = 0

    @property
    def changed(self) -> bool:
        return any(
            (
                self.created_menus,
                self.updated_menus,
                self.merged_menus,
                self.created_roles,
                self.added_grants,
            )
        )


@dataclass(frozen=True)
class StateIssue:
    kind: str
    tenant_id: int
    detail: str


class MenuStateStore(Protocol):
    async def load_state(self, tenant_id: int) -> MenuState: ...

    async def create_menu(self, tenant_id: int, values: Mapping[str, Any]) -> MenuRecord: ...

    async def update_menu(self, menu_id: int, values: Mapping[str, Any]) -> None: ...

    async def merge_menu(self, tenant_id: int, duplicate_id: int, canonical_id: int) -> None: ...

    async def create_role(self, tenant_id: int, code: str, defaults: RoleDefaults) -> RoleRecord: ...

    async def add_grant(self, tenant_id: int, role_id: int, menu_id: int) -> None: ...


@dataclass(frozen=True)
class _CompiledNode:
    spec: MenuNodeSpec
    parent_key: str | None
    level: int


def _compile(declaration: MenuDeclaration) -> tuple[list[_CompiledNode], dict[str, str | None]]:
    nodes: list[_CompiledNode] = []
    parents: dict[str, str | None] = {}

    def visit(node: MenuNodeSpec, parent_key: str | None, level: int) -> None:
        if not node.key or node.key in parents:
            raise ValueError(f"duplicate or empty menu declaration key: {node.key!r}")
        if node.menu_type not in MENU_TYPES:
            raise ValueError(f"invalid menu_type for {node.key}: {node.menu_type!r}")
        parents[node.key] = parent_key
        nodes.append(_CompiledNode(spec=node, parent_key=parent_key, level=level))
        for child in node.children:
            visit(child, node.key, level + 1)

    for root in declaration.roots:
        visit(root, None, 1)

    role_codes: set[str] = set()
    for role in declaration.roles:
        if role.code in role_codes:
            raise ValueError(f"duplicate role declaration: {role.code!r}")
        role_codes.add(role.code)
        unknown = set(role.menu_keys) - parents.keys()
        if unknown:
            raise ValueError(f"role {role.code!r} references unknown menu keys: {sorted(unknown)!r}")
    return nodes, parents


def _candidate_menus(
    state: MenuState,
    node: MenuNodeSpec,
    *,
    parent_id: int | None,
) -> list[MenuRecord]:
    candidates: list[tuple[int, int, MenuRecord]] = []
    for menu in state.menus.values():
        if menu.menu_type != node.menu_type:
            continue
        score: int | None = None
        if node.path is not None and menu.path == node.path:
            score = 0
        elif node.menu_type == "2" and node.perms is not None and menu.perms == node.perms:
            score = 1
        elif menu.parent_id == parent_id and menu.title == node.title:
            score = 2
        if score is not None:
            candidates.append((score, menu.id, menu))
    candidates.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in candidates]


def _changed_values(menu: MenuRecord, expected: Mapping[str, Any]) -> dict[str, Any]:
    return {field_name: value for field_name, value in expected.items() if getattr(menu, field_name) != value}


def _close_over_parents(keys: set[str], parents: Mapping[str, str | None]) -> set[str]:
    closed = set(keys)
    pending = list(keys)
    while pending:
        parent_key = parents[pending.pop()]
        if parent_key is not None and parent_key not in closed:
            closed.add(parent_key)
            pending.append(parent_key)
    return closed


async def apply_menu_declaration(
    store: MenuStateStore,
    *,
    tenant_id: int,
    declaration: MenuDeclaration,
    role_id_overrides: Mapping[str, int | None] | None = None,
) -> ReconcileResult:
    """Converge one tenant to the declared menu and minimum-grant state."""

    nodes, parents = _compile(declaration)
    state = await store.load_state(tenant_id)
    menu_ids: dict[str, int] = {}
    created_menus = updated_menus = merged_menus = created_roles = added_grants = 0

    for compiled in nodes:
        parent_id = menu_ids.get(compiled.parent_key) if compiled.parent_key else None
        expected = compiled.spec.values(parent_id=parent_id, level=compiled.level)
        candidates = _candidate_menus(state, compiled.spec, parent_id=parent_id)
        if not candidates:
            canonical = await store.create_menu(tenant_id, expected)
            state.menus[canonical.id] = canonical
            created_menus += 1
        else:
            canonical = candidates[0]
            for duplicate in candidates[1:]:
                await store.merge_menu(tenant_id, duplicate.id, canonical.id)
                for child in state.menus.values():
                    if child.parent_id == duplicate.id:
                        child.parent_id = canonical.id
                duplicate_grants = {role_id for role_id, menu_id in state.grants if menu_id == duplicate.id}
                state.grants.difference_update({(role_id, duplicate.id) for role_id in duplicate_grants})
                state.grants.update({(role_id, canonical.id) for role_id in duplicate_grants})
                state.menus.pop(duplicate.id, None)
                merged_menus += 1
            changes = _changed_values(canonical, expected)
            if changes:
                await store.update_menu(canonical.id, changes)
                for field_name, value in changes.items():
                    setattr(canonical, field_name, value)
                updated_menus += 1
        menu_ids[compiled.spec.key] = canonical.id

    roles_by_code: dict[str, RoleRecord] = {}
    for role in sorted(state.roles.values(), key=lambda item: item.id):
        roles_by_code.setdefault(role.code, role)
    for code, role_id in (role_id_overrides or {}).items():
        if role_id is not None and role_id in state.roles:
            roles_by_code[code] = state.roles[role_id]

    all_keys = set(menu_ids)
    for role_spec in declaration.roles:
        role = roles_by_code.get(role_spec.code)
        if role is None and role_spec.create is not None:
            role = await store.create_role(tenant_id, role_spec.code, role_spec.create)
            state.roles[role.id] = role
            roles_by_code[role.code] = role
            created_roles += 1
        if role is None:
            continue
        desired_keys = all_keys if role_spec.grant_all else set(role_spec.menu_keys)
        desired_keys = _close_over_parents(desired_keys, parents)
        for menu_key in sorted(desired_keys, key=lambda key: menu_ids[key]):
            grant = (role.id, menu_ids[menu_key])
            if grant in state.grants:
                continue
            await store.add_grant(tenant_id, role.id, menu_ids[menu_key])
            state.grants.add(grant)
            added_grants += 1

    return ReconcileResult(
        created_menus=created_menus,
        updated_menus=updated_menus,
        merged_menus=merged_menus,
        created_roles=created_roles,
        added_grants=added_grants,
    )


def inspect_menu_declaration(
    state: MenuState,
    *,
    tenant_id: int,
    declaration: MenuDeclaration,
) -> list[StateIssue]:
    """Read-only comparison used by the seed-state checker."""

    nodes, parents = _compile(declaration)
    issues: list[StateIssue] = []
    menu_ids: dict[str, int] = {}
    declaration_menu_ids: set[int] = set()

    for compiled in nodes:
        if compiled.parent_key is not None and compiled.parent_key not in menu_ids:
            issues.append(
                StateIssue(
                    "drift",
                    tenant_id,
                    f"menu {compiled.spec.key} cannot resolve parent {compiled.parent_key}",
                )
            )
            continue
        parent_id = menu_ids.get(compiled.parent_key) if compiled.parent_key else None
        candidates = _candidate_menus(state, compiled.spec, parent_id=parent_id)
        if not candidates:
            issues.append(StateIssue("drift", tenant_id, f"missing menu: {compiled.spec.key}"))
            continue
        canonical = candidates[0]
        menu_ids[compiled.spec.key] = canonical.id
        declaration_menu_ids.update(menu.id for menu in candidates)
        if len(candidates) > 1:
            duplicate_ids = [menu.id for menu in candidates[1:]]
            issues.append(
                StateIssue(
                    "duplicate_menu",
                    tenant_id,
                    f"{compiled.spec.key} duplicates: canonical={canonical.id}, duplicates={duplicate_ids}",
                )
            )
        expected = compiled.spec.values(parent_id=parent_id, level=compiled.level)
        changes = _changed_values(canonical, expected)
        if changes:
            issues.append(
                StateIssue(
                    "drift",
                    tenant_id,
                    f"menu {compiled.spec.key} differs in: {', '.join(sorted(changes))}",
                )
            )

    roles_by_code: dict[str, RoleRecord] = {}
    for role in sorted(state.roles.values(), key=lambda item: item.id):
        roles_by_code.setdefault(role.code, role)
    all_keys = set(menu_ids)
    for role_spec in declaration.roles:
        role = roles_by_code.get(role_spec.code)
        if role is None:
            if role_spec.create is not None:
                issues.append(StateIssue("drift", tenant_id, f"missing role: {role_spec.code}"))
            continue
        desired_keys = all_keys if role_spec.grant_all else set(role_spec.menu_keys)
        desired_keys = _close_over_parents(desired_keys, parents)
        for menu_key in sorted(desired_keys):
            menu_id = menu_ids.get(menu_key)
            if menu_id is not None and (role.id, menu_id) not in state.grants:
                issues.append(StateIssue("missing_grant", tenant_id, f"role={role.code}, menu={menu_key} ({menu_id})"))

    for role_id, menu_id in sorted(state.grants):
        if menu_id not in declaration_menu_ids:
            continue
        menu = state.menus.get(menu_id)
        if menu is None or menu.parent_id is None or menu.parent_id not in declaration_menu_ids:
            continue
        if (role_id, menu.parent_id) not in state.grants:
            role_code = state.roles.get(role_id).code if role_id in state.roles else str(role_id)
            issues.append(
                StateIssue(
                    "parent_closure",
                    tenant_id,
                    f"role={role_code}, child={menu.id}, missing_parent={menu.parent_id}",
                )
            )
    return issues


class SQLAlchemyMenuStateStore:
    """AsyncSession-backed adapter for the reconciler."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def load_state(self, tenant_id: int) -> MenuState:
        menu_result = await self.db.execute(
            ptext(
                f"SELECT id, tenant_id, {', '.join(MENU_VALUE_FIELDS)} "
                "FROM menus WHERE tenant_id=:tenant_id AND deleted_at IS NULL ORDER BY id"
            ),
            {"tenant_id": tenant_id},
        )
        menus = {
            int(row["id"]): MenuRecord(
                **{
                    **{key: row[key] for key in ("id", "tenant_id", *MENU_VALUE_FIELDS)},
                    "id": int(row["id"]),
                    "tenant_id": int(row["tenant_id"]),
                    "meta": dict(json_column_value(row["meta"])),
                }
            )
            for row in menu_result.mappings().all()
        }
        role_result = await self.db.execute(
            ptext("SELECT id, tenant_id, code FROM roles WHERE tenant_id=:tenant_id AND deleted_at IS NULL ORDER BY id"),
            {"tenant_id": tenant_id},
        )
        roles = {
            int(row["id"]): RoleRecord(id=int(row["id"]), tenant_id=int(row["tenant_id"]), code=row["code"])
            for row in role_result.mappings().all()
        }
        grant_result = await self.db.execute(
            ptext("SELECT role_id, menu_id FROM role_menus WHERE tenant_id=:tenant_id"),
            {"tenant_id": tenant_id},
        )
        grants = {(int(row[0]), int(row[1])) for row in grant_result.all()}
        return MenuState(menus=menus, roles=roles, grants=grants)

    async def create_menu(self, tenant_id: int, values: Mapping[str, Any]) -> MenuRecord:
        columns = ", ".join(("tenant_id", *MENU_VALUE_FIELDS))
        placeholders = ", ".join(
            "cast(:meta as jsonb)" if field_name == "meta" else f":{field_name}"
            for field_name in ("tenant_id", *MENU_VALUE_FIELDS)
        )
        params = {**values, "tenant_id": tenant_id, "meta": json.dumps(values["meta"])}
        result = await self.db.execute(
            ptext(f"INSERT INTO menus ({columns}) VALUES ({placeholders}) RETURNING id"),
            params,
        )
        menu_id = int(result.scalar_one())
        return MenuRecord(id=menu_id, tenant_id=tenant_id, **dict(values))

    async def update_menu(self, menu_id: int, values: Mapping[str, Any]) -> None:
        assignments = ", ".join(
            f"{field_name}=cast(:{field_name} as jsonb)" if field_name == "meta" else f"{field_name}=:{field_name}"
            for field_name in values
        )
        params = dict(values)
        if "meta" in params:
            params["meta"] = json.dumps(params["meta"])
        await self.db.execute(
            ptext(f"UPDATE menus SET {assignments}, updated_at=now() WHERE id=:menu_id"),
            {**params, "menu_id": menu_id},
        )

    async def merge_menu(self, tenant_id: int, duplicate_id: int, canonical_id: int) -> None:
        await self.db.execute(
            ptext("UPDATE menus SET parent_id=:canonical_id, updated_at=now() WHERE parent_id=:duplicate_id"),
            {"canonical_id": canonical_id, "duplicate_id": duplicate_id},
        )
        await self.db.execute(
            ptext(
                "INSERT INTO role_menus (tenant_id, role_id, menu_id) "
                "SELECT :tenant_id, role_id, :canonical_id FROM role_menus "
                "WHERE tenant_id=:tenant_id AND menu_id=:duplicate_id "
                "ON CONFLICT (role_id, menu_id) DO NOTHING"
            ),
            {"tenant_id": tenant_id, "canonical_id": canonical_id, "duplicate_id": duplicate_id},
        )
        await self.db.execute(
            ptext("DELETE FROM role_menus WHERE tenant_id=:tenant_id AND menu_id=:duplicate_id"),
            {"tenant_id": tenant_id, "duplicate_id": duplicate_id},
        )
        await self.db.execute(
            ptext(
                "UPDATE menus SET is_active=false, deleted_at=coalesce(deleted_at, now()), updated_at=now() "
                "WHERE tenant_id=:tenant_id AND id=:duplicate_id"
            ),
            {"tenant_id": tenant_id, "duplicate_id": duplicate_id},
        )

    async def create_role(self, tenant_id: int, code: str, defaults: RoleDefaults) -> RoleRecord:
        result = await self.db.execute(
            ptext(
                "INSERT INTO roles (tenant_id, name, code, description, sort_order, is_active, is_system, "
                "data_range, data_permissions, extra) VALUES "
                "(:tenant_id, :name, :code, :description, :sort_order, :is_active, :is_system, "
                ":data_range, :data_permissions, cast(:extra as jsonb)) RETURNING id"
            ),
            {
                "tenant_id": tenant_id,
                "code": code,
                "name": defaults.name,
                "description": defaults.description,
                "sort_order": defaults.sort_order,
                "is_active": defaults.is_active,
                "is_system": defaults.is_system,
                "data_range": defaults.data_range,
                "data_permissions": defaults.data_permissions,
                "extra": json.dumps(dict(defaults.extra)),
            },
        )
        return RoleRecord(id=int(result.scalar_one()), tenant_id=tenant_id, code=code)

    async def add_grant(self, tenant_id: int, role_id: int, menu_id: int) -> None:
        await self.db.execute(
            ptext(
                "INSERT INTO role_menus (tenant_id, role_id, menu_id) "
                "VALUES (:tenant_id, :role_id, :menu_id) ON CONFLICT (role_id, menu_id) DO NOTHING"
            ),
            {"tenant_id": tenant_id, "role_id": role_id, "menu_id": menu_id},
        )


async def reconcile_menu_declaration(
    db: AsyncSession,
    *,
    tenant_id: int,
    declaration: MenuDeclaration,
    role_id_overrides: Mapping[str, int | None] | None = None,
) -> ReconcileResult:
    """Public runtime entry point shared by seed, tenant creation, and repair."""

    outcome = await apply_menu_declaration(
        SQLAlchemyMenuStateStore(db),
        tenant_id=tenant_id,
        declaration=declaration,
        role_id_overrides=role_id_overrides,
    )

    # 写了菜单就必须让菜单缓存失效。`/menus/routes` 的响应按 menu_version 缓存，
    # 不 bump 的话：seed / 建租户 / repair 之后接口继续吐旧树，
    # 用户会以为"修了没用"，然后去改数据库——真机验证时就是这样踩到的。
    if outcome.changed:
        from app.infrastructure.cache import bump_menu_structure_cache_version

        await bump_menu_structure_cache_version()

    return outcome
