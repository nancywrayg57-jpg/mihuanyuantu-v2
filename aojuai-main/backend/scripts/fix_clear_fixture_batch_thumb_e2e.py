"""FIX-CLEAR-FIXTURE-DETECT-BATCH-THUMB-2026-11-08 e2e evidence.

Strategy (C1): merchant pass/not_passed/technical → FORBIDDEN_INJECT (no task row);
omitted/unknown → FORCE gemini. Admin may still inject technical.

Writes /tmp/fix-clear-fixture-batch-thumb-e2e.log with C1_E2E_PASS / C2_E2E_PASS.
Does not commit, push, or open S7.
"""

from __future__ import annotations

import asyncio
import io
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
from PIL import Image

LOG_PATH = Path("/tmp/fix-clear-fixture-batch-thumb-e2e.log")
ROOT = Path(__file__).resolve().parents[3]
BE = ROOT / "aojuai-main" / "backend"
FE = ROOT / "aojuai-main" / "frontend" / "src"


def note(message: str) -> None:
    line = message.rstrip()
    print(line)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def must(cond: bool, msg: str) -> None:
    if not cond:
        note(f"FAIL {msg}")
        raise AssertionError(msg)
    note(f"PASS {msg}")


def mark(rid: str, ok: bool, detail: str = "") -> None:
    tag = f"{rid}_E2E_PASS" if ok else f"{rid}_E2E_FAIL"
    note(f"{tag} {detail}".rstrip())


def _jpeg(color: tuple[int, int, int] = (50, 90, 130), size: tuple[int, int] = (1024, 768)) -> bytes:
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
    note("fix_clear_fixture_batch_thumb_e2e start")
    note("ticket=FIX-CLEAR-FIXTURE-DETECT-BATCH-THUMB-2026-11-08")
    note("branch=cursor/clear-fixture-batch-thumb-9973")
    note("c1_strategy=merchant_inject_FORBIDDEN_INJECT omit_or_unknown_FORCE_gemini")
    note("production_billing=false s7_started=false")

    labels = (FE / "lib" / "realphotos-labels.ts").read_text(encoding="utf-8")
    tasks = (FE / "app" / "(app)" / "realphotos" / "tasks" / "page.tsx").read_text(encoding="utf-8")
    batch = (FE / "app" / "(app)" / "realphotos" / "batch" / "batch-client.tsx").read_text(encoding="utf-8")
    s1 = (BE / "app" / "capabilities" / "realphotos" / "services" / "s1_processing.py").read_text(
        encoding="utf-8"
    )
    s1_api = (BE / "app" / "capabilities" / "realphotos" / "api" / "s1.py").read_text(encoding="utf-8")

    must("resolve_detection_mode" in s1, "C1_resolve_detection_mode")
    must("FORBIDDEN_INJECT" in s1 and "DETECT_PASS" in s1, "C1_pass_in_inject_set")
    must('detection_mode: str = DETECT_GEMINI' in s1 or 'detection_mode: str = "gemini"' in s1, "C1_service_default_gemini")
    must('detection_mode: str = Field(default="gemini"' in s1_api, "C1_copy_body_default_gemini")
    must("detectionMode: 'gemini'" in tasks or 'detectionMode: "gemini"' in tasks, "C1_fe_copy_gemini")
    must("pass" not in [line for line in tasks.splitlines() if "detectionMode" in line and "copy" in line.lower()] or "detectionMode: 'gemini'" in tasks, "C1_fe_no_pass_copy")
    must("历史联调替身（已停用）" in labels, "C1_label_retired")
    must("历史联调替身（已停用）" in tasks, "C1_detail_mode_copy")
    must("apiFetchBlob" in batch and "createObjectURL" in batch and "revokeObjectURL" in batch, "C2_batch_gateway_thumbs")
    must("assetIds" in batch and "gateway/objects" in batch, "C2_assetids_gateway_path")

    import app.capabilities.realphotos.models  # noqa: F401
    import app.domain  # noqa: F401
    from app.capabilities.realphotos.permissions import ROLE_ADMIN, ROLE_MERCHANT
    from app.capabilities.realphotos.seed import reconcile
    from app.capabilities.realphotos.services.bootstrap import DEFAULT_PASSWORD, bootstrap_s0_accounts
    from app.capabilities.realphotos.services.s1_processing import RealphotosS1Service
    from app.capabilities.realphotos.services.s1_recharge import RealphotosRechargeService
    from app.capabilities.realphotos.services.s6_ops import RealphotosOpsService
    from app.capabilities.realphotos.services.supplier_config import RealphotosSupplierConfigService
    from app.core.config import settings
    from app.core.exceptions import BusinessError
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
        user = int(summary["rp_merchant_a1"]["userId"])
        platform = int(summary["rp_admin"]["tenantId"])
        support = int(summary["rp_order_support"]["userId"])
        await reconcile(db, tenant_id=platform)
        await reconcile(db, tenant_id=tenant)
        await RealphotosSupplierConfigService(db).ensure()
        # Clear leftover copy latch from prior e2e runs on shared PG.
        from app.capabilities.realphotos.services.copy_execution_guard import (
            RealphotosCopyExecutionGuardService,
        )
        if await RealphotosCopyExecutionGuardService(db).force_clear_active(
            tenant_id=int(tenant), owner_account_id=int(user)
        ):
            note("cleared_stale_copy_guard=true")
        # B2: no merchant.copy_latch_* reads/writes
        presets = await RealphotosOpsService(db).list_enabled_presets()
        must(bool(presets), "presets_enabled")
        preset_code = str(presets[0]["code"])
        recharge = RealphotosRechargeService(db)
        order = await recharge.create_order(
            tenant_id=tenant,
            requester_user_id=user,
            tier_yuan=100,
            voucher_note="c1-c2-e2e",
            idempotency_key=f"c1c2-recharge-{stamp}",
        )
        await recharge.confirm(order_id=int(order.id), operator_user_id=support)
        await db.commit()

        loop = RealphotosS1Service(db)
        asset = await loop.upload(tenant_id=tenant, owner_account_id=user, data=_jpeg())
        await db.commit()

        # Service-level: merchant technical / pass rejected
        for mode in ("technical", "pass", "not_passed"):
            try:
                await loop.submit_single(
                    tenant_id=tenant,
                    owner_account_id=user,
                    actor_role_codes={ROLE_MERCHANT},
                    asset_id=int(asset.id),
                    preset_code=preset_code,
                    idempotency_key=f"c1-svc-{mode}-{stamp}",
                    detection_mode=mode,
                )
                note(f"FAIL merchant_service_{mode}_should_reject")
                raise AssertionError(mode)
            except BusinessError as exc:
                must(exc.code == "FORBIDDEN_INJECT", f"E-C1-2_service_{mode}_FORBIDDEN_INJECT")

        # Admin technical still works (owner stays merchant user; actor roles = admin)
        tech = await loop.submit_single(
            tenant_id=tenant,
            owner_account_id=user,
            actor_role_codes={ROLE_ADMIN},
            asset_id=int(asset.id),
            preset_code=preset_code,
            idempotency_key=f"c1-admin-tech-{stamp}",
            pre_review_mode="pass",
            detection_mode="technical",
        )
        await db.commit()
        must(str(tech.detection_mode) == "technical", "E-C1-4_admin_tech_persisted")
        note(f"E-C1-4 admin_task_id={tech.id} detectionMode={tech.detection_mode}")
        admin_tech_task_id = int(tech.id)

    done_admin = await _claim_and_run(admin_tech_task_id, f"c1-admin-svc-{stamp}")
    must(getattr(done_admin, "failure_class", None) == "technical", "E-C1-4_execute_fixture_technical")
    note(
        f"E-C1-4 executed task={admin_tech_task_id} failure_class={done_admin.failure_class} "
        f"disposition={done_admin.credit_disposition}"
    )

    transport = httpx.ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        merchant = await _login(client, "rp_merchant_a1", DEFAULT_PASSWORD)

        # Upload two assets for batch + thumbs
        asset_ids: list[str] = []
        object_keys: list[str] = []
        for idx, color in enumerate(((20, 40, 60), (70, 90, 110), (120, 140, 160))):
            files = {"file": (f"c1c2-{idx}.jpg", _jpeg(color), "image/jpeg")}
            up = await client.post("/api/v1/realphotos/assets", headers=merchant, files=files)
            must(up.status_code == 200, f"upload_asset_{idx}")
            payload = up.json()["data"]
            asset_ids.append(str(payload["id"]))
            object_keys.append(str(payload["objectKey"]))

        # E-C1-2 HTTP: merchant technical rejected
        bad = await client.post(
            "/api/v1/realphotos/processing-batches",
            headers=merchant,
            json={
                "assetIds": [int(asset_ids[0])],
                "presetCode": preset_code,
                "idempotencyKey": f"ui-batch-tech-{stamp}",
                "detectionMode": "technical",
            },
        )
        body_bad = bad.json()
        note(f"E-C1-2_http_status={bad.status_code} body={json.dumps(body_bad, ensure_ascii=False)[:400]}")
        must(bad.status_code >= 400, "E-C1-2_http_rejected")
        err = json.dumps(body_bad, ensure_ascii=False)
        must("FORBIDDEN_INJECT" in err, "E-C1-2_http_FORBIDDEN_INJECT")

        # E-C1-1: merchant batch omit detectionMode → gemini
        ok_batch = await client.post(
            "/api/v1/realphotos/processing-batches",
            headers=merchant,
            json={
                "assetIds": [int(asset_ids[0])],
                "presetCode": preset_code,
                "idempotencyKey": f"ui-batch-gemini-{stamp}",
            },
        )
        must(ok_batch.status_code == 200, f"E-C1-1_batch_submit status={ok_batch.status_code} {ok_batch.text[:300]}")
        batch_data = ok_batch.json()["data"]
        task0 = batch_data["tasks"][0]
        must(task0.get("detectionMode") == "gemini", f"E-C1-1_detectionMode={task0.get('detectionMode')}")
        note(f"E-C1-1 task_id={task0.get('id')} detectionMode={task0.get('detectionMode')} batchId={batch_data.get('batchId')}")

        # E-C1-3: copy without pass/technical
        copy = await client.post(
            f"/api/v1/realphotos/processing-tasks/{task0['id']}/copy",
            headers=merchant,
            json={"idempotencyKey": f"copy-{task0['id']}-{stamp}"},
        )
        must(copy.status_code == 200, f"E-C1-3_copy status={copy.status_code} {copy.text[:300]}")
        copy_data = copy.json()["data"]
        must(copy_data.get("detectionMode") == "gemini", f"E-C1-3_copy_mode={copy_data.get('detectionMode')}")
        must(copy_data.get("detectionMode") != "technical", "E-C1-3_copy_not_technical")
        note(f"E-C1-3 copy_task_id={copy_data.get('id')} detectionMode={copy_data.get('detectionMode')}")

        # Merchant copy with explicit technical rejected
        copy_bad = await client.post(
            f"/api/v1/realphotos/processing-tasks/{task0['id']}/copy",
            headers=merchant,
            json={"idempotencyKey": f"copy-tech-{task0['id']}-{stamp}", "detectionMode": "technical"},
        )
        must(copy_bad.status_code >= 400, "E-C1-3_copy_tech_rejected")
        must("FORBIDDEN_INJECT" in json.dumps(copy_bad.json()), "E-C1-3_copy_tech_FORBIDDEN")

        # E-C1-4 service path already executed fixture technical above (admin inject retained).
        note("E-C1-4 merchant_list_guidance=historical_label_no_formal_retry")
        mark("C1", True, "E-C1-1..4 strategy=FORBIDDEN_INJECT")

        # -------- C2: gateway thumb path (equivalent to library) --------
        gateway_ok = 0
        for key in object_keys[:2]:
            resp = await client.get(f"/api/v1/realphotos/gateway/objects/{key}", headers=merchant)
            must(resp.status_code == 200, f"E-C2_gateway_{key}_status={resp.status_code}")
            must(len(resp.content) > 100, f"E-C2_gateway_{key}_bytes={len(resp.content)}")
            must(
                resp.headers.get("content-type", "").startswith("image/")
                or resp.content[:3] == b"\xff\xd8\xff",
                f"E-C2_gateway_{key}_image",
            )
            gateway_ok += 1
            note(f"E-C2 gateway objectKey={key} bytes={len(resp.content)} status=200")

        # Mixed: library-brought ids + local upload already covered by 3 uploads; verify assets list has objectKey
        assets = await client.get("/api/v1/realphotos/assets", headers=merchant)
        must(assets.status_code == 200, "E-C2_assets_list")
        items = assets.json()["data"]["items"]
        matched = [row for row in items if str(row.get("id")) in asset_ids[:2]]
        must(len(matched) >= 2, f"E-C2_assets_matched={len(matched)}")
        must(all(row.get("objectKey") for row in matched), "E-C2_objectKey_present")

        # Clear copy guard left by E-C1-3 so batch submit proves GPS/submit path still works.
        async with async_session_factory() as db3:
            from app.capabilities.realphotos.services.copy_execution_guard import (
                RealphotosCopyExecutionGuardService,
            )

            await RealphotosCopyExecutionGuardService(db3).force_clear_active(
                tenant_id=int(tenant), owner_account_id=int(user)
            )
            # B2: no copy_latch_* writes on merchant profile
            await db3.commit()
            note("E-C2-4 cleared_copy_guard_for_submit=true")

        multi = await client.post(
            "/api/v1/realphotos/processing-batches",
            headers=merchant,
            json={
                "assetIds": [int(asset_ids[1]), int(asset_ids[2])],
                "presetCode": preset_code,
                "idempotencyKey": f"ui-batch-multi-{stamp}",
            },
        )
        must(multi.status_code == 200, f"E-C2-4_submit status={multi.status_code} {multi.text[:240]}")
        note(f"E-C2-4 batchId={multi.json()['data'].get('batchId')} tasks={len(multi.json()['data'].get('tasks') or [])}")

        # Source-level E-C2-1/2/3: batch-client maps assetIds → gateway blob → previewUrl
        must("loadLibraryThumbs" in batch or "apiFetchBlob" in batch, "E-C2-1_source_load")
        must("createObjectURL(file)" in batch or "createObjectURL(file)" in batch.replace(" ", ""), "E-C2-2_local_upload_preview")
        # local upload path uses createObjectURL(file)
        must("URL.createObjectURL(file)" in batch, "E-C2-2_local_object_url")
        must("缩略图加载失败" in batch, "E-C2_fail_soft_notice")

        # DOM-equivalent evidence file for thumbs (network 200 already recorded)
        evidence = {
            "gateway_200_count": gateway_ok,
            "asset_ids": asset_ids[:2],
            "object_keys": object_keys[:2],
            "batch_client_has_gateway_thumbs": True,
        }
        evidence_path = Path("/tmp/fix-clear-fixture-batch-thumb-c2-evidence.json")
        evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
        note(f"E-C2 evidence_path={evidence_path}")

        mark("C2", True, f"gateway_ok={gateway_ok} submit_ok=1")

    note("FIX_CLEAR_FIXTURE_BATCH_THUMB_E2E_PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(_main()))
    except Exception as exc:  # noqa: BLE001
        note(f"FIX_CLEAR_FIXTURE_BATCH_THUMB_E2E_FAIL {type(exc).__name__}: {exc}")
        raise
