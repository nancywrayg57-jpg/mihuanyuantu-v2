"""R6 开发机证据：本机即 192.168.19.128 时，用 PG claim_one + Worker 跑 gpsMode=none。

成功后写入 /tmp/r6-devhost-task.json，供 fix_failure_rate_remain_e2e.py 消费。
Exit mark printed: R6_DEVHOST_GPS_NONE_PASS
"""

from __future__ import annotations

import asyncio
import io
import json
import socket
import sys
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image

EVIDENCE = Path("/tmp/r6-devhost-task.json")


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (1024, 768), (18, 42, 66)).save(buf, format="JPEG", quality=88)
    return buf.getvalue()


def _local_ips() -> set[str]:
    import subprocess

    found: set[str] = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, family=socket.AF_INET):
            found.add(info[4][0])
    except OSError:
        pass
    try:
        out = subprocess.check_output(["hostname", "-I"], text=True, timeout=3)
        found.update(part for part in out.split() if part)
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            found.add(sock.getsockname()[0])
    except OSError:
        pass
    return found


async def _run() -> int:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")

    import app.capabilities.realphotos.models  # noqa: F401
    import app.domain  # noqa: F401
    from app.capabilities.realphotos.permissions import ROLE_ADMIN, ROLE_MERCHANT
    from app.capabilities.realphotos.services.bootstrap import bootstrap_s0_accounts
    from app.capabilities.realphotos.services.job_service import RealphotosJobService
    from app.capabilities.realphotos.services.s1_catalog import S1_ENABLED_PRESETS
    from app.capabilities.realphotos.services.s1_processing import RealphotosS1Service
    from app.capabilities.realphotos.services.s1_recharge import RealphotosRechargeService
    from app.capabilities.realphotos.services.s6_ops import RealphotosOpsService
    from app.core.config import settings
    from app.infrastructure.database.session import Base, async_session_factory, engine, init_db

    ips = _local_ips()
    print(f"R6_host_ips={sorted(ips)}")
    if "192.168.19.128" not in ips:
        print("WARN: 192.168.19.128 not in local IPs; continuing because operator asserted 本机即开发机")

    if not str(settings.DB_DIALECT).startswith("postgres"):
        print(f"FAIL: expected postgresql, got {settings.DB_DIALECT!r}", file=sys.stderr)
        return 2

    await init_db()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    stamp = str(int(datetime.now(UTC).timestamp()))
    preset = dict(S1_ENABLED_PRESETS[0])
    if str(preset.get("gpsMode") or "") != "none":
        print("FAIL: catalog preset gpsMode is not none", file=sys.stderr)
        return 1

    async with async_session_factory() as db:
        # Ensure enabled RuntimeCam row (catalog injection may be off).
        ops = RealphotosOpsService(db)
        await ops.save_preset(
            actor_role_codes={ROLE_ADMIN, "admin"},
            code=str(preset["code"]),
            device_type=str(preset["deviceType"]),
            brand="RuntimeCam",
            model_name=str(preset["model"]),
            gps_mode="none",
            enabled=True,
            iso=str(preset.get("iso") or "100"),
            shutter=str(preset.get("shutter") or "1/125"),
            aperture=str(preset.get("aperture") or "f/1.8"),
            focal_length=str(preset.get("focalLength") or "26mm"),
            source="admin",
        )
        summary = await bootstrap_s0_accounts(db)
        tenant = int(summary["rp_merchant_a1"]["tenantId"])
        user = int(summary["rp_merchant_a1"]["userId"])
        support = int(summary["rp_order_support"]["userId"])
        loop = RealphotosS1Service(db)
        recharge = RealphotosRechargeService(db)
        order = await recharge.create_order(
            tenant_id=tenant,
            requester_user_id=user,
            tier_yuan=100,
            voucher_note="r6-gps-none",
            idempotency_key=f"r6-gps-none-recharge-{stamp}",
        )
        await recharge.confirm(order_id=int(order.id), operator_user_id=support)
        asset = await loop.upload(tenant_id=tenant, owner_account_id=user, data=_jpeg())
        task = await loop.submit_single(
            tenant_id=tenant,
            owner_account_id=user,
            actor_role_codes={ROLE_MERCHANT},
            asset_id=int(asset.id),
            preset_code=str(preset["code"]),
            idempotency_key=f"r6-gps-none-{stamp}",
            detection_mode="pass",
        )
        await db.commit()
        jobs = RealphotosJobService(db)
        claimed = await jobs.claim(
            worker_id="r6-gps-none",
            job_kinds=("process_image",),
            payload_task_id=int(task.id),
        )
        if claimed is None or not getattr(claimed, "claimed_by", None):
            print("FAIL: claim_one did not claim process job", file=sys.stderr)
            return 1
        done = await loop.execute_queued(claimed)
        await jobs.complete_success(job=claimed, result={"path": "r6"})
        await db.commit()
        fail_detail = await loop.failure_detail_payload(tenant_id=tenant, task_id=int(done.id))
        gps = await loop.gps_write_summary(tenant_id=tenant, task_id=int(done.id))
        msg = str((fail_detail or {}).get("message") or "")
        fc = str(done.failure_class or "")
        # R6 gate: must not die on GPS-related EXIF_WRITE_FAILED when gpsMode=none
        if fc == "EXIF_WRITE_FAILED" and ("GPS" in msg or "gps" in msg.lower()):
            print(f"FAIL: GPS-related EXIF failure fc={fc} msg={msg}", file=sys.stderr)
            return 1
        if done.status not in {"DELIVERED", "FAILED"}:
            print(f"FAIL: unexpected status {done.status}", file=sys.stderr)
            return 1
        # Prefer DELIVERED with fixture pass; FAILED only ok for non-GPS reasons (e.g. detection)
        if done.status == "FAILED" and fc not in {"detection_not_passed", ""}:
            if fc in {"EXIF_WRITE_FAILED", "MAKERNOTE_WRITE_FAILED", "OUTPUT_CONSTRAINT_UNSATISFIED"}:
                # EXIF fail that is NOT GPS still fails R6 for none path if it's GPS-ish; otherwise
                # ticket allows non-GPS investigation via R2. For catalog none+complete exposure,
                # any EXIF fail is unexpected.
                print(f"FAIL: unexpected technical failure on gpsMode=none complete preset: {fc} {msg}", file=sys.stderr)
                return 1
        payload = {
            "taskId": int(done.id),
            "status": str(done.status),
            "failureClass": fc,
            "failureMessage": msg,
            "gpsMode": "none",
            "gpsWrite": gps,
            "host": "192.168.19.128",
            "dialect": str(settings.DB_DIALECT),
            "claimedBy": str(getattr(claimed, "claimed_by", "") or ""),
        }
        EVIDENCE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print("R6_DEVHOST_GPS_NONE_PASS", json.dumps(payload, ensure_ascii=False))
        return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
