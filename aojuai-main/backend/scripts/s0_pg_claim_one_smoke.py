"""S0 PostgreSQL claim_one smoke (run on development host).

Requires DB_DRIVER=postgresql and a migrated DB with realphotos tables.
Uses the process engine (not the pack's in-memory pytest fixture).
"""

from __future__ import annotations

import asyncio
import os
import sys


async def _main() -> int:
    os.environ.setdefault("AOJ_ENABLED_MODULES", "realphotos")
    from app.core.config import settings

    if not str(settings.DB_DIALECT).startswith("postgres"):
        print(f"FAIL: expected postgresql dialect, got {settings.DB_DIALECT!r}", file=sys.stderr)
        return 2

    from app.capabilities.realphotos.services.bootstrap import bootstrap_s0_accounts
    from app.capabilities.realphotos.services.job_service import RealphotosJobService
    from app.infrastructure.database.session import async_session_factory, init_db

    await init_db()
    async with async_session_factory() as db:
        summary = await bootstrap_s0_accounts(db)
        tenant1 = int(summary["rp_merchant_a1"]["tenantId"])
        owner = int(summary["rp_merchant_a1"]["userId"])
        jobs = RealphotosJobService(db)
        job = await jobs.enqueue(
            tenant_id=tenant1,
            owner_account_id=owner,
            job_kind="heartbeat",
            payload={"smoke": "pg-claim-one"},
        )
        await db.commit()
        claimed = await jobs.claim(worker_id="devhost-s0-smoke")
        if claimed is None or int(claimed.id) != int(job.id):
            print("FAIL: claim_one did not return enqueued job", file=sys.stderr)
            return 1
        if str(settings.DB_DIALECT) == "postgresql" and not claimed.claimed_by:
            print("FAIL: missing claimed_by after PG claim", file=sys.stderr)
            return 1
        finished = await jobs.complete_success(job=claimed, result={"ok": True, "path": "claim_one"})
        await db.commit()
        reloaded = await jobs.get_job(tenant_id=tenant1, job_id=int(job.id))
        print(
            "S0_PG_CLAIM_ONE_PASS",
            f"job_id={reloaded.id}",
            f"status={reloaded.status}",
            f"dialect={settings.DB_DIALECT}",
            f"claimed_by={claimed.claimed_by}",
        )
        assert reloaded.status == "succeeded"
        assert finished.result.get("ok") is True
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
