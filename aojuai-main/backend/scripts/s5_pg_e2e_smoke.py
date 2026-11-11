"""S5 growth on the dev-host PostgreSQL.

Fixture generation proves per-image billing and library storage. It does not
call a supplier. Unconfigured generation, prompt optimization, and URL import
must fail before any outbound call. This is not production billing.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import sys
from datetime import UTC, datetime, timedelta

import httpx
from PIL import Image
from sqlalchemy import func, select


async def _main() -> int:
    import app.capabilities.realphotos.models  # noqa: F401
    import app.domain  # noqa: F401
    from app.capabilities.realphotos.models import (
        RealphotosAsset,
        RealphotosCreditReservation,
        RealphotosGenerationTask,
        RealphotosImageTask,
    )
    from app.capabilities.realphotos.openapi_contract import image_processing_contract
    from app.capabilities.realphotos.services.bootstrap import DEFAULT_PASSWORD, bootstrap_s0_accounts
    from app.capabilities.realphotos.services.credit_service import RealphotosCreditService
    from app.capabilities.realphotos.services.job_service import RealphotosJobService
    from app.capabilities.realphotos.services.s1_catalog import S1_ENABLED_PRESETS
    from app.capabilities.realphotos.services.s1_processing import RealphotosS1Service
    from app.capabilities.realphotos.services.s5_growth import RealphotosGrowthService
    from app.core.config import settings
    from app.core.exceptions import BusinessError, UnauthorizedError
    from app.domain.auth.api_key_models import ApiKey
    from app.domain.auth.api_key_service import ApiKeyService
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
        user = int(summary["rp_merchant_a1"]["userId"])
        tenant_b = int(summary["rp_merchant_b1"]["tenantId"])
        user_b = int(summary["rp_merchant_b1"]["userId"])
        growth = RealphotosGrowthService(db)
        credits = RealphotosCreditService(db)
        before = int((await credits.get_wallet(tenant_id=tenant))["availableInteger"])
        reserved_before = int(
            await db.scalar(
                select(func.count())
                .select_from(RealphotosCreditReservation)
                .where(RealphotosCreditReservation.tenant_id == tenant)
            )
            or 0
        )
        stamp = str(int(datetime.now(UTC).timestamp()))
        task = await growth.submit_generation(
            tenant_id=tenant,
            owner_account_id=user,
            mode="text_to_image",
            positive_prompt="s5-fixture",
            width=256,
            height=256,
            quantity=2,
            idempotency_key=f"s5-pg-{stamp}",
            provider="fixture",
            fail_indexes={1},
        )
        items = await growth.list_generation_items(tenant_id=tenant, task_id=int(task.id))
        stored = [item for item in items if item.asset_id]
        assert len(stored) == 1 and int(stored[0].credits_consumed) == 10
        assert any(item.asset_id is None and int(item.credits_consumed) == 0 for item in items)
        after = int((await credits.get_wallet(tenant_id=tenant))["availableInteger"])
        assert after == before - 10
        reserved_after = int(
            await db.scalar(
                select(func.count())
                .select_from(RealphotosCreditReservation)
                .where(RealphotosCreditReservation.tenant_id == tenant)
            )
            or 0
        )
        assert reserved_after == reserved_before
        linked = int(
            await db.scalar(
                select(func.count())
                .select_from(RealphotosImageTask)
                .where(RealphotosImageTask.asset_id == int(stored[0].asset_id))
            )
            or 0
        )
        assert linked == 0
        both = await growth.submit_generation(
            tenant_id=tenant,
            owner_account_id=user,
            mode="text_to_image",
            positive_prompt="s5-two",
            width=256,
            height=256,
            quantity=2,
            idempotency_key=f"s5-two-{stamp}",
            provider="fixture",
        )
        both_items = await growth.list_generation_items(tenant_id=tenant, task_id=int(both.id))
        assert sum(int(item.credits_consumed) for item in both_items) == 20
        assert all(item.asset_id for item in both_items)
        replay_before = int((await credits.get_wallet(tenant_id=tenant))["availableInteger"])
        replay = await growth.submit_generation(
            tenant_id=tenant,
            owner_account_id=user,
            mode="text_to_image",
            positive_prompt="s5-two",
            width=256,
            height=256,
            quantity=2,
            idempotency_key=f"s5-two-{stamp}",
            provider="fixture",
        )
        assert int(replay.id) == int(both.id)
        assert int((await credits.get_wallet(tenant_id=tenant))["availableInteger"]) == replay_before
        eleventh_tasks = int(
            await db.scalar(
                select(func.count())
                .select_from(RealphotosGenerationTask)
                .where(RealphotosGenerationTask.tenant_id == tenant)
            )
            or 0
        )
        eleventh_assets = int(await db.scalar(select(func.count()).select_from(RealphotosAsset)) or 0)
        try:
            await growth.submit_generation(
                tenant_id=tenant,
                owner_account_id=user,
                mode="text_to_image",
                positive_prompt="s5-eleven",
                width=256,
                height=256,
                quantity=11,
                idempotency_key=f"s5-eleven-{stamp}",
                provider="fixture",
            )
            raise RuntimeError("eleventh generation was accepted")
        except BusinessError as exc:
            assert exc.code == "INPUT_INVALID"
        assert int(
            await db.scalar(
                select(func.count())
                .select_from(RealphotosGenerationTask)
                .where(RealphotosGenerationTask.tenant_id == tenant)
            )
            or 0
        ) == eleventh_tasks
        assert int(await db.scalar(select(func.count()).select_from(RealphotosAsset)) or 0) == eleventh_assets
        charge_before = int((await credits.get_wallet(tenant_id=tenant))["availableInteger"])
        original_consume = RealphotosCreditService.consume_available
        seen = {"n": 0}

        async def consume_then_short(self, **kwargs):
            seen["n"] += 1
            if seen["n"] == 2:
                account = await self.get_or_create_account(tenant_id=int(kwargs["tenant_id"]))
                account.available_integer = 9
                await self.db.flush()
            return await original_consume(self, **kwargs)

        RealphotosCreditService.consume_available = consume_then_short
        try:
            short = await growth.submit_generation(
                tenant_id=tenant,
                owner_account_id=user,
                mode="text_to_image",
                positive_prompt="s5-short",
                width=256,
                height=256,
                quantity=2,
                idempotency_key=f"s5-short-{stamp}",
                provider="fixture",
            )
        finally:
            RealphotosCreditService.consume_available = original_consume
        short_items = await growth.list_generation_items(tenant_id=tenant, task_id=int(short.id))
        stored_short = [item for item in short_items if item.asset_id]
        failed_short = [item for item in short_items if item.asset_id is None]
        assert len(stored_short) == 1 and int(stored_short[0].credits_consumed) == 10
        assert len(failed_short) == 1 and int(failed_short[0].credits_consumed) == 0
        charge_now = int((await credits.get_wallet(tenant_id=tenant))["availableInteger"])
        restore_delta = (charge_before - 10) - charge_now
        if restore_delta != 0:
            await credits.admin_adjust(
                tenant_id=tenant,
                delta_available=restore_delta,
                operator_user_id=user,
                reason="端测把扣费中的可用额改小，恢复到只保留成功张的 10 积分",
                event_key=f"s5-restore-short-{stamp}",
            )
        assert int((await credits.get_wallet(tenant_id=tenant))["availableInteger"]) == charge_before - 10
        template_before = int((await credits.get_wallet(tenant_id=tenant))["availableInteger"])
        await growth.save_template(
            tenant_id=tenant,
            owner_account_id=user,
            actor_role_codes={"rp_merchant"},
            name=f"s5-{stamp}",
            mode="general",
            positive_prompt="白底",
        )
        template_after = int((await credits.get_wallet(tenant_id=tenant))["availableInteger"])
        assert template_after == template_before
        try:
            await growth.submit_generation(
                tenant_id=tenant,
                owner_account_id=user,
                mode="text_to_image",
                positive_prompt="live",
                width=256,
                height=256,
                quantity=1,
                idempotency_key=f"s5-live-{stamp}",
            )
            raise RuntimeError("unconfigured generation was accepted")
        except BusinessError as exc:
            assert exc.code == "SERVICE_NOT_CONFIGURED"
        poor = int((await credits.get_wallet(tenant_id=tenant_b))["availableInteger"])
        assert poor == 0
        gen_before = int(
            await db.scalar(
                select(func.count())
                .select_from(RealphotosGenerationTask)
                .where(RealphotosGenerationTask.tenant_id == tenant_b)
            )
            or 0
        )
        try:
            await growth.submit_generation(
                tenant_id=tenant_b,
                owner_account_id=user_b,
                mode="text_to_image",
                positive_prompt="没钱",
                width=256,
                height=256,
                quantity=1,
                idempotency_key=f"s5-poor-{stamp}",
                provider="fixture",
            )
            raise RuntimeError("insufficient generation was accepted")
        except BusinessError as exc:
            assert exc.code == "INSUFFICIENT_CREDITS"
        gen_after = int(
            await db.scalar(
                select(func.count())
                .select_from(RealphotosGenerationTask)
                .where(RealphotosGenerationTask.tenant_id == tenant_b)
            )
            or 0
        )
        assert gen_after == gen_before
        assets_before = int(await db.scalar(select(func.count()).select_from(RealphotosAsset)) or 0)
        try:
            await growth.import_resources(
                payload="\n".join(f"https://example.invalid/{index}.jpg" for index in range(101)),
                tenant_id=tenant,
                owner_account_id=user,
            )
            raise RuntimeError("101st import was accepted")
        except BusinessError as exc:
            assert exc.code == "INPUT_INVALID"
        try:
            await growth.import_resources(
                payload="https://example.invalid/a.jpg",
                tenant_id=tenant,
                owner_account_id=user,
            )
            raise RuntimeError("url import was accepted")
        except BusinessError as exc:
            assert exc.code == "SERVICE_NOT_CONFIGURED"
        assets_after = int(await db.scalar(select(func.count()).select_from(RealphotosAsset)) or 0)
        assert assets_after == assets_before
        opt_before = int((await credits.get_wallet(tenant_id=tenant))["availableInteger"])
        opt = await growth.optimize_prompt(
            tenant_id=tenant,
            owner_account_id=user,
            original_text=f"s5-opt-{stamp}",
            provider="fixture",
        )
        opt_after = int((await credits.get_wallet(tenant_id=tenant))["availableInteger"])
        assert opt.status == "succeeded" and opt_after == opt_before - 1
        quiet = await credits.get_wallet(tenant_id=tenant)
        quiet_available = int(quiet["availableInteger"])
        quiet_reserved = int(quiet["reservedInteger"])
        try:
            await growth.optimize_prompt(
                tenant_id=tenant,
                owner_account_id=user,
                original_text=f"s5-opt-live-{stamp}",
            )
            raise RuntimeError("unconfigured prompt optimization was accepted")
        except BusinessError as exc:
            assert exc.code == "SERVICE_NOT_CONFIGURED"
        failed_opt = await growth.optimize_prompt(
            tenant_id=tenant,
            owner_account_id=user,
            original_text=f"s5-opt-fail-{stamp}",
            provider="fixture",
            succeed=False,
        )
        assert failed_opt.status == "failed"
        quiet_after = await credits.get_wallet(tenant_id=tenant)
        assert int(quiet_after["availableInteger"]) == quiet_available
        assert int(quiet_after["reservedInteger"]) == quiet_reserved
        i2i_before = int(await db.scalar(select(func.count()).select_from(RealphotosAsset)) or 0)
        reference = io.BytesIO()
        Image.new("RGB", (1024, 768), (12, 34, 56)).save(reference, format="JPEG", quality=85)
        i2i = await growth.submit_generation(
            tenant_id=tenant,
            owner_account_id=user,
            mode="image_to_image",
            positive_prompt=f"s5-i2i-{stamp}",
            width=1024,
            height=768,
            quantity=1,
            idempotency_key=f"s5-i2i-{stamp}",
            provider="fixture",
            reference_bytes=reference.getvalue(),
        )
        i2i_items = await growth.list_generation_items(tenant_id=tenant, task_id=int(i2i.id))
        assert len(i2i_items) == 1 and i2i_items[0].asset_id is not None
        i2i_asset = await db.get(RealphotosAsset, int(i2i_items[0].asset_id))
        assert i2i_asset is not None and i2i_asset.origin_kind == "image_to_image"
        i2i_after = int(await db.scalar(select(func.count()).select_from(RealphotosAsset)) or 0)
        assert i2i_after == i2i_before + 1
        assert await growth.processing_task_count_for_assets(
            tenant_id=tenant, asset_ids=[int(i2i_asset.id)]
        ) == 0
        pasted_rows = [
            {
                "name": str(index),
                "seller": "s",
                "sku": "k",
                "asn": "a",
                "price": "1",
                "website": "https://example.invalid",
                "url": f"https://example.invalid/{index}.jpg",
            }
            for index in range(100)
        ]
        json_before = int(await db.scalar(select(func.count()).select_from(RealphotosAsset)) or 0)
        try:
            await growth.import_resources(
                payload=json.dumps(pasted_rows),
                tenant_id=tenant,
                owner_account_id=user,
            )
            raise RuntimeError("100 json import was accepted")
        except BusinessError as exc:
            assert exc.code == "SERVICE_NOT_CONFIGURED"
        try:
            await growth.import_resources(
                payload=json.dumps(pasted_rows + [pasted_rows[0]]),
                tenant_id=tenant,
                owner_account_id=user,
            )
            raise RuntimeError("101 json import was accepted")
        except BusinessError as exc:
            assert exc.code == "INPUT_INVALID"
        json_after = int(await db.scalar(select(func.count()).select_from(RealphotosAsset)) or 0)
        assert json_after == json_before
        _key, plaintext = await ApiKeyService.create_key(
            db, tenant, user, name=f"s5-{stamp}", scopes=["image_processing"]
        )
        expired_row, expired_plain = await ApiKeyService.create_key(
            db, tenant, user, name=f"s5-expired-{stamp}", scopes=["image_processing"], expires_in_days=1
        )
        expired_row.expires_at = datetime.now(UTC) - timedelta(minutes=5)
        _other, other_plain = await ApiKeyService.create_key(
            db, tenant_b, user_b, name=f"s5-b-{stamp}", scopes=["image_processing"]
        )
        _training, training_plain = await ApiKeyService.create_key(
            db, tenant, user, name=f"s5-training-{stamp}", scopes=None
        )
        try:
            await ApiKeyService.create_key(db, tenant, user, name=f"s5-empty-{stamp}", scopes=[])
            raise RuntimeError("empty scope was accepted")
        except BusinessError as exc:
            assert "空" in exc.message or exc.code
        await ApiKeyService.validate_key(db, plaintext, "/api/v1/realphotos/processing-batches")
        try:
            await ApiKeyService.validate_key(db, plaintext, "/api/v1/realphotos/generation-tasks")
            raise RuntimeError("generation path was allowed")
        except UnauthorizedError:
            pass
        await db.commit()
        task_id = int(task.id)
        preset = S1_ENABLED_PRESETS[0]["code"]
        jpeg = io.BytesIO()
        Image.new("RGB", (1024, 768), (40, 60, 80)).save(jpeg, format="JPEG", quality=85)
        headers = {"X-API-Key": plaintext}
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=fastapi_app), base_url="http://test"
        ) as client:
            uploaded = await client.post(
                "/api/v1/realphotos/assets",
                headers=headers,
                files={"file": ("s5.jpg", jpeg.getvalue(), "image/jpeg")},
            )
            assert uploaded.status_code == 200, uploaded.text
            asset_id = int(uploaded.json()["data"]["id"])
            submitted = await client.post(
                "/api/v1/realphotos/processing-batches",
                headers={**headers, "content-type": "application/json"},
                content=json.dumps(
                    {
                        "assetIds": [asset_id],
                        "presetCode": preset,
                        "idempotencyKey": f"s5-key-{stamp}",
                        "detectionMode": "pass",
                    }
                ).encode(),
            )
            assert submitted.status_code == 200, submitted.text
            submitted_task = int(submitted.json()["data"]["tasks"][0]["id"])
            generated = await client.post(
                "/api/v1/realphotos/generation-tasks",
                headers={**headers, "content-type": "application/json"},
                content=b'{"mode":"text_to_image","positivePrompt":"x","width":256,"height":256,"quantity":1,"idempotencyKey":"nope"}',
            )
            assert generated.status_code == 401
            bad = await client.post(
                "/api/v1/realphotos/assets",
                headers={"X-API-Key": "aoju_sk_" + "ab" * 24},
                files={"file": ("s5.jpg", jpeg.getvalue(), "image/jpeg")},
            )
            assert bad.status_code == 401
            expired = await client.get("/api/v1/realphotos/presets", headers={"X-API-Key": expired_plain})
            assert expired.status_code == 401
            training = await client.post(
                "/api/v1/realphotos/assets",
                headers={"X-API-Key": training_plain},
                files={"file": ("s5.jpg", jpeg.getvalue(), "image/jpeg")},
            )
            assert training.status_code == 401
        async with async_session_factory() as worker_db:
            jobs = RealphotosJobService(worker_db)
            loop = RealphotosS1Service(worker_db)
            claimed = await jobs.claim(
                worker_id="s5-pg",
                job_kinds=("process_image",),
                payload_task_id=submitted_task,
            )
            assert claimed is not None
            done = await loop.execute_queued(claimed)
            await jobs.complete_success(job=claimed, result={"path": "s5-key"})
            await worker_db.commit()
            assert done.output_object_key
            output_key = str(done.output_object_key)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=fastapi_app), base_url="http://test"
        ) as client:
            queried = await client.get(
                f"/api/v1/realphotos/processing-tasks/{submitted_task}",
                headers=headers,
            )
            assert queried.status_code == 200, queried.text
            assert queried.json()["data"]["status"] == "DELIVERED"
            other = await client.get(
                f"/api/v1/realphotos/processing-tasks/{submitted_task}",
                headers={"X-API-Key": other_plain},
            )
            assert other.status_code == 404
            picked = await client.post(
                "/api/v1/realphotos/processing-tasks/selected-downloads",
                headers={**headers, "content-type": "application/json"},
                content=json.dumps({"taskIds": [submitted_task], "pack": "files"}).encode(),
            )
            assert picked.status_code == 200, picked.text
            assert picked.json()["data"]["items"][0]["objectKey"] == output_key
            zipped = await client.post(
                "/api/v1/realphotos/processing-tasks/selected-downloads",
                headers={**headers, "content-type": "application/json"},
                content=json.dumps({"taskIds": [submitted_task], "pack": "zip"}).encode(),
            )
            assert zipped.status_code == 400
            downloaded = await client.get(
                "/api/v1/realphotos/gateway/objects/" + output_key,
                headers=headers,
            )
            assert downloaded.status_code == 200, downloaded.text[:200]
            assert downloaded.content.startswith(b"\xff\xd8\xff")
            await ApiKeyService.revoke_key(db, tenant, user, int(_key.id))
            await db.commit()
            revoked = await client.post(
                "/api/v1/realphotos/assets",
                headers=headers,
                files={"file": ("s5.jpg", jpeg.getvalue(), "image/jpeg")},
            )
            assert revoked.status_code == 401

        file_rows = [
            {
                "name": f"file-{index}",
                "seller": "s",
                "sku": "k",
                "asn": "a",
                "price": "1",
                "website": "https://example.invalid",
                "url": f"https://example.invalid/file-{index}.jpg",
            }
            for index in range(100)
        ]
        async with async_session_factory() as count_db:
            file_before = int(await count_db.scalar(select(func.count()).select_from(RealphotosAsset)) or 0)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=fastapi_app), base_url="http://test"
        ) as client:
            challenge = await client.post("/api/v1/realphotos/auth/challenges")
            assert challenge.status_code == 200, challenge.text
            challenge_data = challenge.json()["data"]
            assert challenge_data.get("devCode")
            logged_in = await client.post(
                "/api/v1/realphotos/auth/login",
                json={
                    "username": "rp_merchant_a1",
                    "password": DEFAULT_PASSWORD,
                    "challengeId": challenge_data["challengeId"],
                    "challengeCode": challenge_data["devCode"],
                },
            )
            assert logged_in.status_code == 200, logged_in.text
            session_headers = {"Authorization": "Bearer " + logged_in.json()["data"]["accessToken"]}
            file_ok = await client.post(
                "/api/v1/realphotos/resource-imports/files",
                headers=session_headers,
                files={"file": ("import-100.json", json.dumps(file_rows).encode(), "application/json")},
            )
            assert file_ok.status_code == 400
            assert file_ok.json()["code"] == "SERVICE_NOT_CONFIGURED"
            file_over = await client.post(
                "/api/v1/realphotos/resource-imports/files",
                headers=session_headers,
                files={
                    "file": (
                        "import-101.json",
                        json.dumps(file_rows + [file_rows[0]]).encode(),
                        "application/json",
                    )
                },
            )
            assert file_over.status_code == 400
            assert file_over.json()["code"] == "INPUT_INVALID"
            scope_cases = (
                ({"name": f"s5-omit-{stamp}"}, "omitted"),
                ({"name": f"s5-empty-{stamp}", "scopes": []}, "empty"),
                ({"name": f"s5-wild-{stamp}", "scopes": ["*"]}, "wildcard"),
                ({"name": f"s5-train-{stamp}", "scopes": ["/api/v1/training"]}, "training"),
            )
            for body, _label in scope_cases:
                rejected = await client.post(
                    "/api/v1/realphotos/business-api-keys",
                    headers=session_headers,
                    json=body,
                )
                assert rejected.status_code == 400, rejected.text
                assert rejected.json()["code"] == "SCOPE_REJECTED"
            issued = await client.post(
                "/api/v1/realphotos/business-api-keys",
                headers=session_headers,
                json={"name": f"s5-http-{stamp}", "scopes": ["image_processing"]},
            )
            assert issued.status_code == 200
            issued_data = issued.json()["data"]
            issued_key = str(issued_data["apiKey"])
            issued_id = int(issued_data["id"])
            assert issued_data["scopes"] == ["image_processing"]
            assert issued_key not in str(issued_data["keyPrefix"])
        async with async_session_factory() as check_db:
            stored_key = await check_db.get(ApiKey, issued_id)
            assert stored_key is not None
            assert stored_key.key_hash == hashlib.sha256(issued_key.encode()).hexdigest()
            assert issued_key not in stored_key.key_prefix
            assert stored_key.scopes == ["image_processing"]
            file_after = int(await check_db.scalar(select(func.count()).select_from(RealphotosAsset)) or 0)
            assert file_after == file_before
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=fastapi_app), base_url="http://test"
        ) as client:
            key_headers = {"X-API-Key": issued_key}
            prompt_denied = await client.post(
                "/api/v1/realphotos/prompt-optimizations",
                headers={**key_headers, "content-type": "application/json"},
                content=b'{"originalText":"no"}',
            )
            import_denied = await client.post(
                "/api/v1/realphotos/resource-imports",
                headers={**key_headers, "content-type": "application/json"},
                content=b'{"payload":"https://example.invalid/a.jpg"}',
            )
            create_denied = await client.post(
                "/api/v1/realphotos/business-api-keys",
                headers={**key_headers, "content-type": "application/json"},
                content=b'{"name":"again","scopes":["image_processing"]}',
            )
            delete_denied = await client.delete(
                f"/api/v1/realphotos/business-api-keys/{issued_id}",
                headers=key_headers,
            )
            assert prompt_denied.status_code == 401
            assert import_denied.status_code == 401
            assert create_denied.status_code in {401, 403}
            assert delete_denied.status_code in {401, 403}

    contract = image_processing_contract(fastapi_app.openapi())
    paths = set(contract["paths"])
    assert contract["components"]["securitySchemes"]["ApiKeyAuth"]["name"] == "X-API-Key"
    assert any(path.startswith("/api/v1/realphotos/processing-") for path in paths)
    assert not any("generation-tasks" in path or "resource-imports" in path for path in paths)
    print(
        "S5_PG_E2E_PASS "
        f"task={task_id} stored_credits=10 failed_credits=0 "
        f"reservation_delta=0 processing_tasks_for_asset=0 "
        "unconfigured=SERVICE_NOT_CONFIGURED url_import=SERVICE_NOT_CONFIGURED "
        "url_101=INPUT_INVALID insufficient=rejected_no_generation "
        "two_success_consumed=20 eleventh=INPUT_INVALID "
        "idempotent_replay_no_second_charge=true "
        "charge_time_insufficient_one_image=true template_delta=0 "
        "prompt_opt_credits=1 prompt_fail_no_charge=true "
        "prompt_unconfigured=SERVICE_NOT_CONFIGURED "
        "i2i_temp_not_stored=true i2i_processing_tasks=0 "
        "json_100=SERVICE_NOT_CONFIGURED json_101=INPUT_INVALID "
        "json_file_100=SERVICE_NOT_CONFIGURED json_file_101=INPUT_INVALID "
        "business_key_issued_via_http=true business_key_scope_rejected=SCOPE_REJECTED "
        "key_prompt_rejected=401 key_import_rejected=401 "
        "key_manage_rejected=true "
        "key_upload_submit_query_download=true query_status=DELIVERED "
        "key_generation_rejected=true revoked=401 expired=401 training_scope=401 "
        "cross_tenant=404 empty_scope=rejected zip=rejected detection_mode=pass "
        "openapi_header=X-API-Key supplier_connected=false production_billing=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
