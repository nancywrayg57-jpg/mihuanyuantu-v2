"""REGISTER-FIX e2e → /tmp/register-fix-e2e.log

Repro: platform registration-config without tenant → enabled=false.
Fix proof: POST /api/v1/realphotos/auth/register creates tenant+merchant; login works.
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx

LOG = Path("/tmp/register-fix-e2e.log")
API = os.environ.get("REGISTER_FIX_API", "http://127.0.0.1:38000")
FE = os.environ.get("REGISTER_FIX_FE", "http://127.0.0.1:3000")


def note(msg: str) -> None:
    line = msg.rstrip()
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def must(cond: bool, label: str) -> None:
    if not cond:
        note(f"FAIL {label}")
        raise SystemExit(1)
    note(f"PASS {label}")


def main() -> None:
    LOG.write_text(
        f"REGISTER_FIX_E2E start utc={datetime.now(UTC).isoformat()} api={API}\n",
        encoding="utf-8",
    )
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        cfg = client.get(f"{API}/api/v1/auth/registration-config")
        must(cfg.status_code == 200, "platform_registration_config_http")
        cfg_data = cfg.json().get("data") or {}
        note(f"platform_registration_config enabled={cfg_data.get('enabled')} tenantSource={cfg_data.get('tenantSource')}")
        must(cfg_data.get("enabled") is False, "repro_default_tenant_missing_enabled_false")

        missing = client.post(f"{API}/api/v1/realphotos/auth/register", json={})
        # After fix: 422 validation; before fix was 404. Either way path must exist.
        note(f"realphotos_register_empty http={missing.status_code} body={missing.text[:200]}")
        must(missing.status_code != 404, "realphotos_register_route_exists")

        challenge = client.post(
            f"{API}/api/v1/realphotos/auth/challenges",
            json={"clientKey": "register-fix-e2e"},
        )
        must(challenge.status_code == 200, "challenge_http")
        ch = challenge.json()["data"]
        must(bool(ch.get("challengeId")), "challenge_id")
        must(bool(ch.get("devCode") or ch.get("imageBase64")), "challenge_payload")
        code = ch.get("devCode")
        must(bool(code), "dev_captcha_available_for_e2e")

        suffix = uuid.uuid4().hex[:8]
        username = f"regfix_{suffix}"
        password = "RegFix@123456"
        nickname = f"端测商家{suffix}"
        registered = client.post(
            f"{API}/api/v1/realphotos/auth/register",
            json={
                "username": username,
                "password": password,
                "nickname": nickname,
                "challengeId": ch["challengeId"],
                "challengeCode": code,
            },
        )
        note(f"register http={registered.status_code} body={registered.text[:400]}")
        must(registered.status_code == 200, "register_http")
        data = registered.json()["data"]
        must(data.get("tenantCode") == f"m-{username}", "tenant_code")
        must(data.get("roleCode") == "rp_merchant", "role_merchant")
        must(data.get("requireAudit") is False, "no_audit")

        login_ch = client.post(
            f"{API}/api/v1/realphotos/auth/challenges",
            json={"clientKey": "register-fix-login"},
        )
        login_data = login_ch.json()["data"]
        logged = client.post(
            f"{API}/api/v1/realphotos/auth/login",
            json={
                "username": username,
                "password": password,
                "challengeId": login_data["challengeId"],
                "challengeCode": login_data["devCode"],
            },
        )
        note(f"login http={logged.status_code} body={logged.text[:300]}")
        must(logged.status_code == 200, "login_after_register")
        roles = logged.json().get("data", {}).get("roles") or []
        must("rp_merchant" in roles, "login_has_rp_merchant")

        fe = client.get(f"{FE}/register")
        note(f"frontend_register http={fe.status_code} bytes={len(fe.content)}")
        # FE may be down in some runs; do not fail hard if so, but record.
        if fe.status_code == 200:
            text = fe.text
            must("register" in text.lower() or "注册" in text, "frontend_register_page")
        else:
            note("frontend_register SKIPPED_NOT_RUNNING")

    note("REGISTER_FIX_E2E_PASS=true")
    note(json.dumps({"username": username, "tenantCode": data.get("tenantCode")}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        note(f"ERROR {type(exc).__name__}: {exc}")
        raise
