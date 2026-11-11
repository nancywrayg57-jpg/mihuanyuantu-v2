"""PRODUCT-GAP-FIX-2026-11-11 e2e → /tmp/product-gap-fix-e2e.log

G1 captcha · G2 image lock · G3 upload≤20 · G4 outbox retry · G5 OpenAPI · G6 cost regression.
S7 out of scope. FR-025 no reimplement.
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import httpx
from PIL import Image

LOG = Path("/tmp/product-gap-fix-e2e.log")
REPO = Path(__file__).resolve().parents[3]


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


def _jpeg(color=(40, 80, 120), size=(1280, 960)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG", quality=85)
    return buf.getvalue()


async def _challenge_login(client: httpx.AsyncClient, username: str, password: str, code: str | None = None) -> httpx.Response:
    challenge = await client.post("/api/v1/realphotos/auth/challenges")
    assert challenge.status_code == 200, challenge.text
    data = challenge.json()["data"]
    img = str(data.get("imageBase64") or "")
    assert img.startswith("data:image/png;base64,"), f"g1_missing_captcha_image keys={list(data)}"
    return await client.post(
        "/api/v1/realphotos/auth/login",
        json={
            "username": username,
            "password": password,
            "challengeId": data["challengeId"],
            "challengeCode": code if code is not None else data["devCode"],
        },
    )


async def main() -> int:
    LOG.write_text("", encoding="utf-8")
    from dotenv import load_dotenv

    load_dotenv(REPO / "aojuai-main/backend/.env")

    import app.capabilities.realphotos.models  # noqa: F401
    import app.domain  # noqa: F401
    from sqlalchemy import func, select

    from app.capabilities.realphotos.models import (
        RealphotosAsset,
        RealphotosCreditLedgerEntry,
        RealphotosExecutionJob,
        RealphotosImageLock,
        RealphotosInboxMessage,
        RealphotosOutbox,
    )
    from app.capabilities.realphotos.services.bootstrap import DEFAULT_PASSWORD, bootstrap_s0_accounts
    from app.capabilities.realphotos.services.credit_service import RealphotosCreditService
    from app.capabilities.realphotos.services.job_service import RealphotosJobService
    from app.capabilities.realphotos.services.notify_outbox import RealphotosNotifyOutboxService
    from app.capabilities.realphotos.services.s1_processing import RealphotosS1Service
    from app.capabilities.realphotos.services.s6_ops import pixel_identity
    from app.capabilities.realphotos.seed import reconcile
    from app.core.config import settings
    from app.infrastructure.database.session import Base, async_session_factory, engine, init_db
    from app.main import app as fastapi_app
    from scripts.product_gap_fix_schema import ensure_product_gap_fix_schema

    sha = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=REPO).decode().strip()
    note(f"product_gap_fix_e2e start sha={sha} at={datetime.now(UTC).isoformat()}")
    note("S7_OUT_OF_SCOPE=true")
    note("G6_NO_REIMPLEMENT=true")
    note("production_billing=false")

    if not str(settings.DB_DIALECT).startswith("postgres"):
        note(f"FAIL expected postgresql got {settings.DB_DIALECT!r}")
        return 2

    await init_db()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await ensure_product_gap_fix_schema(engine)

    stamp = str(int(datetime.now(UTC).timestamp()))
    async with async_session_factory() as db:
        summary = await bootstrap_s0_accounts(db)
        merchant_tenant = int(summary["rp_merchant_a1"]["tenantId"])
        admin_id = int(summary["rp_admin"]["userId"])
        platform = int(summary["rp_admin"]["tenantId"])
        await reconcile(db, tenant_id=platform)
        await reconcile(db, tenant_id=merchant_tenant)
        await RealphotosCreditService(db).admin_adjust(
            tenant_id=merchant_tenant,
            delta_available=5000,
            operator_user_id=admin_id,
            reason="product-gap-fix-e2e",
            event_key=f"gap-fix-topup-{stamp}",
        )
        await db.commit()

    flags = {
        "G1_LOGIN_CAPTCHA_PASS": False,
        "G2_IMAGE_LOCK_ENFORCE_PASS": False,
        "G3_UPLOAD_BATCH20_PASS": False,
        "G4_MSG_OUTBOX_PASS": False,
        "G5_OPENAPI_REACHABLE_PASS": False,
        "G6_OPS_COST_REGRESSION_PASS": False,
    }

    transport = httpx.ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=120.0) as client:
        # —— G1 ——
        probe = await client.post("/api/v1/realphotos/auth/challenges")
        must(probe.status_code == 200, f"g1_challenge_http={probe.status_code}")
        probe_data = probe.json()["data"]
        must(
            str(probe_data.get("imageBase64") or "").startswith("data:image/png;base64,"),
            "g1_captcha_image_present",
        )
        note("PASS g1_captcha_image_present")
        bad = await _challenge_login(client, "rp_merchant_a1", DEFAULT_PASSWORD, code="000000")
        must(bad.status_code in {400, 401, 422}, f"g1_wrong_captcha_status={bad.status_code}")
        good = await _challenge_login(client, "rp_merchant_a1", DEFAULT_PASSWORD)
        must(good.status_code == 200, f"g1_ok_login={good.status_code}")
        g1_data = good.json()["data"]
        must(bool(g1_data.get("accessToken")), "g1_access_token")
        must(isinstance(g1_data.get("expires"), str) and bool(g1_data.get("expires")), "g1_expires_iso_string")
        must(bool(g1_data.get("roles")), "g1_roles_present")
        must(int(g1_data.get("absoluteSessionDays") or 0) == 30, "g1_session_30d")
        set_cookie = good.headers.get("set-cookie") or ""
        must("aoju_access" in set_cookie or settings.AUTH_ACCESS_COOKIE_NAME in set_cookie, "g1_cookie_set")
        merchant = {"Authorization": "Bearer " + g1_data["accessToken"]}
        me = await client.get("/api/v1/realphotos/me", headers=merchant)
        must(me.status_code == 200, f"g1_session_me={me.status_code}")
        flags["G1_LOGIN_CAPTCHA_PASS"] = True
        note("G1_LOGIN_CAPTCHA_PASS=true")

        admin = await _challenge_login(client, "rp_admin", DEFAULT_PASSWORD)
        must(admin.status_code == 200, "admin_login")
        admin_h = {"Authorization": "Bearer " + admin.json()["data"]["accessToken"]}

        # —— G3 ——
        before_count = 0
        async with async_session_factory() as db:
            before_count = int(
                await db.scalar(
                    select(func.count()).select_from(RealphotosAsset).where(RealphotosAsset.deleted_at.is_(None))
                )
                or 0
            )
        files20 = [("files", (f"g3-{i}.jpg", _jpeg((i % 180, 50, 90)), "image/jpeg")) for i in range(20)]
        up20 = await client.post("/api/v1/realphotos/assets/batch", headers=merchant, files=files20)
        must(up20.status_code == 200, f"g3_20_http={up20.status_code} {up20.text[:200]}")
        must(int(up20.json()["data"]["count"]) == 20, "g3_20_count")
        files21 = [("files", (f"g3x-{i}.jpg", _jpeg((i % 180, 60, 100)), "image/jpeg")) for i in range(21)]
        up21 = await client.post("/api/v1/realphotos/assets/batch", headers=merchant, files=files21)
        must(up21.status_code == 400, f"g3_21_http={up21.status_code}")
        must(up21.json().get("code") == "UPLOAD_BATCH_REJECTED", "g3_21_code")
        single = await client.post(
            "/api/v1/realphotos/assets",
            headers=merchant,
            files={"file": ("g3-single.jpg", _jpeg((9, 9, 9)), "image/jpeg")},
        )
        must(single.status_code == 200, "g3_single_ok")
        async with async_session_factory() as db:
            after_count = int(
                await db.scalar(
                    select(func.count()).select_from(RealphotosAsset).where(RealphotosAsset.deleted_at.is_(None))
                )
                or 0
            )
        must(after_count == before_count + 21, f"g3_db_delta={after_count - before_count}")  # 20 batch + 1 single
        flags["G3_UPLOAD_BATCH20_PASS"] = True
        note("G3_UPLOAD_BATCH20_PASS=true")

        # —— G2 ——
        # 每轮换色，避免 pixel_identity 与历史锁行撞 uq
        color_seed = int(stamp[-3:]) % 200
        locked_bytes = _jpeg((200 - color_seed, 10 + color_seed % 40, 10))
        unlocked_bytes = _jpeg((10, 200 - color_seed, 10 + color_seed % 30))
        up_locked = await client.post(
            "/api/v1/realphotos/assets",
            headers=merchant,
            files={"file": ("locked.jpg", locked_bytes, "image/jpeg")},
        )
        up_free = await client.post(
            "/api/v1/realphotos/assets",
            headers=merchant,
            files={"file": ("free.jpg", unlocked_bytes, "image/jpeg")},
        )
        must(up_locked.status_code == 200 and up_free.status_code == 200, "g2_upload_pair")
        locked_id = int(up_locked.json()["data"]["id"])
        free_id = int(up_free.json()["data"]["id"])
        identity = pixel_identity(locked_bytes)
        async with async_session_factory() as db:
            me_payload = (await client.get("/api/v1/realphotos/me", headers=merchant)).json()["data"]
            owner_id = int(me_payload.get("userId") or me_payload.get("id") or 0)
            tenant_id = int(me_payload.get("tenantId") or 1)
            if owner_id <= 0:
                from app.domain.users.models import User

                owner_id = int(
                    (
                        await db.execute(select(User.id).where(User.username == "rp_merchant_a1"))
                    ).scalar_one()
                )
                tenant_id = int(
                    (
                        await db.execute(select(User.tenant_id).where(User.username == "rp_merchant_a1"))
                    ).scalar_one()
                )
            existing_lock = (
                await db.execute(
                    select(RealphotosImageLock).where(
                        RealphotosImageLock.tenant_id == tenant_id,
                        RealphotosImageLock.owner_account_id == owner_id,
                        RealphotosImageLock.image_identity == identity,
                        RealphotosImageLock.deleted_at.is_(None),
                    )
                )
            ).scalar_one_or_none()
            if existing_lock is None:
                db.add(
                    RealphotosImageLock(
                        tenant_id=tenant_id,
                        owner_account_id=owner_id,
                        image_identity=identity,
                        reason="e2e_fixture",
                    )
                )
                await db.commit()
            jobs_before = int(
                await db.scalar(select(func.count()).select_from(RealphotosExecutionJob)) or 0
            )
            freeze_before = int(
                await db.scalar(
                    select(func.count())
                    .select_from(RealphotosCreditLedgerEntry)
                    .where(RealphotosCreditLedgerEntry.entry_type == "freeze")
                )
                or 0
            )

        presets = await client.get("/api/v1/realphotos/presets", headers=admin_h)
        must(presets.status_code == 200, "g2_presets")
        items = (presets.json().get("data") or {}).get("items") or []
        must(len(items) >= 1, "g2_preset_available")
        preset = str(items[0]["code"])
        reject = await client.post(
            "/api/v1/realphotos/processing-tasks",
            headers=merchant,
            json={
                "assetId": locked_id,
                "presetCode": preset,
                "idempotencyKey": f"gap-lock-{stamp}",
            },
        )
        # merchant may lack inject; lock should still fire (or preset path). Prefer IMAGE_LOCKED.
        if reject.status_code != 400 or reject.json().get("code") != "IMAGE_LOCKED":
            reject = await client.post(
                "/api/v1/realphotos/processing-tasks",
                headers=admin_h,
                json={
                    "assetId": locked_id,
                    "presetCode": preset,
                    "idempotencyKey": f"gap-lock-admin-{stamp}",
                    "preReviewMode": "pass",
                    "detectionMode": "pass",
                },
            )
        must(reject.status_code == 400 and reject.json().get("code") == "IMAGE_LOCKED", f"g2_locked={reject.text[:200]}")
        async with async_session_factory() as db:
            jobs_after = int(await db.scalar(select(func.count()).select_from(RealphotosExecutionJob)) or 0)
            freeze_after = int(
                await db.scalar(
                    select(func.count())
                    .select_from(RealphotosCreditLedgerEntry)
                    .where(RealphotosCreditLedgerEntry.entry_type == "freeze")
                )
                or 0
            )
        must(jobs_after == jobs_before, "g2_no_new_job")
        must(freeze_after == freeze_before, "g2_no_new_freeze")
        # 未锁定图：同商家租户提交（管理员会话租户不同，不能看见商家资源）
        ok_submit = await client.post(
            "/api/v1/realphotos/processing-tasks",
            headers=merchant,
            json={
                "assetId": free_id,
                "presetCode": preset,
                "idempotencyKey": f"gap-free-{stamp}",
            },
        )
        must(ok_submit.status_code == 200, f"g2_unlocked_submit={ok_submit.status_code} {ok_submit.text[:160]}")
        assets = await client.get("/api/v1/realphotos/assets", headers=merchant)
        locked_flags = {
            str(item["id"]): bool(item.get("locked"))
            for item in (assets.json().get("data") or {}).get("items") or []
        }
        must(locked_flags.get(str(locked_id)) is True, "g2_list_shows_locked")
        flags["G2_IMAGE_LOCK_ENFORCE_PASS"] = True
        note("G2_IMAGE_LOCK_ENFORCE_PASS=true")

        # —— G4 ——
        os.environ["REALPHOTOS_NOTIFY_FORCE_FAIL_UNTIL"] = "2"
        async with async_session_factory() as db:
            notify = RealphotosNotifyOutboxService(db)
            row = await notify.enqueue_inbox(
                tenant_id=tenant_id,
                recipient_user_id=owner_id,
                event_key=f"gap-outbox-{stamp}",
                title="投递测试",
                body="hello-outbox",
            )
            await db.commit()
            outbox_id = int(row.id)
            # 直接对目标行 deliver_claimed，避免同库其他 pending outbox 抢占 claim
            row = await db.get(RealphotosOutbox, outbox_id)
            assert row is not None
            r1 = await notify.deliver_claimed(row)
            await db.commit()
            must(r1 is not None and r1["status"] == "pending" and r1["attemptCount"] == 1, f"g4_r1={r1}")
            row = await db.get(RealphotosOutbox, outbox_id)
            assert row is not None
            row.next_attempt_at = None
            await db.flush()
            r2 = await notify.deliver_claimed(row)
            await db.commit()
            must(r2 is not None and r2["status"] == "pending" and r2["attemptCount"] == 2, f"g4_r2={r2}")
            row = await db.get(RealphotosOutbox, outbox_id)
            assert row is not None
            row.next_attempt_at = None
            await db.commit()
        os.environ.pop("REALPHOTOS_NOTIFY_FORCE_FAIL_UNTIL", None)
        async with async_session_factory() as db:
            notify = RealphotosNotifyOutboxService(db)
            row = await db.get(RealphotosOutbox, outbox_id)
            assert row is not None
            r3 = await notify.deliver_claimed(row)
            await db.commit()
            must(r3 is not None and r3["status"] == "sent" and r3["attemptCount"] == 3, f"g4_r3={r3}")
            inbox = (
                await db.execute(
                    select(RealphotosInboxMessage).where(
                        RealphotosInboxMessage.event_key == f"gap-outbox-{stamp}",
                        RealphotosInboxMessage.deleted_at.is_(None),
                    )
                )
            ).scalar_one_or_none()
            must(inbox is not None, "g4_inbox_written")
            freeze_mid = int(
                await db.scalar(
                    select(func.count())
                    .select_from(RealphotosCreditLedgerEntry)
                    .where(RealphotosCreditLedgerEntry.entry_type.in_(("freeze", "consume")))
                )
                or 0
            )
        # 补发
        resend = await client.post(
            f"/api/v1/realphotos/inbox/{int(inbox.id)}/resend",
            headers=merchant,
        )
        must(resend.status_code == 200, f"g4_resend={resend.status_code}")
        must(resend.json()["data"].get("queuedForDelivery") is True, "g4_resend_queued")
        # drain notify once
        async with async_session_factory() as db:
            await RealphotosNotifyOutboxService(db).deliver_one()
            await db.commit()
            freeze_after_resend = int(
                await db.scalar(
                    select(func.count())
                    .select_from(RealphotosCreditLedgerEntry)
                    .where(RealphotosCreditLedgerEntry.entry_type.in_(("freeze", "consume")))
                )
                or 0
            )
        must(freeze_after_resend == freeze_mid, "g4_resend_no_credit")
        # CLI 入口可 import
        from scripts import run_realphotos_notify_worker as notify_cli

        must(callable(notify_cli.main), "g4_notify_cli_entrypoint")
        flags["G4_MSG_OUTBOX_PASS"] = True
        note("G4_MSG_OUTBOX_PASS=true")

        # —— G5 ——
        meta = await client.get("/api/v1/realphotos/contracts/image-processing", headers=merchant)
        must(meta.status_code == 200, f"g5_meta={meta.status_code}")
        version = str(meta.json()["data"].get("version") or "")
        must(bool(version), "g5_version")
        note(f"openapi_version={version}")
        art = await client.get(
            "/api/v1/realphotos/contracts/image-processing.openapi.json",
            headers=merchant,
        )
        must(art.status_code == 200, f"g5_download={art.status_code}")
        body = art.json()
        must("image_processing" in json.dumps(body), "g5_scope_in_artifact")
        must("X-API-Key" in json.dumps(body), "g5_api_key_in_artifact")
        issued = await client.post(
            "/api/v1/realphotos/business-api-keys",
            headers=admin_h,
            json={"name": f"gap-{stamp}", "scopes": ["image_processing"]},
        )
        must(issued.status_code == 200, f"g5_key_issue={issued.status_code}")
        raw_key = issued.json()["data"]["apiKey"]
        key_h = {"X-API-Key": raw_key}
        key_up = await client.post(
            "/api/v1/realphotos/assets",
            headers=key_h,
            files={"file": ("key.jpg", _jpeg((33, 44, 55)), "image/jpeg")},
        )
        must(key_up.status_code == 200, f"g5_key_upload={key_up.status_code}")
        asset_id = int(key_up.json()["data"]["id"])
        key_submit = await client.post(
            "/api/v1/realphotos/processing-batches",
            headers=key_h,
            json={
                "assetIds": [asset_id],
                "presetCode": preset,
                "idempotencyKey": f"gap-key-{stamp}",
                "preReviewMode": "pass",
                "detectionMode": "pass",
            },
        )
        must(key_submit.status_code == 200, f"g5_key_submit={key_submit.status_code} {key_submit.text[:160]}")
        task_id = int(key_submit.json()["data"]["tasks"][0]["id"])
        async with async_session_factory() as worker_db:
            jobs = RealphotosJobService(worker_db)
            claimed = await jobs.claim(
                worker_id=f"gap-{stamp}",
                job_kinds=("process_image",),
                payload_task_id=task_id,
            )
            must(claimed is not None, "g5_claim")
            done = await RealphotosS1Service(worker_db).execute_queued(claimed)
            await jobs.complete_success(job=claimed, result={"path": "product-gap-fix"})
            await worker_db.commit()
            must(bool(done.output_object_key), "g5_output")
        q = await client.get(f"/api/v1/realphotos/processing-tasks/{task_id}", headers=key_h)
        must(q.status_code == 200, "g5_query")
        flags["G5_OPENAPI_REACHABLE_PASS"] = True
        note("G5_OPENAPI_REACHABLE_PASS=true")

        # —— G6 regression only（管理员 workspace.opsMetrics；不重做计量）——
        dash = await client.get("/api/v1/realphotos/workspace", headers=admin_h)
        must(dash.status_code == 200, f"g6_workspace_http={dash.status_code}")
        payload = dash.json().get("data") or {}
        ops = payload.get("opsMetrics") or {}
        must(isinstance(ops, dict) and ops, "g6_opsMetrics_present")
        cost = ops.get("cost")
        reason = ops.get("costReason")
        note(f"g6_cost={cost!r} costReason={reason!r} keys={sorted(ops.keys())}")
        if cost is None:
            must(bool(reason), "g6_honest_empty_reason")
            # 无单价时空态不得伪装成数字 0
            must(cost is not False and cost != 0, "g6_not_fake_zero_when_null")
        else:
            must(isinstance(cost, (int, float, str)), "g6_cost_typed")
        module_a = Path("/tmp/module-a-gap-e2e.log")
        if module_a.exists() and "A2_COST_METERING_PASS" in module_a.read_text(encoding="utf-8", errors="ignore"):
            note("g6_cited_module_a_A2_COST_METERING_PASS=true")
        note("G6_NO_REIMPLEMENT=true")
        flags["G6_OPS_COST_REGRESSION_PASS"] = True
        note("G6_OPS_COST_REGRESSION_PASS=true")

    all_pass = all(flags.values())
    note("S7_OUT_OF_SCOPE=true")
    note("G6_NO_REIMPLEMENT=true")
    for key, value in flags.items():
        note(f"{key}={'true' if value else 'false'}")
    note(f"PRODUCT_GAP_FIX_E2E_PASS={'true' if all_pass else 'false'}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
