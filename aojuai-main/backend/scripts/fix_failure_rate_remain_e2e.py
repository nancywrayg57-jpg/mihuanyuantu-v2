"""FIX-FAILURE-RATE-TECH-2026-11-08 remain items R1–R6 e2e evidence.

Writes /tmp/fix-failure-rate-remain-e2e.log with Rn_E2E_PASS / Rn_E2E_FAIL.
Does not invent PASS for blocked 开发机 steps. Does not lower PASS_SCORE.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path

LOG_PATH = Path("/tmp/fix-failure-rate-remain-e2e.log")
ROOT = Path(__file__).resolve().parents[3]
BE = ROOT / "aojuai-main" / "backend"
FE = ROOT / "aojuai-main" / "frontend" / "src"
CONSTRAINTS = ROOT / "docs" / "mihuanyuantu-v2" / "fix-failure-rate-remain-constraints.md"


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


def _load_dotenv() -> None:
    env_path = BE / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line or line.strip().startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def main() -> int:
    LOG_PATH.write_text("", encoding="utf-8")
    note("fix_failure_rate_remain_e2e start")
    note("ticket=FIX-FAILURE-RATE-TECH-2026-11-08")
    note("branch=cursor/fix-failure-rate-remain-9973")
    note("production_billing=false s7_started=false")
    note(f"constraints_file={CONSTRAINTS}")
    must(CONSTRAINTS.is_file(), "constraints_ledger_present")

    # Baseline F1–F6 script must still pass
    prior = subprocess.run(
        [sys.executable, str(BE / "scripts" / "fix_task_failure_ux_e2e.py")],
        cwd=str(BE),
        capture_output=True,
        text=True,
    )
    note("prior_fix_task_failure_ux_e2e_exit=" + str(prior.returncode))
    must(prior.returncode == 0, "baseline_F1F6_e2e_still_pass")
    must("FIX_TASK_FAILURE_UX_E2E_PASS" in (prior.stdout or ""), "baseline_F1F6_mark")

    sys.path.insert(0, str(BE))
    labels = (FE / "lib" / "realphotos-labels.ts").read_text(encoding="utf-8")
    tasks = (FE / "app" / "(app)" / "realphotos" / "tasks" / "page.tsx").read_text(encoding="utf-8")
    batch = (FE / "app" / "(app)" / "realphotos" / "batch" / "batch-client.tsx").read_text(encoding="utf-8")
    library = (FE / "app" / "(app)" / "realphotos" / "library" / "page.tsx").read_text(encoding="utf-8")
    gps_fe = (FE / "lib" / "realphotos-gps-submit.ts").read_text(encoding="utf-8")
    gemini_src = (BE / "app" / "capabilities" / "realphotos" / "services" / "gemini_detector.py").read_text(
        encoding="utf-8"
    )
    five = (BE / "app" / "capabilities" / "realphotos" / "services" / "five_layer.py").read_text(encoding="utf-8")
    s1 = (BE / "app" / "capabilities" / "realphotos" / "services" / "s1_processing.py").read_text(encoding="utf-8")
    s1_api = (BE / "app" / "capabilities" / "realphotos" / "api" / "s1.py").read_text(encoding="utf-8")
    redo = (BE / "app" / "capabilities" / "realphotos" / "services" / "redo_policy.py").read_text(encoding="utf-8")

    # -------- R6 unit / local first (order per ticket) --------
    from app.capabilities.realphotos.services.five_layer import run_five_layer
    from app.capabilities.realphotos.services.gps_write import resolve_gps
    from app.capabilities.realphotos.services.s1_catalog import S1_ENABLED_PRESETS
    from PIL import Image

    preset_none = dict(S1_ENABLED_PRESETS[0])
    must(preset_none.get("gpsMode") == "none", "R6_catalog_gps_none")
    plan = resolve_gps(preset=preset_none, seed=9)
    must(plan.get("action") == "skip", "R6_resolve_none_skip")
    buf = io.BytesIO()
    Image.new("RGB", (640, 480), (1, 2, 3)).save(buf, format="JPEG", quality=85)
    out = run_five_layer(source=buf.getvalue(), preset=preset_none, seed=9)
    gps_field = next(f for f in out.fields if f["tag"] == "GPSLatitude")
    must(gps_field.get("verification_status") == "skipped", "R6_five_layer_gps_skipped")
    must(out.jpeg.startswith(b"\xff\xd8\xff"), "R6_jpeg_ok")

    pytest = subprocess.run(
        [
            str(BE / ".venv" / "bin" / "pytest"),
            "tests/capabilities/realphotos/test_geocoder_adapter.py",
            "-q",
            "--tb=line",
        ],
        cwd=str(BE),
        env={**os.environ, "DB_DRIVER": "sqlite"},
        capture_output=True,
        text=True,
    )
    note("pytest_geocoder_exit=" + str(pytest.returncode))
    note((pytest.stdout or "")[-500:])
    must(pytest.returncode == 0, "R6_pytest_geocoder_green")

    # R6 live 开发机: ONLY pass when explicit host evidence exists (never TCP-only).
    # Required artifact (written by SSH session on 192.168.19.128): /tmp/r6-devhost-task.json
    # with keys taskId,status,failureClass,gpsMode and assertion gps-related EXIF fail absent.
    host_ev = Path("/tmp/r6-devhost-task.json")
    lan_ok = False
    try:
        import socket

        sock = socket.create_connection(("192.168.19.128", 22), timeout=3)
        sock.close()
        lan_ok = True
        note("R6_LAN_TCP22_OPEN")
    except OSError as exc:
        note(f"R6_LAN_PROBE_FAIL {exc}")
    if host_ev.is_file():
        try:
            payload = json.loads(host_ev.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            mark("R6", False, f"host evidence JSON invalid: {exc}")
        else:
            fc = str(payload.get("failureClass") or "")
            gps_mode = str(payload.get("gpsMode") or "")
            status = str(payload.get("status") or "")
            note(f"R6_host_evidence={json.dumps(payload, ensure_ascii=False)[:500]}")
            gps_exif_fail = fc == "EXIF_WRITE_FAILED" and "GPS" in str(payload.get("failureMessage") or "")
            if gps_mode == "none" and not gps_exif_fail and status in {
                "DELIVERED",
                "FAILED",
                "DETECTION",
            }:
                # FAILED only acceptable when not GPS EXIF (e.g. detection_not_passed)
                if status == "FAILED" and fc not in {"detection_not_passed", ""} and "GPS" in fc:
                    mark("R6", False, f"host failed with GPS-related class {fc}")
                else:
                    mark("R6", True, "开发机 evidence file accepted + local pytest green")
            else:
                mark("R6", False, f"host evidence rejected status={status} fc={fc} gpsMode={gps_mode}")
    else:
        mark(
            "R6",
            False,
            "missing /tmp/r6-devhost-task.json; local five_layer+pytest green but 开发机 Worker+API not evidenced"
            + ("; LAN TCP22 open" if lan_ok else "; LAN unreachable (X1)"),
        )

    # -------- R1 --------
    must("PASS_SCORE = 75" in redo, "R1_pass_score_unchanged_75")
    must("仅当 total_score" in gemini_src and "75" in gemini_src, "R1_prompt_has_75_constraint")
    must("gemini_passed_score_misaligned" in gemini_src, "R1_soft_warning_present")
    must("passed is True and int(parsed" in gemini_src or "passed\"] is True" in gemini_src, "R1_no_silent_rewrite")

    _load_dotenv()
    key = str(os.environ.get("GEMINI_API_KEY") or "").strip()
    if not key:
        mark("R1", False, "GEMINI_API_KEY missing; unit/prompt checks only")
    else:
        import asyncio

        from app.capabilities.realphotos.services.redo_policy import PASS_SCORE, accepted

        async def _r1_local_gemini_tasks() -> list[dict]:
            from pathlib import Path as _Path

            import app.capabilities.realphotos.models  # noqa: F401
            import app.domain  # noqa: F401
            from app.capabilities.realphotos.permissions import ROLE_ADMIN, ROLE_MERCHANT
            from app.capabilities.realphotos.services.bootstrap import bootstrap_s0_accounts
            from app.capabilities.realphotos.services.job_service import RealphotosJobService
            from app.capabilities.realphotos.services.s1_catalog import S1_ENABLED_PRESETS
            from app.capabilities.realphotos.services.s1_processing import RealphotosS1Service
            from app.capabilities.realphotos.services.s1_recharge import RealphotosRechargeService
            from app.capabilities.realphotos.services.s6_ops import RealphotosOpsService
            from app.core import feature_switches
            from app.core.config import settings
            from app.infrastructure.database.session import Base
            from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
            from sqlalchemy.pool import StaticPool

            root = _Path("/tmp/r1-remain-storage")
            root.mkdir(parents=True, exist_ok=True)
            settings.REALPHOTOS_STORAGE_ROOT = str(root)
            settings.REALPHOTOS_ALLOW_DEV_CAPTCHA = "true"
            feature_switches.settings.AOJ_ENABLED_MODULES = "realphotos"
            feature_switches.clear_module_install_caches()
            engine = create_async_engine(
                "sqlite+aiosqlite:///:memory:",
                poolclass=StaticPool,
                connect_args={"check_same_thread": False},
            )
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            out_rows: list[dict] = []
            async with session_factory() as session:
                ops = RealphotosOpsService(session)
                for item in S1_ENABLED_PRESETS:
                    await ops.save_preset(
                        actor_role_codes={ROLE_ADMIN, "admin"},
                        code=str(item["code"]),
                        device_type=str(item["deviceType"]),
                        brand="RuntimeCam",
                        model_name=str(item["model"]),
                        gps_mode="none",
                        enabled=True,
                        iso=str(item.get("iso") or "100"),
                        shutter=str(item.get("shutter") or "1/125"),
                        aperture=str(item.get("aperture") or "f/1.8"),
                        focal_length=str(item.get("focalLength") or "26mm"),
                        source="admin",
                    )
                await session.commit()
                summary = await bootstrap_s0_accounts(session)
                tenant1 = int(summary["rp_merchant_a1"]["tenantId"])
                user_a = int(summary["rp_merchant_a1"]["userId"])
                support = int(summary["rp_order_support"]["userId"])
                loop = RealphotosS1Service(session)
                recharge = RealphotosRechargeService(session)
                jobs = RealphotosJobService(session)
                order = await recharge.create_order(
                    tenant_id=tenant1,
                    requester_user_id=user_a,
                    tier_yuan=100,
                    voucher_note="r1-remain",
                    idempotency_key="r1-remain-recharge",
                )
                await recharge.confirm(order_id=int(order.id), operator_user_id=support)
                colors = ((40, 80, 120), (90, 40, 40), (30, 120, 60))
                for i, color in enumerate(colors, start=1):
                    bio = io.BytesIO()
                    Image.new("RGB", (1024, 768), color).save(bio, format="JPEG", quality=88)
                    asset = await loop.upload(
                        tenant_id=tenant1, owner_account_id=user_a, data=bio.getvalue()
                    )
                    task = await loop.submit_single(
                        tenant_id=tenant1,
                        owner_account_id=user_a,
                        actor_role_codes={ROLE_MERCHANT},
                        asset_id=int(asset.id),
                        preset_code=S1_ENABLED_PRESETS[0]["code"],
                        idempotency_key=f"r1-remain-{i}",
                        detection_mode="gemini",
                    )
                    claimed = await jobs.claim(worker_id=f"r1-{i}", job_kinds=("process_image",))
                    done = await loop.execute_queued(claimed)
                    det = await loop.detection_payload(tenant_id=tenant1, task_id=int(done.id))
                    fail_detail = await loop.failure_detail_payload(
                        tenant_id=tenant1, task_id=int(done.id)
                    )
                    passed = bool((det or {}).get("passed"))
                    score = int((det or {}).get("total_score") or -1)
                    platform_ok = accepted(passed=passed, total_score=score) if det else False
                    # Forbidden inconsistency: score>=75 & accepted yet detection_not_passed
                    if (
                        det
                        and score >= PASS_SCORE
                        and platform_ok
                        and done.failure_class == "detection_not_passed"
                    ):
                        raise AssertionError("R1 inconsistency: accepted but detection_not_passed")
                    out_rows.append(
                        {
                            "image": i,
                            "taskId": int(done.id),
                            "status": done.status,
                            "failureClass": done.failure_class,
                            "passed": passed,
                            "total_score": score,
                            "accepted_platform": platform_ok,
                            "failureMessage": (fail_detail or {}).get("message"),
                            "gate": (det or {}).get("platformGateExplanation"),
                        }
                    )
                await session.commit()
            await engine.dispose()
            return out_rows

        try:
            rows = asyncio.run(_r1_local_gemini_tasks())
        except Exception as exc:  # noqa: BLE001
            note(f"R1_local_tasks_error {type(exc).__name__}:{exc}")
            mark("R1", False, f"local gemini tasks failed: {exc}")
            rows = []
        else:
            note("R1_task_table=" + json.dumps(rows, ensure_ascii=False))
            misaligned = sum(
                1 for r in rows if r.get("passed") is True and int(r.get("total_score") or 0) < 75
            )
            note(f"R1_misaligned_passed_true_below_75={misaligned}/{len(rows)}")
            if len(rows) >= 3 and all(r.get("status") for r in rows):
                mark(
                    "R1",
                    True,
                    f"local SQLite+Worker gemini n=3 misaligned={misaligned}; PASS_SCORE=75",
                )
            else:
                mark("R1", False, f"need ≥3 tasks with status; got {rows!r}")

    # -------- R2 --------
    must("assert_preset_exif_ready" in five, "R2_assert_fn")
    must("PRESET_EXIF_INCOMPLETE" in five, "R2_code")
    must("assert_preset_exif_ready(preset)" in s1, "R2_submit_gate")
    must("预设缺少必填字段" in (FE / "app" / "(app)" / "realphotos" / "presets" / "page.tsx").read_text(
        encoding="utf-8"
    ), "R2_fe_form_check")
    from app.capabilities.realphotos.services.five_layer import assert_preset_exif_ready
    from app.core.exceptions import BusinessError

    try:
        assert_preset_exif_ready({"brand": "X", "model": "Y"})
        mark("R2", False, "incomplete preset should raise")
        raise SystemExit(1)
    except BusinessError as exc:
        must(exc.code == "PRESET_EXIF_INCOMPLETE", "R2_raise_code")
        must("ISO" in exc.message and "快门" in exc.message, "R2_message_fields")
    # complete five_layer path
    complete = dict(S1_ENABLED_PRESETS[0])
    assert_preset_exif_ready(complete)
    out2 = run_five_layer(source=buf.getvalue(), preset=complete, seed=1)
    must(out2.jpeg.startswith(b"\xff\xd8\xff"), "R2_complete_preset_exif_ok")
    mark("R2", True, "save/submit gate + complete five_layer ok")

    # -------- R3 --------
    must("MAKERNOTE_WRITE_FAILED" in labels and "MakerNote 写入失败" in labels, "R3_label")
    must("PRESET_EXIF_INCOMPLETE" in labels and "PRESET_GPS_UNUSABLE" in labels, "R3_extra_codes")
    must("MAKERNOTE_WRITE_FAILED" in s1 and "pre_review_failed" in s1, "R3_retryable")
    must("'MAKERNOTE_WRITE_FAILED'" in tasks, "R3_fe_retry")
    mark("R3", True, "labels+retry membership")

    # -------- R4 --------
    must("gpsSubmitGuard" in gps_fe, "R4_shared_helper")
    must("realphotos-gps-submit" in batch, "R4_batch_uses_helper")
    must("将跳过 GPS" in batch, "R4_skip_copy")
    must("去处理" in library and "GPS" in library, "R4_library_points_to_batch")
    must("单张入口" in batch, "R4_single_entry_banner")
    mark("R4", True, "library→batch single entry shares gpsSubmitGuard")

    # -------- R5 --------
    must("detectionBrief" in s1_api, "R5_api_brief")
    must("detectionBrief" in tasks and "线" in tasks, "R5_list_ui")
    mark("R5", True, "list shows score for detection_not_passed")

    # Summary
    log_text = LOG_PATH.read_text(encoding="utf-8")
    for rid in ("R1", "R2", "R3", "R4", "R5", "R6"):
        note(f"summary_{rid}=" + ("PASS" if f"{rid}_E2E_PASS" in log_text else "FAIL"))
    all_green = all(f"{rid}_E2E_PASS" in log_text for rid in ("R1", "R2", "R3", "R4", "R5", "R6"))
    note("ALL_REMAIN_GREEN=" + str(all_green))
    note("MERGE_READY=" + str(all_green))
    if not all_green:
        note("NOTE: per ticket §0/§4, do not squash-merge until every Rn_E2E_PASS")
    return 0 if all_green else 2


if __name__ == "__main__":
    raise SystemExit(main())
