"""S3 control paths on PostgreSQL.

The real Gemini sample stays in scripts.s3_pg_e2e_smoke. This script stubs
detect_jpeg so the remaining exit paths can be checked without forging that sample.
"""

from __future__ import annotations

import asyncio
import io
import sys
from datetime import UTC, datetime

from PIL import Image
from sqlalchemy import func, select

from app.capabilities.realphotos.services import five_layer, gemini_detector
from app.core.exceptions import BusinessError


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (1024, 768), (24, 36, 48)).save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def _report(*, total: int, passed: bool) -> dict:
    return {
        "noise": total,
        "depthOfField": total,
        "lighting": total,
        "colorRealism": total,
        "overallRealism": total,
        "total_score": total,
        "passed": passed,
        "reason": "control",
        "detector": "gemini-control",
    }


class _Queue:
    def __init__(self) -> None:
        self.items: list[dict | Exception] = []

    def push(self, item: dict | Exception) -> None:
        self.items.append(item)

    def detect(self, _jpeg: bytes) -> dict:
        if not self.items:
            raise BusinessError(message="control queue empty", code="GEMINI_TECHNICAL")
        item = self.items.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


async def _main() -> int:
    from app.capabilities.realphotos.constants import DETECT_GEMINI
    from app.capabilities.realphotos.models import (
        RealphotosCreditReservation,
        RealphotosDetectionResult,
        RealphotosImageTask,
    )
    from app.capabilities.realphotos.permissions import ROLE_MERCHANT
    from app.capabilities.realphotos.services.bootstrap import bootstrap_s0_accounts
    from app.capabilities.realphotos.services.credit_service import RealphotosCreditService
    from app.capabilities.realphotos.services.job_service import RealphotosJobService
    from app.capabilities.realphotos.services.s1_catalog import S1_ENABLED_PRESETS
    from app.capabilities.realphotos.services.s1_processing import RealphotosS1Service
    from app.capabilities.realphotos.services.s1_recharge import RealphotosRechargeService
    from app.core.config import settings
    from app.infrastructure.database.session import Base, async_session_factory, engine, init_db

    if not str(settings.DB_DIALECT).startswith("postgres"):
        print(f"FAIL: expected postgresql, got {settings.DB_DIALECT!r}", file=sys.stderr)
        return 2

    queue = _Queue()
    gemini_detector.detect_jpeg = queue.detect
    preset = S1_ENABLED_PRESETS[0]["code"]
    stamp = str(int(datetime.now(UTC).timestamp()))

    import app.capabilities.realphotos.models  # noqa: F401
    import app.domain  # noqa: F401

    await init_db()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as db:
        summary = await bootstrap_s0_accounts(db)
        tenant = int(summary["rp_merchant_a1"]["tenantId"])
        user = int(summary["rp_merchant_a1"]["userId"])
        support = int(summary["rp_order_support"]["userId"])
        loop = RealphotosS1Service(db)
        credits = RealphotosCreditService(db)
        recharge = RealphotosRechargeService(db)
        jobs = RealphotosJobService(db)
        order = await recharge.create_order(
            tenant_id=tenant,
            requester_user_id=user,
            tier_yuan=100,
            voucher_note="s3-controls",
            idempotency_key=f"s3-controls-recharge-{stamp}",
        )
        await recharge.confirm(order_id=int(order.id), operator_user_id=support)
        asset = await loop.upload(tenant_id=tenant, owner_account_id=user, data=_jpeg())

        async def run_task(task_id: int) -> RealphotosImageTask:
            claimed = await jobs.claim(
                worker_id="s3-controls",
                job_kinds=("process_image",),
                payload_task_id=int(task_id),
            )
            if claimed is None:
                raise RuntimeError(f"claim missing for {task_id}")
            done = await loop.execute_queued(claimed)
            await jobs.complete_success(job=claimed, result={"path": "s3-control"})
            await db.commit()
            return done

        async def submit(*, key: str) -> RealphotosImageTask:
            task = await loop.submit_single(
                tenant_id=tenant,
                owner_account_id=user,
                actor_role_codes={ROLE_MERCHANT},
                asset_id=int(asset.id),
                preset_code=preset,
                idempotency_key=key,
                detection_mode=DETECT_GEMINI,
            )
            await db.commit()
            return task

        async def reservation_for(task_id: int) -> RealphotosCreditReservation:
            row = (
                await db.execute(
                    select(RealphotosCreditReservation).where(
                        RealphotosCreditReservation.task_id == int(task_id)
                    )
                )
            ).scalar_one()
            return row

        async def chain_size(chain_id: int) -> int:
            return int(
                (
                    await db.execute(
                        select(func.count())
                        .select_from(RealphotosImageTask)
                        .where(RealphotosImageTask.chain_id == int(chain_id))
                    )
                ).scalar_one()
            )

        async def report_count(task_id: int) -> int:
            return int(
                (
                    await db.execute(
                        select(func.count())
                        .select_from(RealphotosDetectionResult)
                        .where(RealphotosDetectionResult.task_id == int(task_id))
                    )
                ).scalar_one()
            )

        await loop.save_redo_setting(tenant_id=tenant, enabled=True, threshold=70, extra_rounds=1)
        queue.push(BusinessError(message="检测响应无法解析", code="GEMINI_TECHNICAL"))
        invalid = await submit(key=f"s3-ctrl-invalid-{stamp}")
        invalid_done = await run_task(int(invalid.id))
        held = await reservation_for(int(invalid.id))
        if (
            invalid_done.failure_class != "GEMINI_TECHNICAL"
            or invalid_done.output_object_key is not None
            or await report_count(int(invalid.id)) != 0
            or held.state != "held"
            or await chain_size(int(invalid.chain_id)) != 1
        ):
            print("FAIL: invalid response", file=sys.stderr)
            return 1
        for _ in range(2):
            queue.push(BusinessError(message="检测响应无法解析", code="GEMINI_TECHNICAL"))
            retried = await loop.retry_technical(tenant_id=tenant, task_id=int(invalid.id))
            await db.commit()
            await run_task(int(retried.id))
        still = await reservation_for(int(invalid.id))
        reservation_rows = (
            await db.execute(
                select(func.count())
                .select_from(RealphotosCreditReservation)
                .where(RealphotosCreditReservation.task_id == int(invalid.id))
            )
        ).scalar_one()
        try:
            await loop.retry_technical(tenant_id=tenant, task_id=int(invalid.id))
            print("FAIL: retry limit", file=sys.stderr)
            return 1
        except BusinessError as exc:
            if exc.code != "RETRY_LIMIT" or still.state != "held" or int(reservation_rows) != 1:
                print("FAIL: retry hold", file=sys.stderr)
                return 1

        await loop.save_redo_setting(tenant_id=tenant, enabled=False, threshold=70, extra_rounds=1)
        snapshot_task = await submit(key=f"s3-ctrl-snapshot-{stamp}")
        await loop.save_redo_setting(tenant_id=tenant, enabled=True, threshold=70, extra_rounds=1)
        queue.push(_report(total=40, passed=False))
        snapshot_done = await run_task(int(snapshot_task.id))
        if snapshot_done.status != "FAILED" or await chain_size(int(snapshot_task.chain_id)) != 1:
            print("FAIL: setting snapshot", file=sys.stderr)
            return 1

        equal = await submit(key=f"s3-ctrl-equal-{stamp}")
        queue.push(_report(total=70, passed=False))
        equal_done = await run_task(int(equal.id))
        equal_reservation = await reservation_for(int(equal.id))
        if (
            equal_done.failure_class != "detection_not_passed"
            or not equal_done.output_object_key
            or equal_reservation.state != "released"
            or await chain_size(int(equal.chain_id)) != 1
        ):
            print("FAIL: threshold equality", file=sys.stderr)
            return 1
        source_key = str(equal_done.output_object_key)
        source_report = await loop.detection_payload(tenant_id=tenant, task_id=int(equal.id))

        below = await submit(key=f"s3-ctrl-below-{stamp}")
        queue.push(_report(total=60, passed=False))
        below_done = await run_task(int(below.id))
        if below_done.status != "AUTO_REPROCESS_PENDING" or await chain_size(int(below.chain_id)) != 2:
            print("FAIL: auto redo trigger", file=sys.stderr)
            return 1
        child = (
            await db.execute(
                select(RealphotosImageTask)
                .where(RealphotosImageTask.chain_id == int(below.chain_id))
                .order_by(RealphotosImageTask.id.desc())
            )
        ).scalars().first()
        queue.push(_report(total=88, passed=True))
        child_done = await run_task(int(child.id))
        below_reservation = await reservation_for(int(below.id))
        child_reservation = (
            await db.execute(
                select(RealphotosCreditReservation).where(
                    RealphotosCreditReservation.task_id == int(child.id)
                )
            )
        ).scalar_one_or_none()
        if (
            child_done.status != "DELIVERED"
            or below_reservation.state != "consumed"
            or int(below_reservation.amount) != 10
            or child_reservation is not None
        ):
            print("FAIL: auto redo billing", file=sys.stderr)
            return 1

        await loop.save_redo_setting(tenant_id=tenant, enabled=True, threshold=90, extra_rounds=1)
        baseline = await submit(key=f"s3-ctrl-baseline-{stamp}")
        queue.push(_report(total=80, passed=True))
        baseline_done = await run_task(int(baseline.id))
        baseline_reservation_early = await reservation_for(int(baseline.id))
        if (
            baseline_done.status != "DELIVERED"
            or baseline_reservation_early.state != "consumed"
            or await chain_size(int(baseline.chain_id)) != 2
        ):
            print("FAIL: baseline still continues", file=sys.stderr)
            return 1
        later = (
            await db.execute(
                select(RealphotosImageTask)
                .where(RealphotosImageTask.chain_id == int(baseline.chain_id))
                .order_by(RealphotosImageTask.id.desc())
            )
        ).scalars().first()
        queue.push(_report(total=40, passed=False))
        later_done = await run_task(int(later.id))
        baseline_reservation = await reservation_for(int(baseline.id))
        if (
            later_done.status != "FAILED"
            or later_done.output_object_key is None
            or baseline_reservation.state != "consumed"
        ):
            print("FAIL: later round keeps one consume", file=sys.stderr)
            return 1

        original = five_layer.run_five_layer

        def _floor_fail(*_args, **_kwargs):
            raise BusinessError(message="control floor", code="OUTPUT_CONSTRAINT_UNSATISFIED")

        five_layer.run_five_layer = _floor_fail
        try:
            floor = await submit(key=f"s3-ctrl-floor-{stamp}")
            floor_done = await run_task(int(floor.id))
        finally:
            five_layer.run_five_layer = original
        floor_reservation = await reservation_for(int(floor.id))
        if (
            floor_done.failure_class != "OUTPUT_CONSTRAINT_UNSATISFIED"
            or floor_done.output_object_key is not None
            or await report_count(int(floor.id)) != 0
            or floor_reservation.state != "held"
            or await chain_size(int(floor.chain_id)) != 1
        ):
            print("FAIL: quality hold skips redo", file=sys.stderr)
            return 1

        await loop.save_redo_setting(tenant_id=tenant, enabled=False, threshold=70, extra_rounds=1)
        created = await loop.reprocess(
            tenant_id=tenant,
            owner_account_id=user,
            actor_role_codes={ROLE_MERCHANT},
            source_task_id=int(equal.id),
            preset_code=preset,
            idempotency_key=f"s3-ctrl-reprocess-{stamp}",
        )
        await db.commit()
        queue.push(_report(total=91, passed=True))
        created_done = await run_task(int(created.id))
        created_reservation = await reservation_for(int(created.id))
        source_now = await loop.get_task(tenant_id=tenant, task_id=int(equal.id))
        source_report_now = await loop.detection_payload(tenant_id=tenant, task_id=int(equal.id))
        if (
            int(created.id) == int(equal.id)
            or created_done.status != "DELIVERED"
            or created_reservation.state != "consumed"
            or source_now.output_object_key != source_key
            or source_report_now != source_report
        ):
            print("FAIL: reprocess", file=sys.stderr)
            return 1
        wallet = await credits.get_wallet(tenant_id=tenant)
        print(
            "S3_PG_CONTROLS_PASS",
            "invalid=held",
            "retry_limit=3",
            "snapshot=immutable",
            "threshold_equal=no_redo",
            "below=one_consume",
            "baseline_continues=one_consume",
            "floor=held_no_redo",
            "reprocess=new_task",
            f"wallet_available={wallet['availableInteger']}",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
