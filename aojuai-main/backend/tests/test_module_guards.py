from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import ForbiddenError
from app.core.module_guards import ensure_module_enabled_for_tenant


@pytest.mark.asyncio
async def test_ensure_module_enabled_for_tenant_allows_enabled_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = AsyncMock()
    db.scalar.return_value = {
        "feature_switches": {
            "modules": {
                "assistant": True,
            }
        }
    }

    await ensure_module_enabled_for_tenant(
        db=db,
        tenant_id=7,
        module_code="assistant",
    )


@pytest.mark.asyncio
async def test_ensure_module_enabled_for_tenant_rejects_disabled_module() -> None:
    db = AsyncMock()
    db.scalar.return_value = {
        "feature_switches": {
            "modules": {
                "assistant": False,
            }
        }
    }

    with pytest.raises(ForbiddenError):
        await ensure_module_enabled_for_tenant(
            db=db,
            tenant_id=7,
            module_code="assistant",
        )
