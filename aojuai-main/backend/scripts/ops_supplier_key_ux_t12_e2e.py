"""OPS-SUPPLIER-KEY-UX T1+T2 e2e. Appends /tmp/ops-supplier-key-ux-e2e.log.

T1: provider default Base URL is non-empty and changes with the provider;
probe uses the stored/pasted key and falls back with probe=fallback_static.
T2: same duty keeps every registered key; enabling B makes runtime read B;
A stays listed and disabled. One contract row per duty. No schema change.
No weight-based rotation. The gitignored DeepSeek key is read-only and never logged.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

LOG = Path("/tmp/ops-supplier-key-ux-e2e.log")


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


def _sha(path: Path) -> str:
    if not path.is_file():
        return "missing"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _public_ipv4(host: str) -> str:
    """Resolve a public A record. This host's system DNS is Clash fake-ip (198.18/15)."""
    import httpx

    url = f"https://dns.google/resolve?name={host}&type=A"
    for proxy in (None, "http://127.0.0.1:7890"):
        try:
            kwargs: dict = {"timeout": 12.0, "trust_env": False}
            if proxy:
                kwargs["proxy"] = proxy
            with httpx.Client(**kwargs) as client:
                payload = client.get(url).json()
        except Exception:
            continue
        for ans in payload.get("Answer") or []:
            if int(ans.get("type") or 0) != 1:
                continue
            ip = str(ans.get("data") or "").strip()
            if ip and not ip.startswith("198.18.") and not ip.startswith("198.19."):
                return ip
    raise RuntimeError("doh_no_public_a")


def _load_prompt_opt_key() -> str:
    path = REPO / ".secrets" / "realphotos-duty-secrets.json"
    if not path.is_file():
        return ""
    data = json.loads(path.read_text(encoding="utf-8"))
    raw = data.get("prompt_opt") if isinstance(data, dict) else None
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict) and item.get("enabled") and str(item.get("secret") or "").strip():
                return str(item["secret"]).strip()
    return ""


def _frontend_bases(source: str) -> dict[str, str]:
    match = re.search(r"const PROVIDER_DEFAULT_BASE: Record<string, string> = \{([^}]+)\}", source)
    if match is None:
        raise AssertionError("frontend PROVIDER_DEFAULT_BASE missing")
    found: dict[str, str] = {}
    for quoted, bare, url in re.findall(
        r"(?:'([^']+)'|([A-Za-z0-9_.-]+))\s*:\s*'([^']+)'",
        match.group(1),
    ):
        found[quoted or bare] = url
    return found


async def _t1(source: str) -> None:
    from app.capabilities.realphotos.services.supplier_clients import (
        DASHSCOPE_URL,
        DEEPSEEK_URL,
        GEMINI_BASE,
        GENERATION_BASE,
        default_base_for,
        probe_provider_models,
    )

    bases = _frontend_bases(source)
    expect = {
        "DeepSeek": DEEPSEEK_URL,
        "deepseek": DEEPSEEK_URL,
        "阿里千问": DASHSCOPE_URL,
        "dashscope": DASHSCOPE_URL,
        "aoju": GENERATION_BASE,
        "ChatGPT Image 2": GENERATION_BASE,
        "Gemini": GEMINI_BASE,
        "google-gemini": GEMINI_BASE,
    }
    for label, url in expect.items():
        must(bases.get(label) == url, f"T1_fe_base_{label}")
        must(default_base_for(label) == url, f"T1_py_base_{label}")
        must(bool(url.strip()), f"T1_base_nonempty_{label}")
    switched = [bases["DeepSeek"], bases["aoju"], bases["阿里千问"], bases["Gemini"]]
    must(len(set(switched)) == 4, "T1_provider_switch_base_changes")
    must("function onProviderChange" in source or "function onProviderChange(" in source, "T1_provider_onchange")
    must("nonEmptyBase" in source, "T1_base_never_cleared_helper")
    must("PROVIDER_DEFAULT_BASE[next]" in source, "T1_onchange_writes_provider_default")
    must("setBaseUrl('')" not in source and 'setBaseUrl("")' not in source, "T1_no_empty_base_assignment")
    must("/provider-contracts/probe-models" in source, "T1_probe_call_in_ui")
    must(re.search(r"模型版本[\s\S]{0,500}<select", source) is not None, "T1_model_is_select")

    captured: list[str] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured.append(record.getMessage())

    logger = logging.getLogger("realphotos.supplier_clients")
    handler = _Capture()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        static = await probe_provider_models(provider="DeepSeek", base_url="", api_key=None)
        must(static.get("probe") == "fallback_static", "T1_no_key_fallback_flag")
        must(static.get("baseUrl") == DEEPSEEK_URL, "T1_no_key_default_base")
        must("deepseek-chat" in (static.get("models") or []), "T1_static_deepseek_models")
        must(any("probe=fallback_static" in line for line in captured), "T1_log_probe_fallback_static")

        dead = await probe_provider_models(
            provider="aoju",
            base_url="http://127.0.0.1:9/v1",
            api_key="sk-ops-t1-dead-probe-not-real",
        )
        must(dead.get("probe") == "fallback_static", "T1_dead_probe_fallback")
        must("gpt-image-2" in (dead.get("models") or []), "T1_dead_probe_static_models")
        must(str(dead.get("baseUrl") or "").strip() != "", "T1_dead_probe_base_kept")
        must(any("probe=fallback_static" in line for line in captured), "T1_dead_probe_logged")
    finally:
        logger.removeHandler(handler)

    key = _load_prompt_opt_key()
    must(bool(key) and key.startswith("sk-") and len(key) >= 16, "T1_test_key_present_not_printed")
    import socket

    public_ip = _public_ipv4("api.deepseek.com")
    note("T1.live_dns=doh_bypass_fakeip")
    original_getaddrinfo = socket.getaddrinfo

    def _patched_getaddrinfo(host, port, *args, **kwargs):  # type: ignore[no-untyped-def]
        label = host.decode("ascii", "ignore") if isinstance(host, bytes) else str(host or "")
        if label == "api.deepseek.com":
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (public_ip, port))]
        return original_getaddrinfo(host, port, *args, **kwargs)

    socket.getaddrinfo = _patched_getaddrinfo  # type: ignore[assignment]
    try:
        live = await probe_provider_models(provider="DeepSeek", base_url=DEEPSEEK_URL, api_key=key)
    finally:
        socket.getaddrinfo = original_getaddrinfo  # type: ignore[assignment]
    rendered = json.dumps({k: v for k, v in live.items() if k != "reason"}, ensure_ascii=False)
    must(key not in rendered, "T1_live_response_has_no_plaintext_key")
    must("sk-" not in rendered or "sk-redacted" in rendered, "T1_live_response_no_secret_prefix")
    note(f"T1.live_probe={live.get('probe')} model_count={len(live.get('models') or [])} reason={live.get('reason') or '-'}")
    must(live.get("probe") == "live", "T1_live_probe_with_stored_key")
    models = [str(item) for item in (live.get("models") or [])]
    must(any("deepseek" in item.lower() for item in models), "T1_live_models_include_deepseek")
    must(live.get("baseUrl") == DEEPSEEK_URL, "T1_live_base_nonempty")
    must(live.get("pollingEnabled") is False, "T1_probe_no_polling")


async def _t2() -> None:
    from app.capabilities.realphotos.services import supplier_secrets as secrets
    from app.capabilities.realphotos.services.supplier_clients import DASHSCOPE_URL, DEEPSEEK_URL
    from app.capabilities.realphotos.services.supplier_config import RealphotosSupplierConfigService
    from app.infrastructure.database.session import async_session_factory

    real_path = REPO / ".secrets" / "realphotos-duty-secrets.json"
    before = _sha(real_path)
    key_a = "sk-ops-t2-alpha-AAAA1111"
    key_b = "sk-ops-t2-bravo-BBBB2222"
    with tempfile.TemporaryDirectory(prefix="ops-supplier-t2-") as tmp:
        store = Path(tmp) / "realphotos-duty-secrets.json"
        store.write_text(json.dumps({"prompt_opt": "sk-legacy-flat-KEY9999"}, ensure_ascii=False) + "\n", encoding="utf-8")
        original_paths = secrets.secret_store_paths
        secrets.secret_store_paths = lambda: [store]  # type: ignore[method-assign]
        try:
            legacy = secrets.read_duty_secret("prompt_opt")
            must(legacy == "sk-legacy-flat-KEY9999", "T2_flat_string_still_readable")
            secrets.write_duty_secret("pre_review", "sk-ops-t2-write-CCCC3333")
            secrets.write_duty_secret("pre_review", "sk-ops-t2-write-DDDD4444")
            pre = secrets.list_duty_credentials("pre_review")
            must(len(pre) == 2, "T2_write_appends_not_overwrite")
            must(sum(1 for item in pre if item.get("enabled")) == 1, "T2_single_enabled_after_append")
            must(secrets.read_duty_secret("pre_review") == "sk-ops-t2-write-DDDD4444", "T2_runtime_reads_latest_enabled")
            must(secrets.read_duty_secret("pre_review") != "sk-ops-t2-write-CCCC3333", "T2_previous_not_runtime")

            roles = {"rp_admin"}
            async with async_session_factory() as db:
                service = RealphotosSupplierConfigService(db)
                before_row = await service._row("prompt_opt")
                existed = before_row is not None
                snap = None
                if before_row is not None:
                    snap = {
                        "provider": before_row.provider,
                        "model_id": before_row.model_id,
                        "base_url": before_row.base_url,
                        "enabled": bool(before_row.enabled),
                        "config_version": before_row.config_version,
                    }
                await service.ensure()
                try:
                    await service.save(
                        actor_role_codes=roles,
                        duty="prompt_opt",
                        model_id="deepseek-chat",
                        provider="deepseek",
                        base_url=DEEPSEEK_URL,
                        api_key=key_a,
                        enabled=True,
                        actor_user_id=0,
                    )
                    await service.save(
                        actor_role_codes=roles,
                        duty="prompt_opt",
                        model_id="qwen-plus",
                        provider="dashscope",
                        base_url=DASHSCOPE_URL,
                        api_key=key_b,
                        enabled=True,
                        actor_user_id=0,
                    )
                    listed = await service.list_masked(actor_role_codes=roles)
                    item = next(row for row in listed["items"] if row.get("duty") == "prompt_opt")
                    creds = list(item.get("credentials") or [])
                    masks = {str(c.get("masked") or "") for c in creds}
                    must(len(creds) >= 3, "T2_register_keeps_legacy_and_two_new")
                    by_secret_enabled = {secrets.read_duty_secret("prompt_opt") == key_b}
                    must(True in by_secret_enabled and secrets.read_duty_secret("prompt_opt") != key_a, "T2_runtime_reads_B")
                    enabled_flags = [bool(c.get("enabled")) for c in creds]
                    must(enabled_flags.count(True) == 1, "T2_only_one_enabled")
                    active = next(c for c in creds if c.get("enabled"))
                    inactive = [c for c in creds if not c.get("enabled")]
                    must(len(inactive) >= 2, "T2_old_keys_remain_disabled")
                    must(item.get("provider") == "dashscope", "T2_contract_provider_follows_B")
                    must(item.get("modelId") == "qwen-plus", "T2_contract_model_follows_B")
                    must(item.get("baseUrl") == DASHSCOPE_URL, "T2_contract_base_follows_B")
                    must(item.get("pollingEnabled") is False, "T2_no_polling_flag")
                    blob = json.dumps(item, ensure_ascii=False)
                    must(key_a not in blob and key_b not in blob and "sk-legacy-flat-KEY9999" not in blob, "T2_list_masks_only")
                    must("weight" not in blob, "T2_no_weight_field")
                    must(str(active.get("masked") or "").startswith("sk-o"), "T2_active_mask_prefix")
                    must(all(str(c.get("masked") or "") for c in creds), "T2_every_key_masked")
                    _ = masks

                    await service.set_enabled(
                        actor_role_codes=roles,
                        duty="prompt_opt",
                        enabled=True,
                        credential_id=str(next(c["id"] for c in creds if c.get("modelId") == "deepseek-chat")),
                        actor_user_id=0,
                    )
                    listed_a = await service.list_masked(actor_role_codes=roles)
                    item_a = next(row for row in listed_a["items"] if row.get("duty") == "prompt_opt")
                    creds_a = list(item_a.get("credentials") or [])
                    must(secrets.read_duty_secret("prompt_opt") == key_a, "T2_enable_A_runtime_reads_A")
                    must(secrets.read_duty_secret("prompt_opt") != key_b, "T2_enable_A_not_B")
                    must(sum(1 for c in creds_a if c.get("enabled")) == 1, "T2_enable_A_exclusive")
                    must(any(c.get("modelId") == "qwen-plus" and not c.get("enabled") for c in creds_a), "T2_B_still_listed_disabled")
                    must(item_a.get("provider") == "deepseek", "T2_contract_provider_follows_A")
                    must(item_a.get("modelId") == "deepseek-chat", "T2_contract_model_follows_A")
                    must(item_a.get("baseUrl") == DEEPSEEK_URL, "T2_contract_base_follows_A")
                    must(len(creds_a) == len(creds), "T2_enable_does_not_drop_keys")
                finally:
                    await db.rollback()

            async with async_session_factory() as db:
                service = RealphotosSupplierConfigService(db)
                row = await service._row("prompt_opt")
                if not existed:
                    must(row is None, "T2_db_insert_rolled_back")
                else:
                    assert snap is not None
                    must(row is not None, "T2_row_after_rollback")
                    must(row.provider == snap["provider"], "T2_db_provider_restored")
                    must(row.model_id == snap["model_id"], "T2_db_model_restored")
                    must(row.base_url == snap["base_url"], "T2_db_base_restored")
                    must(bool(row.enabled) == snap["enabled"], "T2_db_enabled_restored")
                await db.rollback()
        finally:
            secrets.secret_store_paths = original_paths

    must(_sha(real_path) == before, "T2_real_secret_file_unchanged")
    note("design=secrets_multi_entry_one_contract_row schema_change=none polling=false")


async def main() -> int:
    from dotenv import load_dotenv

    env_candidates = [
        BACKEND / ".env",
        REPO.parent / "mihuanyuantu-v2" / "aojuai-main" / "backend" / ".env",
    ]
    env_file = next((path for path in env_candidates if path.is_file()), None)
    if env_file is None:
        note("T12_E2E_FAIL missing_backend_env")
        return 1
    load_dotenv(env_file)
    note(f"env_loaded={env_file.name}")
    from app.core.config import settings

    branch = subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "--abbrev-ref", "HEAD"], text=True).strip()
    head = subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"], text=True).strip()
    note("--- T1 T2 run " + datetime.now(UTC).isoformat())
    note(f"branch={branch} HEAD={head} db_dialect={settings.DB_DIALECT}")
    note("ticket=OPS-SUPPLIER-KEY-UX-2026-11-13 scope=T1+T2")
    note("production_billing=false s7_started=false polling_enabled=false")
    must(str(settings.DB_DIALECT).startswith("postgres"), "postgresql_required")
    source = (REPO / "aojuai-main/frontend/src/app/(app)/realphotos/system/system-client.tsx").read_text(encoding="utf-8")
    must("第一版不轮询" in source, "T1_no_polling_copy")
    try:
        await _t1(source)
    except Exception as exc:
        note(f"T1_E2E_FAIL {type(exc).__name__}")
        raise
    note("T1_E2E_PASS")
    try:
        await _t2()
    except Exception as exc:
        note(f"T2_E2E_FAIL {type(exc).__name__}")
        raise
    note("T2_E2E_PASS")
    note("T1_T2_DONE")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except Exception as exc:  # noqa: BLE001
        note(f"T12_E2E_FAIL {type(exc).__name__}")
        raise SystemExit(1) from exc
