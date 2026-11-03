"""Idempotent provisioning and reconciliation for installed tenants.

三条链路共用这一个 reconciler：
- 新装 / 全库对账：`python -m scripts.capability sync`
- 已有租户升级：同上（能力包的表由包内迁移链建，菜单不写进迁移）
- 运行时新建租户：`app.core.capability_runtime.provision_installed_capabilities`

对账语义（不是"根节点在就跳过"）：缺的补、变的改、重复的合、授权补齐含父级闭包；
连跑两次第二次不产生任何变更。空库（零租户）时 `sync` 是 no-op。
"""

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
    """Provisioning is reconciliation: safe for the first run and every rerun."""

    return await reconcile(db, tenant_id=tenant_id, role_id_overrides=role_id_overrides)


async def sync(db: AsyncSession) -> list[tuple[int, ReconcileResult]]:
    result = await db.execute(
        text("SELECT id FROM tenants WHERE deleted_at IS NULL ORDER BY id")
    )
    outcomes: list[tuple[int, ReconcileResult]] = []
    for tenant_id in result.scalars().all():
        normalized_id = int(tenant_id)
        outcomes.append((normalized_id, await reconcile(db, tenant_id=normalized_id)))
    return outcomes
