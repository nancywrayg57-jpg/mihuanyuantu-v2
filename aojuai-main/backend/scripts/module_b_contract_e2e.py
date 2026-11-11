"""MODULE-B-CONTRACT-2026-11-10 e2e → /tmp/module-b-contract-e2e.log

B1 FR-033 OpenAPI + no-session key path.
B2-G size-control gate (probe + material doc check); B2-X only if SUPPORTS_SIZE_CONTROL=true.
production_billing=false. No S7. Secrets never logged.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import httpx
from PIL import Image

LOG = Path("/tmp/module-b-contract-e2e.log")
REPO = Path(__file__).resolve().parents[3]
CONTRACT = Path(__file__).resolve().parents[1] / "contracts" / "realphotos_image_processing.openapi.json"
LINES: list[str] = []


def _scrub(text: str) -> str:
    from app.capabilities.realphotos.services.supplier_clients import redact

    cleaned = redact(text or "")
    cleaned = re.sub(r"aoju_sk_[0-9a-fA-F]+", "aoju_sk_redacted", cleaned)
    return cleaned


def note(msg: str) -> None:
    line = _scrub(msg.rstrip())
    print(line, flush=True)
    LINES.append(line)
    LOG.write_text("\n".join(LINES) + "\n", encoding="utf-8")


def must(cond: bool, msg: str) -> None:
    if not cond:
        note(f"FAIL {msg}")
        raise AssertionError(msg)
    note(f"PASS {msg}")


def _jpeg(color=(40, 60, 80), size=(1024, 768)) -> bytes:
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


def _material_has_size_contract() -> bool:
    """Scan material for size-control prose. Never print secrets."""
    candidates = [
        REPO / "生产物料" / "蜜獾原图v2-生产物料.md",
        REPO.parent / "生产物料" / "蜜獾原图v2-生产物料.md",
    ]
    path = next((p for p in candidates if p.is_file()), None)
    if path is None:
        note("B2_G_material_file=missing")
        return False
    text = path.read_text(encoding="utf-8")
    # Drop fenced secret blocks before keyword search.
    scrubbed = re.sub(r"```[\s\S]*?```", "\n", text)
    keys = (
        "size control",
        "尺寸控制",
        "supported sizes",
        "允许尺寸",
        "size=",
        "width×height",
        "width x height",
        "images/generations",
        "1024x1024",
        "1024x768",
    )
    hits = [k for k in keys if k.lower() in scrubbed.lower()]
    note(f"B2_G_material_path_exists=true keyword_hits={hits or 'none'}")
    # Key material currently only holds API keys — no size contract prose.
    # Require explicit contract phrasing, not just incidental numbers in server notes.
    explicit = any(
        k in scrubbed
        for k in ("尺寸控制", "允许尺寸", "supported sizes", "size control", "size enum")
    )
    return bool(explicit)


async def _probe_size(width: int, height: int) -> dict:
    from app.capabilities.realphotos.services.supplier_clients import (
        SupplierCallError,
        generate_images,
        image_size,
    )

    requested = f"{width}x{height}"
    try:
        outcome = await generate_images(
            model_id="gpt-image-2",
            prompt=f"module-b size probe {requested} solid color still life",
            width=width,
            height=height,
            quantity=1,
            reference=None,
            seed=None,
        )
    except SupplierCallError as exc:
        return {
            "requested_size": requested,
            "actual": None,
            "http_status": exc.status,
            "error": exc.kind,
            "charged": False,
            "model_id": "gpt-image-2",
        }
    images = list(outcome.get("images") or [])
    raw = images[0].get("raw") if images else None
    actual = None
    if raw:
        try:
            w, h = image_size(bytes(raw))
            actual = f"{w}x{h}"
        except Exception as exc:  # noqa: BLE001
            return {
                "requested_size": requested,
                "actual": None,
                "http_status": outcome.get("http_status"),
                "error": f"decode:{type(exc).__name__}",
                "charged": False,
                "model_id": outcome.get("model_id"),
            }
    return {
        "requested_size": requested,
        "actual": actual,
        "http_status": outcome.get("http_status"),
        "error": None if actual else "empty_image",
        "charged": False,  # probe via supplier client; no wallet consume here
        "model_id": outcome.get("model_id"),
        "bytes": len(raw) if raw else 0,
    }


async def main() -> int:
    LOG.write_text("", encoding="utf-8")
    LINES.clear()
    from dotenv import load_dotenv

    load_dotenv(REPO / "aojuai-main/backend/.env")

    import app.capabilities.realphotos.models  # noqa: F401
    import app.domain  # noqa: F401
    from sqlalchemy import select

    from app.capabilities.realphotos.models import RealphotosProviderContract
    from app.capabilities.realphotos.seed import reconcile
    from app.capabilities.realphotos.services.bootstrap import DEFAULT_PASSWORD, bootstrap_s0_accounts
    from app.capabilities.realphotos.services.job_service import RealphotosJobService
    from app.capabilities.realphotos.services.s1_processing import RealphotosS1Service
    from app.capabilities.realphotos.services.supplier_config import RealphotosSupplierConfigService
    from app.capabilities.realphotos.services.supplier_material import read_material_secret
    from app.core.config import settings
    from app.infrastructure.database.session import Base, async_session_factory, engine, init_db
    from app.main import app as fastapi_app
    from scripts.export_image_processing_openapi import check as openapi_check
    from scripts.export_image_processing_openapi import export as openapi_export

    branch = subprocess.check_output(
        ["git", "-C", str(REPO), "rev-parse", "--abbrev-ref", "HEAD"], text=True
    ).strip()
    head = subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"], text=True).strip()
    note("MODULE_B_CONTRACT_E2E start")
    note(f"started_at={datetime.now(UTC).isoformat()}")
    note(f"branch={branch} HEAD={head}")
    note(f"db_dialect={settings.DB_DIALECT}")
    note("production_billing=false")
    note("s7_started=false")
    note("OUT_SCORE=true OUT_ND011=true OUT_AC009=true OUT_ND012_FORMAL=true")
    note("detection_fixture_note=detectionMode=pass path-proof-not-gemini-production-sample")

    must(str(settings.DB_DIALECT).startswith("postgres"), "postgresql_required")

    # ---- B1 OpenAPI ----
    before_paths = set()
    if CONTRACT.is_file():
        before_paths = set((json.loads(CONTRACT.read_text(encoding="utf-8")).get("paths") or {}).keys())
    exported = openapi_export(CONTRACT)
    rc = openapi_check(CONTRACT)
    must(rc == 0, "openapi_check_clean")
    after_paths = set((exported.get("paths") or {}).keys())
    added = sorted(after_paths - before_paths)
    removed = sorted(before_paths - after_paths)
    note(f"openapi_export_ok=true paths={len(after_paths)} added={added or '[]'} removed={removed or '[]'}")
    auth = ((exported.get("components") or {}).get("securitySchemes") or {}).get("ApiKeyAuth") or {}
    must(auth.get("name") == "X-API-Key", "openapi_header_X-API-Key")
    for bad in ("generation-tasks", "prompt-optimizations", "resource-imports", "business-api-keys"):
        must(not any(bad in p for p in after_paths), f"openapi_excludes_{bad}")

    await init_db()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    stamp = str(int(datetime.now(UTC).timestamp()))
    async with async_session_factory() as db:
        from app.capabilities.realphotos.services.credit_service import RealphotosCreditService

        summary = await bootstrap_s0_accounts(db)
        tenant = int(summary["rp_merchant_a1"]["tenantId"])
        platform = int(summary["rp_admin"]["tenantId"])
        admin_user = int(summary["rp_admin"]["userId"])
        await reconcile(db, tenant_id=platform)
        await reconcile(db, tenant_id=tenant)
        await RealphotosSupplierConfigService(db).ensure()
        # Path-proof Key is admin-issued (pass inject); ensure platform wallet can freeze 10.
        credits = RealphotosCreditService(db)
        wallet = await credits.get_wallet(tenant_id=platform)
        if int(wallet["availableInteger"]) < 50:
            await credits.admin_adjust(
                tenant_id=platform,
                delta_available=500,
                operator_user_id=admin_user,
                event_key=f"mb-fund-{stamp}",
                reason="module-b path-proof fund",
            )
        await db.commit()

    transport = httpx.ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=180.0) as client:
        merchant = await _login(client, "rp_merchant_a1", DEFAULT_PASSWORD)
        # Admin issues Key for path-proof with detectionMode=pass (merchant Key cannot inject;
        # work order allows fixture/pass for path proof, not a Gemini production sample).
        admin = await _login(client, "rp_admin", DEFAULT_PASSWORD)
        note("detection_path_proof_actor=admin_issued_key detectionMode=pass")

        for body, label in (
            ({"name": f"mb-omit-{stamp}"}, "omitted"),
            ({"name": f"mb-empty-{stamp}", "scopes": []}, "empty"),
            ({"name": f"mb-wild-{stamp}", "scopes": ["*"]}, "wildcard"),
            ({"name": f"mb-train-{stamp}", "scopes": ["/api/v1/training"]}, "training"),
        ):
            rejected = await client.post(
                "/api/v1/realphotos/business-api-keys", headers=merchant, json=body
            )
            must(rejected.status_code == 400 and rejected.json().get("code") == "SCOPE_REJECTED", f"scope_{label}_rejected")

        issued = await client.post(
            "/api/v1/realphotos/business-api-keys",
            headers=admin,
            json={"name": f"mb-{stamp}", "scopes": ["image_processing"]},
        )
        must(issued.status_code == 200, f"key_issue_http={issued.status_code}")
        issued_data = issued.json()["data"]
        raw_key = str(issued_data["apiKey"])
        issued_id = int(issued_data["id"])
        must(issued_data.get("scopes") == ["image_processing"], "key_scope_image_processing")
        note("business_key_issued_via_http=true")
        key_headers = {"X-API-Key": raw_key}

        # no-session main path
        uploaded = await client.post(
            "/api/v1/realphotos/assets",
            headers=key_headers,
            files={"file": ("mb.jpg", _jpeg(), "image/jpeg")},
        )
        must(uploaded.status_code == 200, f"key_upload={uploaded.status_code}")
        asset_id = int(uploaded.json()["data"]["id"])
        presets = await client.get("/api/v1/realphotos/presets", headers=key_headers)
        must(presets.status_code == 200, f"key_list_presets={presets.status_code}")
        preset_items = (presets.json().get("data") or {}).get("items") or []
        must(len(preset_items) >= 1, "enabled_presets_nonempty")
        preset = str(preset_items[0]["code"])
        note(f"preset_code={preset} enabled_count={len(preset_items)}")
        submitted = await client.post(
            "/api/v1/realphotos/processing-batches",
            headers={**key_headers, "content-type": "application/json"},
            content=json.dumps(
                {
                    "assetIds": [asset_id],
                    "presetCode": preset,
                    "idempotencyKey": f"mb-key-{stamp}",
                    "preReviewMode": "pass",
                    "detectionMode": "pass",
                }
            ).encode(),
        )
        must(submitted.status_code == 200, f"key_submit={submitted.status_code} {submitted.text[:160]}")
        task_id = int(submitted.json()["data"]["tasks"][0]["id"])

        async with async_session_factory() as worker_db:
            jobs = RealphotosJobService(worker_db)
            claimed = await jobs.claim(
                worker_id=f"mb-{stamp}",
                job_kinds=("process_image",),
                payload_task_id=task_id,
            )
            must(claimed is not None, "worker_claimed_process_image")
            done = await RealphotosS1Service(worker_db).execute_queued(claimed)
            await jobs.complete_success(job=claimed, result={"path": "module-b"})
            await worker_db.commit()
            must(bool(done.output_object_key), "output_object_key_present")
            output_key = str(done.output_object_key)

        queried = await client.get(f"/api/v1/realphotos/processing-tasks/{task_id}", headers=key_headers)
        must(queried.status_code == 200, "key_query_ok")
        status = queried.json()["data"]["status"]
        must(status == "DELIVERED", f"query_status={status}")
        picked = await client.post(
            "/api/v1/realphotos/processing-tasks/selected-downloads",
            headers={**key_headers, "content-type": "application/json"},
            content=json.dumps({"taskIds": [task_id], "pack": "files"}).encode(),
        )
        must(picked.status_code == 200, "selected_downloads_files")
        must(picked.json()["data"]["items"][0]["objectKey"] == output_key, "download_object_key_match")
        must("/" not in output_key.split("tenant/", 1)[-1] or "tenant/" in output_key, "no_bare_local_disk_path_in_customer_shape")
        note(f"gateway_object_key_prefix={output_key.split('/')[0]}")
        zipped = await client.post(
            "/api/v1/realphotos/processing-tasks/selected-downloads",
            headers={**key_headers, "content-type": "application/json"},
            content=json.dumps({"taskIds": [task_id], "pack": "zip"}).encode(),
        )
        must(zipped.status_code == 400, "zip_rejected=true")
        note("zip_rejected=true")
        downloaded = await client.get(
            "/api/v1/realphotos/gateway/objects/" + output_key,
            headers=key_headers,
        )
        must(downloaded.status_code == 200 and downloaded.content.startswith(b"\xff\xd8\xff"), "gateway_download_jpeg")
        note("no_session_upload_submit_query_download=PASS")

        gen_denied = await client.post(
            "/api/v1/realphotos/generation-tasks",
            headers={**key_headers, "content-type": "application/json"},
            content=b'{"mode":"text_to_image","positivePrompt":"x","width":256,"height":256,"quantity":1,"idempotencyKey":"no"}',
        )
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
        manage_denied = await client.post(
            "/api/v1/realphotos/business-api-keys",
            headers={**key_headers, "content-type": "application/json"},
            content=b'{"name":"again","scopes":["image_processing"]}',
        )
        delete_denied = await client.delete(
            f"/api/v1/realphotos/business-api-keys/{issued_id}",
            headers=key_headers,
        )
        must(gen_denied.status_code in {401, 403}, f"key_rejects_generation={gen_denied.status_code}")
        must(prompt_denied.status_code in {401, 403}, f"key_rejects_prompt={prompt_denied.status_code}")
        must(import_denied.status_code in {401, 403}, f"key_rejects_import={import_denied.status_code}")
        note("key_rejects_generation_or_prompt_or_import=PASS")
        must(manage_denied.status_code in {401, 403} and delete_denied.status_code in {401, 403}, "key_manage_rejected=true")
        note("key_manage_rejected=true")
        note("B1_FR033_CONTRACT_PASS")

    # ---- B2-G ----
    doc_ok = _material_has_size_contract()
    note(f"B2_G_supplier_doc_checked={'true' if doc_ok else 'false'}")
    if not doc_ok:
        note(
            "B2_G_ADMIN_REQUEST="
            "请提供 aoju/gpt-image-2 尺寸控制书面或接口说明："
            "是否支持 size/WxH、允许枚举或范围、不支持时忽略/报错/回落策略。"
            "当前生产物料文件仅有密钥段，无尺寸合同句。"
        )

    probes: list[dict] = []
    if not read_material_secret("generation"):
        note("B2_G_probe_skipped=missing_generation_secret")
        support = "inconclusive"
    else:
        for w, h in ((1024, 768), (1024, 1024)):
            row = await _probe_size(w, h)
            probes.append(row)
            note(
                "B2_G_probe "
                f"requested={row['requested_size']} actual={row['actual']} "
                f"http={row['http_status']} model={row.get('model_id')} "
                f"error={row.get('error')} charged={row.get('charged')} "
                f"bytes={row.get('bytes')}"
            )
        note(
            "B2_G_probe_sizes="
            + ";".join(f"{p['requested_size']}->{p['actual'] or p.get('error')}" for p in probes)
        )
        usable = [p for p in probes if p.get("actual")]
        if not usable:
            support = "inconclusive"
        else:
            mismatches = [p for p in usable if p["actual"] != p["requested_size"]]
            if mismatches and not doc_ok:
                support = "false"
            elif mismatches and doc_ok:
                # Would need approved mapping table — none present → false
                support = "false"
            elif not mismatches and doc_ok:
                support = "true"
            else:
                # Match without written contract → cannot claim true
                support = "inconclusive"
                note("B2_G_note=actual_matched_but_no_written_contract_cannot_claim_true")

    note(f"SUPPORTS_SIZE_CONTROL={support}")

    # Persist honest contract capabilities / gap
    async with async_session_factory() as db:
        await RealphotosSupplierConfigService(db).ensure()
        row = (
            await db.execute(
                select(RealphotosProviderContract).where(
                    RealphotosProviderContract.duty == "generation",
                    RealphotosProviderContract.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if row is not None:
            caps = dict(row.capabilities or {})
            if support == "true":
                caps["sizeControl"] = "enforced"
            elif support == "false":
                caps["sizeControl"] = "unsupported_or_not_honored"
                caps["sizeProbe"] = [
                    {"requested": p["requested_size"], "actual": p.get("actual"), "http": p.get("http_status")}
                    for p in probes
                ]
                row.gap_note = (
                    "种子 gap-not-sent（AC-009）。尺寸：请求原样发送、适配器不改写；"
                    "MODULE-B 探测 actual≠requested 且无批准映射表 / 物料无尺寸书面合同 → "
                    "不得宣称 sizeControl=enforced。客户路径如实展示请求与实际尺寸。"
                )
            else:
                caps["sizeControl"] = "inconclusive"
                row.gap_note = (
                    "种子 gap-not-sent（AC-009）。尺寸门闸 inconclusive："
                    "缺供应商尺寸书面合同且/或探测不稳定；停问管理员后再收口。"
                )
            row.capabilities = caps
            await db.commit()
            note(f"generation_contract_sizeControl={caps.get('sizeControl')}")

    if support == "true":
        note("B2_X_not_implemented_in_this_run=unexpected_true_requires_followup")
        # Gate true would require B2-X; leave marker for follow-up rather than fake PASS.
        note("B2_SIZE_CONTRACT_ENFORCED_PASS_PENDING_IMPLEMENTATION")
        b2_complete = False
    elif support == "false":
        note("B2_SIZE_UNSUPPORTED_RECORDED")
        note("B2_complete=false reason=size_not_honored_or_no_mapping")
        b2_complete = False
    else:
        note("B2_SIZE_INCONCLUSIVE_STOP")
        note("B2_complete=false reason=inconclusive_await_admin_doc")
        b2_complete = False

    note(
        "MODULE_B_CONTRACT_E2E_PASS_PARTIAL "
        "B1_FR033_CONTRACT_PASS "
        f"B2_complete={str(b2_complete).lower()} "
        f"SUPPORTS_SIZE_CONTROL={support} "
        "production_billing=false s7_started=false"
    )
    # B1 alone makes the work-order deliverable; B2 may stop at gate.
    note("B1_required_done=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
