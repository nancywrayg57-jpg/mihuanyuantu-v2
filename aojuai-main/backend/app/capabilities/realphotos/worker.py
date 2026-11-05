"""S0 worker: claim durable heartbeat/noop jobs to terminal success."""

from __future__ import annotations

from typing import Any

from app.capabilities.realphotos.services.job_service import RealphotosJobService
from app.core.logger import get_logger
from app.core.task_queue import QueuePolicy
from app.core.worker_registry import WorkerDefinition
from app.infrastructure.database.session import async_session_factory

logger = get_logger(__name__)

WORKER = WorkerDefinition(
    code="realphotos_heartbeat",
    label="蜜獾原图心跳队列",
    module_code="realphotos",
    task_source_factory="app.capabilities.realphotos.worker:build_task_source",
    default_concurrency=1,
    max_concurrency=4,
    poll_interval=1.0,
    queue=QueuePolicy(
        delivery="at_least_once",
        lease_seconds=60,
        max_attempts=3,
        retry_backoff_seconds=(2, 5, 10),
    ),
    description="S0：消费 cap_realphotos_execution_jobs 的 heartbeat/noop 至终态",
)


class RealphotosHeartbeatTaskSource:
    def __init__(self, *, worker_id: str = "realphotos_heartbeat") -> None:
        self.worker_id = worker_id

    async def claim(self) -> dict[str, Any] | None:
        async with async_session_factory() as db:
            service = RealphotosJobService(db)
            job = await service.claim(worker_id=self.worker_id)
            if job is None:
                await db.rollback()
                return None
            payload = {
                "job_id": int(job.id),
                "tenant_id": int(job.tenant_id),
                "job_kind": job.job_kind,
                "claimed_by": job.claimed_by,
            }
            await db.commit()
            return payload

    async def run(self, claimed: dict[str, Any]) -> None:
        async with async_session_factory() as db:
            service = RealphotosJobService(db)
            job = await service.get_job(
                tenant_id=int(claimed["tenant_id"]),
                job_id=int(claimed["job_id"]),
            )
            # 防御：租约身份仍匹配才写终态
            if str(job.claimed_by or "") != str(claimed.get("claimed_by") or ""):
                await db.rollback()
                logger.warning("realphotos_heartbeat_lease_mismatch", job_id=claimed["job_id"])
                return
            await service.complete_success(
                job=job,
                result={"ok": True, "kind": job.job_kind, "worker": self.worker_id},
            )
            await db.commit()
            logger.info(
                "realphotos_heartbeat_succeeded",
                job_id=int(job.id),
                tenant_id=int(job.tenant_id),
            )

    def describe(self, claimed: dict[str, Any]) -> dict[str, Any]:
        return {
            "job_id": claimed.get("job_id"),
            "tenant_id": claimed.get("tenant_id"),
            "job_kind": claimed.get("job_kind"),
        }


def build_task_source() -> RealphotosHeartbeatTaskSource:
    return RealphotosHeartbeatTaskSource()
