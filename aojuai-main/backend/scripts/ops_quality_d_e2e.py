"""OPS-QUALITY-D-2026-11-07 end-to-end on development-host PostgreSQL.

D1: IA_C6 honest mitigation when Redis is off (ops restart note).
D2: held_until_tech_support → tech release + order_support/merchant 403 + integer ledger.

Evidence: /tmp/ops-quality-d-e2e.log must contain OPS_QUALITY_D_E2E_PASS.
Does not open S7; production_billing=false; url_import_connected=false.
"""

from __future__ import annotations

import asyncio
import io
from datetime import UTC, datetime
from pathlib import Path

import httpx
from PIL import Image

LOG_PATH = Path("/tmp/ops-quality-d-e2e.log")
S3_CONTROLS = Path("/tmp/s3-pg-e2e-controls.log")


def note(message: str) -> None:
    line = message.rstrip()
    print(line)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def _jpeg(color: tuple[int, int, int] = (70, 90, 110), size: tuple[int, int] = (1024, 768)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG", quality=85)
    return buf.getvalue()


async def _login(client: httpx.AsyncClient, username: str, password: str) -> dict[str, str]:
    challenge = await client.post("/api/v1/realphotos/auth/challenges")
    assert challenge.status_code == 200
    data = challenge.json()["data"]
    logged_in = await client.post(
        "/api/v1/realphotos/auth/login",
        json={
            "username": username,
            "password": password,
            "challengeId": data["challengeId"],
            "challengeCode": data["devCode"],
        },
    )
    assert logged_in.status_code == 200, logged_in.text
    return {"Authorization": "Bearer " + logged_in.json()["data"]["accessToken"]}


async def _main() -> int:
    LOG_PATH.write_text("", encoding="utf-8")
    note("ops_quality_d_e2e start")
    note("production_billing=false url_import_connected=false s7_started=false")

    from sqlalchemy import select

    import app.capabilities.realphotos.models  # noqa: F401
    import app.domain  # noqa: F401
    from app.capabilities.realphotos.models import RealphotosImageTask, RealphotosMerchantProfile
    from app.capabilities.realphotos.permissions import ROLE_ADMIN
    from app.capabilities.realphotos.seed import reconcile
    from app.capabilities.realphotos.services.bootstrap import DEFAULT_PASSWORD, bootstrap_s0_accounts
    from app.capabilities.realphotos.services.credit_service import RealphotosCreditService
    from app.capabilities.realphotos.services.job_service import RealphotosJobService
    from app.capabilities.realphotos.services.redo_policy import MAX_EXECUTIONS
    from app.capabilities.realphotos.services.s1_catalog import S1_ENABLED_PRESETS
    from app.capabilities.realphotos.services.s1_processing import RealphotosS1Service
    from app.capabilities.realphotos.services.s6_ops import RealphotosOpsService
    from app.capabilities.realphotos.services.supplier_config import RealphotosSupplierConfigService
    from app.core.config import settings
    from app.infrastructure.cache.ui_cache import (
        bump_menu_structure_cache_version,
        get_menu_tree_options_cache_version,
        menu_structure_cache_mode,
    )
    from app.infrastructure.database.session import Base, async_session_factory, engine, init_db
    from app.main import app as fastapi_app
    from scripts.blocking_fix_schema import ensure_blocking_fix_schema
    from scripts.product_gap_a_schema import ensure_product_gap_a_schema

    if not str(settings.DB_DIALECT).startswith("postgres"):
        note(f"FAIL expected postgresql got {settings.DB_DIALECT!r}")
        return 2

    await init_db()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await ensure_blocking_fix_schema(engine)
    await ensure_product_gap_a_schema(engine)

    stamp = str(int(datetime.now(UTC).timestamp()))

    # --- D1: IA_C6 scheme B (Redis off on this host) ---
    redis_on = bool(settings.REDIS_ENABLED_EFFECTIVE)
    mode = menu_structure_cache_mode()
    note(f"D1 redis_enabled_effective={redis_on} menu_structure_cache_mode={mode}")
    if redis_on:
        # Scheme A path — not expected on current .env (REDIS_ENABLED=false).
        before = await get_menu_tree_options_cache_version(is_superuser=False)
        bumped = await bump_menu_structure_cache_version()
        after = await get_menu_tree_options_cache_version(is_superuser=False)
        assert after >= before and after == bumped
        note(f"IA_C6=fixed_shared_redis menu_bump before={before} bumped={bumped} after={after}")
    else:
        before = await get_menu_tree_options_cache_version(is_superuser=False)
        bumped = await bump_menu_structure_cache_version()
        after = await get_menu_tree_options_cache_version(is_superuser=False)
        assert after == bumped and after > before
        note(
            "IA_C6=mitigated_with_ops_note "
            f"menu_bump before={before} bumped={bumped} after={after} "
            "same_process_only=true"
        )
        note(
            "D1_ops_restart_required=true "
            "restart_cmd_summary="
            "'pkill -f \"uvicorn app.main:app\" || true; "
            "cd aojuai-main/backend && set -a && . ./.env && set +a && "
            "nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 38000 &' "
            "(滚动重启全部 API worker；禁止宣称已自动跨进程一致)"
        )
        note("REDIS_DISABLED menu_version=process_local")
        note(
            "D1_merchant_sidebar_acceptance="
            "授权/菜单 reconcile 后同进程可读新 menu_version；"
            "多 uvicorn worker 须按上列命令滚动重启后商家侧栏才保证一致"
        )

    async with async_session_factory() as db:
        summary = await bootstrap_s0_accounts(db)
        tenant = int(summary["rp_merchant_a1"]["tenantId"])
        merchant_user = int(summary["rp_merchant_a1"]["userId"])
        platform = int(summary["rp_admin"]["tenantId"])
        await reconcile(db, tenant_id=platform)
        await reconcile(db, tenant_id=tenant)
        await RealphotosSupplierConfigService(db).ensure()
        # Ensure a usable preset (catalog injection may be off after bulk-import).
        ops = RealphotosOpsService(db)
        preset_code = f"opsd-phone-{stamp}"
        await ops.save_preset(
            actor_role_codes={ROLE_ADMIN, "admin"},
            code=preset_code,
            device_type="phone",
            brand="RuntimeCam",
            model_name="OPS-D-Phone",
            gps_mode="none",
            enabled=True,
            iso="100",
            shutter="1/125",
            aperture="f/1.8",
            focal_length="26mm",
            source="admin",
        )
        profile = (
            await db.execute(
                select(RealphotosMerchantProfile).where(
                    RealphotosMerchantProfile.tenant_id == tenant,
                    RealphotosMerchantProfile.user_id == merchant_user,
                )
            )
        ).scalar_one_or_none()
        from app.capabilities.realphotos.services.copy_execution_guard import (
            RealphotosCopyExecutionGuardService,
        )
        await RealphotosCopyExecutionGuardService(db).force_clear_active(
            tenant_id=int(tenant), owner_account_id=int(merchant_user)
        )
        # B2: skip legacy copy_latch_* mirror clears.
        credits = RealphotosCreditService(db)
        wallet_before = await credits.get_wallet(tenant_id=tenant)
        await db.commit()
        note(
            f"D2 wallet_before available={wallet_before.get('availableInteger')} "
            f"reserved={wallet_before.get('reservedInteger')}"
        )

    transport = httpx.ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=180.0) as client:
        merchant = await _login(client, "rp_merchant_a1", DEFAULT_PASSWORD)
        support = await _login(client, "rp_order_support", DEFAULT_PASSWORD)
        tech = await _login(client, "rp_tech_support", DEFAULT_PASSWORD)
        await _login(client, "rp_admin", DEFAULT_PASSWORD)

        # --- D2: construct held_until_tech_support via detection_mode=technical ---
        async with async_session_factory() as db:
            loop = RealphotosS1Service(db)
            asset = await loop.upload(tenant_id=tenant, owner_account_id=merchant_user, data=_jpeg())
            _batch, tasks = await loop.submit_batch(
                tenant_id=tenant,
                owner_account_id=merchant_user,
                actor_role_codes={ROLE_ADMIN},
                asset_ids=[int(asset.id)],
                preset_code=preset_code,
                idempotency_key=f"opsd-held-{stamp}",
                detection_mode="technical",
            )
            jobs = RealphotosJobService(db)
            claimed = await jobs.claim(
                worker_id="ops-quality-d",
                job_kinds=("process_image",),
                payload_task_id=int(tasks[0].id),
            )
            assert claimed is not None
            done = await loop.execute_queued(claimed)
            await db.commit()
            held_id = int(done.id)
            assert done.credit_disposition == "held_until_tech_support", done.credit_disposition
            note(f"tech_hold=held_until_tech_support task_id={held_id}")

            mid = await RealphotosCreditService(db).get_wallet(tenant_id=tenant)
            note(
                f"D2 wallet_held available={mid.get('availableInteger')} "
                f"reserved={mid.get('reservedInteger')}"
            )
            assert "." not in str(mid.get("availableInteger"))
            assert "." not in str(mid.get("reservedInteger"))

        denied_support = await client.post(
            f"/api/v1/realphotos/held-credits/{held_id}/release",
            headers=support,
            json={"tenantId": tenant, "reason": "订单客服不能放"},
        )
        denied_merchant = await client.post(
            f"/api/v1/realphotos/held-credits/{held_id}/release",
            headers=merchant,
            json={"tenantId": tenant, "reason": "商家不能放"},
        )
        note(f"order_support_release={denied_support.status_code}")
        note(f"merchant_release={denied_merchant.status_code}")
        assert denied_support.status_code == 403
        assert denied_merchant.status_code == 403

        # Non-held task must not release via this path
        async with async_session_factory() as db:
            loop = RealphotosS1Service(db)
            asset2 = await loop.upload(
                tenant_id=tenant, owner_account_id=merchant_user, data=_jpeg((20, 40, 60))
            )
            _b2, tasks2 = await loop.submit_batch(
                tenant_id=tenant,
                owner_account_id=merchant_user,
                actor_role_codes={ROLE_ADMIN},
                asset_ids=[int(asset2.id)],
                preset_code=preset_code,
                idempotency_key=f"opsd-ok-{stamp}",
                detection_mode="pass",
            )
            jobs = RealphotosJobService(db)
            claimed2 = await jobs.claim(
                worker_id="ops-quality-d-ok",
                job_kinds=("process_image",),
                payload_task_id=int(tasks2[0].id),
            )
            ok_task = await loop.execute_queued(claimed2)
            await db.commit()
            ok_id = int(ok_task.id)
            note(f"D2 non_held_task_id={ok_id} disposition={ok_task.credit_disposition}")

        bad_release = await client.post(
            f"/api/v1/realphotos/held-credits/{ok_id}/release",
            headers=tech,
            json={"tenantId": tenant, "reason": "非冻结任务不应释放"},
        )
        note(f"D2 non_held_release_status={bad_release.status_code} body={(bad_release.text or '')[:160]}")
        assert bad_release.status_code >= 400, "non-held task must not release successfully"

        released = await client.post(
            f"/api/v1/realphotos/held-credits/{held_id}/release",
            headers=tech,
            json={"tenantId": tenant, "reason": "技术客服审计释放 OPS-QUALITY-D"},
        )
        assert released.status_code == 200, released.text
        assert released.json()["data"]["disposition"] == "released_tech_audit"
        note("tech_release=ok disposition=released_tech_audit")

        wallet = await client.get("/api/v1/realphotos/wallet", headers=merchant)
        assert wallet.status_code == 200, wallet.text
        wdata = wallet.json()["data"]
        avail = str(wdata.get("availableInteger"))
        reserved = str(wdata.get("reservedInteger"))
        note(f"D2 wallet_after available={avail} reserved={reserved}")
        assert avail.lstrip("-").isdigit()
        assert reserved.lstrip("-").isdigit()
        note("ledger_integer=true")

        async with async_session_factory() as db:
            task = await db.get(RealphotosImageTask, held_id)
            assert task is not None
            assert task.credit_disposition == "released_tech_audit"
            # Idempotent second release must fail (no double credit)
            from app.capabilities.realphotos.services.s6_ops import RealphotosOpsService
            from app.core.exceptions import BusinessError

            ops = RealphotosOpsService(db)
            try:
                await ops.release_held_credit(
                    actor_role_codes={"rp_tech_support"},
                    operator_user_id=int(summary["rp_tech_support"]["userId"]),
                    tenant_id=tenant,
                    task_id=held_id,
                    reason="重复释放应拒绝",
                )
                note("FAIL second_release_should_reject")
                return 3
            except BusinessError as exc:
                note(f"D2 second_release_rejected code={exc.code}")

        # Retry ceiling index (FR-024): first + 2 manual = 3 executions
        note(f"D2 max_executions={MAX_EXECUTIONS} (FR-024 first+2_manual)")
        assert int(MAX_EXECUTIONS) == 3
        if S3_CONTROLS.is_file():
            controls = S3_CONTROLS.read_text(encoding="utf-8", errors="replace")
            note(
                "D2_retry_controls_index="
                + ("S3_PG_CONTROLS_PASS" if "S3_PG_CONTROLS_PASS" in controls else "present_without_pass")
                + f" path={S3_CONTROLS} "
                + ("retry_limit=3" if "retry_limit=3" in controls else "retry_limit_mark_absent")
            )
        else:
            note(
                "D2_retry_controls_index=absent_file "
                f"path={S3_CONTROLS} "
                "policy_constant_MAX_EXECUTIONS=3 still asserted this round"
            )

        # Catalog constant still documented (not used for injection claim)
        note(f"D2_catalog_codes_documented={len(S1_ENABLED_PRESETS)}")

        # Admin can still bump menus (auth stays on)
        menus = await client.get("/api/v1/menus/routes", headers=merchant)
        note(f"D1 menus_routes_status={menus.status_code} (auth not disabled)")
        assert menus.status_code == 200

        note(
            "OPS_QUALITY_D_E2E_PASS "
            f"IA_C6={'fixed_shared_redis' if redis_on else 'mitigated_with_ops_note'} "
            "tech_hold=held_until_tech_support tech_release=ok "
            "order_support_release=403 ledger_integer=true "
            "production_billing=false url_import_connected=false s7_started=false"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
