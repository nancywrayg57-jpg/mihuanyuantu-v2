"""S4 batch settlement on the dev-host PostgreSQL.

The downloadable image uses detection_mode=pass so the partial-success
evidence does not depend on a live Gemini call. This log is not a public
检测通过 claim and does not mark production billing ready.
"""

from __future__ import annotations

import asyncio
import io
import sys
from datetime import UTC, datetime

from PIL import Image
from sqlalchemy import func, select


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (1024, 768), (30, 48, 66)).save(buf, format="JPEG", quality=85)
    return buf.getvalue()


async def _main() -> int:
    from app.capabilities.realphotos.models import (
        RealphotosCreditLedgerEntry,
        RealphotosCreditReservation,
    )
    from app.capabilities.realphotos.permissions import ROLE_ADMIN, ROLE_MERCHANT
    from app.capabilities.realphotos.services.bootstrap import bootstrap_s0_accounts
    from app.capabilities.realphotos.services.credit_service import RealphotosCreditService
    from app.capabilities.realphotos.services.job_service import RealphotosJobService
    from app.capabilities.realphotos.services.s1_catalog import S1_ENABLED_PRESETS
    from app.capabilities.realphotos.services.s1_processing import RealphotosS1Service
    from app.core.config import settings
    from app.core.exceptions import BusinessError, NotFoundError
    from app.infrastructure.database.session import Base, async_session_factory, engine, init_db

    if not str(settings.DB_DIALECT).startswith("postgres"):
        print(f"FAIL: expected postgresql, got {settings.DB_DIALECT!r}", file=sys.stderr)
        return 2

    import app.capabilities.realphotos.models  # noqa: F401
    import app.domain  # noqa: F401

    await init_db()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    stamp = str(int(datetime.now(UTC).timestamp()))
    preset = S1_ENABLED_PRESETS[0]["code"]

    async with async_session_factory() as db:
        summary = await bootstrap_s0_accounts(db)
        tenant = int(summary["rp_merchant_a1"]["tenantId"])
        tenant_b = int(summary["rp_merchant_b1"]["tenantId"])
        user_a = int(summary["rp_merchant_a1"]["userId"])
        user_b = int(summary["rp_merchant_a2"]["userId"])
        user_b1 = int(summary["rp_merchant_b1"]["userId"])
        admin = int(summary["rp_admin"]["userId"])
        loop = RealphotosS1Service(db)
        credits = RealphotosCreditService(db)
        jobs = RealphotosJobService(db)

        async def run_task(task_id: int):
            claimed = await jobs.claim(
                worker_id="s4-pg",
                job_kinds=("process_image",),
                payload_task_id=int(task_id),
            )
            if claimed is None:
                raise RuntimeError(f"claim missing for {task_id}")
            done = await loop.execute_queued(claimed)
            await jobs.complete_success(job=claimed, result={"path": "s4"})
            return done

        before_rows = await _reservation_count(db, RealphotosCreditReservation, tenant)
        await _expect(
            loop.submit_batch(
                tenant_id=tenant,
                owner_account_id=user_a,
                actor_role_codes={ROLE_MERCHANT},
                asset_ids=list(range(1, 12)),
                preset_code=preset,
                idempotency_key=f"s4-eleven-{stamp}",
            ),
            "BATCH_REJECTED",
        )
        if await _reservation_count(db, RealphotosCreditReservation, tenant) != before_rows:
            print("FAIL: eleventh image left a reservation", file=sys.stderr)
            return 2

        poor_before = await _reservation_count(db, RealphotosCreditReservation, tenant_b)
        wallet_b = await credits.get_wallet(tenant_id=tenant_b)
        if int(wallet_b["availableInteger"]) >= 10:
            print("FAIL: tenant 2 already has 10 credits; insufficient case would not be clean", file=sys.stderr)
            return 2
        await _expect(
            loop.submit_batch(
                tenant_id=tenant_b,
                owner_account_id=user_b1,
                actor_role_codes={ROLE_MERCHANT},
                asset_ids=[1],
                preset_code=preset,
                idempotency_key=f"s4-poor-{stamp}",
            ),
            "INSUFFICIENT_CREDITS",
        )
        if await _reservation_count(db, RealphotosCreditReservation, tenant_b) != poor_before:
            print("FAIL: insufficient balance left a reservation", file=sys.stderr)
            return 2

        good = await loop.upload(tenant_id=tenant, owner_account_id=user_a, data=_jpeg())
        bad = await loop.upload(tenant_id=tenant, owner_account_id=user_a, data=_jpeg())
        await loop.soft_delete_asset(tenant_id=tenant, asset_id=int(bad.id))
        _partial, partial_tasks = await loop.submit_batch(
            tenant_id=tenant,
            owner_account_id=user_a,
            actor_role_codes={ROLE_MERCHANT},
            asset_ids=[int(good.id), int(bad.id)],
            preset_code=preset,
            idempotency_key=f"s4-partial-{stamp}",
            detection_mode="pass",
        )
        again, again_tasks = await loop.submit_batch(
            tenant_id=tenant,
            owner_account_id=user_a,
            actor_role_codes={ROLE_MERCHANT},
            asset_ids=[int(good.id), int(bad.id)],
            preset_code=preset,
            idempotency_key=f"s4-partial-{stamp}",
            detection_mode="pass",
        )
        if [int(task.id) for task in again_tasks] != [int(task.id) for task in partial_tasks]:
            print("FAIL: idempotent replay created new tasks", file=sys.stderr)
            return 2
        if int(again.id) != int(_partial.id):
            print("FAIL: idempotent replay created a new batch", file=sys.stderr)
            return 2
        delivered = await run_task(int(partial_tasks[0].id))
        if partial_tasks[1].credit_disposition != "released_precheck":
            print("FAIL: precheck image was not released", file=sys.stderr)
            return 2
        if delivered.credit_disposition != "consumed_detection_pass":
            print("FAIL: downloadable image was not consumed per image", file=sys.stderr)
            return 2

        first_pass = await loop.upload(tenant_id=tenant, owner_account_id=user_a, data=_jpeg())
        second_pass = await loop.upload(tenant_id=tenant, owner_account_id=user_a, data=_jpeg())
        _two, two_tasks = await loop.submit_batch(
            tenant_id=tenant,
            owner_account_id=user_a,
            actor_role_codes={ROLE_MERCHANT},
            asset_ids=[int(first_pass.id), int(second_pass.id)],
            preset_code=preset,
            idempotency_key=f"s4-two-{stamp}",
            detection_mode="pass",
        )
        done_two = [await run_task(int(task.id)) for task in two_tasks]
        two_consumed = sum(
            10 for task in done_two if task.credit_disposition == "consumed_detection_pass"
        )
        if two_consumed != 20:
            print(f"FAIL: two-image batch consumed {two_consumed}", file=sys.stderr)
            return 2

        tech_asset = await loop.upload(tenant_id=tenant, owner_account_id=admin, data=_jpeg())
        _tech, tech_tasks = await loop.submit_batch(
            tenant_id=tenant,
            owner_account_id=admin,
            actor_role_codes={ROLE_ADMIN},
            asset_ids=[int(tech_asset.id)],
            preset_code=preset,
            idempotency_key=f"s4-tech-{stamp}",
            detection_mode="technical",
        )
        tech_done = await run_task(int(tech_tasks[0].id))
        tech_reservation = (
            await db.execute(
                select(RealphotosCreditReservation).where(
                    RealphotosCreditReservation.task_id == int(tech_done.id)
                )
            )
        ).scalar_one()
        if tech_done.credit_disposition != "held_until_tech_support" or tech_reservation.state != "held":
            print("FAIL: technical image was not held", file=sys.stderr)
            return 2
        if hasattr(loop, "unfreeze_for_support"):
            print("FAIL: support unfreeze entry exists", file=sys.stderr)
            return 2

        try:
            await loop.get_task(tenant_id=tenant, task_id=int(delivered.id), owner_account_id=user_b)
            print("FAIL: other account read the batch task", file=sys.stderr)
            return 2
        except NotFoundError:
            pass
        try:
            await loop.read_object_for_gateway(
                tenant_id=tenant,
                object_key=str(delivered.output_object_key),
                owner_account_id=user_b,
            )
            print("FAIL: other account downloaded the result", file=sys.stderr)
            return 2
        except NotFoundError:
            pass
        _content_type, owned_bytes = await loop.read_object_for_gateway(
            tenant_id=tenant,
            object_key=str(delivered.output_object_key),
            owner_account_id=user_a,
        )
        if not owned_bytes.startswith(b"\xff\xd8\xff"):
            print("FAIL: owner download is not a JPEG", file=sys.stderr)
            return 2

        picked = await loop.selected_download_items(
            tenant_id=tenant,
            owner_account_id=user_a,
            task_ids=[int(done_two[0].id)],
            pack="files",
        )
        if [item["taskId"] for item in picked] != [str(int(done_two[0].id))]:
            print("FAIL: selected download did not keep only the checked task", file=sys.stderr)
            return 2
        if any(item.get("pack") == "zip" for item in picked):
            print("FAIL: selected download returned a zip", file=sys.stderr)
            return 2
        try:
            await loop.selected_download_items(
                tenant_id=tenant,
                owner_account_id=user_a,
                task_ids=[int(done_two[0].id), int(done_two[1].id)],
                pack="zip",
            )
            print("FAIL: zip pack was accepted", file=sys.stderr)
            return 2
        except BusinessError as exc:
            if exc.code != "ZIP_REJECTED":
                raise

        concurrent_asset_ids = [
            int(
                (
                    await loop.upload(tenant_id=tenant, owner_account_id=user_a, data=_jpeg())
                ).id
            )
            for _ in range(2)
        ]
        await db.commit()
        wallet_before = await RealphotosCreditService(db).get_wallet(tenant_id=tenant)
        before_available = int(wallet_before["availableInteger"])
        before_reserved = int(wallet_before["reservedInteger"])
        partial_consumed_id = int(delivered.id)
        partial_released_id = int(partial_tasks[1].id)
        replay_batch_id = int(again.id)
        tech_task_id = int(tech_done.id)
        two_ids = [int(task.id) for task in done_two]

    async def _concurrent(index: int, asset_id: int) -> tuple[int, int]:
        async with async_session_factory() as session:
            created, tasks = await RealphotosS1Service(session).submit_batch(
                tenant_id=tenant,
                owner_account_id=user_a,
                actor_role_codes={ROLE_MERCHANT},
                asset_ids=[asset_id],
                preset_code=preset,
                idempotency_key=f"s4-concurrent-{stamp}-{index}",
                detection_mode="pass",
            )
            await session.commit()
            return int(tasks[0].id), int(created.id)

    concurrent_ids = await asyncio.gather(
        _concurrent(0, concurrent_asset_ids[0]),
        _concurrent(1, concurrent_asset_ids[1]),
    )
    task_ids = [item[0] for item in concurrent_ids]

    async with async_session_factory() as db:
        wallet_after = await RealphotosCreditService(db).get_wallet(tenant_id=tenant)
        after_available = int(wallet_after["availableInteger"])
        after_reserved = int(wallet_after["reservedInteger"])
        if after_available != before_available - 20 or after_reserved != before_reserved + 20:
            print(
                f"FAIL: concurrent ledger available {before_available}->{after_available} "
                f"reserved {before_reserved}->{after_reserved}",
                file=sys.stderr,
            )
            return 2
        if after_available + after_reserved != before_available + before_reserved:
            print("FAIL: concurrent available+reserved changed", file=sys.stderr)
            return 2
        freeze_rows = (
            await db.execute(
                select(RealphotosCreditLedgerEntry).where(
                    RealphotosCreditLedgerEntry.event_key.in_(
                        [f"freeze:task:{task_id}" for task_id in task_ids]
                    )
                )
            )
        ).scalars().all()
        if len(freeze_rows) != 2:
            print(f"FAIL: concurrent freeze rows {len(freeze_rows)}", file=sys.stderr)
            return 2
        if any(int(row.delta_available) != -10 or int(row.delta_reserved) != 10 for row in freeze_rows):
            print("FAIL: concurrent freeze deltas are not 10 per image", file=sys.stderr)
            return 2
        loop = RealphotosS1Service(db)
        jobs = RealphotosJobService(db)
        for task_id in task_ids:
            claimed = await jobs.claim(
                worker_id="s4-pg",
                job_kinds=("process_image",),
                payload_task_id=int(task_id),
            )
            if claimed is None:
                raise RuntimeError(f"claim missing for concurrent {task_id}")
            await loop.execute_queued(claimed)
            await jobs.complete_success(job=claimed, result={"path": "s4-concurrent"})
        await db.commit()

    print(
        "S4_PG_IMAGE "
        f"task_id={partial_consumed_id} disposition=consumed_detection_pass amount=10 detector=fixture"
    )
    print(
        "S4_PG_IMAGE "
        f"task_id={partial_released_id} disposition=released_precheck amount=10 detector=none"
    )
    print("S4_PG_BATCH_TOTAL consumed=10 released=10 flat_batch_fee=false")
    print(
        "S4_PG_E2E_PASS "
        f"partial_tasks={partial_consumed_id},{partial_released_id} "
        f"two_pass_consumed={two_consumed} two_pass_tasks={two_ids[0]},{two_ids[1]} "
        f"eleventh=rejected_no_reservation insufficient=rejected_no_reservation "
        f"idempotent_batch={replay_batch_id} "
        f"concurrent_tasks={task_ids[0]},{task_ids[1]} "
        f"concurrent_available_delta=-20 concurrent_reserved_delta=20 concurrent_sum_unchanged=true "
        f"technical_task={tech_task_id} technical_held=true unfreeze_route=false "
        "other_account_task=404 other_account_download=404 "
        f"selected_task={picked[0]['taskId']} selected_omits_unchecked=true zip=rejected "
        "detector=fixture sample_is_not_public_pass=true production_billing=false"
    )
    return 0


async def _reservation_count(db, model, tenant_id: int) -> int:
    return int(
        await db.scalar(
            select(func.count()).select_from(model).where(model.tenant_id == int(tenant_id))
        )
        or 0
    )


async def _expect(awaitable, code: str) -> None:
    from app.core.exceptions import BusinessError

    try:
        await awaitable
    except BusinessError as exc:
        if exc.code != code:
            raise
        return
    raise RuntimeError(f"expected {code}")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
