"""UX-PRESET-LOGS-2026-11-10 e2e evidence → /tmp/ux-preset-logs-e2e.log

R1 import_records needed? clear Honeybadger; R2 legacy fields; R3 log displays.
production_billing=false. Does not open S7 / merge PR.
"""

from __future__ import annotations

import asyncio
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import httpx

LOG = Path("/tmp/ux-preset-logs-e2e.log")
REPO = Path(__file__).resolve().parents[3]
API = "http://127.0.0.1:38000"
FE = "http://127.0.0.1:3000"
LEGACY_DIR = REPO / "输入材料/旧版可复用模块/02_设备参数/按旧分类"


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


def mark(rid: str, ok: bool, detail: str = "") -> None:
    note(f"{rid}_{'PASS' if ok else 'FAIL'} {detail}".rstrip())


async def login(client: httpx.AsyncClient, username: str, password: str) -> dict[str, str]:
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


async def main() -> int:
    LOG.write_text("", encoding="utf-8")
    from dotenv import load_dotenv

    load_dotenv(REPO / "aojuai-main/backend/.env")
    from app.capabilities.realphotos.services.bootstrap import DEFAULT_PASSWORD
    from app.capabilities.realphotos.services.legacy_preset_imports import expected_template_count
    from app.core.config import settings

    branch = subprocess.check_output(
        ["git", "-C", str(REPO), "rev-parse", "--abbrev-ref", "HEAD"], text=True
    ).strip()
    head = subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip()
    note("UX_PRESET_LOGS_E2E start")
    note(f"started_at={datetime.now(UTC).isoformat()}")
    note(f"branch={branch}")
    note(f"HEAD={head}")
    note(f"api_base={API} fe_base={FE}")
    note(f"db_dialect={settings.DB_DIALECT}")
    note("production_billing=false")
    note("ticket=UX-PRESET-LOGS-2026-11-10")

    must(str(settings.DB_DIALECT).startswith("postgres"), "postgresql_required")

    # --- R1 verify ---
    template_count = expected_template_count()
    note(f"R1.legacy_template_count={template_count} dir={LEGACY_DIR}")
    must(template_count == 405, "R1_legacy_source_405")

    async with httpx.AsyncClient(base_url=API, timeout=120.0) as client:
        admin = await login(client, "rp_admin", DEFAULT_PASSWORD)
        merchant = await login(client, "rp_merchant_a1", DEFAULT_PASSWORD)

        presets = await client.get("/api/v1/realphotos/device-presets", headers=admin)
        must(presets.status_code == 200, "R1_admin_presets_http")
        items = presets.json()["data"]["items"]
        legacy_rows = [x for x in items if x.get("source") == "legacy_import"]
        hb_rows = [x for x in items if str(x.get("brand") or "").lower() == "honeybadger"]
        note(f"R1.admin_presets total={len(items)} legacy_import={len(legacy_rows)} honeybadger_visible={len(hb_rows)}")

        # Merchant enabled list never reads import API
        enabled = await client.get("/api/v1/realphotos/presets", headers=merchant)
        must(enabled.status_code == 200, "R1_merchant_presets_http")
        e_items = enabled.json()["data"]["items"]
        e_hb = [x for x in e_items if str(x.get("brand") or "").lower() == "honeybadger"]
        note(f"R1.merchant_enabled count={len(e_items)} honeybadger={len(e_hb)}")
        must(len(e_hb) == 0, "R1_merchant_no_honeybadger")

        # Clear placeholders
        cleared = await client.post(
            "/api/v1/realphotos/device-preset-imports/clear-placeholders",
            headers=admin,
        )
        note(f"R1.clear_placeholders http={cleared.status_code} body={json.dumps(cleared.json().get('data', {}), ensure_ascii=False)[:500]}")
        must(cleared.status_code == 200, "R1_clear_placeholders_http")

        presets2 = await client.get("/api/v1/realphotos/device-presets", headers=admin)
        items2 = presets2.json()["data"]["items"]
        hb2 = [x for x in items2 if str(x.get("brand") or "").lower() == "honeybadger"]
        legacy2 = [x for x in items2 if x.get("source") == "legacy_import"]
        note(f"R1.after_clear honeybadger={len(hb2)} legacy_import={len(legacy2)}")
        must(len(hb2) == 0, "R1_honeybadger_gone_from_ledger")
        must(len(legacy2) >= 400, "R1_legacy_not_wiped")

        # Reject Honeybadger on save
        blocked = await client.post(
            "/api/v1/realphotos/device-presets",
            headers=admin,
            json={
                "code": f"ux-hb-block-{int(datetime.now(UTC).timestamp())}",
                "deviceType": "phone",
                "brand": "Honeybadger",
                "model": "ShouldFail",
                "gpsMode": "none",
                "iso": "100",
                "shutter": "1/125",
                "aperture": "f/1.8",
                "focalLength": "26mm",
            },
        )
        note(f"R1.honeybadger_save http={blocked.status_code}")
        must(blocked.status_code >= 400, "R1_honeybadger_save_rejected")

        # import API still exists for scripts but marked retired
        imports = await client.get("/api/v1/realphotos/device-preset-imports?page_size=5", headers=admin)
        must(imports.status_code == 200, "R1_import_api_kept_for_scripts")
        idata = imports.json()["data"]
        note(f"R1.import_api uiRetired={idata.get('uiRetired')} total={idata.get('total')}")

        # FE source: import table removed; brand default empty
        presets_page = (REPO / "aojuai-main/frontend/src/app/(app)/realphotos/presets/page.tsx").read_text(
            encoding="utf-8"
        )
        must("导入记录" not in presets_page or "导入记录区已移除" in presets_page, "R1_fe_import_section_removed")
        must("device-preset-imports" not in presets_page, "R1_fe_no_import_api_call")
        must("brand: ''" in presets_page or "brand: \"\"" in presets_page, "R1_fe_brand_default_empty")
        must("Honeybadger" not in presets_page or "禁止使用 Honeybadger" in presets_page, "R1_fe_no_default_honeybadger")

        # Decision: 405 already activated; merchant never reads imports; ops bulk UI already withdrawn.
        note(
            "import_records_needed=false reason=legacy_405_fully_activated;merchant_uses_device_presets_only;"
            "ops_bulk_ui_already_retired;per_row_activate_redundant_with_runtime_ledger"
        )
        mark("R1_IMPORT_HONEYBADGER", True, "import_ui_removed honeybadger_cleared legacy_kept")

        # --- R2 ---
        sample = next((x for x in items2 if x.get("source") == "legacy_import"), None)
        must(sample is not None, "R2_legacy_sample_exists")
        code = str(sample["code"])
        detail = await client.get(f"/api/v1/realphotos/device-presets/{code}", headers=admin)
        must(detail.status_code == 200, f"R2_detail_http code={code}")
        d = detail.json()["data"]
        lp = d.get("legacyParameters") or {}
        note(f"R2.sample code={code} brand={d.get('brand')} lp_keys={len(lp)} copyrightPolicy={d.get('copyrightPolicy')}")
        core_keys = [
            "camera_make",
            "camera_model",
            "iso",
            "shutter_speed",
            "aperture",
            "focal_length",
            "white_balance",
            "metering_mode",
            "sensor_size",
            "color_space",
            "lens_model",
            "software",
            "gps_mode",
        ]
        present = {k: lp.get(k) for k in core_keys}
        note("R2.core_key_sample " + json.dumps(present, ensure_ascii=False))
        must(len(lp) >= 40, "R2_legacy_param_volume")
        must(bool(lp.get("camera_make") or d.get("brand")), "R2_brand_visible")
        must(bool(lp.get("white_balance") or lp.get("color_space")), "R2_extended_keys_visible")
        must(d.get("copyrightPolicy") == "excluded_prd_no_author_copyright_ip_geo", "R2_copyright_excluded_policy")
        must("author" not in lp or lp.get("author") in (None, ""), "R2_no_author_in_legacy_payload")

        fields_ts = (REPO / "aojuai-main/frontend/src/lib/realphotos-preset-fields.ts").read_text(encoding="utf-8")
        must("copyright_excluded" in fields_ts, "R2_fe_copyright_excluded_tab")
        must("white_balance" in fields_ts and "sensor_size" in fields_ts, "R2_fe_extended_fields")
        must("data-preset-form-tab" in presets_page, "R2_fe_tabbed_form")
        must("sparse" in fields_ts and "lighting" in fields_ts, "R2_sparse_prototype_only_marked")
        note(
            "R2.excluded_list=author,copyright,ip_geo;sparse_prototype_only=lighting,background,post_processing,is_public"
        )
        mark("R2_PRESET_FIELDS", True, f"detail={code} lp_keys={len(lp)}")

        # --- R3 ---
        logs = await client.get("/api/v1/realphotos/account-logs", headers=admin)
        must(logs.status_code == 200, "R3_logs_http")
        litems = logs.json()["data"]["items"]
        must(len(litems) >= 1, "R3_has_log_rows")
        row = litems[0]
        note(
            "R3.sample "
            + json.dumps(
                {
                    "id": row.get("id"),
                    "operatorUserId": row.get("operatorUserId"),
                    "operatorDisplay": row.get("operatorDisplay"),
                    "targetUserId": row.get("targetUserId"),
                    "targetDisplay": row.get("targetDisplay"),
                    "tenantId": row.get("tenantId"),
                    "tenantDisplay": row.get("tenantDisplay"),
                    "action": row.get("action"),
                    "actionLabel": row.get("actionLabel"),
                    "result": row.get("result"),
                    "resultLabel": row.get("resultLabel"),
                },
                ensure_ascii=False,
            )
        )
        must(bool(row.get("operatorDisplay")), "R3_operator_display")
        must(bool(row.get("targetDisplay")), "R3_target_display")
        must(bool(row.get("tenantDisplay")), "R3_tenant_display")
        must(str(row.get("operatorDisplay")) != str(row.get("operatorUserId")), "R3_operator_not_raw_id")
        must(bool(row.get("actionLabel")) and not re.fullmatch(r"[a-z_]+", str(row.get("actionLabel"))), "R3_action_zh")
        must(bool(row.get("resultLabel")), "R3_result_label")
        logs_page = (REPO / "aojuai-main/frontend/src/app/(app)/realphotos/logs/page.tsx").read_text(encoding="utf-8")
        must("operatorDisplay" in logs_page and "actionLabel" in logs_page, "R3_fe_binds_display")
        mark("R3_LOGS_DISPLAY", True, f"log_id={row.get('id')}")

    note("production_billing=false")
    note("UX_PRESET_LOGS_E2E_PASS")
    note(f"ended_at={datetime.now(UTC).isoformat()}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except Exception as exc:  # noqa: BLE001
        note(f"UX_PRESET_LOGS_E2E_FAIL error={exc}")
        raise
