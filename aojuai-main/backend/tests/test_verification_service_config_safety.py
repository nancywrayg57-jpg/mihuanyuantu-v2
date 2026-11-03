from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.domain.verification import service as verification_service_module
from app.domain.verification.service import VerificationService


@pytest.mark.asyncio
async def test_send_bind_phone_code_normalizes_non_object_tenant_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = VerificationService(AsyncMock())
    service._ensure_phone_available = AsyncMock()  # type: ignore[method-assign]
    service._ensure_cooldown_ok = AsyncMock()  # type: ignore[method-assign]
    service.create = AsyncMock()  # type: ignore[method-assign]

    send_code = AsyncMock(return_value="123456")
    monkeypatch.setattr(verification_service_module, "send_verification_code", send_code)

    user = SimpleNamespace(id=1, tenant_id=1, phone=None)
    tenant = SimpleNamespace(name="Demo Tenant", config=[])

    result = await service.send_bind_phone_code(user=user, tenant=tenant, phone="+86 13800138000")

    assert result["debugCode"] == "123456"
    assert send_code.await_args.kwargs["tenant_config"] == {}
