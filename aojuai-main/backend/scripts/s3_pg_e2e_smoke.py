"""S3 PostgreSQL smoke. Prints S3_PG_E2E_PASS only after a real Gemini sample."""

from __future__ import annotations

import asyncio
import io
import sys
from datetime import UTC, datetime

from PIL import Image

from app.capabilities.realphotos.services.redo_policy import accepted, should_auto_redo


def _policy_ok() -> bool:
    return (
        should_auto_redo(enabled=True, total_score=69, threshold=70, redo_count=0, extra_rounds=1)
        and not should_auto_redo(enabled=True, total_score=70, threshold=70, redo_count=0, extra_rounds=1)
        and should_auto_redo(enabled=True, total_score=80, threshold=90, redo_count=0, extra_rounds=1)
        and accepted(passed=True, total_score=75)
        and not accepted(passed=True, total_score=74)
    )


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (1024, 768), (18, 32, 44)).save(buf, format="JPEG", quality=85)
    return buf.getvalue()


async def _main() -> int:
    from app.capabilities.realphotos.constants import DETECT_GEMINI
    from app.capabilities.realphotos.permissions import ROLE_MERCHANT
    from app.capabilities.realphotos.services.bootstrap import bootstrap_s0_accounts
    from app.capabilities.realphotos.services.credit_service import RealphotosCreditService
    from app.capabilities.realphotos.services.job_service import RealphotosJobService
    from app.capabilities.realphotos.services.s1_catalog import S1_ENABLED_PRESETS
    from app.capabilities.realphotos.services.s1_processing import RealphotosS1Service
    from app.capabilities.realphotos.services.s1_recharge import RealphotosRechargeService
    from app.core.config import settings
    from app.infrastructure.database.session import Base, async_session_factory, engine, init_db

    if not _policy_ok():
        print("FAIL: redo policy", file=sys.stderr)
        return 1
    if not str(settings.DB_DIALECT).startswith("postgres"):
        print(f"FAIL: expected postgresql, got {settings.DB_DIALECT!r}", file=sys.stderr)
        return 2
    if not str(settings.GEMINI_API_KEY or "").strip():
        print("FAIL: GEMINI_NOT_CONFIGURED", file=sys.stderr)
        return 2

    import app.capabilities.realphotos.models  # noqa: F401
    import app.domain  # noqa: F401

    await init_db()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    stamp = str(int(datetime.now(UTC).timestamp()))
    async with async_session_factory() as db:
        summary = await bootstrap_s0_accounts(db)
        tenant = int(summary["rp_merchant_a1"]["tenantId"])
        user = int(summary["rp_merchant_a1"]["userId"])
        support = int(summary["rp_order_support"]["userId"])
        loop = RealphotosS1Service(db)
        credits = RealphotosCreditService(db)
        recharge = RealphotosRechargeService(db)
        order = await recharge.create_order(
            tenant_id=tenant,
            requester_user_id=user,
            tier_yuan=100,
            voucher_note="s3-e2e",
            idempotency_key=f"s3-pg-e2e-recharge-{stamp}",
        )
        await recharge.confirm(order_id=int(order.id), operator_user_id=support)
        saved = await loop.save_redo_setting(tenant_id=tenant, enabled=False, threshold=70, extra_rounds=1)
        if saved.enabled or int(saved.score_threshold) != 70 or int(saved.extra_rounds) != 1:
            print("FAIL: default redo setting", file=sys.stderr)
            return 1
        asset = await loop.upload(tenant_id=tenant, owner_account_id=user, data=_jpeg())
        task = await loop.submit_single(
            tenant_id=tenant,
            owner_account_id=user,
            actor_role_codes={ROLE_MERCHANT},
            asset_id=int(asset.id),
            preset_code=S1_ENABLED_PRESETS[0]["code"],
            idempotency_key=f"s3-pg-e2e-{stamp}",
            detection_mode=DETECT_GEMINI,
        )
        await db.commit()
        jobs = RealphotosJobService(db)
        claimed = await jobs.claim(
            worker_id="s3-pg-e2e",
            job_kinds=("process_image",),
            payload_task_id=int(task.id),
        )
        if claimed is None:
            print("FAIL: claim", file=sys.stderr)
            return 1
        done = await loop.execute_queued(claimed)
        await jobs.complete_success(job=claimed, result={"path": "s3"})
        await db.commit()
        report = await loop.detection_payload(tenant_id=tenant, task_id=int(done.id))
        if done.failure_class in {"GEMINI_TECHNICAL", "GEMINI_NOT_CONFIGURED"} or report is None:
            print(f"FAIL: gemini {done.failure_class}", file=sys.stderr)
            return 1
        if report.get("detector") in {None, "", "fixture"}:
            print("FAIL: detector", file=sys.stderr)
            return 1
        keys = ("noise", "depthOfField", "lighting", "colorRealism", "overallRealism", "total_score", "passed")
        if any(key not in report for key in keys):
            print("FAIL: report keys", file=sys.stderr)
            return 1
        expect = accepted(passed=bool(report["passed"]), total_score=int(report["total_score"]))
        if bool(report["accepted"]) is not expect:
            print("FAIL: accepted rule", file=sys.stderr)
            return 1
        from sqlalchemy import select

        from app.capabilities.realphotos.models import RealphotosCreditReservation

        reservation = (
            await db.execute(
                select(RealphotosCreditReservation).where(
                    RealphotosCreditReservation.task_id == int(done.id)
                )
            )
        ).scalar_one()
        dimensions = [
            int(report[key])
            for key in ("noise", "depthOfField", "lighting", "colorRealism", "overallRealism")
        ]
        wallet = await credits.get_wallet(tenant_id=tenant)
        print(
            "S3_PG_E2E_PASS",
            f"task_id={int(done.id)}",
            f"status={done.status}",
            f"detector={report['detector']}",
            f"noise={report['noise']}",
            f"depthOfField={report['depthOfField']}",
            f"lighting={report['lighting']}",
            f"colorRealism={report['colorRealism']}",
            f"overallRealism={report['overallRealism']}",
            f"total_score={report['total_score']}",
            f"passed={report['passed']}",
            f"accepted={report['accepted']}",
            f"has_jpeg={bool(done.output_object_key)}",
            f"output_bytes={int(done.output_byte_size or 0)}",
            f"reservation={reservation.state}",
            f"total_is_not_dimension_average={int(report['total_score']) != (sum(dimensions) / len(dimensions))}",
            f"wallet_available={wallet['availableInteger']}",
            "redo_default=off",
            "threshold_equal_does_not_trigger=true",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
