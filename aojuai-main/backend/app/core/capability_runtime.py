"""Runtime orchestration shared by tenant provisioning and operator scripts."""

from __future__ import annotations

import importlib
from collections.abc import Mapping
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.capability_registry import (
    CapabilityDefinition,
    discover_capabilities,
    order_capabilities,
)
from app.core.feature_switches import is_module_installed


def installed_capabilities() -> tuple[CapabilityDefinition, ...]:
    return order_capabilities(
        tuple(definition for definition in discover_capabilities() if is_module_installed(definition.code))
    )


async def provision_installed_capabilities(
    db: AsyncSession,
    *,
    tenant_id: int,
    role_id_overrides: Mapping[str, int | None] | None = None,
) -> dict[str, Any]:
    outcomes: dict[str, Any] = {}
    for definition in installed_capabilities():
        seed = importlib.import_module(definition.seed_module)
        outcomes[definition.code] = await seed.provision(
            db,
            tenant_id=tenant_id,
            role_id_overrides=role_id_overrides,
        )
    return outcomes


async def sync_installed_capabilities(db: AsyncSession) -> dict[str, Any]:
    outcomes: dict[str, Any] = {}
    for definition in installed_capabilities():
        seed = importlib.import_module(definition.seed_module)
        outcomes[definition.code] = await seed.sync(db)
    return outcomes
