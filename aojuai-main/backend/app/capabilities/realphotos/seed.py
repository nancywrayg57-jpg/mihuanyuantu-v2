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
    return await reconcile_menu_declaration(
        db,
        tenant_id=tenant_id,
        declaration=ACCESS,
        role_id_overrides=role_id_overrides,
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
