"""realphotos durable queue workers（AD-001 分角色认领）。"""

from __future__ import annotations

from typing import Any

from app.capabilities.realphotos.services.job_service import RealphotosJobService
from app.capabilities.realphotos.worker_roles import PROCESS_JOB_KINDS, job_kinds_for_role
from app.core.logger import get_logger
from app.core.task_queue import QueuePolicy
from app.core.worker_registry import WorkerDefinition
from app.infrastructure.database.session import async_session_factory

logger = get_logger(__name__)

# 注册入口：默认 process 角色（不再认领 cleanup，避免与 cleanup 进程抢队列）
WORKER = WorkerDefinition(
    code="realphotos_heartbeat",
    label="蜜獾原图处理队列（process）",
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
    description="AD-001：认领 process 侧 job（heartbeat/noop/process_image）；cleanup/notify 另进程",
)


class RealphotosRoleTaskSource:
    """按角色过滤 job_kind，保证 process/cleanup 互不抢错队列。"""

    def __init__(
        self,
        *,
        worker_id: str,
        job_kinds: tuple[str, ...],
        role: str,
    ) -> None:
        self.worker_id = worker_id
        self.job_kinds = tuple(job_kinds)
        self.role = role

    async def claim(self) -> dict[str, Any] | None:
        async with async_session_factory() as db:
            service = RealphotosJobService(db)
            job = await service.claim(worker_id=self.worker_id, job_kinds=self.job_kinds)
            if job is None:
                await db.rollback()
                return None
            # 防御：即便 service 放宽，也不接受角色外 kind
            if str(job.job_kind) not in set(self.job_kinds):
                await db.rollback()
                logger.error(
                    "realphotos_role_claim_kind_mismatch",
                    role=self.role,
                    job_kind=job.job_kind,
                    allowed=list(self.job_kinds),
                )
                return None
            payload = {
                "job_id": int(job.id),
                "tenant_id": int(job.tenant_id),
                "job_kind": job.job_kind,
                "claimed_by": job.claimed_by,
                "role": self.role,
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
            if str(job.claimed_by or "") != str(claimed.get("claimed_by") or ""):
                await db.rollback()
                logger.warning("realphotos_role_lease_mismatch", job_id=claimed["job_id"], role=self.role)
                return
            if str(job.job_kind) not in set(self.job_kinds):
                await db.rollback()
                logger.error(
                    "realphotos_role_run_kind_rejected",
                    role=self.role,
                    job_kind=job.job_kind,
                )
                return
            result: dict[str, Any] = {
                "ok": True,
                "kind": job.job_kind,
                "worker": self.worker_id,
                "role": self.role,
            }
            if job.job_kind == "process_image":
                from app.capabilities.realphotos.services.s1_processing import RealphotosS1Service

                await RealphotosS1Service(db).execute_queued(job)
            elif job.job_kind == "inbox_cleanup":
                from app.capabilities.realphotos.services.s1_processing import RealphotosS1Service

                cleanup = await RealphotosS1Service(db).cleanup_expired_inbox()
                result.update(cleanup)
            elif job.job_kind == "output_cleanup":
                from app.capabilities.realphotos.services.s1_processing import RealphotosS1Service

                cleanup = await RealphotosS1Service(db).cleanup_expired_outputs()
                result.update(cleanup)
            await service.complete_success(job=job, result=result)
            await db.commit()
            logger.info(
                "realphotos_role_job_succeeded",
                job_id=int(job.id),
                tenant_id=int(job.tenant_id),
                role=self.role,
                job_kind=job.job_kind,
            )

    def describe(self, claimed: dict[str, Any]) -> dict[str, Any]:
        return {
            "job_id": claimed.get("job_id"),
            "tenant_id": claimed.get("tenant_id"),
            "job_kind": claimed.get("job_kind"),
            "role": claimed.get("role") or self.role,
        }


def build_task_source() -> RealphotosRoleTaskSource:
    return RealphotosRoleTaskSource(
        worker_id="realphotos_heartbeat",
        job_kinds=PROCESS_JOB_KINDS,
        role="process",
    )


def build_role_task_source(*, role: str, worker_id: str | None = None) -> RealphotosRoleTaskSource:
    kinds = job_kinds_for_role(role)
    wid = worker_id or f"realphotos_{role}"
    return RealphotosRoleTaskSource(worker_id=wid, job_kinds=kinds, role=role)
