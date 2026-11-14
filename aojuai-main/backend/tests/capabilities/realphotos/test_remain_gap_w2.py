"""REMAIN-GAP W2：R3 Alembic head + R4 ACCOUNT_SPEND_BUSY / guard_epoch."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from PIL import Image
from sqlalchemy import func, select

from app.capabilities.realphotos import CAPABILITY
from app.capabilities.realphotos.models import RealphotosCopyExecutionGuard, RealphotosImageTask
from app.capabilities.realphotos.permissions import ROLE_MERCHANT
from app.capabilities.realphotos.services.bootstrap import bootstrap_s0_accounts
from app.capabilities.realphotos.services.copy_execution_guard import (
    ACCOUNT_SPEND_BUSY,
    RealphotosCopyExecutionGuardService,
)
from app.capabilities.realphotos.services.credit_service import RealphotosCreditService
from app.capabilities.realphotos.services.s1_catalog import S1_ENABLED_PRESETS
from app.capabilities.realphotos.services.s1_processing import RealphotosS1Service
from app.capabilities.realphotos.services.s1_recharge import RealphotosRechargeService
from app.core.exceptions import BusinessError


def test_r3_alembic_head_is_single() -> None:
    backend = Path(__file__).resolve().parents[3]
    cfg = Config(str(backend / "alembic.ini"))
    cfg.set_main_option("script_location", str(CAPABILITY.migration_path()))
    heads = list(ScriptDirectory.from_config(cfg).get_heads())
    assert heads == ["realphotos_0005"], heads


@pytest.mark.asyncio
async def test_r4_second_copy_returns_account_spend_busy(db) -> None:
    summary = await bootstrap_s0_accounts(db)
    tenant = int(summary["rp_merchant_a1"]["tenantId"])
    user = int(summary["rp_merchant_a1"]["userId"])
    support = int(summary["rp_order_support"]["userId"])
    recharge = RealphotosRechargeService(db)
    order = await recharge.create_order(
        tenant_id=tenant,
        requester_user_id=user,
        tier_yuan=100,
        voucher_note="w2",
        idempotency_key="w2-copy-recharge",
    )
    await recharge.confirm(order_id=int(order.id), operator_user_id=support)
    loop = RealphotosS1Service(db)
    credits = RealphotosCreditService(db)
    asset = await loop.upload(tenant_id=tenant, owner_account_id=user, data=_jpeg())
    source = await loop.submit_single(
        tenant_id=tenant,
        owner_account_id=user,
        actor_role_codes={ROLE_MERCHANT},
        asset_id=int(asset.id),
        preset_code=S1_ENABLED_PRESETS[0]["code"],
        idempotency_key="w2-copy-src",
        detection_mode="gemini",
    )
    first = await loop.copy_processing_task(
        tenant_id=tenant,
        owner_account_id=user,
        source_task_id=int(source.id),
        idempotency_key="w2-copy-1",
        actor_role_codes={ROLE_MERCHANT},
        detection_mode="gemini",
    )
    guard = await RealphotosCopyExecutionGuardService(db).get_active(
        tenant_id=tenant, owner_account_id=user
    )
    assert guard is not None
    assert int(guard.batch_id) == int(first.batch_id)
    assert int(guard.guard_epoch) >= 1
    with pytest.raises(BusinessError) as exc:
        await loop.copy_processing_task(
            tenant_id=tenant,
            owner_account_id=user,
            source_task_id=int(source.id),
            idempotency_key="w2-copy-2",
            actor_role_codes={ROLE_MERCHANT},
            detection_mode="gemini",
        )
    assert exc.value.code == ACCOUNT_SPEND_BUSY
    with pytest.raises(BusinessError) as freeze_exc:
        await credits.freeze(
            tenant_id=tenant,
            amount=10,
            operator_user_id=user,
            event_key="w2-freeze-blocked",
        )
    assert freeze_exc.value.code == ACCOUNT_SPEND_BUSY
    assert "COPY_LATCH_ACTIVE" not in {exc.value.code, freeze_exc.value.code}
    assert await db.scalar(select(func.count()).select_from(RealphotosCopyExecutionGuard)) >= 1
    assert await db.scalar(select(func.count()).select_from(RealphotosImageTask)) >= 2


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (1024, 768), (12, 34, 56)).save(buf, format="JPEG")
    return buf.getvalue()
