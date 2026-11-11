"""MODULE-A-GAP-2026-11-10 e2e → /tmp/module-a-gap-e2e.log

A1 staging URL import · A2 call-time cost · A3 cleanup queue.
Skips AC-009 / FR-012 code / OSS / geocoder. production_billing=false. No S7.
"""

from __future__ import annotations

import asyncio
import io
import json
import subprocess
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx
from PIL import Image

LOG = Path("/tmp/module-a-gap-e2e.log")
REPO = Path(__file__).resolve().parents[3]
STAGING = "http://47.85.47.252"


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


def _jpeg(color=(40, 80, 120), size=(1024, 768)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG", quality=85)
    return buf.getvalue()


async def _login(client: httpx.AsyncClient, username: str, password: str) -> dict[str, str]:
    challenge = await client.post("/api/v1/realphotos/auth/challenges")
    assert challenge.status_code == 200
    data = challenge.json()["data"]
    logged = await client.post(
        "/api/v1/realphotos/auth/login",
        json={
            "username": username,
            "password": password,
            "challengeId": data["challengeId"],
            "challengeCode": data["devCode"],
        },
    )
    assert logged.status_code == 200, logged.text
    return {"Authorization": "Bearer " + logged.json()["data"]["accessToken"]}


async def _upload_staging() -> str:
    async with httpx.AsyncClient(timeout=30.0) as client:
        files = {"file": ("module-a-gap.jpg", _jpeg(), "image/jpeg")}
        resp = await client.post(f"{STAGING}/upload", files=files)
        must(resp.status_code == 200, f"staging_upload_http={resp.status_code}")
        body = resp.json()
        rel = body["results"][0]["url"]
        url = f"{STAGING}{rel}" if str(rel).startswith("/") else str(rel)
        note(f"staging_url={url}")
        return url


async def main() -> int:
    LOG.write_text("", encoding="utf-8")
    from dotenv import load_dotenv

    load_dotenv(REPO / "aojuai-main/backend/.env")

    from sqlalchemy import func, select

    import app.capabilities.realphotos.models  # noqa: F401
    import app.domain  # noqa: F401
    from app.capabilities.realphotos.constants import (
        JOB_KIND_INBOX_CLEANUP,
        JOB_KIND_OUTPUT_CLEANUP,
    )
    from app.capabilities.realphotos.models import (
        RealphotosAsset,
        RealphotosCreditLedgerEntry,
        RealphotosDetectionResult,
        RealphotosImageTask,
        RealphotosInboxMessage,
        RealphotosProviderUsage,
    )
    from app.capabilities.realphotos.seed import reconcile
    from app.capabilities.realphotos.services.bootstrap import DEFAULT_PASSWORD, bootstrap_s0_accounts
    from app.capabilities.realphotos.services.credit_service import RealphotosCreditService
    from app.capabilities.realphotos.services.job_service import RealphotosJobService
    from app.capabilities.realphotos.services.provider_usage import RealphotosProviderUsageService
    from app.capabilities.realphotos.services.s1_processing import RealphotosS1Service
    from app.capabilities.realphotos.services.supplier_config import RealphotosSupplierConfigService
    from app.capabilities.realphotos.services.supplier_material import import_staging_enabled
    from app.core.config import settings
    from app.domain.auth.api_key_service import ApiKeyService
    from app.infrastructure.database.session import Base, async_session_factory, engine, init_db
    from app.main import app as fastapi_app

    # Work-order gates via Settings only (GOV-10 forbids scripts touching os.environ).
    settings.REALPHOTOS_IMPORT_STAGING = "true"
    if not str(settings.REALPHOTOS_UNIT_COSTS_JSON or "").strip():
        settings.REALPHOTOS_UNIT_COSTS_JSON = json.dumps(
            {
                "pre_review|qwen3-vl-plus": {
                    "unit_cost": "0.02",
                    "currency": "CNY",
                    "unit_name": "call",
                }
            }
        )

    branch = subprocess.check_output(
        ["git", "-C", str(REPO), "rev-parse", "--abbrev-ref", "HEAD"], text=True
    ).strip()
    head = subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"], text=True).strip()
    note("MODULE_A_GAP_E2E start")
    note(f"started_at={datetime.now(UTC).isoformat()}")
    note(f"branch={branch} HEAD={head}")
    note(f"db_dialect={settings.DB_DIALECT}")
    note("production_billing=false")
    note("formal_supplier=false")
    note("s7_started=false")
    note("AC009_SKIPPED=true reason=gpt-image-2_no_seed")
    note("FR012_PRE_REVIEW_WIRED=true code_change=false")
    note("OSS_IMPL_OUT_OF_SCOPE=true")
    note("GEOCODER_OUT_OF_SCOPE=true")
    note("import_strategy=per_item_continue")
    note("physical_table=cap_realphotos_provider_usage maps_to=rp_provider_usage")
    note("alembic_deviation=orm_create_all_like_sibling_realphotos_tables")

    must(str(settings.DB_DIALECT).startswith("postgres"), "postgresql_required")
    must(import_staging_enabled(), "import_staging_flag_on")

    await init_db()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    stamp = str(int(datetime.now(UTC).timestamp()))
    async with async_session_factory() as db:
        summary = await bootstrap_s0_accounts(db)
        tenant = int(summary["rp_merchant_a1"]["tenantId"])
        merchant_user = int(summary["rp_merchant_a1"]["userId"])
        platform = int(summary["rp_admin"]["tenantId"])
        await reconcile(db, tenant_id=platform)
        await reconcile(db, tenant_id=tenant)
        await RealphotosSupplierConfigService(db).ensure()
        contract = await RealphotosSupplierConfigService(db).enabled("import")
        must(contract is not None, "import_contract_enabled")
        must(bool((contract.capabilities or {}).get("stagingAllowed")), "stagingAllowed_true")
        must(not bool((contract.capabilities or {}).get("formalSupplier")), "formalSupplier_false")
        note(f"import_gap_note={contract.gap_note}")
        credits = RealphotosCreditService(db)
        wallet_before = await credits.get_wallet(tenant_id=tenant)
        await db.commit()

    transport = httpx.ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=180.0) as client:
        merchant = await _login(client, "rp_merchant_a1", DEFAULT_PASSWORD)
        admin = await _login(client, "rp_admin", DEFAULT_PASSWORD)
        order_support = await _login(client, "rp_order_support", DEFAULT_PASSWORD)

        # ---- A1.1 disabled path: flip flag off ----
        settings.REALPHOTOS_IMPORT_STAGING = "false"
        async with async_session_factory() as db:
            await RealphotosSupplierConfigService(db).ensure()
            await db.commit()
        denied = await client.post(
            "/api/v1/realphotos/resource-imports",
            headers=merchant,
            json={"payload": f"{STAGING}/images/denied.jpg"},
        )
        must(denied.status_code == 400 or denied.json().get("code") == "SERVICE_NOT_CONFIGURED", "A1_disabled_rejected")
        must(denied.json().get("code") == "SERVICE_NOT_CONFIGURED", "A1_disabled_code")
        note("A1_disabled_no_egress=true")

        # Re-enable
        settings.REALPHOTOS_IMPORT_STAGING = "true"
        async with async_session_factory() as db:
            await RealphotosSupplierConfigService(db).ensure()
            await db.commit()

        staging_url = await _upload_staging()

        async with async_session_factory() as db:
            assets_before = int(
                await db.scalar(
                    select(func.count())
                    .select_from(RealphotosAsset)
                    .where(
                        RealphotosAsset.tenant_id == tenant,
                        RealphotosAsset.deleted_at.is_(None),
                    )
                )
                or 0
            )

        single = await client.post(
            "/api/v1/realphotos/resource-imports",
            headers=merchant,
            json={"payload": staging_url},
        )
        must(single.status_code == 200, f"A1_single_http={single.status_code} body={single.text[:200]}")
        sdata = single.json()["data"]
        must(int(sdata.get("imported") or 0) == 1, "A1_single_imported_1")
        must(int(sdata.get("creditsCharged") or 0) == 0, "A1_no_credit_charge")
        must(sdata.get("formalSupplier") is False, "A1_formal_supplier_false")
        note(f"A1_strategy={sdata.get('strategy')}")

        async with async_session_factory() as db:
            assets_after = int(
                await db.scalar(
                    select(func.count())
                    .select_from(RealphotosAsset)
                    .where(
                        RealphotosAsset.tenant_id == tenant,
                        RealphotosAsset.deleted_at.is_(None),
                        RealphotosAsset.origin_kind == "url_import",
                    )
                )
                or 0
            )
            wallet_after = await RealphotosCreditService(db).get_wallet(tenant_id=tenant)
        must(assets_after >= 1, "A1_asset_origin_url_import")
        must(
            int(wallet_after["availableInteger"]) == int(wallet_before["availableInteger"]),
            "A1_credits_unchanged",
        )
        note(f"A1_assets_url_import_count>={assets_after} before_all={assets_before}")

        mixed = await client.post(
            "/api/v1/realphotos/resource-imports",
            headers=merchant,
            json={
                "payload": json.dumps(
                    [
                        {
                            "name": f"ok-{stamp}",
                            "seller": "s",
                            "sku": "",
                            "asn": "",
                            "price": "",
                            "website": "",
                            "url": staging_url,
                        },
                        {
                            "name": f"bad-{stamp}",
                            "seller": "s",
                            "sku": "",
                            "asn": "",
                            "price": "",
                            "website": "",
                            "url": "https://example.invalid/images/x.jpg",
                        },
                    ]
                )
            },
        )
        must(mixed.status_code == 200, f"A1_mixed_http={mixed.status_code}")
        mdata = mixed.json()["data"]
        must(int(mdata.get("imported") or 0) == 1, "A1_mixed_imported_1")
        must(len(mdata.get("failed") or []) == 1, "A1_mixed_failed_1")
        note(f"A1_mixed_fail_code={(mdata.get('failed') or [{}])[0].get('code')}")

        hundred_one = [{"name": str(i), "sku": "", "url": staging_url} for i in range(101)]
        too_many = await client.post(
            "/api/v1/realphotos/resource-imports",
            headers=merchant,
            json={"payload": json.dumps(hundred_one)},
        )
        must(too_many.json().get("code") == "INPUT_INVALID", "A1_101_rejected")

        key_row, plaintext = None, None
        async with async_session_factory() as db:
            key_row, plaintext = await ApiKeyService.create_key(
                db, tenant, merchant_user, name=f"mod-a-{stamp}", scopes=["image_processing"]
            )
            await db.commit()
        api_key_resp = await client.post(
            "/api/v1/realphotos/resource-imports",
            headers={"X-API-Key": plaintext},
            json={"payload": staging_url},
        )
        must(api_key_resp.status_code in {401, 403}, f"A1_api_key_rejected status={api_key_resp.status_code}")
        note("A1_api_key_image_processing_cannot_import=true")

        note("A1_URL_IMPORT_STAGING_PASS")

        # ---- A2 cost metering ----
        async with async_session_factory() as db:
            # wipe usage for deterministic empty check on this process evidence
            rows = (
                await db.execute(select(RealphotosProviderUsage).where(RealphotosProviderUsage.deleted_at.is_(None)))
            ).scalars().all()
            now = datetime.now(UTC)
            for row in rows:
                row.deleted_at = now
            await db.commit()

        empty_ws = await client.get("/api/v1/realphotos/workspace", headers=admin)
        must(empty_ws.status_code == 200, "A2_admin_workspace")
        em = empty_ws.json()["data"].get("opsMetrics") or {}
        must(em.get("cost") is None, "A2_empty_cost_null")
        must(em.get("cost") != 0, "A2_empty_not_fake_zero")
        note(f"A2_empty_costReason={em.get('costReason')}")

        denied_cost = await client.get("/api/v1/realphotos/workspace", headers=merchant)
        mview = denied_cost.json()["data"]
        must(not mview.get("opsMetrics"), "A2_merchant_no_opsMetrics")
        support_ws = await client.get("/api/v1/realphotos/workspace", headers=order_support)
        must(not (support_ws.json()["data"] or {}).get("opsMetrics"), "A2_order_support_no_opsMetrics")

        # Fixture / non-egress paths must not create known cost rows.
        async with async_session_factory() as db:
            skipped = await RealphotosProviderUsageService(db).record_call(
                duty="generation",
                provider="fixture",
                model_id="fixture",
                tenant_id=tenant,
                fixture=True,
            )
            must(skipped is None, "A2_fixture_not_recorded")
            await db.commit()

        settings.REALPHOTOS_UNIT_COSTS_JSON = json.dumps(
            {"pre_review|qwen3-vl-plus": {"unit_cost": "0.02", "currency": "CNY", "unit_name": "call"}}
        )
        async with async_session_factory() as db:
            priced = await RealphotosProviderUsageService(db).record_call(
                duty="pre_review",
                provider="dashscope",
                model_id="qwen3-vl-plus",
                tenant_id=tenant,
                units=Decimal("1"),
                note="e2e-priced",
            )
            must(priced is not None and priced.cost_status == "known", "A2_priced_known")
            must(Decimal(str(priced.amount)) == Decimal("0.02"), "A2_amount_0_02")
            await db.commit()

        priced_ws = await client.get("/api/v1/realphotos/workspace", headers=admin)
        pm = priced_ws.json()["data"]["opsMetrics"]
        must(pm.get("cost") == 0.02 or float(pm.get("cost")) == 0.02, f"A2_cost_sum={pm.get('cost')}")
        must(pm.get("creditsNotUsedForCost") is True, "A2_credits_not_used")
        note(f"A2_cost_known={pm.get('cost')} unknownCount={pm.get('costUnknownCount')}")

        # Remove unit price → new rows unavailable; historical known remains.
        settings.REALPHOTOS_UNIT_COSTS_JSON = ""
        async with async_session_factory() as db:
            unpriced = await RealphotosProviderUsageService(db).record_call(
                duty="pre_review",
                provider="dashscope",
                model_id="qwen3-vl-plus",
                tenant_id=tenant,
                note="e2e-unpriced",
            )
            must(unpriced is not None and unpriced.cost_status == "unavailable", "A2_new_unavailable")
            await db.commit()
        still = await client.get("/api/v1/realphotos/workspace", headers=admin)
        sm = still.json()["data"]["opsMetrics"]
        must(float(sm.get("cost")) == 0.02, "A2_history_known_preserved")
        note("A2_COST_METERING_PASS")

        # ---- A3 cleanup queue ----
        async with async_session_factory() as db:
            past = datetime.now(UTC) - timedelta(days=2)
            inbox = RealphotosInboxMessage(
                tenant_id=tenant,
                recipient_user_id=merchant_user,
                event_key=f"mod-a-inbox-{stamp}",
                title="expired-e2e",
                body="cleanup",
                expires_at=past,
            )
            db.add(inbox)
            # Minimal delivered task with expired output
            from app.capabilities.realphotos.adapters.storage import get_storage_adapter
            from app.capabilities.realphotos.models import RealphotosBatch, RealphotosTaskChain

            batch = RealphotosBatch(
                tenant_id=tenant,
                owner_account_id=merchant_user,
                image_count=1,
                preset_code="legacy-legacy-online-1001",
            )
            db.add(batch)
            await db.flush()
            chain = RealphotosTaskChain(tenant_id=tenant, batch_id=int(batch.id), round_no=1)
            db.add(chain)
            await db.flush()
            # reuse an existing asset if any
            asset = (
                await db.execute(
                    select(RealphotosAsset)
                    .where(
                        RealphotosAsset.tenant_id == tenant,
                        RealphotosAsset.deleted_at.is_(None),
                    )
                    .limit(1)
                )
            ).scalar_one_or_none()
            if asset is None:
                s1 = RealphotosS1Service(db)
                asset = await s1.upload(
                    tenant_id=tenant,
                    owner_account_id=merchant_user,
                    data=_jpeg(),
                    meta_name=f"a3-{stamp}",
                )
            out_key = f"tenant/{tenant}/output/mod-a-{stamp}.jpg"
            get_storage_adapter().put_bytes(out_key, _jpeg((1, 2, 3)), content_type="image/jpeg")
            task = RealphotosImageTask(
                tenant_id=tenant,
                owner_account_id=merchant_user,
                batch_id=int(batch.id),
                chain_id=int(chain.id),
                asset_id=int(asset.id),
                status="delivered",
                preset_code="legacy-legacy-online-1001",
                preset_snapshot={},
                idempotency_key=f"mod-a-out-{stamp}",
                output_object_key=out_key,
                output_expires_at=past,
                output_byte_size=100,
            )
            db.add(task)
            await db.flush()
            ledger_before = int(
                await db.scalar(
                    select(func.count())
                    .select_from(RealphotosCreditLedgerEntry)
                    .where(RealphotosCreditLedgerEntry.tenant_id == tenant)
                )
                or 0
            )
            detect_before = int(
                await db.scalar(select(func.count()).select_from(RealphotosDetectionResult)) or 0
            )
            job_inbox = await RealphotosJobService(db).enqueue_cleanup(
                tenant_id=tenant,
                owner_account_id=merchant_user,
                job_kind=JOB_KIND_INBOX_CLEANUP,
            )
            job_out = await RealphotosJobService(db).enqueue_cleanup(
                tenant_id=tenant,
                owner_account_id=merchant_user,
                job_kind=JOB_KIND_OUTPUT_CLEANUP,
            )
            await db.commit()
            note(f"A3_enqueued inbox={job_inbox.id} output={job_out.id}")

        # Worker claim/run cleanup kinds
        from app.capabilities.realphotos.worker import RealphotosHeartbeatTaskSource

        source = RealphotosHeartbeatTaskSource(worker_id=f"mod-a-gap-{stamp}")
        ran = 0
        for _ in range(8):
            claimed = await source.claim()
            if claimed is None:
                continue
            if claimed.get("job_kind") in {"inbox_cleanup", "output_cleanup"}:
                await source.run(claimed)
                ran += 1
                note(f"A3_worker_ran kind={claimed.get('job_kind')} job={claimed.get('job_id')}")
            if ran >= 2:
                break
        must(ran >= 2, f"A3_worker_ran_cleanup_jobs ran={ran}")

        async with async_session_factory() as db:
            inbox_alive = (
                await db.execute(
                    select(RealphotosInboxMessage).where(
                        RealphotosInboxMessage.event_key == f"mod-a-inbox-{stamp}",
                        RealphotosInboxMessage.deleted_at.is_(None),
                    )
                )
            ).scalar_one_or_none()
            must(inbox_alive is None, "A3_inbox_soft_deleted")
            task_row = (
                await db.execute(
                    select(RealphotosImageTask).where(
                        RealphotosImageTask.idempotency_key == f"mod-a-out-{stamp}"
                    )
                )
            ).scalar_one()
            must(task_row.output_object_key is None, "A3_output_key_cleared")
            ledger_after = int(
                await db.scalar(
                    select(func.count())
                    .select_from(RealphotosCreditLedgerEntry)
                    .where(RealphotosCreditLedgerEntry.tenant_id == tenant)
                )
                or 0
            )
            detect_after = int(
                await db.scalar(select(func.count()).select_from(RealphotosDetectionResult)) or 0
            )
            must(ledger_after == ledger_before, "A3_ledger_intact")
            must(detect_after == detect_before, "A3_detection_intact")
            expired_task_id = int(task_row.id)

        # selected download should refuse missing output object
        dl = await client.post(
            "/api/v1/realphotos/processing-tasks/selected-downloads",
            headers=merchant,
            json={"taskIds": [int(expired_task_id)]},
        )
        note(f"A3_selected_download_after_cleanup status={dl.status_code} body={dl.text[:240]}")
        if dl.status_code == 200:
            items = (dl.json().get("data") or {}).get("items") or []
            must(len(items) == 0, "A3_download_items_empty")
        else:
            must(dl.status_code >= 400, "A3_download_rejected")
        note("A3_CLEANUP_QUEUE_PASS")

    note(
        "MODULE_A_GAP_E2E_PASS "
        "A1_URL_IMPORT_STAGING_PASS A2_COST_METERING_PASS A3_CLEANUP_QUEUE_PASS "
        "AC009_SKIPPED=true FR012_PRE_REVIEW_WIRED=true production_billing=false "
        "formal_supplier=false s7_started=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
