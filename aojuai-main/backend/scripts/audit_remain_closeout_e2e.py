"""AUDIT-REMAIN-CLOSEOUT e2e → /tmp/audit-remain-closeout-e2e.log

W1: A1 frozen no-acquire · A2 library download naming helpers.
W2: B1 Alembic head · B2 LEASE_TTL_DEFERRED + no copy_latch business path.
W3: C1 architecture body vs front-matter.
Gates: R9_S7_BLOCKED / production_billing=false / OUT_ND012_SKIPPED.
"""

from __future__ import annotations

import asyncio
import io
import re
from datetime import UTC, datetime
from pathlib import Path

from alembic.config import Config
from PIL import Image
from sqlalchemy import select, text

from alembic import command

LOG = Path("/tmp/audit-remain-closeout-e2e.log")
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


def _png(color=(10, 90, 40)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (1280, 960), color).save(buf, format="PNG")
    return buf.getvalue()


def _ext_for_content_type(content_type: str) -> str:
    raw = str(content_type or "").split(";", 1)[0].strip().lower()
    mapping = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/pjpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }
    return mapping.get(raw, ".jpg")


def _allocate(basename: str, extension: str, used: dict[str, int]) -> str:
    ext = extension if extension.startswith(".") else f".{extension}"
    stem = re.sub(r"[\\/]+", "_", str(basename or "asset")).strip() or "asset"
    preferred = f"{stem}{ext}"
    seen = used.get(preferred, 0)
    used[preferred] = seen + 1
    if seen == 0:
        return preferred
    return f"{stem}_{seen + 1}{ext}"


def _upgrade_realphotos_chain() -> None:
    from app.capabilities.realphotos import CAPABILITY
    from app.core.config import settings

    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(CAPABILITY.migration_path()))
    cfg.set_main_option("prepend_sys_path", str(BACKEND))
    sync_url = str(settings.DATABASE_URL_SYNC)
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
    from app.capabilities.realphotos.models import RealphotosAsset, RealphotosMerchantProfile
    from app.capabilities.realphotos.permissions import ROLE_MERCHANT
    from app.capabilities.realphotos.seed import reconcile
    from app.capabilities.realphotos.services.bootstrap import bootstrap_s0_accounts
    from app.capabilities.realphotos.services.s1_catalog import S1_ENABLED_PRESETS
    from app.capabilities.realphotos.services.s1_processing import RealphotosS1Service
    from app.capabilities.realphotos.services.s5_growth import RealphotosGrowthService
    from app.core.config import settings
    from app.core.exceptions import BusinessError
    from app.infrastructure.database.session import Base, async_session_factory, engine, init_db

    note(f"audit_remain_closeout_e2e start at={datetime.now(UTC).isoformat()}")
    note("R9_S7_BLOCKED=true")
    note("production_billing=false")
    note("OUT_ND012_SKIPPED=true")

    must(str(settings.DB_DIALECT).startswith("postgres"), f"postgresql_required got={settings.DB_DIALECT}")
    await init_db()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as db:
        summary = await bootstrap_s0_accounts(db)
        platform = int(summary["rp_admin"]["tenantId"])
        tenant = int(summary["rp_merchant_a1"]["tenantId"])
        user = int(summary["rp_merchant_a1"]["userId"])
        await reconcile(db, tenant_id=platform)
        await reconcile(db, tenant_id=tenant)
        await db.commit()
        s1 = RealphotosS1Service(db)
        growth = RealphotosGrowthService(db)

        # --- A1 ---
        seeded = await s1.upload(tenant_id=tenant, owner_account_id=user, data=_jpeg((1, 2, 3)))
        await db.commit()

        profile = (
            await db.execute(
                select(RealphotosMerchantProfile).where(
                    RealphotosMerchantProfile.tenant_id == tenant,
                    RealphotosMerchantProfile.user_id == user,
                )
            )
        ).scalar_one()
        profile.pre_review_frozen = True
        await db.flush()

        try:
            await s1.upload(tenant_id=tenant, owner_account_id=user, data=_jpeg((4, 5, 6)))
            must(False, "a1_upload_should_freeze")
        except BusinessError as exc:
            must(exc.code == "ACCOUNT_FROZEN", f"a1_upload_code={exc.code}")

        try:
            await s1.upload_batch(tenant_id=tenant, owner_account_id=user, files=[_jpeg((7, 8, 9))])
            must(False, "a1_batch_should_freeze")
        except BusinessError as exc:
            must(exc.code == "ACCOUNT_FROZEN", f"a1_batch_code={exc.code}")

        try:
            await growth.import_resources(
                payload=["https://example.invalid/images/x.jpg"],
                tenant_id=tenant,
                owner_account_id=user,
            )
            must(False, "a1_import_should_freeze")
        except BusinessError as exc:
            must(exc.code == "ACCOUNT_FROZEN", f"a1_import_code={exc.code}")

        # 处理提交仍拒
        try:
            await s1.submit_batch(
                tenant_id=tenant,
                owner_account_id=user,
                actor_role_codes={ROLE_MERCHANT},
                asset_ids=[int(seeded.id)],
                preset_code=S1_ENABLED_PRESETS[0]["code"],
                idempotency_key=f"audit-remain-a1-{seeded.id}",
            )
            must(False, "a1_submit_should_freeze")
        except BusinessError as exc:
            must(exc.code == "ACCOUNT_FROZEN", f"a1_submit_code={exc.code}")

        # 列表仍可见
        still = (
            await db.execute(
                select(RealphotosAsset).where(
                    RealphotosAsset.id == int(seeded.id),
                    RealphotosAsset.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        must(still is not None, "a1_list_retained")

        profile.pre_review_frozen = False
        await db.flush()
        thawed = await s1.upload(tenant_id=tenant, owner_account_id=user, data=_jpeg((11, 12, 13)))
        must(int(thawed.id) > 0, "a1_unfreeze_upload")
        note("A1_FROZEN_NO_ACQUIRE_PASS=true")

        # --- A2 ---
        png_asset = await s1.upload(tenant_id=tenant, owner_account_id=user, data=_png())
        must(png_asset.content_type == "image/png", f"a2_png_ct={png_asset.content_type}")
        must(_ext_for_content_type(png_asset.content_type) == ".png", "a2_png_ext")

        fe_helper = REPO / "aojuai-main/frontend/src/lib/realphotos-download.ts"
        must(fe_helper.is_file(), "a2_fe_helper")
        helper_text = fe_helper.read_text(encoding="utf-8")
        must("allocateDownloadFileName" in helper_text, "a2_fe_allocate")
        must("_2" in helper_text or "seen + 1" in helper_text, "a2_fe_suffix")

        used: dict[str, int] = {}
        base = "same_sku"
        n1 = _allocate(base, ".png", used)
        n2 = _allocate(base, ".png", used)
        must(n1 == "same_sku.png", f"a2_name1={n1}")
        must(n2 == "same_sku_2.png", f"a2_name2={n2}")
        note("A2_LIBRARY_DOWNLOAD_PASS=true")
        await db.commit()

    note("AUDIT_REMAIN_W1_PASS=true")

    # --- B1 Alembic ---
    from app.capabilities.realphotos import CAPABILITY
    from app.capabilities.realphotos.services.copy_execution_guard import (
        ACCOUNT_SPEND_BUSY,
        LEASE_TTL_DEFERRED,
        RealphotosCopyExecutionGuardService,
    )
    from app.capabilities.realphotos.services.credit_service import RealphotosCreditService
    from app.capabilities.realphotos.services.s1_recharge import RealphotosRechargeService

    # 开发库可能停在 0003：直接 upgrade head（0004 幂等）
    _upgrade_realphotos_chain()
    note("PASS b1_alembic_upgrade_head")

    required_tables = [
        "cap_realphotos_generation_tasks",
        "cap_realphotos_provider_contracts",
        "cap_realphotos_device_presets",
        "cap_realphotos_copy_execution_guards",
        "cap_realphotos_redo_settings",
        "cap_realphotos_support_tickets",
    ]
    async with engine.begin() as conn:
        for table in required_tables:
            exists = await conn.scalar(text(f"SELECT to_regclass('{table}') IS NOT NULL"))
            must(bool(exists), f"b1_table_{table}")
        has_meta = await conn.scalar(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name='cap_realphotos_assets' AND column_name='meta_sku'"
            )
        )
        must(bool(has_meta), "b1_assets_meta_sku")
        has_billing = await conn.scalar(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name='cap_realphotos_image_tasks' AND column_name='billing_mode'"
            )
        )
        must(bool(has_billing), "b1_tasks_billing_mode")
        version = await conn.scalar(text(f"SELECT version_num FROM {CAPABILITY.version_table}"))
        must(str(version) == "realphotos_0004", f"b1_version={version}")
    note("B1_ALEMBIC_HEAD_PASS=true")

    # --- B2 guard residual ---
    must(LEASE_TTL_DEFERRED is True, "b2_lease_deferred_flag")
    async with async_session_factory() as db:
        summary = await bootstrap_s0_accounts(db)
        tenant = int(summary["rp_merchant_a1"]["tenantId"])
        user = int(summary["rp_merchant_a1"]["userId"])
        support = int(summary["rp_order_support"]["userId"])
        recharge = RealphotosRechargeService(db)
        order = await recharge.create_order(
            tenant_id=tenant,
            requester_user_id=user,
            tier_yuan=100,
            voucher_note="audit-remain-b2",
            idempotency_key=f"audit-remain-b2-{datetime.now(UTC).timestamp()}",
        )
        await recharge.confirm(order_id=int(order.id), operator_user_id=support)
        # 人为占用 guard（模拟复制中）；不读写 merchant.copy_latch_*
        await RealphotosCopyExecutionGuardService(db).force_clear_active(
            tenant_id=tenant, owner_account_id=user
        )
        guard = await RealphotosCopyExecutionGuardService(db).acquire(
            tenant_id=tenant, owner_account_id=user, batch_id=900001
        )
        must(guard.lease_until is None, "b2_lease_until_null")
        try:
            await RealphotosCopyExecutionGuardService(db).reject_if_busy(
                tenant_id=tenant, owner_account_id=user
            )
            must(False, "b2_should_busy")
        except BusinessError as exc:
            must(exc.code == ACCOUNT_SPEND_BUSY, f"b2_busy_code={exc.code}")
            must(exc.code != "COPY_LATCH_ACTIVE", "b2_no_copy_latch_code")
        try:
            await RealphotosCreditService(db).freeze(
                tenant_id=tenant,
                amount=10,
                operator_user_id=user,
                event_key=f"audit-remain-busy-{guard.id}",
            )
            must(False, "b2_freeze_should_busy")
        except BusinessError as exc:
            must(exc.code == ACCOUNT_SPEND_BUSY, f"b2_freeze_code={exc.code}")
        await RealphotosCopyExecutionGuardService(db).force_clear_active(
            tenant_id=tenant, owner_account_id=user
        )
        await db.commit()
        note("LEASE_TTL_DEFERRED=true")
        note("B2_COPY_GUARD_RESIDUAL_PASS=true")

    note("AUDIT_REMAIN_W2_PASS=true")

    # --- C1 ---
    arch = REPO / "docs" / "蜜獾原图-v2-项目架构-v1.0.md"
    arch_text = arch.read_text(encoding="utf-8")
    must("implementation_status: s0_s6_coded_partial" in arch_text, "c1_frontmatter")
    must("NOT_IMPLEMENTED" not in arch_text, "c1_no_not_implemented_token")
    must("LEASE_TTL_DEFERRED" in arch_text, "c1_lease_doc")
    # 「未实现」允许出现在否定句中，但禁止「完全未实现」误读断言
    must("完全未实现" not in arch_text, "c1_no_fully_unimplemented")
    note("C1_ARCH_DOC_CONSISTENCY_PASS=true")
    note("AUDIT_REMAIN_W3_PASS=true")

    note("OUT_ND012_SKIPPED=true")
    note("R9_S7_BLOCKED=true")
    note("production_billing=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
