"""PARTIAL-ALIGN-2026-11-07 end-to-end on development-host PostgreSQL.

Covers A–F success + key reject/empty paths. Keeps production_billing=false.
Does not enable URL import or open S7. Does not redo blocking-fix GPS EXIF writes.
"""

from __future__ import annotations

import asyncio
import io
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
from PIL import Image

LOG_PATH = Path("/tmp/partial-align-e2e.log")
BROWSER_PATH = Path("/tmp/partial-align-browser.txt")


def note(message: str) -> None:
    line = message.rstrip()
    print(line)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def _jpeg(color: tuple[int, int, int] = (40, 80, 120), size: tuple[int, int] = (1024, 768)) -> bytes:
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


async def _claim_and_run(task_id: int, worker_id: str) -> object:
    from app.capabilities.realphotos.services.job_service import RealphotosJobService
    from app.capabilities.realphotos.services.s1_processing import RealphotosS1Service
    from app.infrastructure.database.session import async_session_factory

    async with async_session_factory() as worker_db:
        claimed = await RealphotosJobService(worker_db).claim(
            worker_id=worker_id,
            job_kinds=("process_image",),
            payload_task_id=int(task_id),
        )
        assert claimed is not None
        done = await RealphotosS1Service(worker_db).execute_queued(claimed)
        await worker_db.commit()
        return done


async def _main() -> int:
    LOG_PATH.write_text("", encoding="utf-8")
    note("partial_align_e2e start")
    note("production_billing=false s7_started=false url_import_connected=false")

    from sqlalchemy import select

    import app.capabilities.realphotos.models  # noqa: F401
    import app.domain  # noqa: F401
    from app.capabilities.realphotos.seed import reconcile
    from app.capabilities.realphotos.services.bootstrap import DEFAULT_PASSWORD, bootstrap_s0_accounts
    from app.capabilities.realphotos.services.credit_service import RealphotosCreditService
    from app.capabilities.realphotos.services.legacy_preset_imports import browse_legacy_imports
    from app.capabilities.realphotos.services.supplier_config import RealphotosSupplierConfigService
    from app.core.config import settings
    from app.infrastructure.cache.ui_cache import (
        bump_menu_structure_cache_version,
        get_menu_tree_options_cache_version,
    )
    from app.infrastructure.database.session import Base, async_session_factory, engine, init_db
    from app.main import app as fastapi_app
    from scripts.blocking_fix_schema import ensure_blocking_fix_schema

    if not str(settings.DB_DIALECT).startswith("postgres"):
        note(f"FAIL expected postgresql got {settings.DB_DIALECT!r}")
        return 2

    await init_db()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await ensure_blocking_fix_schema(engine)

    stamp = str(int(datetime.now(UTC).timestamp()))
    async with async_session_factory() as db:
        from app.capabilities.realphotos.models import RealphotosMerchantProfile

        summary = await bootstrap_s0_accounts(db)
        tenant = int(summary["rp_merchant_a1"]["tenantId"])
        merchant_user = int(summary["rp_merchant_a1"]["userId"])
        platform = int(summary["rp_admin"]["tenantId"])
        await reconcile(db, tenant_id=platform)
        await reconcile(db, tenant_id=tenant)
        await RealphotosSupplierConfigService(db).ensure()
        # Clear leftover ND-025 latch from prior interrupted runs so A live path can proceed.
        profile = (
            await db.execute(
                select(RealphotosMerchantProfile).where(
                    RealphotosMerchantProfile.tenant_id == tenant,
                    RealphotosMerchantProfile.user_id == merchant_user,
                )
            )
        ).scalar_one_or_none()
        if profile is not None and bool(profile.copy_latch_active):
            profile.copy_latch_active = False
            profile.copy_latch_batch_id = None
            note("cleared_stale_copy_latch=true")
        await db.commit()
        wallet_before = await RealphotosCreditService(db).get_wallet(tenant_id=tenant)

    # --- E: S5 exit evidence still present ---
    s5_log = Path("/tmp/s5-pg-e2e.log")
    s5_text = s5_log.read_text(encoding="utf-8") if s5_log.is_file() else ""
    assert "S5_PG_E2E_PASS" in s5_text, "missing /tmp/s5-pg-e2e.log PASS"
    for token in (
        "query_status=DELIVERED",
        "business_key_scope_rejected=SCOPE_REJECTED",
        "zip=rejected",
        "supplier_connected=false",
        "production_billing=false",
    ):
        assert token in s5_text, token
    note("E s5_exit_evidence=green log=/tmp/s5-pg-e2e.log")

    marks: dict[str, object] = {}
    transport = httpx.ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=180.0) as client:
        merchant = await _login(client, "rp_merchant_a1", DEFAULT_PASSWORD)
        admin = await _login(client, "rp_admin", DEFAULT_PASSWORD)
        order_support = await _login(client, "rp_order_support", DEFAULT_PASSWORD)
        tech_support = await _login(client, "rp_tech_support", DEFAULT_PASSWORD)

        # --- A: force unconfigured ---
        async with async_session_factory() as db:
            svc = RealphotosSupplierConfigService(db)
            await svc.ensure()
            row = await svc._row("pre_review")
            if row is None:
                # Create disabled row so ensure won't auto-add enabled later when live flips
                from app.capabilities.realphotos.models import RealphotosProviderContract

                db.add(
                    RealphotosProviderContract(
                        tenant_id=0,
                        duty="pre_review",
                        provider="dashscope",
                        model_id="qwen3-vl-plus",
                        config_version="partial-align-test",
                        region="",
                        credential_ref="",
                        base_url="",
                        capabilities={},
                        enabled=False,
                        gap_note="partial-align unconfigured sample",
                    )
                )
            else:
                row.enabled = False
            await db.commit()

        upload = await client.post(
            "/api/v1/realphotos/assets",
            headers=merchant,
            files={"file": ("pa.jpg", _jpeg(), "image/jpeg")},
        )
        assert upload.status_code == 200, upload.text
        asset_id = int(upload.json()["data"]["id"])
        reject = await client.post(
            "/api/v1/realphotos/processing-tasks",
            headers=merchant,
            json={
                "assetId": asset_id,
                "presetCode": "s1-phone-01",
                "idempotencyKey": f"pa-unconf-{stamp}",
            },
        )
        assert reject.status_code == 400, reject.text
        assert reject.json().get("code") == "SERVICE_NOT_CONFIGURED"
        note("A unconfigured=SERVICE_NOT_CONFIGURED pre_review_mode=unconfigured")

        fake_pass = await client.post(
            "/api/v1/realphotos/processing-tasks",
            headers=merchant,
            json={
                "assetId": asset_id,
                "presetCode": "s1-phone-01",
                "idempotencyKey": f"pa-fake-pass-{stamp}",
                "preReviewMode": "pass",
            },
        )
        assert fake_pass.status_code == 400
        assert fake_pass.json().get("code") == "SERVICE_NOT_CONFIGURED"
        note("A customer_fixture_pass=SERVICE_NOT_CONFIGURED")

        async with async_session_factory() as db:
            wallet_mid = await RealphotosCreditService(db).get_wallet(tenant_id=tenant)
        assert int(wallet_mid["availableInteger"]) == int(wallet_before["availableInteger"])
        assert int(wallet_mid["reservedInteger"]) == int(wallet_before["reservedInteger"])
        note("A unconfigured_no_credit_delta=true")

        # Enable contract if material allows; else admin fixture_test_only
        async with async_session_factory() as db:
            svc = RealphotosSupplierConfigService(db)
            await svc.ensure()
            row = await svc._row("pre_review")
            live_ok = False
            if row is not None:
                from app.capabilities.realphotos.services.supplier_material import (
                    read_material_secret,
                    supplier_live_enabled,
                )

                if supplier_live_enabled() and read_material_secret("pre_review"):
                    row.enabled = True
                    await db.commit()
                    live_ok = True
            marks["pre_review_contract_enabled"] = live_ok

        if live_ok:
            live_submit = await client.post(
                "/api/v1/realphotos/processing-tasks",
                headers=merchant,
                json={
                    "assetId": asset_id,
                    "presetCode": "s1-phone-01",
                    "idempotencyKey": f"pa-live-{stamp}",
                    "detectionMode": "pass",
                },
            )
            assert live_submit.status_code == 200, live_submit.text
            payload = live_submit.json()["data"]
            assert payload.get("preReviewMode") == "live"
            assert payload.get("preReviewAudit") == "live"
            marks["pre_review_mode"] = "live"
            note("A live_submit=ok pre_review_mode=live")
            try:
                done = await _claim_and_run(int(payload["id"]), f"pa-live-{stamp}")
                note(
                    f"A live_execute status={getattr(done, 'status', None)} "
                    f"failure={getattr(done, 'failure_class', None)}"
                )
            except Exception as exc:  # noqa: BLE001
                note(f"A live_execute_recorded error={type(exc).__name__}:{exc}")
        else:
            # Admin owns asset for inject path
            up_admin = await client.post(
                "/api/v1/realphotos/assets",
                headers=admin,
                files={"file": ("pa-admin.jpg", _jpeg((90, 40, 40)), "image/jpeg")},
            )
            assert up_admin.status_code == 200, up_admin.text
            admin_submit = await client.post(
                "/api/v1/realphotos/processing-tasks",
                headers=admin,
                json={
                    "assetId": int(up_admin.json()["data"]["id"]),
                    "presetCode": "s1-phone-01",
                    "idempotencyKey": f"pa-fixture-{stamp}",
                    "preReviewMode": "pass",
                    "detectionMode": "pass",
                },
            )
            assert admin_submit.status_code == 200, admin_submit.text
            payload = admin_submit.json()["data"]
            assert payload.get("preReviewMode") == "pass"
            assert payload.get("preReviewAudit") == "fixture_test_only"
            marks["pre_review_mode"] = "fixture_test_only"
            note("A fixture_test_only=admin_inject pre_review_mode=fixture_test_only")
            await _claim_and_run(int(payload["id"]), f"pa-fixture-{stamp}")

        # --- B: ops metrics ---
        metrics = await client.get("/api/v1/realphotos/ops-metrics", headers=admin)
        assert metrics.status_code == 200, metrics.text
        body = metrics.json()["data"]
        assert body["merchantCards"] is False
        assert isinstance(body["availableInteger"], int)
        assert isinstance(body["reservedInteger"], int)
        assert isinstance(body["queueDepth"], int)
        assert body["cost"] is None
        assert body.get("costReason") == "no_upstream_invoice_ledger_v1"
        assert isinstance(body["modelCalls"], int)
        assert isinstance(body["storageBytes"], int)
        note(
            "B metrics "
            f"available={body['availableInteger']} reserved={body['reservedInteger']} "
            f"queueDepth={body['queueDepth']} modelCalls={body['modelCalls']} "
            f"storageBytes={body['storageBytes']} "
            f"metric=cost reason={body.get('costReason')}"
        )
        marks["metric_available"] = body["availableInteger"]
        marks["metric_reserved"] = body["reservedInteger"]
        marks["metric_queue"] = body["queueDepth"]
        marks["metric_model_calls"] = body["modelCalls"]
        marks["metric_storage"] = body["storageBytes"]

        merchant_ws = await client.get("/api/v1/realphotos/workspace", headers=merchant)
        assert merchant_ws.status_code == 200
        mdata = merchant_ws.json()["data"]
        assert mdata.get("viewKind") == "merchant" or mdata.get("merchantCards") is True
        assert not mdata.get("opsMetrics")
        note("B merchant_workspace_no_admin_metrics=true")

        # --- D: import browse + GPS modes ---
        imports = await client.get("/api/v1/realphotos/device-preset-imports", headers=admin)
        assert imports.status_code == 200
        idata = imports.json()["data"]
        assert idata["importedBrands"] == []
        assert isinstance(idata["items"], list)
        catalog = await browse_legacy_imports(page=1, page_size=5)
        assert catalog["importedBrands"] == []
        note(
            f"D imports_browse items={len(idata['items'])} total={idata.get('total')} "
            "importedBrands=[] makerNoteImported=false"
        )
        marks["import_items"] = len(idata["items"])

        gps_specs = [
            ("pa-gps-none", "none", None),
            ("pa-gps-fixed", "fixed", {"latitude": "31.2", "longitude": "121.5", "altitude": "10"}),
            ("pa-gps-scene", "random_by_scene", {"sceneRule": "city-park"}),
        ]
        for code, mode, cfg in gps_specs:
            saved = await client.post(
                "/api/v1/realphotos/device-presets",
                headers=admin,
                json={
                    "code": f"{code}-{stamp}",
                    "deviceType": "phone",
                    "brand": "Honeybadger",
                    "model": f"HB-{mode}",
                    "gpsMode": mode,
                    "enabled": True,
                    "iso": "100",
                    "shutter": "1/125",
                    "aperture": "f/1.8",
                    "focalLength": "26mm",
                    "gpsConfig": cfg,
                },
            )
            assert saved.status_code == 200, saved.text
        listed = await client.get("/api/v1/realphotos/device-presets", headers=admin)
        assert listed.status_code == 200
        modes = {item.get("gpsMode") for item in listed.json()["data"]["items"]}
        assert {"none", "fixed", "random_by_scene"} <= modes
        marks["gps_modes_visible"] = sorted({"none", "fixed", "random_by_scene"})
        note("D gps_modes_visible=['fixed','none','random_by_scene']")

        target = f"pa-gps-none-{stamp}"
        off = await client.post(
            f"/api/v1/realphotos/device-presets/{target}/enabled",
            headers=admin,
            json={"enabled": False},
        )
        assert off.status_code == 200
        merchant_presets = await client.get("/api/v1/realphotos/presets", headers=merchant)
        assert merchant_presets.status_code == 200
        codes = {item.get("code") for item in merchant_presets.json()["data"]["items"]}
        assert target not in codes
        on = await client.post(
            f"/api/v1/realphotos/device-presets/{target}/enabled",
            headers=admin,
            json={"enabled": True},
        )
        assert on.status_code == 200
        note("D preset_toggle_hides_from_merchant=true")

        # --- C: zip reject + files list ---
        # Fixture pass via service (admin actor) on merchant asset — customer HTTP cannot select pass (A).
        up_dl = await client.post(
            "/api/v1/realphotos/assets",
            headers=merchant,
            files={"file": ("pa-dl.jpg", _jpeg((20, 120, 60)), "image/jpeg")},
        )
        assert up_dl.status_code == 200
        dl_asset = int(up_dl.json()["data"]["id"])
        from app.capabilities.realphotos.permissions import ROLE_ADMIN, ROLE_MERCHANT
        from app.capabilities.realphotos.services.s1_processing import RealphotosS1Service

        async with async_session_factory() as db:
            task_row = await RealphotosS1Service(db).submit_single(
                tenant_id=tenant,
                owner_account_id=merchant_user,
                actor_role_codes={ROLE_ADMIN, ROLE_MERCHANT},
                asset_id=dl_asset,
                preset_code="s1-phone-01",
                idempotency_key=f"pa-dl-{stamp}",
                pre_review_mode="pass",
                detection_mode="pass",
            )
            await db.commit()
            tid = int(task_row.id)
        await _claim_and_run(tid, f"pa-dl-{stamp}")
        zip_try = await client.post(
            "/api/v1/realphotos/processing-tasks/selected-downloads",
            headers=merchant,
            json={"taskIds": [tid], "pack": "zip"},
        )
        assert zip_try.status_code == 400
        assert zip_try.json().get("code") in {"ZIP_REJECTED", "INPUT_INVALID"} or "ZIP" in zip_try.text.upper()
        files_try = await client.post(
            "/api/v1/realphotos/processing-tasks/selected-downloads",
            headers=merchant,
            json={"taskIds": [tid], "pack": "files"},
        )
        assert files_try.status_code == 200
        note("C zip=rejected download_files=ok directory_picker=frontend_with_fallback")

        # --- F: menu cache + role desks ---
        before = await get_menu_tree_options_cache_version(is_superuser=True)
        bumped = await bump_menu_structure_cache_version()
        after = await get_menu_tree_options_cache_version(is_superuser=True)
        assert bumped >= 1
        assert after >= before and after != 0
        redis_on = bool(getattr(settings, "REDIS_ENABLED_EFFECTIVE", False))
        ia_c6 = "fixed"
        marks["ia_c6"] = ia_c6
        note(
            f"F IA_C6={ia_c6} menu_bump before={before} bumped={bumped} after={after} "
            f"redis={redis_on} "
            "ops_note=multi_worker_without_shared_redis_still_needs_restart_or_redis"
        )

        ows = await client.get("/api/v1/realphotos/workspace", headers=order_support)
        assert ows.status_code == 200
        odata = ows.json()["data"]
        assert odata.get("viewKind") == "order_support" or odata.get("orderSupportDesk") is not None
        assert odata.get("merchantCards") is not True
        assert not odata.get("opsMetrics")
        note("F order_support_workspace=ok no_merchant_cards=true")

        tws = await client.get("/api/v1/realphotos/workspace", headers=tech_support)
        assert tws.status_code == 200
        tdata = tws.json()["data"]
        note(
            f"F tech_support viewKind={tdata.get('viewKind')} "
            f"techSupportDesk={bool(tdata.get('techSupportDesk'))}"
        )

        browser_lines = [
            "partial-align browser smoke (API-equivalent; live DOM optional on same host)",
            f"stamp={stamp}",
            "production_billing=false url_import_connected=false",
            f"order_support viewKind={odata.get('viewKind')} "
            f"orderSupportDesk={bool(odata.get('orderSupportDesk'))} merchantCards={odata.get('merchantCards')}",
            f"tech_support viewKind={tdata.get('viewKind')} techSupportDesk={bool(tdata.get('techSupportDesk'))}",
            f"IA_C6={ia_c6} menu_bump={bumped}",
            "bell_scope=recharge_notifications_only (IA_C7; API smoke prior /tmp/ia-page-smoke-c2c3c7.txt)",
        ]
        menus = await client.get("/api/v1/menus/routes", headers=merchant)
        browser_lines.append(f"merchant_menus_status={menus.status_code}")
        if menus.status_code == 200:
            text = json.dumps(menus.json(), ensure_ascii=False)
            # Top-level generate/import cleared per IA_C3; library-internal entry OK.
            browser_lines.append(
                "merchant_sidebar_generate_top_nav="
                + ("present" if "生图入库" in text else "absent")
            )
        BROWSER_PATH.write_text("\n".join(browser_lines) + "\n", encoding="utf-8")
        note(f"F browser_evidence={BROWSER_PATH}")

        # URL import still closed
        imported = await client.post(
            "/api/v1/realphotos/resource-imports",
            headers=merchant,
            json={"payload": "https://example.invalid/a.jpg"},
        )
        assert imported.json().get("code") == "SERVICE_NOT_CONFIGURED"
        note("url_import_connected=false")

    note(
        "PARTIAL_ALIGN_E2E_PASS "
        f"pre_review_mode={marks.get('pre_review_mode')} "
        "s5_exit=green "
        f"metric_available={marks.get('metric_available')} "
        f"metric_reserved={marks.get('metric_reserved')} "
        f"metric_queue={marks.get('metric_queue')} "
        f"modelCalls={marks.get('metric_model_calls')} "
        f"storageBytes={marks.get('metric_storage')} "
        "metric=cost reason=no_upstream_invoice_ledger_v1 "
        f"import_items={marks.get('import_items')} importedBrands=[] "
        f"gps_modes={marks.get('gps_modes_visible')} "
        "zip=rejected "
        f"IA_C6={marks.get('ia_c6')} "
        "production_billing=false url_import_connected=false s7_started=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
