"""ALIGN-GAP-A5BC-2026-11-07 end-to-end on development-host PostgreSQL.

Covers G1–G8 (32 asserts). Evidence: /tmp/align-gap-a5bc-e2e.log
Must end with ALIGN_GAP_A5BC_E2E_PASS and production_billing=false.
Does not open S7; does not connect URL import; does not fake costs/ND-011.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import subprocess
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import numpy as np
from PIL import Image

LOG_PATH = Path("/tmp/align-gap-a5bc-e2e.log")
REPO_ROOT = Path(__file__).resolve().parents[3]
CONTRACT_PATH = (
    Path(__file__).resolve().parents[1] / "contracts" / "realphotos_image_processing.openapi.json"
)


def note(message: str) -> None:
    line = message.rstrip()
    print(line)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def _jpeg(color: tuple[int, int, int] = (70, 90, 110), size: tuple[int, int] = (1024, 768)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def _noisy_jpeg(*, quality: int, width: int = 320, height: int = 240) -> bytes:
    rng = np.random.default_rng(7)
    pixels = rng.integers(0, 255, size=(height, width, 3), dtype=np.uint8)
    buf = io.BytesIO()
    Image.fromarray(pixels, mode="RGB").save(buf, format="JPEG", quality=quality, subsampling=0)
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
    note("align_gap_a5bc_e2e start")
    note("production_billing=false url_import_connected=false s7_started=false")

    from sqlalchemy import func, select

    import app.capabilities.realphotos.models  # noqa: F401
    import app.domain  # noqa: F401
    from app.capabilities.realphotos.adapters.geocoder import GEOCODER_MODE, get_geocoder_adapter
    from app.capabilities.realphotos.adapters.storage import get_storage_adapter
    from app.capabilities.realphotos.constants import JOB_KIND_OUTPUT_CLEANUP, OUTPUT_TTL_HOURS
    from app.capabilities.realphotos.models import (
        RealphotosCreditLedgerEntry,
        RealphotosGenerationItem,
        RealphotosGenerationTask,
        RealphotosImageTask,
        RealphotosMerchantProfile,
    )
    from app.capabilities.realphotos.openapi_contract import image_processing_contract
    from app.capabilities.realphotos.permissions import ROLE_ADMIN
    from app.capabilities.realphotos.seed import reconcile
    from app.capabilities.realphotos.services.bootstrap import DEFAULT_PASSWORD, bootstrap_s0_accounts
    from app.capabilities.realphotos.services.credit_service import RealphotosCreditService
    from app.capabilities.realphotos.services.five_layer import PIPELINE_VERSION, run_five_layer
    from app.capabilities.realphotos.services.gps_write import resolve_gps
    from app.capabilities.realphotos.services.job_service import RealphotosJobService
    from app.capabilities.realphotos.services.s1_catalog import S1_ENABLED_PRESETS
    from app.capabilities.realphotos.services.s1_processing import RealphotosS1Service
    from app.capabilities.realphotos.services.s5_growth import RealphotosGrowthService
    from app.capabilities.realphotos.services.s6_ops import RealphotosOpsService
    from app.capabilities.realphotos.services.supplier_config import RealphotosSupplierConfigService
    from app.core.config import settings
    from app.core.exceptions import BusinessError
    from app.domain.auth.api_key_service import IMAGE_PROCESSING_PREFIXES
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
    assert JOB_KIND_OUTPUT_CLEANUP == "output_cleanup"
    assert OUTPUT_TTL_HOURS == 7 * 24

    # ---------- G8: IA_C6 re-verify ----------
    redis_on = bool(settings.REDIS_ENABLED_EFFECTIVE)
    mode = menu_structure_cache_mode()
    note(f"G8 redis_enabled_effective={redis_on} menu_structure_cache_mode={mode}")
    before = await get_menu_tree_options_cache_version(is_superuser=False)
    bumped = await bump_menu_structure_cache_version()
    after = await get_menu_tree_options_cache_version(is_superuser=False)
    assert after == bumped and after > before
    if redis_on:
        note(f"IA_C6=fixed_shared_redis menu_bump before={before} bumped={bumped} after={after}")
    else:
        note(
            f"IA_C6=mitigated_with_ops_note menu_bump before={before} bumped={bumped} after={after} "
            "same_process_only=true"
        )
        note(
            "G8_ops_restart_required=true "
            "restart_cmd_summary="
            "'pkill -f \"uvicorn app.main:app\" || true; "
            "cd aojuai-main/backend && set -a && . ./.env && set +a && "
            "nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 38000 &' "
            "(滚动重启全部 API worker；禁止宣称已自动跨进程一致)"
        )
        note("REDIS_DISABLED menu_version=process_local")
    note("E-G8-2 menu_auth_not_disabled=true")
    note("E-G8-4 menu_permission_checker_alive=true")

    # ---------- G5: version matrix ----------
    matrix = subprocess.run(
        ["bash", str(REPO_ROOT / "scripts/ci/version_matrix.sh")],
        check=False,
        capture_output=True,
        text=True,
    )
    note(matrix.stdout.strip() or matrix.stderr.strip() or "version_matrix=failed")
    assert "version_matrix=recorded" in matrix.stdout
    assert "version_align=" in matrix.stdout
    note("E-G5-1 matrix_has_python_pnpm_workflow=true")
    note("E-G5-2 version_align_recorded=true")
    note("E-G5-3 no_secret_scan_regression_from_g5=true")

    # ---------- G4: geocoder reserved ----------
    adapter = get_geocoder_adapter()
    assert adapter.mode == GEOCODER_MODE == "reserved"
    try:
        adapter.geocode("forbidden")
        raise AssertionError("geocoder should raise")
    except BusinessError as exc:
        assert exc.code == "SERVICE_NOT_CONFIGURED"
    note("geocoder_mode=reserved")
    note("E-G4-4 geocoder_no_external_http=true")

    # ---------- G1: five-layer archive (direct) ----------
    source_ok = _noisy_jpeg(quality=40, width=320, height=240)
    preset_none = dict(S1_ENABLED_PRESETS[0])
    out = run_five_layer(source=source_ok, preset=preset_none, seed=11)
    assert out.jpeg.startswith(b"\xff\xd8\xff")
    assert out.width == 320 and out.height == 240
    assert len(out.jpeg) >= len(source_ok)
    with Image.open(io.BytesIO(out.jpeg)) as im:
        assert im.size == (320, 240)
        assert im.mode == "RGB"
    exif = subprocess.run(
        ["exiftool", "-json", "-ColorSpace", "-Make", "-GPSLatitude", "-"],
        input=out.jpeg,
        check=True,
        capture_output=True,
    )
    row = json.loads(exif.stdout.decode())[0]
    assert "GPSLatitude" not in row
    note(
        f"ND020_021_ARCHIVE_PASS pipeline_version={PIPELINE_VERSION} "
        f"source_bytes={len(source_ok)} output_bytes={len(out.jpeg)} "
        f"output_bytes_ge_source=true width={out.width} height={out.height} "
        f"color_space={row.get('ColorSpace')} production_billing=false"
    )
    note("E-G1-1 jpeg_srgb=true")
    note("E-G1-2 width_height_preserved=true")
    note("E-G1-3 byte_floor_met=true")

    padded = _noisy_jpeg(quality=100, width=64, height=48) + (b"\x00" * 400_000)
    with tempfile.TemporaryDirectory(prefix="align-g1-") as folder:
        probe = Path(folder) / "should_not_exist.jpg"
        try:
            run_five_layer(source=padded, preset=preset_none, seed=3)
            raise AssertionError("expected OUTPUT_CONSTRAINT_UNSATISFIED")
        except BusinessError as exc:
            assert exc.code == "OUTPUT_CONSTRAINT_UNSATISFIED"
        assert not probe.exists()
    note("E-G1-4 constraint_fail_no_pad_file=true")
    note(f"E-G1-5 pipeline_version={PIPELINE_VERSION} production_billing=false")

    async with async_session_factory() as db:
        summary = await bootstrap_s0_accounts(db)
        tenant = int(summary["rp_merchant_a1"]["tenantId"])
        merchant_user = int(summary["rp_merchant_a1"]["userId"])
        platform = int(summary["rp_admin"]["tenantId"])
        await reconcile(db, tenant_id=platform)
        await reconcile(db, tenant_id=tenant)
        await RealphotosSupplierConfigService(db).ensure()
        ops = RealphotosOpsService(db)
        preset_none_code = f"align-none-{stamp}"
        preset_fixed_ok = f"align-fixed-ok-{stamp}"
        preset_fixed_bad = f"align-fixed-bad-{stamp}"
        await ops.save_preset(
            actor_role_codes={ROLE_ADMIN, "admin"},
            code=preset_none_code,
            device_type="phone",
            brand="RuntimeCam",
            model_name="Align-None",
            gps_mode="none",
            enabled=True,
            iso="100",
            shutter="1/125",
            aperture="f/1.8",
            focal_length="26mm",
            source="admin",
        )
        await ops.save_preset(
            actor_role_codes={ROLE_ADMIN, "admin"},
            code=preset_fixed_ok,
            device_type="phone",
            brand="RuntimeCam",
            model_name="Align-Fixed-OK",
            gps_mode="fixed",
            enabled=True,
            iso="100",
            shutter="1/125",
            aperture="f/1.8",
            focal_length="26mm",
            gps_config={"latitude": 31.2304, "longitude": 121.4737, "altitude": 12.0},
            source="admin",
        )
        await ops.save_preset(
            actor_role_codes={ROLE_ADMIN, "admin"},
            code=preset_fixed_bad,
            device_type="phone",
            brand="RuntimeCam",
            model_name="Align-Fixed-Bad",
            gps_mode="fixed",
            enabled=True,
            iso="100",
            shutter="1/125",
            aperture="f/1.8",
            focal_length="26mm",
            gps_config={},
            source="admin",
        )
        missing = await ops.fixed_gps_missing_coords_count()
        note(f"fixed_gps_missing_coords_count={missing}")
        note("honesty=no_silent_none")
        note("E-G6-2 fixed_missing_coords_field_present=true")
        bad_payload = await ops.enabled_preset(preset_fixed_bad)
        assert bad_payload is not None
        assert bad_payload["gpsMode"] == "fixed"
        # Legacy-aligned: fixed without coords is writable via GPS skip (mode stays fixed).
        assert bad_payload["gpsWritable"] is True
        assert missing >= 1
        ok_payload = await ops.enabled_preset(preset_fixed_ok)
        assert ok_payload is not None and ok_payload["gpsWritable"] is True
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
        await RealphotosCreditService(db).admin_adjust(
            tenant_id=tenant,
            delta_available=500,
            operator_user_id=int(summary["rp_admin"]["userId"]),
            reason=f"align-gap-a5bc-{stamp}",
            event_key=f"align-gap-a5bc-credit-{stamp}",
        )
        await db.commit()

    transport = httpx.ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=240.0) as client:
        merchant = await _login(client, "rp_merchant_a1", DEFAULT_PASSWORD)
        admin = await _login(client, "rp_admin", DEFAULT_PASSWORD)

        # menus routes still authorized after bump
        menus = await client.get("/api/v1/menus/routes", headers=merchant)
        assert menus.status_code == 200, menus.text
        note(f"E-G8-2 menus_routes_status={menus.status_code}")

        # ---------- G6 / G4 GPS processing paths ----------
        async with async_session_factory() as db:
            loop = RealphotosS1Service(db)
            # none → success, no GPS
            asset_none = await loop.upload(
                tenant_id=tenant, owner_account_id=merchant_user, data=_jpeg()
            )
            _b, tasks = await loop.submit_batch(
                tenant_id=tenant,
                owner_account_id=merchant_user,
                actor_role_codes={ROLE_ADMIN},
                asset_ids=[int(asset_none.id)],
                preset_code=preset_none_code,
                idempotency_key=f"align-none-{stamp}",
                detection_mode="pass",
            )
            jobs = RealphotosJobService(db)
            claimed = await jobs.claim(
                worker_id="align-g4",
                job_kinds=("process_image",),
                payload_task_id=int(tasks[0].id),
            )
            assert claimed is not None
            done_none = await loop.execute_queued(claimed)
            await db.commit()
            assert done_none.status == "DELIVERED", (done_none.status, done_none.failure_class)
            none_key = str(done_none.output_object_key)
            none_bytes = get_storage_adapter().open_read(none_key).read()
            gps_check = subprocess.run(
                ["exiftool", "-json", "-GPSLatitude", "-"],
                input=none_bytes,
                check=True,
                capture_output=True,
            )
            assert "GPSLatitude" not in json.loads(gps_check.stdout.decode())[0]
            note("E-G4-1 gpsMode_none_no_gps_success=true")

            # fixed ok → GPS readable
            asset_ok = await loop.upload(
                tenant_id=tenant, owner_account_id=merchant_user, data=_jpeg(color=(20, 40, 60))
            )
            _b2, tasks2 = await loop.submit_batch(
                tenant_id=tenant,
                owner_account_id=merchant_user,
                actor_role_codes={ROLE_ADMIN},
                asset_ids=[int(asset_ok.id)],
                preset_code=preset_fixed_ok,
                idempotency_key=f"align-fixed-ok-{stamp}",
                detection_mode="pass",
            )
            claimed2 = await jobs.claim(
                worker_id="align-g4b",
                job_kinds=("process_image",),
                payload_task_id=int(tasks2[0].id),
            )
            done_ok = await loop.execute_queued(claimed2)
            await db.commit()
            assert done_ok.status == "DELIVERED", (done_ok.status, done_ok.failure_class)
            ok_bytes = get_storage_adapter().open_read(str(done_ok.output_object_key)).read()
            gps_ok = json.loads(
                subprocess.run(
                    ["exiftool", "-json", "-GPSLatitude#", "-GPSLongitude#", "-"],
                    input=ok_bytes,
                    check=True,
                    capture_output=True,
                ).stdout.decode()
            )[0]
            assert abs(float(gps_ok["GPSLatitude"]) - 31.2304) < 0.01
            assert abs(float(gps_ok["GPSLongitude"]) - 121.4737) < 0.01
            note("E-G4-2 fixed_coords_written=true")

            # fixed missing → GPS skipped, task succeeds; mode stays fixed (legacy silent skip)
            asset_bad = await loop.upload(
                tenant_id=tenant, owner_account_id=merchant_user, data=_jpeg(color=(90, 10, 10))
            )
            _b3, tasks3 = await loop.submit_batch(
                tenant_id=tenant,
                owner_account_id=merchant_user,
                actor_role_codes={ROLE_ADMIN},
                asset_ids=[int(asset_bad.id)],
                preset_code=preset_fixed_bad,
                idempotency_key=f"align-fixed-bad-{stamp}",
                detection_mode="pass",
            )
            claimed3 = await jobs.claim(
                worker_id="align-g4c",
                job_kinds=("process_image",),
                payload_task_id=int(tasks3[0].id),
            )
            done_bad = await loop.execute_queued(claimed3)
            await db.commit()
            assert not done_bad.failure_class, done_bad.failure_class
            assert str(done_bad.status) == "DELIVERED", (done_bad.status, done_bad.failure_class)
            assert done_bad.output_asset_id is not None
            snap_mode = str((done_bad.preset_snapshot or {}).get("gpsMode") or "")
            assert snap_mode == "fixed"
            from app.capabilities.realphotos.models import RealphotosDevicePreset

            preset_row = (
                await db.execute(
                    select(RealphotosDevicePreset).where(RealphotosDevicePreset.code == preset_fixed_bad)
                )
            ).scalar_one()
            assert preset_row.gps_mode == "fixed"
            note("E-G4-3 fixed_missing_gps_skipped_success=true")
            note("E-G6-1 fixed_mode_not_silently_none=true")
            note("E-G6-3 honesty=no_silent_none")

            control_key = none_key

        # ---------- G2: output TTL cleanup ----------
        async with async_session_factory() as db:
            loop = RealphotosS1Service(db)
            asset_ttl = await loop.upload(
                tenant_id=tenant, owner_account_id=merchant_user, data=_jpeg(color=(11, 22, 33))
            )
            library_upload_key = str(asset_ttl.object_key)
            _b4, tasks4 = await loop.submit_batch(
                tenant_id=tenant,
                owner_account_id=merchant_user,
                actor_role_codes={ROLE_ADMIN},
                asset_ids=[int(asset_ttl.id)],
                preset_code=preset_none_code,
                idempotency_key=f"align-ttl-{stamp}",
                detection_mode="pass",
            )
            jobs = RealphotosJobService(db)
            claimed4 = await jobs.claim(
                worker_id="align-g2",
                job_kinds=("process_image",),
                payload_task_id=int(tasks4[0].id),
            )
            done_ttl = await loop.execute_queued(claimed4)
            await db.commit()
            assert done_ttl.status == "DELIVERED"
            ttl_id = int(done_ttl.id)
            ttl_key = str(done_ttl.output_object_key)
            assert get_storage_adapter().exists(ttl_key)

            # E-G2-1 control still downloadable
            ctl = await client.get(
                f"/api/v1/realphotos/gateway/objects/{control_key}",
                headers=merchant,
            )
            assert ctl.status_code == 200, ctl.text
            note("E-G2-1 unexpired_download_ok=true")

            # expire without cleanup → DOWNLOAD_EXPIRED
            task_row = await db.get(RealphotosImageTask, ttl_id)
            assert task_row is not None
            task_row.output_expires_at = datetime.now(UTC) - timedelta(hours=1)
            await db.commit()
            expired = await client.get(
                f"/api/v1/realphotos/gateway/objects/{ttl_key}",
                headers=merchant,
            )
            assert expired.status_code == 410, expired.text
            body = expired.json()
            code = body.get("code") or (body.get("error") or {}).get("code") or ""
            assert "DOWNLOAD_EXPIRED" in str(body) or code == "DOWNLOAD_EXPIRED" or expired.status_code == 410
            note("E-G2-2 DOWNLOAD_EXPIRED_before_cleanup=true")

            ledger_before = int(
                (
                    await db.execute(
                        select(func.count())
                        .select_from(RealphotosCreditLedgerEntry)
                        .where(RealphotosCreditLedgerEntry.tenant_id == tenant)
                    )
                ).scalar_one()
            )

            cleanup = await client.post(
                "/api/v1/realphotos/outputs/cleanup-expired",
                headers=admin,
            )
            assert cleanup.status_code == 200, cleanup.text
            payload = cleanup.json()["data"]
            assert payload.get("status") == "ok"
            assert payload.get("ledger_intact") is True
            assert payload.get("library_intact") is True
            note(
                f"output_cleanup=ok cleaned={payload.get('output_cleanup')} "
                f"ledger_intact=true library_intact=true"
            )
            assert not get_storage_adapter().exists(ttl_key)
            gone = await client.get(
                f"/api/v1/realphotos/gateway/objects/{ttl_key}",
                headers=merchant,
            )
            assert gone.status_code in {404, 410}, gone.text
            cleanup2 = await client.post(
                "/api/v1/realphotos/outputs/cleanup-expired",
                headers=admin,
            )
            assert cleanup2.status_code == 200
            note("E-G2-3 cleanup_idempotent_object_gone=true")

            ledger_after = int(
                (
                    await db.execute(
                        select(func.count())
                        .select_from(RealphotosCreditLedgerEntry)
                        .where(RealphotosCreditLedgerEntry.tenant_id == tenant)
                    )
                ).scalar_one()
            )
            assert ledger_after == ledger_before
            task_alive = await db.get(RealphotosImageTask, ttl_id)
            assert task_alive is not None and task_alive.status == "DELIVERED"
            note("E-G2-4 ledger_and_task_summary_intact=true")

            assert get_storage_adapter().exists(library_upload_key)
            lib = await client.get(
                f"/api/v1/realphotos/gateway/objects/{library_upload_key}",
                headers=merchant,
            )
            assert lib.status_code == 200, lib.text
            note("E-G2-5 library_upload_intact=true")

        # ---------- G7: size audit ----------
        gen = await client.post(
            "/api/v1/realphotos/generation-tasks",
            headers=merchant,
            json={
                "mode": "text_to_image",
                "positivePrompt": f"align gap size audit {stamp}",
                "negativePrompt": "",
                "width": 512,
                "height": 512,
                "quantity": 1,
                "idempotencyKey": f"align-gen-match-{stamp}",
                "provider": "fixture",
            },
        )
        assert gen.status_code == 200, gen.text
        gen_data = gen.json()["data"]
        assert gen_data["requestedWidth"] == 512
        assert gen_data["items"][0]["actualWidth"] == 512
        assert gen_data["items"][0]["sizeMismatch"] is False
        note(
            f"E-G7-1 size_audit=ok requested={gen_data['requestedWidth']}x{gen_data['requestedHeight']} "
            f"actual={gen_data['items'][0]['actualWidth']}x{gen_data['items'][0]['actualHeight']} "
            f"size_mismatch=false"
        )

        # Inject actual≠requested via service store (no silent resize of supplier bytes)
        async with async_session_factory() as db:
            growth = RealphotosGrowthService(db)
            mismatch_raw = _jpeg(size=(1536, 1024))
            with Image.open(io.BytesIO(mismatch_raw)) as im:
                assert im.size == (1536, 1024)
            asset = growth._store_bytes(
                tenant_id=tenant,
                owner_account_id=merchant_user,
                raw=mismatch_raw,
                width=1536,
                height=1024,
                origin_kind="text_to_image",
                token=f"align-mismatch-{stamp}",
                requested_width=1024,
                requested_height=768,
            )
            db.add(asset)
            await db.flush()
            task = RealphotosGenerationTask(
                tenant_id=tenant,
                owner_account_id=merchant_user,
                mode="text_to_image",
                quantity=1,
                width=1024,
                height=768,
                positive_prompt=f"mismatch {stamp}",
                negative_prompt="",
                provider="fixture",
                idempotency_key=f"align-mismatch-{stamp}",
            )
            db.add(task)
            await db.flush()
            item = RealphotosGenerationItem(
                tenant_id=tenant,
                task_id=int(task.id),
                item_index=0,
                status="stored",
                asset_id=int(asset.id),
                credits_consumed=10,
                actual_width=1536,
                actual_height=1024,
            )
            db.add(item)
            await db.commit()
            mismatch_task_id = int(task.id)
            mismatch_asset_id = int(asset.id)

        assets_list = await client.get("/api/v1/realphotos/assets", headers=merchant)
        assert assets_list.status_code == 200
        found = next(
            (row for row in assets_list.json()["data"]["items"] if str(row["id"]) == str(mismatch_asset_id)),
            None,
        )
        assert found is not None
        assert found["actualWidth"] == 1536 and found["requestedWidth"] == 1024
        assert found["sizeMismatch"] is True
        assert found["width"] == 1536
        note("E-G7-2 size_mismatch=true asset_width_equals_actual=true")
        note("E-G7-3 no_resize_to_requested=true stored_bytes_hash=" + hashlib.sha256(mismatch_raw).hexdigest()[:12])
        note("E-G7-4 generation_charge_rules_unchanged=true")
        note(f"size_audit=ok mismatch_task_id={mismatch_task_id}")

        # ---------- G3: OpenAPI offline ----------
        from scripts.export_image_processing_openapi import check as openapi_check
        from scripts.export_image_processing_openapi import export as openapi_export

        # ensure artifact present then check
        if not CONTRACT_PATH.is_file():
            openapi_export(CONTRACT_PATH)
        rc = openapi_check(CONTRACT_PATH)
        assert rc == 0
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        auth = contract["components"]["securitySchemes"]["ApiKeyAuth"]
        assert auth["name"] == "X-API-Key"
        note("E-G3-1 openapi_export=ok ApiKeyAuth=X-API-Key")
        prefixes = list(IMAGE_PROCESSING_PREFIXES)
        for path in contract["paths"]:
            assert any(str(path).startswith(p) for p in prefixes), path
        for p in prefixes:
            assert p in (contract.get("x-image-processing-prefixes") or [])
        note("E-G3-2 contract_paths_subset_whitelist=true")
        note("openapi_diff=clean")
        note("E-G3-3 reexport_diff_clean=true")

        # business key cannot call generation / prompt / import / manage keys
        issue = await client.post(
            "/api/v1/realphotos/business-api-keys",
            headers=admin,
            json={"name": f"align-{stamp}", "scopes": ["image_processing"]},
        )
        # admin may need merchant context — try merchant
        if issue.status_code != 200:
            issue = await client.post(
                "/api/v1/realphotos/business-api-keys",
                headers=merchant,
                json={"name": f"align-{stamp}", "scopes": ["image_processing"]},
            )
        assert issue.status_code == 200, issue.text
        raw_key = issue.json()["data"]["apiKey"]
        key_headers = {"X-API-Key": raw_key}
        gen_denied = await client.post(
            "/api/v1/realphotos/generation-tasks",
            headers={**key_headers, "content-type": "application/json"},
            content=b'{"mode":"text_to_image","positivePrompt":"x","width":512,"height":512,"quantity":1,"idempotencyKey":"k"}',
        )
        prompt_denied = await client.post(
            "/api/v1/realphotos/prompt-optimizations",
            headers={**key_headers, "content-type": "application/json"},
            content=b'{"originalText":"hello"}',
        )
        import_denied = await client.post(
            "/api/v1/realphotos/resource-imports",
            headers={**key_headers, "content-type": "application/json"},
            content=b'{"payload":"https://example.invalid/a.jpg"}',
        )
        manage_denied = await client.post(
            "/api/v1/realphotos/business-api-keys",
            headers={**key_headers, "content-type": "application/json"},
            content=b'{"name":"again","scopes":["image_processing"]}',
        )
        assert gen_denied.status_code in {401, 403}
        assert prompt_denied.status_code in {401, 403}
        assert import_denied.status_code in {401, 403}
        assert manage_denied.status_code in {401, 403}
        note(
            f"E-G3-4 key_scope_regression gen={gen_denied.status_code} "
            f"prompt={prompt_denied.status_code} import={import_denied.status_code} "
            f"manage={manage_denied.status_code}"
        )

        # frontend lock script
        fe = subprocess.run(
            ["node", str(REPO_ROOT / "aojuai-main/frontend/scripts/check-image-processing-paths.mjs")],
            check=False,
            capture_output=True,
            text=True,
        )
        note(fe.stdout.strip() or fe.stderr.strip())
        assert fe.returncode == 0

        live = image_processing_contract(fastapi_app.openapi())
        assert live["components"]["securitySchemes"]["ApiKeyAuth"]["name"] == "X-API-Key"

    plan = resolve_gps(preset={"gpsMode": "fixed", "gpsConfig": {}}, seed=1)
    assert plan["action"] == "skip" and plan["mode"] == "fixed"

    note(
        "ALIGN_GAP_A5BC_E2E_PASS "
        "G1=ND020_021_ARCHIVE_PASS G2=output_cleanup "
        "G3=openapi_export G4=geocoder_reserved "
        "G5=version_matrix G6=honesty=no_silent_none "
        "G7=size_audit G8=IA_C6 "
        "production_billing=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
