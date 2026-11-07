"""BLOCKING-FIX-2026-11-07 end-to-end on development-host PostgreSQL.

Covers A–G success + key reject paths. Keeps production_billing=false.
Does not enable URL import or open S7.
"""

from __future__ import annotations

import asyncio
import io
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
from PIL import Image
from sqlalchemy import func, select

LOG_PATH = Path("/tmp/blocking-fix-e2e.log")


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
    assert logged_in.status_code == 200
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
    note("blocking_fix_e2e start")
    note("production_billing=false s7_started=false url_import_connected=false")

    import app.capabilities.realphotos.models  # noqa: F401
    import app.domain  # noqa: F401
    from app.capabilities.realphotos.models import (
        RealphotosAsset,
        RealphotosCreditLedgerEntry,
        RealphotosCreditReservation,
    )
    from app.capabilities.realphotos.permissions import ROLE_ADMIN
    from app.capabilities.realphotos.seed import reconcile
    from app.capabilities.realphotos.services.bootstrap import DEFAULT_PASSWORD, bootstrap_s0_accounts
    from app.capabilities.realphotos.services.credit_service import RealphotosCreditService
    from app.capabilities.realphotos.services.s6_ops import RealphotosOpsService
    from app.capabilities.realphotos.services.supplier_config import RealphotosSupplierConfigService
    from app.capabilities.realphotos.services.supplier_material import supplier_live_enabled
    from app.core.config import settings
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
        summary = await bootstrap_s0_accounts(db)
        tenant = int(summary["rp_merchant_a1"]["tenantId"])
        platform = int(summary["rp_admin"]["tenantId"])
        await reconcile(db, tenant_id=platform)
        await reconcile(db, tenant_id=tenant)
        await RealphotosSupplierConfigService(db).ensure()
        await db.commit()
        credits = RealphotosCreditService(db)
        wallet_before = await credits.get_wallet(tenant_id=tenant)

    note(f"gemini_settings_model={settings.GEMINI_MODEL}")
    note(f"supplier_live_enabled={supplier_live_enabled()}")
    note(
        f"wallet_before available={wallet_before['availableInteger']} reserved={wallet_before['reservedInteger']}"
    )

    transport = httpx.ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=180.0) as client:
        merchant = await _login(client, "rp_merchant_a1", DEFAULT_PASSWORD)
        admin = await _login(client, "rp_admin", DEFAULT_PASSWORD)
        support = await _login(client, "rp_order_support", DEFAULT_PASSWORD)

        # G — final_detection contract modelId
        contracts = await client.get("/api/v1/realphotos/provider-contracts", headers=admin)
        assert contracts.status_code == 200
        items = (contracts.json().get("data") or {}).get("items") or []
        final = next((row for row in items if row.get("duty") == "final_detection"), None)
        note(f"G_contract final_detection={json.dumps(final, ensure_ascii=False) if final else None}")
        assert final is not None
        assert final.get("modelId") == str(settings.GEMINI_MODEL)
        assert final.get("modelId") != "gemini-2.5-pro"

        # C — filename composition
        upload_meta = await client.post(
            "/api/v1/realphotos/assets",
            headers=merchant,
            files={"file": ("c.jpg", _jpeg((10, 20, 30)), "image/jpeg")},
            data={
                "name": "杯",
                "seller": "店A",
                "sku": f"SKU-{stamp}",
                "asn": "ASN1",
                "price": "12",
                "website": "shop.example",
                "url": "https://shop.example/p/1",
            },
        )
        assert upload_meta.status_code == 200
        upload_plain = await client.post(
            "/api/v1/realphotos/assets",
            headers=merchant,
            files={"file": ("plain.jpg", _jpeg((11, 22, 33)), "image/jpeg")},
        )
        assert upload_plain.status_code == 200
        listed = await client.get("/api/v1/realphotos/assets", headers=merchant)
        assert listed.status_code == 200
        assets = (listed.json().get("data") or {}).get("items") or []
        named = next(row for row in assets if row["id"] == upload_meta.json()["data"]["id"])
        plain = next(row for row in assets if row["id"] == upload_plain.json()["data"]["id"])
        note(f"C_named displayName={named.get('displayName')} degraded={named.get('degraded')}")
        note(f"C_plain displayName={plain.get('displayName')} degraded={plain.get('degraded')}")
        assert named["displayName"].startswith("杯_店A_")
        assert named["degraded"] is False
        assert plain["degraded"] is True

        # URL import still unconfigured
        imported = await client.post(
            "/api/v1/realphotos/resource-imports",
            headers=merchant,
            json={"payload": "https://example.invalid/a.jpg"},
        )
        note(f"C_url_import status={imported.status_code} code={imported.json().get('code')}")
        assert imported.json().get("code") == "SERVICE_NOT_CONFIGURED"

        # B — GPS presets + processing
        async with async_session_factory() as db:
            ops = RealphotosOpsService(db)
            fixed = await ops.save_preset(
                actor_role_codes={ROLE_ADMIN, "admin"},
                code=f"bf-fixed-{stamp}",
                device_type="phone",
                brand="Honeybadger",
                model_name="HB-Fixed",
                gps_mode="fixed",
                enabled=True,
                iso="100",
                shutter="1/100",
                aperture="f/2.8",
                focal_length="28 mm",
                gps_config={"latitude": "31.2304", "longitude": "121.4737", "altitude": "12"},
            )
            random_p = await ops.save_preset(
                actor_role_codes={ROLE_ADMIN, "admin"},
                code=f"bf-rand-{stamp}",
                device_type="phone",
                brand="Honeybadger",
                model_name="HB-Rand",
                gps_mode="random_by_scene",
                enabled=True,
                iso="200",
                shutter="1/200",
                aperture="f/2.0",
                focal_length="35 mm",
                gps_config={"sceneRule": "urban"},
            )
            none_p = await ops.save_preset(
                actor_role_codes={ROLE_ADMIN, "admin"},
                code=f"bf-none-{stamp}",
                device_type="phone",
                brand="Honeybadger",
                model_name="HB-None",
                gps_mode="none",
                enabled=True,
                iso="100",
                shutter="1/60",
                aperture="f/2.2",
                focal_length="24 mm",
            )
            await db.commit()
            note(
                f"B_presets fixed_write={fixed.get('gpsWriteConnected')} "
                f"rand_write={random_p.get('gpsWriteConnected')} none={none_p.get('code')}"
            )

        asset_id = int(upload_plain.json()["data"]["id"])
        for label, code in (("fixed", fixed["code"]), ("random", random_p["code"]), ("none", none_p["code"])):
            submitted = await client.post(
                "/api/v1/realphotos/processing-batches",
                headers=merchant,
                json={
                    "assetIds": [asset_id],
                    "presetCode": code,
                    "idempotencyKey": f"bf-gps-{label}-{stamp}",
                    "detectionMode": "pass",
                    "preReviewMode": "pass",
                },
            )
            assert submitted.status_code == 200, submitted.text
            task_id = int((((submitted.json().get("data") or {}).get("tasks") or [{}])[0]).get("id"))
            done = await _claim_and_run(task_id, f"bf-gps-{label}")
            detail = await client.get(f"/api/v1/realphotos/processing-tasks/{task_id}", headers=merchant)
            gps = (detail.json().get("data") or {}).get("gpsWrite")
            note(
                f"B_{label} status={done.status} gpsWrite={json.dumps(gps, ensure_ascii=False)} "
                f"failure={done.failure_class}"
            )
            assert done.status == "DELIVERED"
            if label == "none":
                assert gps and gps.get("written") is False
            else:
                assert gps and gps.get("written") is True and gps.get("actualGps")

        # D — seed unsupported reject; E — requested/actual honesty on fixture-free live or fixture
        seed_reject = await client.post(
            "/api/v1/realphotos/generation-tasks",
            headers=merchant,
            json={
                "mode": "text_to_image",
                "positivePrompt": "seed reject probe",
                "width": 512,
                "height": 512,
                "quantity": 1,
                "idempotencyKey": f"bf-seed-{stamp}",
                "provider": "fixture",
                "seed": "12345",
            },
        )
        note(f"D_seed_reject status={seed_reject.status_code} code={seed_reject.json().get('code')}")
        assert seed_reject.json().get("code") == "SEED_UNSUPPORTED"

        fixture_gen = await client.post(
            "/api/v1/realphotos/generation-tasks",
            headers=merchant,
            json={
                "mode": "text_to_image",
                "positivePrompt": "size honesty",
                "width": 512,
                "height": 384,
                "quantity": 1,
                "idempotencyKey": f"bf-size-{stamp}",
                "provider": "fixture",
            },
        )
        assert fixture_gen.status_code == 200
        gen_data = fixture_gen.json()["data"]
        note(
            f"E_fixture requested={gen_data.get('requestedWidth')}x{gen_data.get('requestedHeight')} "
            f"items={gen_data.get('items')}"
        )
        assert gen_data["requestedWidth"] == 512
        assert gen_data["items"][0]["actualWidth"] == 512

        # F — image_to_image live path when supplier live; reject path must not debit.
        f_live_stored = False
        if supplier_live_enabled():
            # Reject path first (solid color often rejected): no debit / no store.
            rejected = await client.post(
                "/api/v1/realphotos/generation-tasks",
                headers=merchant,
                data={
                    "mode": "image_to_image",
                    "positivePrompt": "保持主体，浅灰背景",
                    "width": "1024",
                    "height": "768",
                    "quantity": "1",
                    "idempotencyKey": f"bf-i2i-reject-{stamp}",
                },
                files={"reference": ("ref.jpg", _jpeg((90, 90, 90)), "image/jpeg")},
            )
            reject_body = rejected.json()
            note(
                f"F_i2i_reject status={rejected.status_code} code={reject_body.get('code')} "
                f"message={reject_body.get('message')}"
            )
            assert reject_body.get("code") in {
                "PRE_REVIEW_REJECTED",
                "PRE_REVIEW_FAILED",
                "SUPPLIER_FAILED",
            }

            # Success path: use a live text-to-image result as reference asset.
            live_text = await client.post(
                "/api/v1/realphotos/generation-tasks",
                headers=merchant,
                json={
                    "mode": "text_to_image",
                    "positivePrompt": "一张木桌上的白瓷杯，自然光，浅景深",
                    "width": 1024,
                    "height": 768,
                    "quantity": 1,
                    "idempotencyKey": f"bf-i2i-refsrc-{stamp}",
                },
            )
            note(f"F_ref_source status={live_text.status_code} code={live_text.json().get('code')}")
            if live_text.status_code == 200:
                ref_items = (live_text.json().get("data") or {}).get("items") or []
                ref_asset = next((item.get("assetId") for item in ref_items if item.get("status") == "stored"), None)
                if ref_asset:
                    i2i = await client.post(
                        "/api/v1/realphotos/generation-tasks",
                        headers=merchant,
                        json={
                            "mode": "image_to_image",
                            "positivePrompt": "保持杯子，背景改成浅灰墙",
                            "width": 1024,
                            "height": 768,
                            "quantity": 1,
                            "idempotencyKey": f"bf-i2i-live-{stamp}",
                            "referenceAssetId": int(ref_asset),
                        },
                    )
                    body = i2i.json()
                    note(
                        f"F_i2i_live status={i2i.status_code} code={body.get('code')} "
                        f"message={body.get('message')} supplier={body.get('data', {}).get('supplier')}"
                    )
                    if i2i.status_code == 200:
                        items = (body.get("data") or {}).get("items") or []
                        stored = [item for item in items if item.get("status") == "stored"]
                        assert stored and stored[0].get("assetId")
                        f_live_stored = True
                        note(
                            f"F_i2i_stored=true asset={stored[0].get('assetId')} "
                            f"credits={stored[0].get('creditsConsumed')}"
                        )
            if not f_live_stored:
                note("F_i2i_live_stored=false")
                raise AssertionError("F live image_to_image did not store a result")
        else:
            note("F_i2i skipped supplier_live=false; fixture path still covered below")

        fixture_i2i = await client.post(
            "/api/v1/realphotos/generation-tasks",
            headers=merchant,
            data={
                "mode": "image_to_image",
                "positivePrompt": "fixture i2i",
                "width": "512",
                "height": "512",
                "quantity": "1",
                "idempotencyKey": f"bf-i2i-fix-{stamp}",
                "provider": "fixture",
            },
            files={"reference": ("ref.jpg", _jpeg((70, 70, 70)), "image/jpeg")},
        )
        note(f"F_fixture_i2i status={fixture_i2i.status_code} code={fixture_i2i.json().get('code')}")
        assert fixture_i2i.status_code == 200
        f_items = fixture_i2i.json()["data"]["items"]
        assert f_items[0]["status"] == "stored"
        # temporary reference not stored as its own asset beyond result
        async with async_session_factory() as db:
            temp_refs = int(
                await db.scalar(
                    select(func.count())
                    .select_from(RealphotosAsset)
                    .where(
                        RealphotosAsset.tenant_id == tenant,
                        RealphotosAsset.origin_kind == "temporary_reference",
                    )
                )
                or 0
            )
        note(f"F_temporary_reference_assets={temp_refs}")
        assert temp_refs == 0

        # A — copy no reserve + latch + recharge still works
        src = await client.post(
            "/api/v1/realphotos/processing-batches",
            headers=merchant,
            json={
                "assetIds": [asset_id],
                "presetCode": none_p["code"],
                "idempotencyKey": f"bf-copy-src-{stamp}",
                "detectionMode": "pass",
                "preReviewMode": "pass",
            },
        )
        src_task = int((((src.json().get("data") or {}).get("tasks") or [{}])[0]).get("id"))
        await _claim_and_run(src_task, "bf-copy-src")
        async with async_session_factory() as db:
            reserved_before_copy = int(
                (
                    await RealphotosCreditService(db).get_wallet(tenant_id=tenant)
                )["reservedInteger"]
            )
            ledger_before = int(
                await db.scalar(
                    select(func.count())
                    .select_from(RealphotosCreditLedgerEntry)
                    .where(
                        RealphotosCreditLedgerEntry.tenant_id == tenant,
                        RealphotosCreditLedgerEntry.entry_type == "freeze",
                    )
                )
                or 0
            )
        copied = await client.post(
            f"/api/v1/realphotos/processing-tasks/{src_task}/copy",
            headers=merchant,
            json={"idempotencyKey": f"bf-copy-dst-{stamp}", "detectionMode": "pass"},
        )
        assert copied.status_code == 200, copied.text
        copy_data = copied.json()["data"]
        note(
            f"A_copy id={copy_data.get('id')} copiedFrom={copy_data.get('copiedFrom')} "
            f"billingMode={copy_data.get('billingMode')}"
        )
        assert copy_data.get("copiedFrom") == str(src_task)
        assert copy_data.get("billingMode") == "copy_no_reserve"
        async with async_session_factory() as db:
            reserved_after_copy = int(
                (await RealphotosCreditService(db).get_wallet(tenant_id=tenant))["reservedInteger"]
            )
            ledger_after = int(
                await db.scalar(
                    select(func.count())
                    .select_from(RealphotosCreditLedgerEntry)
                    .where(
                        RealphotosCreditLedgerEntry.tenant_id == tenant,
                        RealphotosCreditLedgerEntry.entry_type == "freeze",
                    )
                )
                or 0
            )
            copy_reservations = int(
                await db.scalar(
                    select(func.count())
                    .select_from(RealphotosCreditReservation)
                    .where(RealphotosCreditReservation.task_id == int(copy_data["id"]))
                )
                or 0
            )
        note(
            f"A_reserve_delta={reserved_after_copy - reserved_before_copy} "
            f"freeze_ledger_delta={ledger_after - ledger_before} copy_reservations={copy_reservations}"
        )
        assert reserved_after_copy == reserved_before_copy
        assert ledger_after == ledger_before
        assert copy_reservations == 0

        blocked = await client.post(
            "/api/v1/realphotos/processing-batches",
            headers=merchant,
            json={
                "assetIds": [asset_id],
                "presetCode": none_p["code"],
                "idempotencyKey": f"bf-copy-block-{stamp}",
                "detectionMode": "pass",
                "preReviewMode": "pass",
            },
        )
        note(f"A_latch_block status={blocked.status_code} code={blocked.json().get('code')}")
        assert blocked.json().get("code") == "COPY_LATCH_ACTIVE"

        # recharge still available during latch
        recharge = await client.post(
            "/api/v1/realphotos/recharge-orders",
            headers=merchant,
            json={"tierYuan": 100, "voucherNote": "bf-latch", "idempotencyKey": f"bf-recharge-{stamp}"},
        )
        assert recharge.status_code == 200
        order_id = recharge.json()["data"]["id"]
        confirmed = await client.post(
            f"/api/v1/realphotos/recharge-orders/{order_id}/confirm",
            headers=support,
        )
        note(f"A_recharge_during_latch status={confirmed.status_code} code={confirmed.json().get('code')}")
        assert confirmed.status_code == 200

        done_copy = await _claim_and_run(int(copy_data["id"]), "bf-copy-dst")
        note(f"A_copy_done status={done_copy.status} disposition={done_copy.credit_disposition}")
        assert done_copy.status == "DELIVERED"

        # generation tasks have no copy endpoint
        gen_copy = await client.post(
            f"/api/v1/realphotos/generation-tasks/{gen_data['id']}/copy",
            headers=merchant,
            json={},
        )
        note(f"A_generation_copy_status={gen_copy.status_code}")
        assert gen_copy.status_code in {404, 405, 422}

    note("BLOCKING_FIX_E2E_PASS")
    note("production_billing=false")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(_main()))
    except Exception as exc:  # noqa: BLE001
        note(f"FAIL {type(exc).__name__}: {exc}")
        raise
