"""S6 ops on the dev-host PostgreSQL.

Fixture verdicts are in-process. They are not a connected supplier and not
production billing. This script does not call Qwen, Gemini, or a public URL.
"""

from __future__ import annotations

import asyncio
import io
import sys
from datetime import UTC, datetime, timedelta

import httpx
from PIL import Image
from sqlalchemy import func, select


def _jpeg(color: tuple[int, int, int]) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (1024, 768), color).save(buf, format="JPEG", quality=85)
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


async def _main() -> int:
    import app.capabilities.realphotos.models  # noqa: F401
    import app.domain  # noqa: F401
    from app.capabilities.realphotos.api.s1 import BatchBody
    from app.capabilities.realphotos.models import (
        RealphotosAccountLog,
        RealphotosAuthGuard,
        RealphotosContentReview,
        RealphotosCreditLedgerEntry,
        RealphotosImageTask,
        RealphotosMerchantProfile,
        RealphotosPresetVersion,
        RealphotosSupportTicket,
    )
    from app.capabilities.realphotos.permissions import ROLE_ADMIN
    from app.capabilities.realphotos.seed import reconcile
    from app.capabilities.realphotos.services.bootstrap import DEFAULT_PASSWORD, bootstrap_s0_accounts
    from app.capabilities.realphotos.services.credit_service import RealphotosCreditService
    from app.capabilities.realphotos.services.job_service import RealphotosJobService
    from app.capabilities.realphotos.services.s1_catalog import S1_ENABLED_PRESETS
    from app.capabilities.realphotos.services.s1_processing import RealphotosS1Service
    from app.core.config import settings
    from app.domain.users.models import User
    from app.infrastructure.database.session import Base, async_session_factory, engine, init_db
    from app.main import app as fastapi_app

    if not str(settings.DB_DIALECT).startswith("postgres"):
        print(f"FAIL: expected postgresql, got {settings.DB_DIALECT!r}", file=sys.stderr)
        return 2

    await init_db()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as db:
        summary = await bootstrap_s0_accounts(db)
        tenant = int(summary["rp_merchant_a1"]["tenantId"])
        tenant_b = int(summary["rp_merchant_b1"]["tenantId"])
        platform = int(summary["rp_admin"]["tenantId"])
        user = int(summary["rp_merchant_a1"]["userId"])
        await reconcile(db, tenant_id=platform)
        await reconcile(db, tenant_id=tenant)
        await db.commit()
        credits = RealphotosCreditService(db)
        available_before = int((await credits.get_wallet(tenant_id=tenant))["availableInteger"])
        reserved_before = int((await credits.get_wallet(tenant_id=tenant))["reservedInteger"])
        tenant_b_before = int((await credits.get_wallet(tenant_id=tenant_b))["availableInteger"])
        history = (
            await db.execute(
                select(RealphotosImageTask.id).where(
                    RealphotosImageTask.tenant_id == tenant,
                    RealphotosImageTask.owner_account_id == user,
                    RealphotosImageTask.deleted_at.is_(None),
                    RealphotosImageTask.id != 29,
                ).limit(1)
            )
        ).scalar_one()

    preset_code = S1_ENABLED_PRESETS[0]["code"]
    stamp = str(int(datetime.now(UTC).timestamp()))
    password = "S6Pg@" + stamp
    transport = httpx.ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        merchant = await _login(client, "rp_merchant_a1", DEFAULT_PASSWORD)
        tech = await _login(client, "rp_tech_support", DEFAULT_PASSWORD)
        admin = await _login(client, "rp_admin", DEFAULT_PASSWORD)
        support = await _login(client, "rp_order_support", DEFAULT_PASSWORD)

        reviews_before = 0
        async with async_session_factory() as db:
            reviews_before = int(await db.scalar(select(func.count()).select_from(RealphotosContentReview)) or 0)
        unconfigured = await client.post(
            "/api/v1/realphotos/content-reviews",
            headers=merchant,
            files={"file": ("a.jpg", _jpeg((1, 2, 3)), "image/jpeg")},
            data={"subject": "processing", "provider": "unconfigured", "verdict": "reject"},
        )
        assert unconfigured.status_code == 400
        assert unconfigured.json()["code"] == "SERVICE_NOT_CONFIGURED"
        tiny = io.BytesIO()
        Image.new("RGB", (8, 8), (1, 1, 1)).save(tiny, format="JPEG")
        hard = await client.post(
            "/api/v1/realphotos/content-reviews",
            headers=merchant,
            files={"file": ("tiny.jpg", tiny.getvalue(), "image/jpeg")},
            data={"subject": "processing", "provider": "fixture", "verdict": "reject"},
        )
        assert hard.status_code == 400
        async with async_session_factory() as db:
            assert int(await db.scalar(select(func.count()).select_from(RealphotosContentReview)) or 0) == reviews_before

        uncertain = await client.post(
            "/api/v1/realphotos/content-reviews",
            headers=merchant,
            files={"file": ("u.jpg", _jpeg((8, 8, 8)), "image/jpeg")},
            data={"subject": "processing", "provider": "fixture", "verdict": "uncertain"},
        )
        assert uncertain.status_code == 200
        assert uncertain.json()["data"]["passed"] is False
        passed = await client.post(
            "/api/v1/realphotos/content-reviews",
            headers=merchant,
            files={"file": ("p.jpg", _jpeg((4, 5, 6)), "image/jpeg")},
            data={"subject": "processing", "provider": "fixture", "verdict": "pass"},
        )
        assert passed.status_code == 200 and passed.json()["data"]["passed"] is True
        image_a = _jpeg((11, 22, 33))
        first = await client.post(
            "/api/v1/realphotos/content-reviews",
            headers=merchant,
            files={"file": ("a.jpg", image_a, "image/jpeg")},
            data={"subject": "processing", "provider": "fixture", "verdict": "reject"},
        )
        second = await client.post(
            "/api/v1/realphotos/content-reviews",
            headers=merchant,
            files={"file": ("a.jpg", image_a, "image/jpeg")},
            data={"subject": "processing", "provider": "fixture", "verdict": "reject"},
        )
        assert first.json()["data"]["locked"] is False
        assert second.json()["data"]["locked"] is True
        assert second.json()["data"]["frozen"] is False
        last = None
        for color in ((30, 0, 0), (0, 30, 0), (0, 0, 30)):
            last = await client.post(
                "/api/v1/realphotos/content-reviews",
                headers=merchant,
                files={"file": ("c.jpg", _jpeg(color), "image/jpeg")},
                data={"subject": "processing", "provider": "fixture", "verdict": "reject"},
            )
            assert last.status_code == 200
        assert last is not None and last.json()["data"]["frozen"] is True
        ref = _jpeg((70, 70, 70))
        other = await _login(client, "rp_merchant_a2", DEFAULT_PASSWORD)
        await client.post(
            "/api/v1/realphotos/content-reviews",
            headers=other,
            files={"file": ("r.jpg", ref, "image/jpeg")},
            data={"subject": "reference", "provider": "fixture", "verdict": "reject"},
        )
        ref_again = await client.post(
            "/api/v1/realphotos/content-reviews",
            headers=other,
            files={"file": ("r.jpg", ref, "image/jpeg")},
            data={"subject": "reference", "provider": "fixture", "verdict": "reject"},
        )
        assert ref_again.json()["data"]["locked"] is True
        assert ref_again.json()["data"]["frozen"] is False

        viewed = await client.get(f"/api/v1/realphotos/processing-tasks/{int(history)}", headers=merchant)
        assert viewed.status_code == 200
        blocked = await client.post(
            "/api/v1/realphotos/processing-batches",
            headers=merchant,
            json={
                "assetIds": [1],
                "presetCode": preset_code,
                "idempotencyKey": f"s6-frozen-{stamp}",
                "detectionMode": "pass",
            },
        )
        assert blocked.status_code == 400
        assert blocked.json()["code"] == "ACCOUNT_FROZEN"
        still_in = await _login(client, "rp_merchant_a1", DEFAULT_PASSWORD)
        assert still_in["Authorization"].startswith("Bearer ")

        async with async_session_factory() as db:
            guard = (
                await db.execute(
                    select(RealphotosAuthGuard).where(RealphotosAuthGuard.username_normalized == "rp_merchant_a1")
                )
            ).scalar_one_or_none()
            previous_lock = None if guard is None else guard.locked_until
            locked_until = datetime.now(UTC) + timedelta(minutes=30)
            if guard is None:
                guard = RealphotosAuthGuard(username_normalized="rp_merchant_a1", locked_until=locked_until)
                db.add(guard)
            else:
                guard.locked_until = locked_until
            await db.commit()
        unfrozen = await client.post(
            "/api/v1/realphotos/account-freezes/release",
            headers=tech,
            json={"userId": user, "tenantId": tenant, "reason": "端测解除预审冻结"},
        )
        assert unfrozen.status_code == 200
        async with async_session_factory() as db:
            kept = (
                await db.execute(
                    select(RealphotosAuthGuard).where(RealphotosAuthGuard.username_normalized == "rp_merchant_a1")
                )
            ).scalar_one()
            assert kept.locked_until == locked_until
            kept.locked_until = previous_lock
            await db.commit()
            profile = (
                await db.execute(
                    select(RealphotosMerchantProfile).where(RealphotosMerchantProfile.user_id == user)
                )
            ).scalar_one()
            assert profile.pre_review_frozen is False

        async with async_session_factory() as db:
            loop = RealphotosS1Service(db)
            asset = await loop.upload(tenant_id=tenant, owner_account_id=user, data=_jpeg((90, 90, 90)))
            _batch, tasks = await loop.submit_batch(
                tenant_id=tenant,
                owner_account_id=user,
                actor_role_codes={ROLE_ADMIN},
                asset_ids=[int(asset.id)],
                preset_code=preset_code,
                idempotency_key=f"s6-held-{stamp}",
                detection_mode="technical",
            )
            jobs = RealphotosJobService(db)
            claimed = await jobs.claim(
                worker_id="s6-pg", job_kinds=("process_image",), payload_task_id=int(tasks[0].id)
            )
            done = await loop.execute_queued(claimed)
            await db.commit()
            held_id = int(done.id)
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
        assert denied_support.status_code == 403
        assert denied_merchant.status_code == 403
        released = await client.post(
            f"/api/v1/realphotos/held-credits/{held_id}/release",
            headers=tech,
            json={"tenantId": tenant, "reason": "技术客服审计释放"},
        )
        assert released.status_code == 200
        assert released.json()["data"]["disposition"] == "released_tech_audit"

        created = await client.post(
            "/api/v1/realphotos/managed-users",
            headers=tech,
            json={
                "tenantId": tenant,
                "username": f"rp_s6_{stamp}",
                "password": password,
                "roleCode": "rp_merchant",
            },
        )
        assert created.status_code == 200
        created_id = int(created.json()["data"]["id"])
        decimal = await client.post(
            "/api/v1/realphotos/managed-users/credits",
            headers=admin,
            json={"tenantId": tenant, "userId": created_id, "delta": 1.5, "reason": "小数", "eventKey": f"s6-dec-{stamp}"},
        )
        assert decimal.status_code == 422
        plus = await client.post(
            "/api/v1/realphotos/managed-users/credits",
            headers=admin,
            json={"tenantId": tenant, "userId": created_id, "delta": 1, "reason": "整数加一", "eventKey": f"s6-plus-{stamp}"},
        )
        minus = await client.post(
            "/api/v1/realphotos/managed-users/credits",
            headers=admin,
            json={"tenantId": tenant, "userId": created_id, "delta": -1, "reason": "整数减一", "eventKey": f"s6-minus-{stamp}"},
        )
        assert plus.status_code == 200 and minus.status_code == 200
        roles = await client.post(
            f"/api/v1/realphotos/managed-users/{created_id}/roles",
            headers=admin,
            json={"tenantId": tenant, "roleCodes": ["rp_merchant"]},
        )
        status = await client.post(
            f"/api/v1/realphotos/managed-users/{created_id}/status",
            headers=admin,
            json={"enabled": False},
        )
        mismatch = await client.post(
            f"/api/v1/realphotos/managed-users/{created_id}/password",
            headers=tech,
            json={"password": password, "confirm": "other"},
        )
        reset = await client.post(
            f"/api/v1/realphotos/managed-users/{created_id}/password",
            headers=tech,
            json={"password": password, "confirm": password},
        )
        bad_delete = await client.post(
            f"/api/v1/realphotos/managed-users/{created_id}/delete",
            headers=admin,
            json={"confirmUsername": "wrong"},
        )
        deleted = await client.post(
            f"/api/v1/realphotos/managed-users/{created_id}/delete",
            headers=admin,
            json={"confirmUsername": f"rp_s6_{stamp}"},
        )
        assert roles.status_code == 200
        assert status.status_code == 200
        assert mismatch.status_code == 400
        assert reset.status_code == 200
        assert bad_delete.status_code == 400
        assert deleted.status_code == 200
        merchant_users = await client.get("/api/v1/realphotos/managed-users", headers=merchant)
        support_users = await client.get("/api/v1/realphotos/managed-users", headers=support)
        assert merchant_users.status_code == 403
        assert support_users.status_code == 403
        listed = await client.get("/api/v1/realphotos/managed-users", headers=tech)
        logs = await client.get("/api/v1/realphotos/account-logs", headers=admin)
        assert listed.status_code == 200 and listed.json()["data"]["pageSize"] == 10
        assert logs.status_code == 200 and logs.json()["data"]["pageSize"] == 20
        assert password not in logs.text
        actions = {item["action"] for item in logs.json()["data"]["items"]}
        assert actions <= {"create", "credit", "permission", "status", "reset_password", "delete"}
        assert all(item.get("createdAt") for item in logs.json()["data"]["items"])

        try:
            disabled = await client.post(
                f"/api/v1/realphotos/device-presets/{preset_code}/enabled",
                headers=admin,
                json={"enabled": False},
            )
            assert disabled.status_code == 200
            hidden = await client.get("/api/v1/realphotos/presets", headers=merchant)
            assert hidden.status_code == 200
            assert preset_code not in {item["code"] for item in hidden.json()["data"]["items"]}
            customer = await client.post(
                "/api/v1/realphotos/device-presets",
                headers=merchant,
                json={"code": f"s6-no-{stamp}", "brand": "Honeybadger", "model": "HB-No", "gpsMode": "none"},
            )
            assert customer.status_code == 403
        finally:
            enabled = await client.post(
                f"/api/v1/realphotos/device-presets/{preset_code}/enabled",
                headers=admin,
                json={"enabled": True},
            )
            assert enabled.status_code == 200
        imports = await client.get("/api/v1/realphotos/device-preset-imports", headers=admin)
        assert imports.status_code == 200 and imports.json()["data"]["importedBrands"] == []
        assert "gps" not in BatchBody.model_fields
        metrics = await client.get("/api/v1/realphotos/ops-metrics", headers=admin)
        assert metrics.status_code == 200
        body = metrics.json()["data"]
        assert body["merchantCards"] is False
        assert body["cost"] is None and body["modelCalls"] is None
        assert "一条任务链" not in metrics.text
        tech_metrics = await client.get("/api/v1/realphotos/ops-metrics", headers=tech)
        assert tech_metrics.status_code == 403

    async with async_session_factory() as db:
        credits = RealphotosCreditService(db)
        available_after = int((await credits.get_wallet(tenant_id=tenant))["availableInteger"])
        reserved_after = int((await credits.get_wallet(tenant_id=tenant))["reservedInteger"])
        tenant_b_after = int((await credits.get_wallet(tenant_id=tenant_b))["availableInteger"])
        assert available_after == available_before
        assert reserved_after == reserved_before
        assert tenant_b_after == tenant_b_before
        ledger = (
            await db.execute(
                select(RealphotosCreditLedgerEntry).where(
                    RealphotosCreditLedgerEntry.event_key == f"tech-release:{held_id}"
                )
            )
        ).scalar_one()
        assert int(ledger.delta_available) == 10
        assert isinstance(int(ledger.delta_available), int)
        user_row = await db.get(User, created_id)
        assert user_row is not None and user_row.password_hash != password
        logs_with_secret = int(
            await db.scalar(
                select(func.count())
                .select_from(RealphotosAccountLog)
                .where(RealphotosAccountLog.reason.contains(password))
            )
            or 0
        )
        assert logs_with_secret == 0
        versions = int(
            await db.scalar(
                select(func.count())
                .select_from(RealphotosPresetVersion)
                .where(RealphotosPresetVersion.preset_code == preset_code)
            )
            or 0
        )
        tickets = int(await db.scalar(select(func.count()).select_from(RealphotosSupportTicket)) or 0)
        assert versions >= 1 and tickets >= 1

    print(
        "S6_PG_E2E_PASS "
        "pre_review_reject_no_charge=true uncertain_passed=false unconfigured=SERVICE_NOT_CONFIGURED "
        "second_lock=true third_distinct_freezes=true pass_resets=true reference_lock_only=true "
        "frozen_cannot_create=true frozen_can_view_history=true frozen_can_login=true "
        "password_lock_kept=true tech_release=released_tech_audit support_release=403 merchant_release=403 "
        "ledger_integer=true user_admin=true password_not_in_log=true merchant_users=403 support_users=403 "
        "log_page_size=20 user_page_size=10 preset_disabled_hidden=true preset_reenabled=true "
        "customer_preset=403 gps_not_on_batch=true imports_empty=true metrics_no_merchant_cards=true "
        "cost_empty=true model_calls_empty=true tech_metrics=403 "
        "supplier_connected=false production_billing=false"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(_main()))
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
