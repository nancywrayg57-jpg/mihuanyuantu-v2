"""PRESET-BULK-IMPORT B1–B3 end-to-end on development host PostgreSQL.

Evidence: /tmp/preset-bulk-import-e2e.log must contain PRESET_BULK_IMPORT_E2E_PASS.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

import httpx

LOG = Path("/tmp/preset-bulk-import-e2e.log")
RUN = Path("/tmp/preset-bulk-import-e2e-run.txt")
BASE = "http://127.0.0.1:38000"


def note(line: str) -> None:
    text = line if line.endswith("\n") else line + "\n"
    print(text, end="")
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(text)
    with RUN.open("a", encoding="utf-8") as fh:
        fh.write(text)


async def _login(client: httpx.AsyncClient, username: str, password: str) -> dict[str, str]:
    r = await client.post(
        f"{BASE}/api/v1/auth/login",
        json={"username": username, "password": password},
        timeout=60,
    )
    r.raise_for_status()
    data = r.json().get("data") or r.json()
    token = data.get("accessToken") or data.get("token") or data.get("access_token")
    assert token, data
    return {"Authorization": f"Bearer {token}"}


async def main() -> int:
    LOG.write_text("", encoding="utf-8")
    RUN.write_text("", encoding="utf-8")
    note("preset_bulk_import_e2e start")
    note("production_billing=false url_import_connected=false s7_started=false")

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.product_gap_a_schema import ensure_product_gap_a_schema
    from app.capabilities.realphotos.services.bootstrap import DEFAULT_PASSWORD, bootstrap_s0_accounts
    from app.capabilities.realphotos.services.legacy_preset_imports import (
        LEGACY_PARAMETER_KEYS,
        expected_template_count,
    )
    from app.infrastructure.database.session import async_session_factory, engine

    await ensure_product_gap_a_schema(engine)

    expected = expected_template_count()
    note(f"legacy_catalog_total={expected}")
    assert expected == 405, expected

    async with async_session_factory() as db:
        await bootstrap_s0_accounts(db)
        await db.commit()

    async with httpx.AsyncClient() as client:
        admin = await _login(client, "rp_admin", DEFAULT_PASSWORD)
        merchant = await _login(client, "rp_merchant_a1", DEFAULT_PASSWORD)

        # B1 — clear placeholders first (hard gate).
        cleared = await client.post(
            f"{BASE}/api/v1/realphotos/device-preset-imports/clear-placeholders",
            headers=admin,
            json={},
            timeout=120,
        )
        assert cleared.status_code == 200, cleared.text
        cdata = cleared.json()["data"]
        assert cdata.get("placeholder_presets_removed") is True
        note(
            "placeholder_presets_removed=true "
            f"softDeleted={len(cdata.get('softDeletedCodes') or [])} "
            f"disabled={len(cdata.get('disabledCodes') or [])}"
        )

        presets_m = await client.get(f"{BASE}/api/v1/realphotos/presets", headers=merchant, timeout=60)
        assert presets_m.status_code == 200, presets_m.text
        m_payload = presets_m.json()["data"]
        m_items = m_payload.get("items") if isinstance(m_payload, dict) else m_payload
        m_items = list(m_items or [])
        codes = {str(item.get("code") or "") for item in m_items}
        assert "s1-phone-01" not in codes
        assert "s1-dslr-01" not in codes
        assert "s1-mirrorless-01" not in codes
        honey = [
            item
            for item in m_items
            if item.get("brand") == "Honeybadger" and str(item.get("code", "")).startswith("s1-")
        ]
        assert not honey
        note(f"B1 merchant_enabled_without_s1=true merchant_count_before_import={len(m_items)}")

        # B2 — bulk activate all 405
        t0 = time.time()
        bulk = await client.post(
            f"{BASE}/api/v1/realphotos/device-preset-imports/activate-all",
            headers=admin,
            json={},
            timeout=600,
        )
        assert bulk.status_code == 200, bulk.text
        bdata = bulk.json()["data"]
        note(
            f"B2 total={bdata.get('total')} legacy_activated_count={bdata.get('legacy_activated_count')} "
            f"failedCount={bdata.get('failedCount')} progress={bdata.get('progress')} "
            f"elapsed_s={time.time() - t0:.1f}"
        )
        assert int(bdata.get("total") or 0) == 405
        failures = list(bdata.get("failures") or [])
        activated = int(bdata.get("legacy_activated_count") or 0)
        if failures:
            note("B2 failures=" + json.dumps(failures[:20], ensure_ascii=False))
        assert activated == 405 - len(failures)
        assert activated >= 405 or failures, "must be full success or documented failures"
        assert activated == 405, f"DoD requires 405 unless failures documented; got {activated} failures={failures}"

        browse = await client.get(
            f"{BASE}/api/v1/realphotos/device-preset-imports?page=1&page_size=5",
            headers=admin,
            timeout=60,
        )
        assert browse.status_code == 200
        br = browse.json()["data"]
        note(
            f"B2 browse total={br.get('total')} activatedCount={br.get('activatedCount')} "
            f"importedBrands_n={len(br.get('importedBrands') or [])}"
        )
        assert int(br.get("total") or 0) == 405
        assert int(br.get("activatedCount") or 0) == 405

        presets_m2 = await client.get(f"{BASE}/api/v1/realphotos/presets", headers=merchant, timeout=120)
        assert presets_m2.status_code == 200
        m2_payload = presets_m2.json()["data"]
        m2 = m2_payload.get("items") if isinstance(m2_payload, dict) else m2_payload
        m2 = list(m2 or [])
        enabled_count = int(m2_payload.get("enabledCount") if isinstance(m2_payload, dict) else len(m2))
        note(f"B2 merchant_enabledCount={enabled_count}")
        assert enabled_count >= 405
        assert "s1-phone-01" not in {str(x.get("code")) for x in m2}

        by_type: dict[str, list] = {"phone": [], "dslr": [], "mirrorless": [], "action": []}
        for item in m2:
            dt = str(item.get("deviceType") or "")
            if dt in by_type and len(by_type[dt]) < 1:
                by_type[dt].append(item.get("code"))
        for dt, codes_dt in by_type.items():
            assert codes_dt, f"missing enabled preset for type {dt}"
        note(f"B2 sample_by_type={json.dumps(by_type, ensure_ascii=False)}")

        # B3 — snapshot legacyParameters completeness for >=5 samples
        admin_list = await client.get(f"{BASE}/api/v1/realphotos/device-presets", headers=admin, timeout=120)
        assert admin_list.status_code == 200
        a_items = admin_list.json()["data"]["items"]
        legacy_rows = [x for x in a_items if x.get("source") == "legacy_import"]
        assert len(legacy_rows) >= 405
        sample_codes = [str(x["code"]) for x in legacy_rows[:5]]
        # Prefer diverse types
        for dt in ("phone", "dslr", "mirrorless", "action"):
            hit = next((x for x in legacy_rows if x.get("deviceType") == dt), None)
            if hit and hit["code"] not in sample_codes:
                sample_codes.append(hit["code"])
        sample_codes = sample_codes[:8]
        complete = True
        for code in sample_codes:
            vers = await client.get(
                f"{BASE}/api/v1/realphotos/device-presets/{code}/versions",
                headers=admin,
                timeout=60,
            )
            assert vers.status_code == 200, vers.text
            items = vers.json()["data"]["items"]
            assert items, code
            snap = dict(items[0].get("snapshot") or {})
            lp = dict(snap.get("legacyParameters") or {})
            missing = [k for k in LEGACY_PARAMETER_KEYS if k not in lp]
            if missing:
                complete = False
                note(f"B3 incomplete code={code} missing={missing[:10]}")
            else:
                note(f"B3 ok code={code} legacy_keys={len(lp)} gpsMode={snap.get('gpsMode')}")
            # GPS honesty: source mode retained in legacyParameters / meta
            assert "gps_mode" in lp
            meta = snap.get("legacyGpsMeta") or {}
            assert meta.get("gpsSourceMode") is not None
        assert complete
        note("legacy_param_keys_complete=true")

        # MakerNote path: pick one with non-empty maker note and run process if possible
        mn_row = next((x for x in legacy_rows if str(x.get("makerNote") or "").strip()), None)
        if mn_row is None:
            note("B3 makerNote_sample=none_in_first_page_skip")
        else:
            note(f"B3 makerNote_sample_code={mn_row.get('code')} len={len(str(mn_row.get('makerNote') or ''))}")

        note(
            "PRESET_BULK_IMPORT_E2E_PASS "
            f"legacy_activated_count={activated} "
            "placeholder_presets_removed=true "
            "legacy_param_keys_complete=true "
            "production_billing=false url_import_connected=false s7_started=false"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
