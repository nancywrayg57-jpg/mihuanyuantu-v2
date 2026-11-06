"""PostgreSQL end-to-end smoke. Prints S2_PG_E2E_PASS when the S2 exit checks pass."""

from __future__ import annotations

import asyncio
import io
import json
import math
import subprocess
import sys
from datetime import UTC, datetime, timedelta

from PIL import Image


def _assert_s2_exit_sample(*, source: bytes, body: bytes, preset: dict) -> str | None:
    """Return an error string when the downloaded JPEG misses an S2 exit check."""
    with Image.open(io.BytesIO(source)) as before, Image.open(io.BytesIO(body)) as after:
        if after.size != before.size or after.mode != "RGB":
            return "dimensions"
    raw = subprocess.run(
        [
            "exiftool",
            "-json",
            "-Make",
            "-Model",
            "-ColorSpace",
            "-GPSLatitude",
            "-MakerNote",
            "-ShutterSpeedValue#",
            "-ApertureValue#",
            "-",
        ],
        input=body,
        check=False,
        capture_output=True,
    )
    if raw.returncode != 0:
        return "exif read"
    row = json.loads(raw.stdout.decode() or "[]")[0]
    if row.get("Make") != preset["brand"] or row.get("Model") != preset["model"]:
        return "make model"
    if row.get("ColorSpace") != "sRGB":
        return "colorspace"
    if row.get("GPSLatitude") or row.get("MakerNote"):
        return "gps or makernote"
    shutter = str(preset["shutter"])
    numerator, denominator = shutter.split("/", 1)
    expected_tv = -math.log2(float(numerator) / float(denominator))
    expected_av = 2.0 * math.log2(float(str(preset["aperture"]).removeprefix("f/")))
    if abs(float(row["ShutterSpeedValue"]) - expected_tv) >= 0.02:
        return "apex shutter"
    if abs(float(row["ApertureValue"]) - expected_av) >= 0.02:
        return "apex aperture"
    return None


def _jpeg(width: int, height: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (8, 16, 24)).save(buf, format="JPEG", quality=85)
    return buf.getvalue()


async def _main() -> int:
    from sqlalchemy import select

    import app.capabilities.realphotos.models  # noqa: F401
    import app.domain  # noqa: F401
    from app.capabilities.realphotos.models import (
        RealphotosDetectionResult,
        RealphotosStageResult,
        RealphotosTaskSnapshot,
    )
    from app.capabilities.realphotos.permissions import ROLE_ADMIN, ROLE_MERCHANT
    from app.capabilities.realphotos.services.bootstrap import bootstrap_s0_accounts
    from app.capabilities.realphotos.services.credit_service import RealphotosCreditService
    from app.capabilities.realphotos.services.job_service import RealphotosJobService
    from app.capabilities.realphotos.services.s1_catalog import S1_ENABLED_PRESETS
    from app.capabilities.realphotos.services.s1_processing import RealphotosS1Service
    from app.capabilities.realphotos.services.s1_recharge import RealphotosRechargeService
    from app.core.config import settings
    from app.core.exceptions import AOJUException, BusinessError, NotFoundError
    from app.infrastructure.database.session import Base, async_session_factory, engine, init_db

    if not str(settings.DB_DIALECT).startswith("postgres"):
        print(f"FAIL: expected postgresql, got {settings.DB_DIALECT!r}", file=sys.stderr)
        return 2

    await init_db()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as db:
        summary = await bootstrap_s0_accounts(db)
        tenant1 = int(summary["rp_merchant_a1"]["tenantId"])
        tenant2 = int(summary["rp_merchant_b1"]["tenantId"])
        user_a = int(summary["rp_merchant_a1"]["userId"])
        user_b = int(summary["rp_merchant_a2"]["userId"])
        support = int(summary["rp_order_support"]["userId"])
        loop = RealphotosS1Service(db)
        recharge = RealphotosRechargeService(db)
        credits = RealphotosCreditService(db)
        if len(S1_ENABLED_PRESETS) != 3:
            print("FAIL: preset count", file=sys.stderr)
            return 1
        try:
            await loop.upload(tenant_id=tenant1, owner_account_id=user_a, data=b"nope")
            print("FAIL: invalid upload created a path", file=sys.stderr)
            return 1
        except BusinessError:
            pass
        stamp = str(int(datetime.now(UTC).timestamp()))
        before = await credits.get_wallet(tenant_id=tenant1)
        order = await recharge.create_order(
            tenant_id=tenant1,
            requester_user_id=user_a,
            tier_yuan=100,
            voucher_note="devhost-e2e",
            idempotency_key=f"s1-pg-e2e-recharge-{stamp}",
        )
        await recharge.confirm(order_id=int(order.id), operator_user_id=support)
        source = _jpeg(1024, 768)
        asset = await loop.upload(tenant_id=tenant1, owner_account_id=user_a, data=source)
        task = await loop.submit_single(
            tenant_id=tenant1,
            owner_account_id=user_a,
            actor_role_codes={ROLE_MERCHANT},
            asset_id=int(asset.id),
            preset_code=S1_ENABLED_PRESETS[0]["code"],
            idempotency_key=f"s1-pg-e2e-pass-{stamp}",
        )
        await db.commit()
        if task.status != "SUBMITTED":
            print("FAIL: task reached terminal before worker", file=sys.stderr)
            return 1
        try:
            await loop.soft_delete_asset(tenant_id=tenant1, asset_id=int(asset.id))
            print("FAIL: running asset deleted", file=sys.stderr)
            return 1
        except BusinessError as exc:
            if exc.code != "ASSET_IN_USE":
                raise
        jobs = RealphotosJobService(db)
        claimed = await jobs.claim(
            worker_id="s1-pg-e2e",
            job_kinds=("process_image",),
            payload_task_id=int(task.id),
        )
        if claimed is None or str(settings.DB_DIALECT) != "postgresql" or not claimed.claimed_by:
            print("FAIL: claim_one did not return process job", file=sys.stderr)
            return 1
        done = await loop.execute_queued(claimed)
        await jobs.complete_success(job=claimed, result={"path": "s1"})
        await db.commit()
        report = await loop.detection_payload(tenant_id=tenant1, task_id=int(done.id))
        if (
            done.status != "DELIVERED"
            or not report
            or report.get("accepted") is not True
            or report.get("detector") != "fixture"
        ):
            print("FAIL: delivery", file=sys.stderr)
            return 1
        _ctype, body = await loop.read_object_for_gateway(
            tenant_id=tenant1, object_key=str(done.output_object_key)
        )
        if not body.startswith(b"\xff\xd8\xff"):
            print("FAIL: jpeg", file=sys.stderr)
            return 1
        if len(body) < len(source) or str(done.pipeline_version) == "stub-s1":
            print("FAIL: byte floor or pipeline", file=sys.stderr)
            return 1
        stages = (
            await db.execute(
                select(RealphotosStageResult)
                .where(RealphotosStageResult.task_id == int(done.id))
                .order_by(RealphotosStageResult.id.asc())
            )
        ).scalars().all()
        if [row.stage_code for row in stages] != ["L1", "L2", "L3", "L4", "L5"]:
            print("FAIL: stages", file=sys.stderr)
            return 1
        if any(row.stage_status != "completed" for row in stages):
            print("FAIL: stage status", file=sys.stderr)
            return 1
        exit_error = _assert_s2_exit_sample(
            source=source,
            body=body,
            preset=S1_ENABLED_PRESETS[0],
        )
        if exit_error:
            print(f"FAIL: s2 exit sample {exit_error}", file=sys.stderr)
            return 1
        ledgers = (
            await db.execute(
                select(RealphotosTaskSnapshot).where(RealphotosTaskSnapshot.task_id == int(done.id))
            )
        ).scalars().all()
        ledger = next(
            (
                item.snapshot
                for item in ledgers
                if isinstance(item.snapshot, dict) and item.snapshot.get("kind") == "s2_exif_field_ledger"
            ),
            None,
        )
        if ledger is None:
            print("FAIL: exif field ledger", file=sys.stderr)
            return 1
        by_tag = {field["tag"]: field for field in ledger["fields"]}
        required = (
            "Make",
            "Model",
            "ISO",
            "ExposureTime",
            "FNumber",
            "FocalLength",
            "ColorSpace",
            "ShutterSpeedValue",
            "ApertureValue",
        )
        if any(by_tag[tag]["verification_status"] != "verified" for tag in required):
            print("FAIL: exif field verification", file=sys.stderr)
            return 1
        if by_tag["GPSLatitude"]["verification_status"] != "skipped":
            print("FAIL: gps ledger", file=sys.stderr)
            return 1
        if by_tag["MakerNote"]["verification_status"] != "disabled" or by_tag["MakerNote"]["read_back"]:
            print("FAIL: makernote ledger", file=sys.stderr)
            return 1
        done.output_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await db.flush()
        try:
            await loop.read_object_for_gateway(tenant_id=tenant1, object_key=str(done.output_object_key))
            print("FAIL: expired download allowed", file=sys.stderr)
            return 1
        except AOJUException as exc:
            if exc.status_code != 410:
                raise
        try:
            await loop.get_task(tenant_id=tenant2, task_id=int(done.id))
            print("FAIL: cross tenant read", file=sys.stderr)
            return 1
        except NotFoundError:
            pass
        asset_b = await loop.upload(tenant_id=tenant1, owner_account_id=user_b, data=_jpeg(1200, 800))
        task_b = await loop.submit_single(
            tenant_id=tenant1,
            owner_account_id=user_b,
            actor_role_codes={ROLE_MERCHANT},
            asset_id=int(asset_b.id),
            preset_code=S1_ENABLED_PRESETS[1]["code"],
            idempotency_key=f"s1-pg-e2e-b-{stamp}",
        )
        claimed_b = await jobs.claim(
            worker_id="s1-pg-e2e-b",
            job_kinds=("process_image",),
            payload_task_id=int(task_b.id),
        )
        if claimed_b is None:
            print("FAIL: peer claim", file=sys.stderr)
            return 1
        await loop.execute_queued(claimed_b)
        await jobs.complete_success(job=claimed_b, result={"path": "s1-b"})
        await db.commit()
        wallet = await credits.get_wallet(tenant_id=tenant1)
        expected_available = int(before["availableInteger"]) + 1000 - 20
        if int(wallet["availableInteger"]) != expected_available:
            print(f"FAIL: wallet {wallet}", file=sys.stderr)
            return 1
        asset_t = await loop.upload(tenant_id=tenant1, owner_account_id=user_a, data=_jpeg(1024, 768))
        task_t = await loop.submit_single(
            tenant_id=tenant1,
            owner_account_id=user_a,
            actor_role_codes={ROLE_ADMIN},
            asset_id=int(asset_t.id),
            preset_code=S1_ENABLED_PRESETS[2]["code"],
            idempotency_key=f"s1-pg-e2e-tech-{stamp}",
            detection_mode="technical",
        )
        claimed_t = await jobs.claim(
            worker_id="s1-pg-e2e-tech",
            job_kinds=("process_image",),
            payload_task_id=int(task_t.id),
        )
        if claimed_t is None:
            print("FAIL: technical claim", file=sys.stderr)
            return 1
        tech = await loop.execute_queued(claimed_t)
        await jobs.complete_success(job=claimed_t, result={"path": "s1-tech"})
        await db.commit()
        if tech.credit_disposition != "held_until_tech_support":
            print("FAIL: technical disposition", file=sys.stderr)
            return 1
        padded = _jpeg(1024, 768) + (b"\x00" * 2_000_000)
        asset_c = await loop.upload(tenant_id=tenant1, owner_account_id=user_a, data=padded)
        task_c = await loop.submit_single(
            tenant_id=tenant1,
            owner_account_id=user_a,
            actor_role_codes={ROLE_MERCHANT},
            asset_id=int(asset_c.id),
            preset_code=S1_ENABLED_PRESETS[0]["code"],
            idempotency_key=f"s2-pg-e2e-floor-{stamp}",
        )
        claimed_c = await jobs.claim(
            worker_id="s2-pg-e2e-floor",
            job_kinds=("process_image",),
            payload_task_id=int(task_c.id),
        )
        if claimed_c is None:
            print("FAIL: constraint claim", file=sys.stderr)
            return 1
        constrained = await loop.execute_queued(claimed_c)
        await jobs.complete_success(job=claimed_c, result={"path": "s2-floor"})
        await db.commit()
        if (
            constrained.status != "FAILED"
            or constrained.failure_class != "OUTPUT_CONSTRAINT_UNSATISFIED"
            or constrained.output_object_key
            or constrained.credit_disposition != "held_until_tech_support"
        ):
            print("FAIL: byte floor task", file=sys.stderr)
            return 1
        detection_count = (
            await db.execute(
                select(RealphotosDetectionResult.id).where(
                    RealphotosDetectionResult.task_id == int(constrained.id)
                )
            )
        ).first()
        if detection_count is not None:
            print("FAIL: constraint task wrote a detection report", file=sys.stderr)
            return 1
        print(
            "S2_PG_E2E_PASS",
            f"task_id={int(done.id)}",
            f"peer_task_id={int(task_b.id)}",
            f"constraint_task_id={int(constrained.id)}",
            f"dialect={settings.DB_DIALECT}",
            f"claimed_by={claimed.claimed_by}",
            f"pipeline={done.pipeline_version}",
            "wallet_delta_two_passes=-20",
            "byte_floor=held",
            "dimensions=match",
            "colorspace=sRGB",
            "exif=read_back",
            "gps=none",
            "makernote=absent",
            "detector=fixture",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
