"""REMAIN-GAP W3/W4 e2e → append /tmp/remain-gap-e2e.log

R5 process/cleanup 认领隔离 · R6 SDK 文件 · R7 OSS stub · R8 front-matter · R9 blocked.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

LOG = Path("/tmp/remain-gap-e2e.log")
REPO = Path(__file__).resolve().parents[3]


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


async def main() -> int:
    if not LOG.exists():
        LOG.write_text("", encoding="utf-8")
    from dotenv import load_dotenv

    load_dotenv(REPO / "aojuai-main/backend/.env")

    import app.capabilities.realphotos.models  # noqa: F401
    import app.domain  # noqa: F401
    from app.capabilities.realphotos.adapters.storage import (
        LocalDiskStorageAdapter,
        get_storage_adapter,
    )
    from app.capabilities.realphotos.constants import JOB_KIND_INBOX_CLEANUP, JOB_KIND_PROCESS_IMAGE, JOB_STATUS_QUEUED
    from app.capabilities.realphotos.models import RealphotosExecutionJob
    from app.capabilities.realphotos.services.bootstrap import bootstrap_s0_accounts
    from app.capabilities.realphotos.services.job_service import RealphotosJobService
    from app.capabilities.realphotos.worker import build_role_task_source
    from app.core.config import settings
    from app.core.exceptions import BusinessError
    from app.infrastructure.database.session import Base, async_session_factory, engine, init_db

    note(f"remain_gap_w3w4_e2e start at={datetime.now(UTC).isoformat()}")
    note("R9_S7_BLOCKED=true")
    note("production_billing=false")

    must(str(settings.DB_DIALECT).startswith("postgres"), f"postgresql_required got={settings.DB_DIALECT}")
    await init_db()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # R8
    arch = REPO / "docs" / "蜜獾原图-v2-项目架构-v1.0.md"
    arch_text = arch.read_text(encoding="utf-8")
    fm = arch_text.split("---", 2)[1]
    must("implementation_status: s0_s6_coded_partial" in fm, "r8_status")
    must("implementation_status: NOT_IMPLEMENTED" not in fm, "r8_not_unimplemented")
    note("R8_ARCH_STATUS_DOC_PASS=true")

    # R6
    gen = REPO / "aojuai-main/frontend/src/generated/realphotos/image_processing.ts"
    must(gen.is_file(), "r6_file")
    must("AUTO-GENERATED" in gen.read_text(encoding="utf-8"), "r6_banner")
    must("/api/v1/realphotos/assets" in gen.read_text(encoding="utf-8"), "r6_assets_path")
    note("R6_FE_SDK_GENERATED_PASS=true")

    # R7
    adapter = get_storage_adapter()
    must(isinstance(adapter, LocalDiskStorageAdapter), f"r7_default={type(adapter)}")
    settings.REALPHOTOS_STORAGE_BACKEND = "oss"
    settings.REALPHOTOS_OSS_ENDPOINT = ""
    try:
        get_storage_adapter()
        must(False, "r7_oss_should_fail")
    except BusinessError as exc:
        must(exc.code == "OSS_NOT_CONFIGURED", f"r7_code={exc.code}")
    settings.REALPHOTOS_STORAGE_BACKEND = "local"
    note("R7_OSS_ADAPTER_STUB_PASS=true")

    # R5：仅 enqueue cleanup，process 不得认领；cleanup 认领之
    async with async_session_factory() as db:
        summary = await bootstrap_s0_accounts(db)
        tenant = int(summary["rp_admin"]["tenantId"])
        owner = int(summary["rp_admin"]["userId"])
        jobs = RealphotosJobService(db)
        stamp = str(int(datetime.now(UTC).timestamp()))
        cleanup_job = await jobs.enqueue(
            tenant_id=tenant,
            owner_account_id=owner,
            job_kind=JOB_KIND_INBOX_CLEANUP,
            payload={"remain_gap": "w3w4", "stamp": stamp},
        )
        await db.commit()
        cleanup_id = int(cleanup_job.id)

    process = build_role_task_source(role="process", worker_id=f"e2e-process-{stamp}")
    for _ in range(3):
        claimed = await process.claim()
        if claimed is None:
            break
        must(int(claimed["job_id"]) != cleanup_id, "r5_process_claimed_cleanup")
        must(claimed["job_kind"] != JOB_KIND_INBOX_CLEANUP, f"r5_process_kind={claimed['job_kind']}")
        must(claimed["job_kind"] != "output_cleanup", "r5_process_no_output_cleanup")

    async with async_session_factory() as db:
        still = (
            await db.execute(select(RealphotosExecutionJob).where(RealphotosExecutionJob.id == cleanup_id))
        ).scalar_one()
        must(str(still.status) == JOB_STATUS_QUEUED, f"r5_cleanup_still={still.status}")
        must(still.claimed_by is None, "r5_cleanup_unclaimed")

    cleanup = build_role_task_source(role="cleanup", worker_id=f"e2e-cleanup-{stamp}")
    claimed_c = None
    for _ in range(5):
        claimed_c = await cleanup.claim()
        if claimed_c is None:
            break
        if int(claimed_c["job_id"]) == cleanup_id:
            break
        must(claimed_c["job_kind"] != JOB_KIND_PROCESS_IMAGE, f"r5_cleanup_got_process={claimed_c['job_kind']}")
    must(claimed_c is not None and int(claimed_c["job_id"]) == cleanup_id, "r5_cleanup_claim_target")
    must(claimed_c["job_kind"] == JOB_KIND_INBOX_CLEANUP, f"r5_cleanup_kind={claimed_c['job_kind']}")

    from scripts import run_realphotos_cleanup_worker as cleanup_mod
    from scripts import run_realphotos_notify_worker as notify_mod
    from scripts import run_realphotos_process_worker as process_mod

    must(callable(notify_mod.main), "r5_notify_cli")
    must(callable(cleanup_mod.main), "r5_cleanup_cli")
    must(callable(process_mod.main), "r5_process_cli")
    must((REPO / "docs/mihuanyuantu-v2/WORKER_TOPOLOGY.md").is_file(), "r5_topo_doc")
    must(
        (REPO / "docs/mihuanyuantu-v2/deploy-examples/realphotos-process.service").is_file(),
        "r5_systemd",
    )
    note("R5_WORKER_TOPOLOGY_PASS=true")
    note("R9_S7_BLOCKED=true")
    note("production_billing=false")
    note("REMAIN_GAP_W3_PASS=true")
    note("REMAIN_GAP_W4_PASS=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
