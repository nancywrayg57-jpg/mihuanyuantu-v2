"""One live request per configured duty on the dev-host PostgreSQL.

Import stays unconfigured. This is not production billing and does not call Gemini.
Secrets are never written to the log.
"""

from __future__ import annotations

import asyncio
import json
import re
import socket
from datetime import UTC, datetime
from pathlib import Path

import httpx
from sqlalchemy import func, select

LOG_PATH = Path("/tmp/supplier-live-e2e.log")
IMAGE_PATH = Path("/home/hbs/hbs-projects/mihuanyuantu-v2/测试用/测试图/AI生图-即梦-0001.png")
LINES: list[str] = []


def _scrub(text: str) -> str:
    from app.capabilities.realphotos.services.supplier_clients import redact

    cleaned = redact(text or "")
    cleaned = re.sub(r"aoju_sk_[0-9a-fA-F]+", "aoju_sk_redacted", cleaned)
    return cleaned


def note(line: str) -> None:
    LINES.append(_scrub(line))
    LOG_PATH.write_text("\n".join(LINES) + "\n", encoding="utf-8")


def _body(response: httpx.Response) -> dict:
    try:
        payload = response.json()
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


async def _login(client: httpx.AsyncClient, username: str, password: str) -> dict[str, str]:
    challenge = await client.post("/api/v1/realphotos/auth/challenges")
    if challenge.status_code != 200 or not challenge.json().get("data", {}).get("devCode"):
        raise RuntimeError("dev captcha unavailable")
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
    if logged_in.status_code != 200:
        raise RuntimeError(f"login failed status={logged_in.status_code}")
    return {"Authorization": "Bearer " + logged_in.json()["data"]["accessToken"]}


async def _wallet(factory, tenant_id: int) -> tuple[int, int]:
    from app.capabilities.realphotos.services.credit_service import RealphotosCreditService

    async with factory() as db:
        data = await RealphotosCreditService(db).get_wallet(tenant_id=int(tenant_id))
    return int(data["availableInteger"]), int(data["reservedInteger"])


async def _counts(factory, tenant_id: int) -> tuple[int, int]:
    from app.capabilities.realphotos.models import RealphotosAsset, RealphotosImageTask

    async with factory() as db:
        assets = int(
            await db.scalar(
                select(func.count())
                .select_from(RealphotosAsset)
                .where(RealphotosAsset.tenant_id == int(tenant_id), RealphotosAsset.deleted_at.is_(None))
            )
            or 0
        )
        tasks = int(
            await db.scalar(
                select(func.count())
                .select_from(RealphotosImageTask)
                .where(RealphotosImageTask.tenant_id == int(tenant_id), RealphotosImageTask.deleted_at.is_(None))
            )
            or 0
        )
    return assets, tasks


async def _main() -> int:
    import app.capabilities.realphotos.models  # noqa: F401
    import app.domain  # noqa: F401
    from app.capabilities.realphotos.models import RealphotosAsset, RealphotosGenerationItem
    from app.capabilities.realphotos.seed import reconcile
    from app.capabilities.realphotos.services.bootstrap import DEFAULT_PASSWORD, bootstrap_s0_accounts
    from app.capabilities.realphotos.services.job_service import RealphotosJobService
    from app.capabilities.realphotos.services.s1_catalog import S1_ENABLED_PRESETS
    from app.capabilities.realphotos.services.s1_processing import RealphotosS1Service
    from app.capabilities.realphotos.services.s1_upload import inspect_upload
    from app.capabilities.realphotos.services.supplier_material import material_paths, read_material_secret
    from app.core.config import settings
    from app.domain.auth.api_key_service import IMAGE_PROCESSING_PREFIXES, ApiKeyService
    from app.domain.users.models import User
    from app.infrastructure.database.session import Base, async_session_factory, engine, init_db
    from app.main import app as fastapi_app

    note("supplier_live_e2e start")
    note("production_billing=false public_detection_pass_claim=false s7_started=false")
    note("s6_rerun=false")
    s6_log = Path("/tmp/s6-pg-e2e.log")
    s6_text = s6_log.read_text(encoding="utf-8") if s6_log.is_file() else ""
    note(f"s6_log_has_pass={'S6_PG_E2E_PASS' in s6_text}")
    note(
        "gaps generation=aoju https://apis.aoju.ai/v1 sample_model=gpt-image-2 seed=not-sent "
        "result=pending-response official_openai=not-used"
    )
    note("gaps prompt_opt=deepseek sample_model=deepseek-chat single_request=true truncate=false")
    note("gaps pre_review=dashscope sample_model=qwen3-vl-plus hard_check=outside-model")
    note("gaps import=T03-missing formal_supplier=false temp_host_not_used=true no_public_fetch=true")
    note("gaps final_detector=out-of-scope gemini_called=false")
    note("account_scope=platform-process-reads-gitignored-material customer_key=rejected business_key=rejected")
    note("supplier_fee=not-stated-in-生产物料 supplier_terms=not-stated-in-生产物料")
    note(f"host={socket.gethostname()} db_dialect={settings.DB_DIALECT}")
    if not str(settings.DB_DIALECT).startswith("postgres"):
        note("FAIL db is not postgresql")
        return 2
    for path in material_paths():
        note(f"material_path={path} exists={path.is_file()}")
    for duty in ("generation", "prompt_opt", "pre_review"):
        present = bool(read_material_secret(duty))
        note(f"credential_present duty={duty} present={present}")
        if not present:
            note(f"abort missing credential for {duty}; no outbound call")
            return 2
    if not IMAGE_PATH.is_file():
        note(f"abort missing image {IMAGE_PATH.name}")
        return 2
    image = IMAGE_PATH.read_bytes()
    inspected = inspect_upload(image)
    note(f"hard_check_image={IMAGE_PATH.name} width={inspected['width']} height={inspected['height']} bytes={len(image)}")

    try:
        async with httpx.AsyncClient(timeout=20.0) as geo:
            looked = await geo.get("https://ipinfo.io/json")
        payload = looked.json() if looked.status_code == 200 else {}
        country = str(payload.get("country") or "")
        note(
            f"egress_http={looked.status_code} country={country or 'unknown'} "
            f"region={payload.get('region') or 'unknown'} final_mainland_china_node="
            f"{'yes' if country == 'CN' else 'no' if country else 'unknown'}"
        )
    except Exception as exc:
        note(f"egress_lookup_failed={type(exc).__name__} final_mainland_china_node=unknown")
    note("network_path=this-dev-host egress to apis.aoju.ai api.deepseek.com dashscope.aliyuncs.com; import has no hop")

    await init_db()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_session_factory() as db:
        summary = await bootstrap_s0_accounts(db)
        tenant = int(summary["rp_merchant_a1"]["tenantId"])
        tenant_b = int(summary["rp_merchant_b1"]["tenantId"])
        platform = int(summary["rp_admin"]["tenantId"])
        await reconcile(db, tenant_id=platform)
        await reconcile(db, tenant_id=tenant)
        await db.commit()
        merchant = (
            await db.execute(select(User.id).where(User.username == "rp_merchant_a1"))
        ).scalar_one()
    note(f"tenant_a={tenant} tenant_b={tenant_b}")
    before_b = await _wallet(async_session_factory, tenant_b)
    before_a = await _wallet(async_session_factory, tenant)
    assets_before, tasks_before = await _counts(async_session_factory, tenant)
    note(f"wallet_a_before available={before_a[0]} reserved={before_a[1]}")
    note(f"wallet_b_before available={before_b[0]} reserved={before_b[1]}")
    note(f"counts_before assets={assets_before} processing_tasks={tasks_before}")

    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    blocked = (
        "/api/v1/realphotos/generation-tasks",
        "/api/v1/realphotos/prompt-optimizations",
        "/api/v1/realphotos/resource-imports",
        "/api/v1/realphotos/provider-contracts",
    )
    for path in blocked:
        note(f"business_key_prefix_excluded path={path} excluded={path not in IMAGE_PROCESSING_PREFIXES}")

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=fastapi_app), base_url="http://test", timeout=180.0) as client:
        merchant_headers = await _login(client, "rp_merchant_a1", DEFAULT_PASSWORD)
        support_headers = await _login(client, "rp_order_support", DEFAULT_PASSWORD)
        admin_headers = await _login(client, "rp_admin", DEFAULT_PASSWORD)
        other_headers = await _login(client, "rp_merchant_b1", DEFAULT_PASSWORD)

        async with async_session_factory() as db:
            user = (await db.execute(select(User).where(User.username == "rp_merchant_a1"))).scalar_one()
            _row, plaintext = await ApiKeyService.create_key(
                db, tenant, int(user.id), name=f"supplier-live-{stamp}", scopes=["image_processing"]
            )
            await db.commit()
        for path in blocked:
            denied = await client.post(path, headers={"X-API-Key": plaintext}, json={"payload": "https://example.invalid/a.jpg"})
            note(f"business_key_http path={path} status={denied.status_code}")
        merchant_contracts = await client.get("/api/v1/realphotos/provider-contracts", headers=merchant_headers)
        support_contracts = await client.get("/api/v1/realphotos/provider-contracts", headers=support_headers)
        note(f"merchant_contracts={merchant_contracts.status_code} order_support_contracts={support_contracts.status_code}")
        admin_contracts = await client.get("/api/v1/realphotos/provider-contracts", headers=admin_headers)
        admin_body = _body(admin_contracts).get("data") or {}
        items = admin_body.get("items") if isinstance(admin_body, dict) else None
        serialized = json.dumps(items, ensure_ascii=False) if items is not None else ""
        note(f"admin_contracts={admin_contracts.status_code} secret_in_list={'sk-' in serialized}")
        if isinstance(items, list):
            for item in items:
                note(
                    "contract duty={duty} provider={provider} modelId={modelId} version={configVersion} "
                    "region={region} credentialRef={credentialRef} enabled={enabled} gap={gapNote}".format(**item)
                )
        rejected_key = await client.post(
            "/api/v1/realphotos/provider-contracts",
            headers=admin_headers,
            json={"duty": "generation", "modelId": "gpt-image-2", "apiKey": "rejected-input"},
        )
        note(f"admin_raw_key_rejected status={rejected_key.status_code} code={_body(rejected_key).get('code')}")

        short = await client.post(
            "/api/v1/realphotos/generation-tasks",
            headers={**other_headers, "content-type": "application/json"},
            content=json.dumps(
                {
                    "mode": "text_to_image",
                    "positivePrompt": "一张空桌面",
                    "width": 1024,
                    "height": 768,
                    "quantity": 1,
                    "idempotencyKey": f"supplier-short-{stamp}",
                }
            ).encode(),
        )
        note(f"tenant_b_generation status={short.status_code} code={_body(short).get('code')}")

        text_key = f"supplier-t2i-{stamp}"
        text = await client.post(
            "/api/v1/realphotos/generation-tasks",
            headers={**merchant_headers, "content-type": "application/json"},
            content=json.dumps(
                {
                    "mode": "text_to_image",
                    "positivePrompt": "一张干净的木桌，桌上有一只白瓷杯",
                    "width": 1024,
                    "height": 768,
                    "quantity": 1,
                    "idempotencyKey": text_key,
                }
            ).encode(),
        )
        text_data = (_body(text).get("data") or {}) if text.status_code == 200 else {}
        supplier = text_data.get("supplier") if isinstance(text_data, dict) else None
        note(
            f"text_to_image status={text.status_code} code={_body(text).get('code')} "
            f"message={_body(text).get('message') or ''} supplier={json.dumps(supplier, ensure_ascii=False) if supplier else _body(text).get('details')}"
        )
        text_id = int(text_data["id"]) if text.status_code == 200 and text_data.get("id") else None
        if text_id is not None:
            replay = await client.post(
                "/api/v1/realphotos/generation-tasks",
                headers={**merchant_headers, "content-type": "application/json"},
                content=json.dumps(
                    {
                        "mode": "text_to_image",
                        "positivePrompt": "一张干净的木桌，桌上有一只白瓷杯",
                        "width": 1024,
                        "height": 768,
                        "quantity": 1,
                        "idempotencyKey": text_key,
                    }
                ).encode(),
            )
            replay_id = (_body(replay).get("data") or {}).get("id")
            note(f"text_to_image_replay status={replay.status_code} same_id={str(replay_id) == str(text_id)}")

        image_call = await client.post(
            "/api/v1/realphotos/generation-tasks",
            headers=merchant_headers,
            data={
                "mode": "image_to_image",
                "positivePrompt": "保持杯子，背景改成浅灰墙",
                "width": "1024",
                "height": "768",
                "quantity": "1",
                "idempotencyKey": f"supplier-i2i-{stamp}",
            },
            files={"reference": (IMAGE_PATH.name, image, "image/png")},
        )
        image_data = (_body(image_call).get("data") or {}) if image_call.status_code == 200 else {}
        image_supplier = image_data.get("supplier") if isinstance(image_data, dict) else None
        note(
            f"image_to_image status={image_call.status_code} code={_body(image_call).get('code')} "
            f"message={_body(image_call).get('message') or ''} "
            f"supplier={json.dumps(image_supplier, ensure_ascii=False) if image_supplier else _body(image_call).get('details')}"
        )

        prompt = await client.post(
            "/api/v1/realphotos/prompt-optimizations",
            headers=merchant_headers,
            json={"originalText": "木桌上的白瓷杯，晨光，浅景深"},
        )
        prompt_data = (_body(prompt).get("data") or {}) if prompt.status_code == 200 else {}
        optimized = str(prompt_data.get("optimizedText") or "")
        note(
            f"prompt_opt status={prompt.status_code} row_status={prompt_data.get('status')} "
            f"code={_body(prompt).get('code')} original_present={bool(prompt_data.get('originalText'))} "
            f"optimized_present={bool(optimized)} optimized_length={len(optimized)} "
            f"supplier={json.dumps(prompt_data.get('supplier'), ensure_ascii=False)}"
        )

        imported = await client.post(
            "/api/v1/realphotos/resource-imports",
            headers=merchant_headers,
            json={"payload": "https://example.invalid/a.jpg"},
        )
        too_many = "\n".join(f"https://example.invalid/{index}.jpg" for index in range(101))
        rejected = await client.post(
            "/api/v1/realphotos/resource-imports",
            headers=merchant_headers,
            json={"payload": too_many},
        )
        note(f"import_one status={imported.status_code} code={_body(imported).get('code')}")
        note(f"import_101 status={rejected.status_code} code={_body(rejected).get('code')}")
        note("import_outbound=false temp_image_host_used=false")

        uploaded = await client.post(
            "/api/v1/realphotos/assets",
            headers=merchant_headers,
            files={"file": (IMAGE_PATH.name, image, "image/png")},
        )
        upload_id = (_body(uploaded).get("data") or {}).get("id") if uploaded.status_code == 200 else None
        note(f"processing_upload status={uploaded.status_code} asset_id={upload_id}")
        if upload_id:
            submitted = await client.post(
                "/api/v1/realphotos/processing-batches",
                headers=merchant_headers,
                json={
                    "assetIds": [int(upload_id)],
                    "presetCode": S1_ENABLED_PRESETS[0]["code"],
                    "idempotencyKey": f"supplier-review-{stamp}",
                    "detectionMode": "pass",
                },
            )
            task_payload = ((_body(submitted).get("data") or {}).get("tasks") or [{}])[0]
            task_id = task_payload.get("id")
            note(f"processing_submit status={submitted.status_code} task_id={task_id} code={_body(submitted).get('code')}")
            if task_id:
                async with async_session_factory() as worker_db:
                    claimed = await RealphotosJobService(worker_db).claim(
                        worker_id="supplier-live",
                        job_kinds=("process_image",),
                        payload_task_id=int(task_id),
                    )
                    if claimed is None:
                        note("processing_worker=no_job")
                    else:
                        done = await RealphotosS1Service(worker_db).execute_queued(claimed)
                        trace = getattr(done, "supplier_trace", None)
                        note(
                            f"processing_pre_review status={done.status} failure_class={done.failure_class} "
                            f"credit_disposition={done.credit_disposition} detection_mode={done.detection_mode} "
                            f"supplier={json.dumps(trace, ensure_ascii=False)}"
                        )
                        await worker_db.commit()

    assets_after, tasks_after = await _counts(async_session_factory, tenant)
    after_a = await _wallet(async_session_factory, tenant)
    after_b = await _wallet(async_session_factory, tenant_b)
    note(f"wallet_a_after available={after_a[0]} reserved={after_a[1]}")
    note(f"wallet_b_after available={after_b[0]} reserved={after_b[1]} unchanged={after_b == before_b}")
    note(f"counts_after assets={assets_after} processing_tasks={tasks_after}")
    async with async_session_factory() as db:
        if text_id is not None:
            rows = (
                await db.execute(
                    select(RealphotosGenerationItem).where(RealphotosGenerationItem.task_id == int(text_id))
                )
            ).scalars().all()
            for row in rows:
                asset = await db.get(RealphotosAsset, int(row.asset_id)) if row.asset_id else None
                note(
                    f"text_item index={row.item_index} status={row.status} credits={row.credits_consumed} "
                    f"asset_id={row.asset_id} origin={getattr(asset, 'origin_kind', None)} "
                    f"width={getattr(asset, 'width', None)} height={getattr(asset, 'height', None)}"
                )
                if asset is not None:
                    linked = int(
                        await db.scalar(
                            select(func.count())
                            .select_from(RealphotosAsset)
                            .where(RealphotosAsset.id == int(asset.id))
                        )
                        or 0
                    )
                    from app.capabilities.realphotos.models import RealphotosImageTask

                    processing = int(
                        await db.scalar(
                            select(func.count())
                            .select_from(RealphotosImageTask)
                            .where(RealphotosImageTask.asset_id == int(asset.id))
                        )
                        or 0
                    )
                    note(f"text_asset_stored={linked == 1} processing_tasks_for_result={processing}")
        refs = (
            await db.execute(
                select(func.count())
                .select_from(RealphotosAsset)
                .where(
                    RealphotosAsset.tenant_id == tenant,
                    RealphotosAsset.owner_account_id == int(merchant),
                    RealphotosAsset.origin_kind == "generation_reference",
                )
            )
        ).scalar_one()
        note(f"temporary_reference_assets={int(refs or 0)}")
    note(f"asset_delta={assets_after - assets_before} processing_task_delta={tasks_after - tasks_before}")
    note(f"credit_delta_available={after_a[0] - before_a[0]} credit_delta_reserved={after_a[1] - before_a[1]}")
    note("import_connected=false supplier_connected_does_not_mean_import=true")
    note("SUPPLIER_LIVE_E2E_RECORDED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(_main()))
    except Exception as exc:
        note(f"UNCAUGHT {type(exc).__name__}: {_scrub(str(exc))[:300]}")
        raise
