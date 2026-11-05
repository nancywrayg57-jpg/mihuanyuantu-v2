"""Durable job enqueue + claim for S0 worker skeleton."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.realphotos.constants import (
    JOB_KIND_HEARTBEAT,
    JOB_KIND_NOOP,
    JOB_STATUS_FAILED,
    JOB_STATUS_QUEUED,
    JOB_STATUS_RUNNING,
    JOB_STATUS_SUCCEEDED,
)
from app.capabilities.realphotos.models import RealphotosExecutionJob
from app.core.config import settings
from app.core.exceptions import BusinessError, NotFoundError
from app.core.task_queue import QueuePolicy, claim_one

QUEUE_POLICY = QueuePolicy(
    delivery="at_least_once",
    lease_seconds=60,
    max_attempts=3,
    retry_backoff_seconds=(2, 5, 10),
    fairness_key=None,
    renew_lease=False,
    queued_status=JOB_STATUS_QUEUED,
    running_status=JOB_STATUS_RUNNING,
    failed_status=JOB_STATUS_FAILED,
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


class RealphotosJobService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def enqueue(
        self,
        *,
        tenant_id: int,
        owner_account_id: int | None,
        job_kind: str = JOB_KIND_HEARTBEAT,
        payload: dict | None = None,
    ) -> RealphotosExecutionJob:
        kind = str(job_kind or "").strip() or JOB_KIND_HEARTBEAT
        if kind not in {JOB_KIND_HEARTBEAT, JOB_KIND_NOOP}:
            raise BusinessError(message="S0 仅允许 heartbeat/noop 任务", code="INPUT_INVALID")
        job = RealphotosExecutionJob(
            tenant_id=int(tenant_id),
            job_kind=kind,
            status=JOB_STATUS_QUEUED,
            owner_account_id=int(owner_account_id) if owner_account_id else None,
            payload=dict(payload or {}),
            available_at=_utcnow(),
        )
        self.db.add(job)
        await self.db.flush()
        return job

    async def get_job(self, *, tenant_id: int, job_id: int) -> RealphotosExecutionJob:
        result = await self.db.execute(
            select(RealphotosExecutionJob).where(
                RealphotosExecutionJob.id == int(job_id),
                RealphotosExecutionJob.tenant_id == int(tenant_id),
                RealphotosExecutionJob.deleted_at.is_(None),
            )
        )
        job = result.scalar_one_or_none()
        if job is None:
            raise NotFoundError(message="任务不存在")
        return job

    async def claim(self, *, worker_id: str) -> RealphotosExecutionJob | None:
        if str(settings.DB_DIALECT) == "postgresql":
            return await claim_one(
                self.db,
                RealphotosExecutionJob,
                policy=QUEUE_POLICY,
                worker_id=worker_id,
            )
        # SQLite / CI：无 SKIP LOCKED 时用条件更新做单 worker 认领
        result = await self.db.execute(
            select(RealphotosExecutionJob)
            .where(
                RealphotosExecutionJob.deleted_at.is_(None),
                RealphotosExecutionJob.status == JOB_STATUS_QUEUED,
            )
            .order_by(RealphotosExecutionJob.created_at.asc(), RealphotosExecutionJob.id.asc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        token = f"{worker_id[:40]}#{secrets.token_hex(8)}"[:64]
        moment = _utcnow()
        upd = await self.db.execute(
            update(RealphotosExecutionJob)
            .where(
                RealphotosExecutionJob.id == int(row.id),
                RealphotosExecutionJob.status == JOB_STATUS_QUEUED,
            )
            .values(
                status=JOB_STATUS_RUNNING,
                claimed_by=token,
                claimed_at=moment,
                attempts=int(row.attempts or 0) + 1,
            )
        )
        if int(getattr(upd, "rowcount", 0) or 0) != 1:
            return None
        await self.db.refresh(row)
        return row

    async def complete_success(
        self, *, job: RealphotosExecutionJob, result: dict | None = None
    ) -> RealphotosExecutionJob:
        token = str(job.claimed_by or "")
        upd = await self.db.execute(
            update(RealphotosExecutionJob)
            .where(
                RealphotosExecutionJob.id == int(job.id),
                RealphotosExecutionJob.claimed_by == token,
                RealphotosExecutionJob.status == JOB_STATUS_RUNNING,
            )
            .values(
                status=JOB_STATUS_SUCCEEDED,
                result=dict(result or {"ok": True}),
                finished_at=_utcnow(),
                last_error=None,
            )
        )
        if int(getattr(upd, "rowcount", 0) or 0) != 1:
            raise BusinessError(message="租约丢失，放弃写回", code="LEASE_LOST")
        await self.db.refresh(job)
        return job

    def to_payload(self, job: RealphotosExecutionJob) -> dict:
        return {
            "id": str(int(job.id)),
            "tenantId": str(int(job.tenant_id)),
            "jobKind": job.job_kind,
            "status": job.status,
            "attempts": int(job.attempts or 0),
            "payload": dict(job.payload or {}),
            "result": dict(job.result or {}),
            "lastError": job.last_error,
            "finishedAt": job.finished_at.isoformat() if job.finished_at else None,
        }
