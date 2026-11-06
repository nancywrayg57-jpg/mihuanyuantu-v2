"""Idempotent menu/permission reconciliation (no demo business data)."""

from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.menus.reconciler import ReconcileResult, reconcile_menu_declaration

from .access import ACCESS


async def reconcile(
    db: AsyncSession,
    *,
    tenant_id: int,
    role_id_overrides: Mapping[str, int | None] | None = None,
) -> ReconcileResult:
    result = await reconcile_menu_declaration(
        db,
        tenant_id=tenant_id,
        declaration=ACCESS,
        role_id_overrides=role_id_overrides,
    )
    await _drop_undeclared_realphotos_grants(db, tenant_id=tenant_id)
    return result


async def _drop_undeclared_realphotos_grants(db: AsyncSession, *, tenant_id: int) -> None:
    """菜单声明收紧后，拿掉角色上多出来的蜜獾原图入口。隐藏权限节点仍保留。"""
    from app.domain.menus.reconciler import _close_over_parents, _compile

    nodes, parents = _compile(ACCESS)
    key_by_path = {node.spec.path: node.spec.key for node in nodes if node.spec.path}
    key_by_button = {
        node.spec.perms: node.spec.key
        for node in nodes
        if node.spec.menu_type == "2" and node.spec.perms
    }
    desired = {
        role.code: _close_over_parents(set(role.menu_keys), parents) for role in ACCESS.roles
    }
    role_rows = (
        await db.execute(
            text("SELECT id, code FROM roles WHERE tenant_id = :tenant_id AND deleted_at IS NULL"),
            {"tenant_id": int(tenant_id)},
        )
    ).all()
    menu_rows = (
        await db.execute(
            text(
                "SELECT id, path, perms, menu_type FROM menus "
                "WHERE tenant_id = :tenant_id AND deleted_at IS NULL "
                "AND (path LIKE '/realphotos%' OR perms LIKE 'realphotos:%')"
            ),
            {"tenant_id": int(tenant_id)},
        )
    ).all()
    key_by_id: dict[int, str] = {}
    for menu_id, path, perms, menu_type in menu_rows:
        if path and path in key_by_path:
            key_by_id[int(menu_id)] = key_by_path[path]
        elif str(menu_type) == "2" and perms in key_by_button:
            key_by_id[int(menu_id)] = key_by_button[perms]
    for role_id, code in role_rows:
        keep = desired.get(str(code))
        if keep is None:
            continue
        for menu_id, key in key_by_id.items():
            if key in keep:
                continue
            await db.execute(
                text(
                    "DELETE FROM role_menus "
                    "WHERE tenant_id = :tenant_id AND role_id = :role_id AND menu_id = :menu_id"
                ),
                {"tenant_id": int(tenant_id), "role_id": int(role_id), "menu_id": int(menu_id)},
            )


async def provision(
    db: AsyncSession,
    *,
    tenant_id: int,
    role_id_overrides: Mapping[str, int | None] | None = None,
) -> ReconcileResult:
    return await reconcile(
        db,
        tenant_id=tenant_id,
        role_id_overrides=role_id_overrides,
    )


async def sync(db: AsyncSession) -> list[tuple[int, ReconcileResult]]:
    result = await db.execute(
        text("SELECT id FROM tenants WHERE deleted_at IS NULL ORDER BY id")
    )
    outcomes: list[tuple[int, ReconcileResult]] = []
    for tenant_id in result.scalars().all():
        normalized_id = int(tenant_id)
        outcomes.append(
            (normalized_id, await reconcile(db, tenant_id=normalized_id))
        )
    return outcomes
