"""S1 single-image loop: upload, submit, worker execution, download, soft delete."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.realphotos.adapters.storage import get_storage_adapter
from app.capabilities.realphotos.constants import (
    DETECT_NOT_PASSED,
    DETECT_PASS,
    DETECT_TECHNICAL,
    INBOX_TTL_DAYS,
    OUTPUT_TTL_HOURS,
    PRE_REVIEW_REJECT,
    PROCESS_UNIT_CREDITS,
    RUNNING_TASK_STATUSES,
    S1_MAX_IMAGES,
    TASK_DELIVERED,
    TASK_DETECTION,
    TASK_FAILED,
    TASK_FULL_PROCESSING,
    TASK_PRE_REVIEW,
    TASK_PRE_REVIEW_FAILED,
    TASK_PRE_REVIEW_PASSED,
    TASK_SUBMITTED,
)
from app.capabilities.realphotos.models import (
    RealphotosAsset,
    RealphotosBatch,
    RealphotosCreditReservation,
    RealphotosDetectionResult,
    RealphotosExecutionJob,
    RealphotosImageTask,
    RealphotosInboxMessage,
    RealphotosOutbox,
    RealphotosStageResult,
    RealphotosTaskChain,
    RealphotosTaskSnapshot,
)
from app.capabilities.realphotos.permissions import ROLE_ADMIN
from app.capabilities.realphotos.services.credit_service import RealphotosCreditService
from app.capabilities.realphotos.services.job_service import RealphotosJobService
from app.capabilities.realphotos.services.s1_catalog import preset_by_code
from app.capabilities.realphotos.services.s1_upload import inspect_upload
from app.core.exceptions import AOJUException, BusinessError, NotFoundError

_PIPELINE = "s2-five-layer-1"
_STAGES = ("L1", "L2", "L3", "L4", "L5")


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _report(*, passed: bool, total: int, each: int, reason: str | None) -> dict:
    # total_score 由替身直接给出，不用五维平均冒充模型总分。
    return {
        "noise": each,
        "depthOfField": each,
        "lighting": each,
        "colorRealism": each,
        "overallRealism": each,
        "total_score": total,
        "passed": passed,
        "reason": reason,
    }


class RealphotosS1Service:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.credits = RealphotosCreditService(db)
        self.jobs = RealphotosJobService(db)

    async def upload(
        self,
        *,
        tenant_id: int,
        owner_account_id: int,
        data: bytes,
    ) -> RealphotosAsset:
        meta = inspect_upload(data)
        token = secrets.token_hex(8)
        key = f"tenant/{int(tenant_id)}/upload/{token}.{meta['extension']}"
        get_storage_adapter().put_bytes(key, bytes(data), content_type=meta["content_type"])
        asset = RealphotosAsset(
            tenant_id=int(tenant_id),
            owner_account_id=int(owner_account_id),
            object_key=key,
            content_type=meta["content_type"],
            byte_size=int(meta["byte_size"]),
            width=int(meta["width"]),
            height=int(meta["height"]),
            sha256=meta["sha256"],
            origin_kind="local_upload",
        )
        self.db.add(asset)
        await self.db.flush()
        return asset

    async def submit_single(
        self,
        *,
        tenant_id: int,
        owner_account_id: int,
        actor_role_codes: set[str],
        asset_id: int,
        preset_code: str,
        idempotency_key: str,
        pre_review_mode: str = "pass",
        detection_mode: str = DETECT_PASS,
    ) -> RealphotosImageTask:
        if S1_MAX_IMAGES != 1:
            raise BusinessError(message="S1 仅单张", code="INPUT_INVALID")
        key = str(idempotency_key or "").strip()
        if not key:
            raise BusinessError(message="缺少幂等键", code="INPUT_INVALID")
        existing = await self._task_by_idempotency(tenant_id=tenant_id, idempotency_key=key)
        if existing is not None:
            return existing
        preset = preset_by_code(preset_code)
        if preset is None:
            raise BusinessError(message="预设未启用或不存在", code="PRESET_REJECTED")
        review = pre_review_mode if pre_review_mode in {"pass", PRE_REVIEW_REJECT} else "pass"
        detect = detection_mode if detection_mode in {DETECT_PASS, DETECT_NOT_PASSED, DETECT_TECHNICAL} else DETECT_PASS
        if (review != "pass" or detect != DETECT_PASS) and ROLE_ADMIN not in actor_role_codes:
            raise BusinessError(message="仅管理员可注入预审或检测结果", code="FORBIDDEN_INJECT")
        asset = await self._asset(tenant_id=tenant_id, asset_id=asset_id)
        if asset.deleted_at is not None:
            raise NotFoundError(message="资源不存在")
        batch = RealphotosBatch(
            tenant_id=int(tenant_id),
            owner_account_id=int(owner_account_id),
            image_count=1,
            preset_code=preset["code"],
        )
        self.db.add(batch)
        await self.db.flush()
        chain = RealphotosTaskChain(tenant_id=int(tenant_id), batch_id=int(batch.id), round_no=1)
        self.db.add(chain)
        await self.db.flush()
        task = RealphotosImageTask(
            tenant_id=int(tenant_id),
            owner_account_id=int(owner_account_id),
            batch_id=int(batch.id),
            chain_id=int(chain.id),
            asset_id=int(asset.id),
            status=TASK_SUBMITTED,
            preset_code=preset["code"],
            preset_snapshot=preset,
            pre_review_mode=review,
            detection_mode=detect,
            idempotency_key=key,
            pipeline_version=_PIPELINE,
        )
        self.db.add(task)
        await self.db.flush()
        self.db.add(
            RealphotosTaskSnapshot(tenant_id=int(tenant_id), task_id=int(task.id), snapshot=preset)
        )
        await self.credits.freeze(
            tenant_id=int(tenant_id),
            amount=PROCESS_UNIT_CREDITS,
            operator_user_id=int(owner_account_id),
            event_key=f"freeze:task:{int(task.id)}",
            reference={"taskId": int(task.id), "images": 1},
        )
        self.db.add(
            RealphotosCreditReservation(
                tenant_id=int(tenant_id),
                task_id=int(task.id),
                amount=PROCESS_UNIT_CREDITS,
                state="reserved",
                operator_user_id=int(owner_account_id),
            )
        )
        await self.jobs.enqueue_process(
            tenant_id=int(tenant_id),
            owner_account_id=int(owner_account_id),
            payload={"task_id": int(task.id)},
        )
        await self.db.flush()
        return task

    async def execute_queued(self, job: RealphotosExecutionJob) -> RealphotosImageTask:
        task_id = int((job.payload or {}).get("task_id") or 0)
        task = await self._task(tenant_id=int(job.tenant_id), task_id=task_id)
        if task.status in {TASK_DELIVERED, TASK_FAILED, TASK_PRE_REVIEW_FAILED}:
            return task
        task.status = TASK_PRE_REVIEW
        await self.db.flush()
        if task.pre_review_mode == PRE_REVIEW_REJECT:
            await self._release(task, disposition="released_pre_review_reject")
            task.status = TASK_PRE_REVIEW_FAILED
            task.failure_class = "pre_review"
            await self._notify(task, title="预审未通过", body="占位预审被管理员拒绝，未扣处理积分。")
            await self.db.flush()
            return task
        task.status = TASK_PRE_REVIEW_PASSED
        task.status = TASK_FULL_PROCESSING
        task.status = TASK_DETECTION
        await self.db.flush()
        if task.detection_mode == DETECT_TECHNICAL:
            # 管理员 2026-11-06：S1 技术失败保持冻结，等到开发技术客服时再释放。
            reservation = await self._reservation(task)
            reservation.state = "held"
            task.status = TASK_FAILED
            task.failure_class = "technical"
            task.credit_disposition = "held_until_tech_support"
            await self._notify(
                task,
                title="技术异常",
                body="规则替身技术异常。积分保持冻结，待技术客服阶段处理，本次未扣费。",
            )
            await self.db.flush()
            return task
        try:
            jpeg = await self._five_layer_jpeg(task)
        except BusinessError as exc:
            if exc.code not in {"OUTPUT_CONSTRAINT_UNSATISFIED", "EXIF_WRITE_FAILED"}:
                raise
            reservation = await self._reservation(task)
            reservation.state = "held"
            task.status = TASK_FAILED
            task.failure_class = exc.code
            task.credit_disposition = "held_until_tech_support"
            await self._notify(task, title="技术异常", body=exc.message)
            await self.db.flush()
            return task
        for stage in _STAGES:
            self.db.add(
                RealphotosStageResult(
                    tenant_id=int(task.tenant_id),
                    task_id=int(task.id),
                    stage_code=stage,
                    stage_status="completed",
                )
            )
        out_key = f"tenant/{int(task.tenant_id)}/output/{int(task.id)}.jpg"
        stored = get_storage_adapter().put_bytes(out_key, jpeg, content_type="image/jpeg")
        task.output_object_key = stored.object_key
        task.output_byte_size = stored.size
        task.output_expires_at = _utcnow() + timedelta(hours=OUTPUT_TTL_HOURS)
        passed = task.detection_mode == DETECT_PASS
        if passed:
            report = _report(passed=True, total=90, each=90, reason=None)
            await self._consume(task, disposition="consumed_detection_pass")
            task.status = TASK_DELIVERED
            await self._notify(task, title="处理完成", body="单张处理已交付，已结算 10 积分。")
        else:
            report = _report(passed=False, total=60, each=40, reason="规则替身：未达通过线")
            await self._release(task, disposition="released_detection_not_passed")
            task.status = TASK_FAILED
            task.failure_class = "detection_not_passed"
            await self._notify(task, title="检测未通过", body="有效结果可下载，该张处理费为 0。")
        self.db.add(
            RealphotosDetectionResult(
                tenant_id=int(task.tenant_id),
                task_id=int(task.id),
                noise=report["noise"],
                depth_of_field=report["depthOfField"],
                lighting=report["lighting"],
                color_realism=report["colorRealism"],
                overall_realism=report["overallRealism"],
                total_score=report["total_score"],
                passed=bool(report["passed"]),
                reason=report["reason"],
                detector="fixture",
            )
        )
        await self.db.flush()
        return task

    async def soft_delete_asset(self, *, tenant_id: int, asset_id: int) -> None:
        asset = await self._asset(tenant_id=tenant_id, asset_id=asset_id)
        running = await self.db.execute(
            select(RealphotosImageTask.id).where(
                RealphotosImageTask.tenant_id == int(tenant_id),
                RealphotosImageTask.asset_id == int(asset.id),
                RealphotosImageTask.deleted_at.is_(None),
                RealphotosImageTask.status.in_(tuple(RUNNING_TASK_STATUSES)),
            )
        )
        if running.first() is not None:
            raise BusinessError(message="运行中任务占用该资源，禁止删除", code="ASSET_IN_USE")
        asset.deleted_at = _utcnow()
        await self.db.flush()

    async def read_object_for_gateway(self, *, tenant_id: int, object_key: str) -> tuple[str, bytes]:
        key = object_key.strip().lstrip("/")
        now = _utcnow()
        if "/output/" in key:
            result = await self.db.execute(
                select(RealphotosImageTask).where(
                    RealphotosImageTask.tenant_id == int(tenant_id),
                    RealphotosImageTask.output_object_key == key,
                    RealphotosImageTask.deleted_at.is_(None),
                )
            )
            task = result.scalar_one_or_none()
            if task is None:
                raise NotFoundError(message="对象不存在")
            expires = task.output_expires_at
            if expires is not None and _as_utc(expires) <= now:
                raise AOJUException(message="处理结果已过期", code="DOWNLOAD_EXPIRED", status_code=410)
            handle = get_storage_adapter().open_read(key)
            try:
                return "image/jpeg", handle.read()
            finally:
                handle.close()
        if "/upload/" in key:
            result = await self.db.execute(
                select(RealphotosAsset).where(
                    RealphotosAsset.tenant_id == int(tenant_id),
                    RealphotosAsset.object_key == key,
                    RealphotosAsset.deleted_at.is_(None),
                )
            )
            asset = result.scalar_one_or_none()
            if asset is None:
                raise NotFoundError(message="对象不存在")
            handle = get_storage_adapter().open_read(key)
            try:
                return asset.content_type, handle.read()
            finally:
                handle.close()
        raise NotFoundError(message="对象不存在")

    async def list_inbox(self, *, tenant_id: int, recipient_user_id: int) -> list[RealphotosInboxMessage]:
        now = _utcnow()
        rows = (
            await self.db.execute(
                select(RealphotosInboxMessage).where(
                    RealphotosInboxMessage.tenant_id == int(tenant_id),
                    RealphotosInboxMessage.recipient_user_id == int(recipient_user_id),
                    RealphotosInboxMessage.deleted_at.is_(None),
                )
            )
        ).scalars().all()
        return [row for row in rows if _as_utc(row.expires_at) > now]

    async def get_task(self, *, tenant_id: int, task_id: int) -> RealphotosImageTask:
        return await self._task(tenant_id=tenant_id, task_id=task_id)

    async def detection_payload(self, *, tenant_id: int, task_id: int) -> dict | None:
        row = (
            await self.db.execute(
                select(RealphotosDetectionResult).where(
                    RealphotosDetectionResult.tenant_id == int(tenant_id),
                    RealphotosDetectionResult.task_id == int(task_id),
                    RealphotosDetectionResult.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        accepted = bool(row.passed) and int(row.total_score) >= 75
        return {
            "noise": int(row.noise),
            "depthOfField": int(row.depth_of_field),
            "lighting": int(row.lighting),
            "colorRealism": int(row.color_realism),
            "overallRealism": int(row.overall_realism),
            "total_score": int(row.total_score),
            "passed": bool(row.passed),
            "accepted": accepted,
            "reason": row.reason,
            "detector": row.detector,
        }

    async def _five_layer_jpeg(self, task: RealphotosImageTask) -> bytes:
        from app.capabilities.realphotos.services.five_layer import run_five_layer

        asset = await self._asset(tenant_id=int(task.tenant_id), asset_id=int(task.asset_id))
        handle = get_storage_adapter().open_read(asset.object_key)
        try:
            source = handle.read()
        finally:
            handle.close()
        result = run_five_layer(
            source=source,
            preset=dict(task.preset_snapshot or {}),
            seed=int(task.id),
        )
        self.db.add(
            RealphotosTaskSnapshot(
                tenant_id=int(task.tenant_id),
                task_id=int(task.id),
                snapshot={"kind": "s2_exif_field_ledger", "fields": result.fields},
            )
        )
        return result.jpeg

    async def _release(self, task: RealphotosImageTask, *, disposition: str) -> None:
        reservation = await self._reservation(task)
        if reservation.state != "reserved":
            return
        await self.credits.release_reserved(
            tenant_id=int(task.tenant_id),
            amount=int(reservation.amount),
            operator_user_id=int(task.owner_account_id),
            event_key=f"release:task:{int(task.id)}",
            reference={"taskId": int(task.id), "disposition": disposition},
        )
        reservation.state = "released"
        task.credit_disposition = disposition

    async def _consume(self, task: RealphotosImageTask, *, disposition: str) -> None:
        reservation = await self._reservation(task)
        if reservation.state != "reserved":
            return
        await self.credits.consume_reserved(
            tenant_id=int(task.tenant_id),
            amount=int(reservation.amount),
            operator_user_id=int(task.owner_account_id),
            event_key=f"consume:task:{int(task.id)}",
            reference={"taskId": int(task.id), "disposition": disposition},
        )
        reservation.state = "consumed"
        task.credit_disposition = disposition

    async def _notify(self, task: RealphotosImageTask, *, title: str, body: str) -> None:
        event_key = f"inbox:task:{int(task.id)}:{task.failure_class or task.status}"
        self.db.add(
            RealphotosInboxMessage(
                tenant_id=int(task.tenant_id),
                recipient_user_id=int(task.owner_account_id),
                event_key=event_key,
                title=title,
                body=body,
                expires_at=_utcnow() + timedelta(days=INBOX_TTL_DAYS),
            )
        )
        self.db.add(
            RealphotosOutbox(
                tenant_id=int(task.tenant_id),
                event_key=event_key,
                event_type="inbox",
                payload={"taskId": int(task.id), "title": title},
                status="pending",
            )
        )

    async def _reservation(self, task: RealphotosImageTask) -> RealphotosCreditReservation:
        row = (
            await self.db.execute(
                select(RealphotosCreditReservation).where(
                    RealphotosCreditReservation.tenant_id == int(task.tenant_id),
                    RealphotosCreditReservation.task_id == int(task.id),
                    RealphotosCreditReservation.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise BusinessError(message="缺少冻结记录", code="RESERVATION_MISSING")
        return row

    async def _asset(self, *, tenant_id: int, asset_id: int) -> RealphotosAsset:
        row = (
            await self.db.execute(
                select(RealphotosAsset).where(
                    RealphotosAsset.id == int(asset_id),
                    RealphotosAsset.tenant_id == int(tenant_id),
                    RealphotosAsset.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError(message="资源不存在")
        return row

    async def _task(self, *, tenant_id: int, task_id: int) -> RealphotosImageTask:
        row = (
            await self.db.execute(
                select(RealphotosImageTask).where(
                    RealphotosImageTask.id == int(task_id),
                    RealphotosImageTask.tenant_id == int(tenant_id),
                    RealphotosImageTask.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError(message="任务不存在")
        return row

    async def _task_by_idempotency(self, *, tenant_id: int, idempotency_key: str) -> RealphotosImageTask | None:
        return (
            await self.db.execute(
                select(RealphotosImageTask).where(
                    RealphotosImageTask.tenant_id == int(tenant_id),
                    RealphotosImageTask.idempotency_key == idempotency_key,
                    RealphotosImageTask.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
