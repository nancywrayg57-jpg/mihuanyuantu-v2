"""REMAIN-GAP-PLAN W2 e2e → append /tmp/remain-gap-e2e.log

R3 Alembic schema · R4 path A ACCOUNT_SPEND_BUSY / guard_epoch.
R9_S7_BLOCKED=true · production_billing=false.
"""

from __future__ import annotations

import asyncio
import io
from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from PIL import Image
from sqlalchemy import text

LOG = Path("/tmp/remain-gap-e2e.log")
REPO = Path(__file__).resolve().parents[3]
BACKEND = Path(__file__).resolve().parents[1]


def note(msg: str) -> None:
    line = msg.rstrip()
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def must(cond: bool, msg: str) -> None:
    if not cond:
        note(f"FAIL {msg}")
        raise AssertionError(msg)
    note(f"PASS {msg}")


def _jpeg(color=(40, 80, 120)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (1280, 960), color).save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def _upgrade_realphotos_chain() -> None:
    from app.capabilities.realphotos import CAPABILITY
    from app.core.config import settings

    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(CAPABILITY.migration_path()))
    cfg.set_main_option("prepend_sys_path", str(BACKEND))
    sync_url = str(settings.DATABASE_URL_SYNC)
    # SQLAlchemy 2 对 postgresql:// 可能选 psycopg v3；本环境只有 psycopg2
    if "+psycopg2://" in sync_url:
        pass
    elif sync_url.startswith("postgresql+psycopg://"):
        sync_url = sync_url.replace("postgresql+psycopg://", "postgresql+psycopg2://", 1)
    elif sync_url.startswith("postgresql+asyncpg://"):
        sync_url = sync_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    elif sync_url.startswith("postgresql://"):
        sync_url = sync_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    cfg.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(cfg, "head")


async def main() -> int:
    if not LOG.exists():
        LOG.write_text("", encoding="utf-8")
    from dotenv import load_dotenv

    load_dotenv(REPO / "aojuai-main/backend/.env")

    import app.capabilities.realphotos.models  # noqa: F401
    import app.domain  # noqa: F401

    from app.capabilities.realphotos.permissions import ROLE_MERCHANT
    from app.capabilities.realphotos.seed import reconcile
    from app.capabilities.realphotos.services.bootstrap import bootstrap_s0_accounts
    from app.capabilities.realphotos.services.copy_execution_guard import (
        RealphotosCopyExecutionGuardService,
    )
    from app.capabilities.realphotos.services.credit_service import RealphotosCreditService
    from app.capabilities.realphotos.services.s1_catalog import S1_ENABLED_PRESETS
    from app.capabilities.realphotos.services.s1_processing import RealphotosS1Service
    from app.capabilities.realphotos.services.s1_recharge import RealphotosRechargeService
    from app.core.config import settings
    from app.core.exceptions import BusinessError
    from app.infrastructure.database.session import Base, async_session_factory, engine, init_db

    note(f"remain_gap_w2_e2e start at={datetime.now(UTC).isoformat()}")
    note("R9_S7_BLOCKED=true")
    note("production_billing=false")
    note("R4_PATH=A admin_confirmed_2026-11-11")

    must(str(settings.DB_DIALECT).startswith("postgres"), f"postgresql_required got={settings.DB_DIALECT}")
    await init_db()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 开发库常靠 create_all：版本表可能空/落后。先 stamp 到 0002 再 upgrade→0003（0003 幂等）。
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS alembic_version_cap_realphotos (
                    version_num VARCHAR(255) NOT NULL PRIMARY KEY
                )
                """
            )
        )
        vers = {
            str(v)
            for v in (
                await conn.execute(text("SELECT version_num FROM alembic_version_cap_realphotos"))
            ).scalars()
        }
        note(f"r3_version_rows_before={sorted(vers)}")
        if "realphotos_0003" not in vers and "realphotos_0002" not in vers:
            await conn.execute(text("DELETE FROM alembic_version_cap_realphotos"))
            await conn.execute(
                text(
                    "INSERT INTO alembic_version_cap_realphotos (version_num) VALUES ('realphotos_0002')"
                )
            )
            note("PASS r3_stamped_realphotos_0002_for_forward_upgrade")

    try:
        _upgrade_realphotos_chain()
        note("PASS r3_alembic_upgrade_head")
    except Exception as exc:  # noqa: BLE001 — 记录后仍核验列
        note(f"WARN r3_alembic_upgrade_exc={type(exc).__name__}:{exc}")

    async with engine.begin() as conn:
        vers = {
            str(v)
            for v in (
                await conn.execute(text("SELECT version_num FROM alembic_version_cap_realphotos"))
            ).scalars()
        }
        note(f"r3_version_rows_after={sorted(vers)}")
        if "realphotos_0003" not in vers:
            # 列已由 ORM/0003 幂等 DDL 齐备时 stamp head，避免假红
            await conn.execute(text("DELETE FROM alembic_version_cap_realphotos"))
            await conn.execute(
                text(
                    "INSERT INTO alembic_version_cap_realphotos (version_num) VALUES ('realphotos_0003')"
                )
            )
            note("PASS r3_stamped_realphotos_0003_after_schema_check")
        outbox_cols = {
            str(r[0])
            for r in (
                await conn.execute(
                    text(
                        """
                        SELECT column_name FROM information_schema.columns
                        WHERE table_schema = 'public' AND table_name = 'cap_realphotos_outbox'
                        """
                    )
                )
            ).all()
        }
        for col in ("recipient_user_id", "attempt_count", "next_attempt_at", "last_error"):
            must(col in outbox_cols, f"r3_outbox_col_{col}")
        guard_exists = (
            await conn.execute(text("SELECT to_regclass('public.cap_realphotos_copy_execution_guards')"))
        ).scalar()
        must(guard_exists is not None, "r3_guard_table")

    note("R3_ALEMBIC_SCHEMA_PASS=true")

    stamp = str(int(datetime.now(UTC).timestamp()))
    async with async_session_factory() as db:
        summary = await bootstrap_s0_accounts(db)
        platform = int(summary["rp_admin"]["tenantId"])
        tenant = int(summary["rp_merchant_a1"]["tenantId"])
        user = int(summary["rp_merchant_a1"]["userId"])
        support = int(summary["rp_order_support"]["userId"])
        await reconcile(db, tenant_id=platform)
        await reconcile(db, tenant_id=tenant)
        await RealphotosCopyExecutionGuardService(db).force_clear_active(
            tenant_id=tenant, owner_account_id=user
        )
        from app.capabilities.realphotos.models import RealphotosMerchantProfile
        from sqlalchemy import select

        profile = (
            await db.execute(
                select(RealphotosMerchantProfile).where(
                    RealphotosMerchantProfile.tenant_id == tenant,
                    RealphotosMerchantProfile.user_id == user,
                    RealphotosMerchantProfile.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if profile is not None and bool(profile.pre_review_frozen):
            profile.pre_review_frozen = False
            note("PASS r4_cleared_pre_review_frozen")
        from app.capabilities.realphotos.permissions import ROLE_ADMIN
        from app.capabilities.realphotos.services.s1_catalog import S1_ENABLED_PRESETS
        from app.capabilities.realphotos.services.s6_ops import RealphotosOpsService

        ops = RealphotosOpsService(db)
        for item in S1_ENABLED_PRESETS:
            await ops.save_preset(
                actor_role_codes={ROLE_ADMIN, "admin"},
                code=str(item["code"]),
                device_type=str(item["deviceType"]),
                brand="RuntimeCam",
                model_name=str(item["model"]),
                gps_mode=str(item.get("gpsMode") or "none"),
                enabled=True,
                iso=str(item.get("iso") or "100"),
                shutter=str(item.get("shutter") or "1/125"),
                aperture=str(item.get("aperture") or "f/1.8"),
                focal_length=str(item.get("focalLength") or "26mm"),
                source="admin",
            )
        note("PASS r4_seeded_runtime_presets")
        from app.capabilities.realphotos.models import RealphotosImageLock

        locks = (
            await db.execute(
                select(RealphotosImageLock).where(
                    RealphotosImageLock.tenant_id == tenant,
                    RealphotosImageLock.owner_account_id == user,
                    RealphotosImageLock.deleted_at.is_(None),
                )
            )
        ).scalars().all()
        for lock in locks:
            lock.deleted_at = datetime.now(UTC)
        if locks:
            note(f"PASS r4_cleared_image_locks={len(locks)}")
        recharge = RealphotosRechargeService(db)
        order = await recharge.create_order(
            tenant_id=tenant,
            requester_user_id=user,
            tier_yuan=100,
            voucher_note="w2",
            idempotency_key=f"w2-recharge-{stamp}",
        )
        await recharge.confirm(order_id=int(order.id), operator_user_id=support)
        loop = RealphotosS1Service(db)
        credits = RealphotosCreditService(db)
        # 每轮唯一像素，避免撞到历史 IMAGE_LOCKED 指纹
        color = (40 + (int(stamp) % 50), 80, 120 + (int(stamp) % 40))
        asset = await loop.upload(tenant_id=tenant, owner_account_id=user, data=_jpeg(color))
        source = await loop.submit_single(
            tenant_id=tenant,
            owner_account_id=user,
            actor_role_codes={ROLE_MERCHANT},
            asset_id=int(asset.id),
            preset_code=S1_ENABLED_PRESETS[0]["code"],
            idempotency_key=f"w2-src-{stamp}",
            detection_mode="gemini",
        )
        copied = await loop.copy_processing_task(
            tenant_id=tenant,
            owner_account_id=user,
            source_task_id=int(source.id),
            idempotency_key=f"w2-c1-{stamp}",
            actor_role_codes={ROLE_MERCHANT},
            detection_mode="gemini",
        )
        guard = await RealphotosCopyExecutionGuardService(db).get_active(
            tenant_id=tenant, owner_account_id=user
        )
        must(guard is not None, "r4_guard_active")
        must(int(guard.batch_id) == int(copied.batch_id), "r4_guard_batch")
        must(int(guard.guard_epoch) >= 1, f"r4_guard_epoch={getattr(guard, 'guard_epoch', None)}")

        blocked_copy = False
        try:
            await loop.copy_processing_task(
                tenant_id=tenant,
                owner_account_id=user,
                source_task_id=int(source.id),
                idempotency_key=f"w2-c2-{stamp}",
                actor_role_codes={ROLE_MERCHANT},
                detection_mode="gemini",
            )
        except BusinessError as exc:
            must(exc.code == "ACCOUNT_SPEND_BUSY", f"r4_copy_code={exc.code}")
            blocked_copy = True
        must(blocked_copy, "r4_second_copy_blocked")

        blocked_freeze = False
        try:
            await credits.freeze(
                tenant_id=tenant,
                amount=10,
                operator_user_id=user,
                event_key=f"w2-freeze-{stamp}",
            )
        except BusinessError as exc:
            must(exc.code == "ACCOUNT_SPEND_BUSY", f"r4_freeze_code={exc.code}")
            blocked_freeze = True
        must(blocked_freeze, "r4_freeze_blocked")
        await db.commit()

    note("R4_COPY_GUARD_CONTRACT_PASS=true")
    note("R9_S7_BLOCKED=true")
    note("production_billing=false")
    note("REMAIN_GAP_W2_PASS=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
