#!/usr/bin/env python3
"""LIBRARY-ASSET-PURGE e2e: delete purges disk; orphan cleanup clears leftovers.

Evidence marker: LIBRARY_ASSET_PURGE_E2E_PASS
"""

from __future__ import annotations

import asyncio
import io
import sys
from datetime import UTC, datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _jpeg(width: int = 1024, height: int = 768) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (width, height), (33, 66, 99)).save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def note(msg: str) -> None:
    print(msg, flush=True)


async def main() -> int:
    from sqlalchemy import select

    from app.capabilities.realphotos.adapters.storage import get_storage_adapter
    from app.capabilities.realphotos.constants import SEED_OBJECT_KEY
    from app.capabilities.realphotos.models import RealphotosAsset
    from app.capabilities.realphotos.permissions import ROLE_ADMIN
    from app.capabilities.realphotos.services.bootstrap import bootstrap_s0_accounts
    from app.capabilities.realphotos.services.s1_processing import RealphotosS1Service
    from app.capabilities.realphotos.services.s1_recharge import RealphotosRechargeService
    from app.capabilities.realphotos.services.s6_ops import RealphotosOpsService
    from app.infrastructure.database.session import async_session_factory, init_db

    await init_db()
    async with async_session_factory() as db:
        summary = await bootstrap_s0_accounts(db)
        tenant = int(summary["rp_merchant_a1"]["tenantId"])
        user = int(summary["rp_merchant_a1"]["userId"])
        support = int(summary["rp_order_support"]["userId"])
        loop = RealphotosS1Service(db)
        recharge = RealphotosRechargeService(db)
        preset_code = f"purge-e2e-{int(datetime.now(UTC).timestamp())}"
        await RealphotosOpsService(db).save_preset(
            actor_role_codes={ROLE_ADMIN, "admin"},
            code=preset_code,
            device_type="phone",
            brand="Apple",
            model_name="iPhone-Purge-E2E",
            gps_mode="none",
            enabled=True,
            iso="100",
            shutter="1/120",
            aperture="f/1.8",
            focal_length="26mm",
            source="admin",
        )
        await db.commit()
        order = await recharge.create_order(
            tenant_id=tenant,
            requester_user_id=user,
            tier_yuan=100,
            voucher_note="library-purge-e2e",
            idempotency_key=f"library-purge-e2e-{datetime.now(UTC).timestamp()}",
        )
        await recharge.confirm(order_id=int(order.id), operator_user_id=support)

        asset = await loop.upload(tenant_id=tenant, owner_account_id=user, data=_jpeg())
        key = str(asset.object_key)
        storage = get_storage_adapter()
        assert storage.exists(key), "upload must land on disk"
        await loop.soft_delete_asset(tenant_id=tenant, asset_id=int(asset.id))
        await db.commit()
        assert storage.exists(key) is False, "DELETE must purge object copy"
        note(f"delete_purge_ok key={key}")

        # Legacy soft-delete without purge + true disk orphan.
        leftover = await loop.upload(tenant_id=tenant, owner_account_id=user, data=_jpeg(1200, 900))
        leftover_key = str(leftover.object_key)
        leftover.deleted_at = datetime.now(UTC)
        await db.flush()
        assert storage.exists(leftover_key)
        orphan_key = f"tenant/{tenant}/upload/e2e-orphan-{int(datetime.now(UTC).timestamp())}.jpg"
        storage.put_bytes(orphan_key, _jpeg(1024, 768), content_type="image/jpeg")
        output_key = f"tenant/{tenant}/output/e2e-keep-{int(datetime.now(UTC).timestamp())}.jpg"
        storage.put_bytes(output_key, _jpeg(1024, 768), content_type="image/jpeg")
        live = await loop.upload(tenant_id=tenant, owner_account_id=user, data=_jpeg(1280, 960))
        live_key = str(live.object_key)
        storage.ensure_seed_file()

        cleaned = await loop.cleanup_library_orphans()
        await db.commit()
        note(f"orphan_cleanup={cleaned}")
        assert storage.exists(leftover_key) is False
        assert storage.exists(orphan_key) is False
        assert storage.exists(live_key) is True
        assert storage.exists(output_key) is True
        assert storage.exists(SEED_OBJECT_KEY) is True
        live_row = (
            await db.execute(select(RealphotosAsset).where(RealphotosAsset.id == int(live.id)))
        ).scalar_one()
        assert live_row.deleted_at is None

        # Running task still blocks delete.
        task = await loop.submit_single(
            tenant_id=tenant,
            owner_account_id=user,
            actor_role_codes={ROLE_ADMIN},
            asset_id=int(live.id),
            preset_code=preset_code,
            idempotency_key=f"library-purge-run-{int(datetime.now(UTC).timestamp())}",
            detection_mode="pass",
            pre_review_mode="pass",
        )
        from app.core.exceptions import BusinessError

        try:
            await loop.soft_delete_asset(tenant_id=tenant, asset_id=int(live.id))
            raise AssertionError("expected ASSET_IN_USE")
        except BusinessError as exc:
            assert exc.code == "ASSET_IN_USE"
        assert storage.exists(live_key) is True
        note(f"in_use_guard_ok task={task.id}")

    note("LIBRARY_ASSET_PURGE_E2E_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
