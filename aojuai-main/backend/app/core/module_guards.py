"""Shared tenant module guards for authenticated and public flows."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.feature_switches import is_module_enabled, label_for_module


async def get_tenant_config_by_id(
    *,
    db: AsyncSession,
    tenant_id: int,
) -> dict[str, Any] | None:
    from app.domain.auth.models import Tenant

    return await db.scalar(
        select(Tenant.config).where(
            Tenant.id == tenant_id,
            Tenant.deleted_at.is_(None),
        )
    )


async def ensure_module_enabled_for_tenant(
    *,
    db: AsyncSession,
    tenant_id: int,
    module_code: str,
) -> None:
    if await is_module_enabled_for_tenant(
        db=db,
        tenant_id=tenant_id,
        module_code=module_code,
    ):
        return

    raise ForbiddenError(message=f"模块已关闭：{label_for_module(module_code)}")


async def ensure_public_module_enabled_for_tenant(
    *,
    db: AsyncSession,
    tenant_id: int,
    module_code: str,
) -> None:
    """Enforce a public module without disclosing that a disabled feature exists."""
    if await is_module_enabled_for_tenant(
        db=db,
        tenant_id=tenant_id,
        module_code=module_code,
    ):
        return

    raise NotFoundError()


async def is_module_enabled_for_tenant(
    *,
    db: AsyncSession,
    tenant_id: int,
    module_code: str,
) -> bool:
    """Return a tenant module switch without enforcing it.

    Optional cross-module integrations use this to skip the downstream action
    while keeping the owning module's own write available. Enforcing here would
    turn "the other module is off" into a 403 for the caller's own feature.
    """
    tenant_config = await get_tenant_config_by_id(
        db=db,
        tenant_id=tenant_id,
    )
    return is_module_enabled(tenant_config, module_code)
