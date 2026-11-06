"""S1 single-image loop: upload, submit, worker execution, download, soft delete."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.realphotos.adapters.storage import get_storage_adapter
from app.capabilities.realphotos.constants import (
    DETECT_GEMINI,
    DETECT_NOT_PASSED,
    DETECT_PASS,
    DETECT_TECHNICAL,
    INBOX_TTL_DAYS,
    OUTPUT_TTL_HOURS,
    PRE_REVIEW_REJECT,
    PROCESS_UNIT_CREDITS,
    RUNNING_TASK_STATUSES,
    S1_MAX_IMAGES,
    S4_MAX_IMAGES,
    S4_MIN_IMAGES,
    TASK_AUTO_REPROCESS_PENDING,
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
    RealphotosChainPolicy,
    RealphotosCreditReservation,
    RealphotosDetectionResult,
    RealphotosExecutionJob,
    RealphotosImageTask,
    RealphotosInboxMessage,
    RealphotosOutbox,
    RealphotosRedoSetting,
    RealphotosStageResult,
    RealphotosTaskChain,
    RealphotosTaskSnapshot,
)
from app.capabilities.realphotos.permissions import ROLE_ADMIN
from app.capabilities.realphotos.services.credit_service import RealphotosCreditService
from app.capabilities.realphotos.services.job_service import RealphotosJobService
from app.capabilities.realphotos.services.redo_policy import (
    MAX_EXECUTIONS,
    accepted,
    should_auto_redo,
    validate_setting,
)
from app.capabilities.realphotos.services.s1_catalog import preset_by_code
from app.capabilities.realphotos.services.s1_upload import inspect_upload
from app.core.exceptions import AOJUException, BusinessError, NotFoundError

_PIPELINE = "s2-five-layer-1"
_STAGES = ("L1", "L2", "L3", "L4", "L5")
_RETRYABLE_FAILURES = frozenset(
    {
        "technical",
        "gemini_technical",
        "GEMINI_TECHNICAL",
        "GEMINI_NOT_CONFIGURED",
        "OUTPUT_CONSTRAINT_UNSATISFIED",
        "EXIF_WRITE_FAILED",
    }
)


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
        if detection_mode == DETECT_GEMINI:
            detect = DETECT_GEMINI
        elif detection_mode in {DETECT_PASS, DETECT_NOT_PASSED, DETECT_TECHNICAL}:
            detect = detection_mode
        else:
            detect = DETECT_PASS
        injected = review != "pass" or detect in {DETECT_NOT_PASSED, DETECT_TECHNICAL}
        if injected and ROLE_ADMIN not in actor_role_codes:
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
        setting = await self.get_redo_setting(tenant_id=int(tenant_id))
        self.db.add(
            RealphotosChainPolicy(
                tenant_id=int(tenant_id),
                chain_id=int(chain.id),
                enabled=bool(setting.enabled),
                score_threshold=int(setting.score_threshold),
                extra_rounds=int(setting.extra_rounds),
                execution_count=1,
                origin="submit",
            )
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

    async def submit_batch(
        self,
        *,
        tenant_id: int,
        owner_account_id: int,
        actor_role_codes: set[str],
        asset_ids: list[int],
        preset_code: str,
        idempotency_key: str,
        pre_review_mode: str = "pass",
        detection_mode: str = DETECT_PASS,
    ) -> tuple[RealphotosBatch, list[RealphotosImageTask]]:
        """FR-015 / FR-016：1–10 张共用一个预设。整单拒绝不留预留；通过后按张冻结。"""
        key = str(idempotency_key or "").strip()
        if not key:
            raise BusinessError(message="缺少幂等键", code="INPUT_INVALID")
        if len(key) > 110:
            raise BusinessError(message="幂等键过长", code="INPUT_INVALID")
        existing = await self._tasks_for_batch_key(tenant_id=int(tenant_id), batch_key=key)
        if existing:
            batch = await self._batch_row(tenant_id=int(tenant_id), batch_id=int(existing[0].batch_id))
            return batch, existing
        requested = [int(asset_id) for asset_id in asset_ids]
        if len(requested) < S4_MIN_IMAGES or len(requested) > S4_MAX_IMAGES:
            raise BusinessError(message="批次只接受 1 到 10 张，整单拒绝", code="BATCH_REJECTED")
        preset = preset_by_code(preset_code)
        if preset is None:
            raise BusinessError(message="预设未启用或不存在", code="PRESET_REJECTED")
        review = pre_review_mode if pre_review_mode in {"pass", PRE_REVIEW_REJECT} else "pass"
        if detection_mode == DETECT_GEMINI:
            detect = DETECT_GEMINI
        elif detection_mode in {DETECT_PASS, DETECT_NOT_PASSED, DETECT_TECHNICAL}:
            detect = detection_mode
        else:
            detect = DETECT_PASS
        injected = review != "pass" or detect in {DETECT_NOT_PASSED, DETECT_TECHNICAL}
        if injected and ROLE_ADMIN not in actor_role_codes:
            raise BusinessError(message="仅管理员可注入预审或检测结果", code="FORBIDDEN_INJECT")
        wallet = await self.credits.get_wallet(tenant_id=int(tenant_id))
        needed = len(requested) * PROCESS_UNIT_CREDITS
        if int(wallet["availableInteger"]) < needed:
            raise BusinessError(message="余额不足，整单拒绝", code="INSUFFICIENT_CREDITS")
        try:
            async with self.db.begin_nested():
                return await self._open_batch(
                    tenant_id=int(tenant_id),
                    owner_account_id=int(owner_account_id),
                    asset_ids=requested,
                    preset=preset,
                    batch_key=key,
                    review=review,
                    detect=detect,
                )
        except IntegrityError:
            found = await self._tasks_for_batch_key(tenant_id=int(tenant_id), batch_key=key)
            if not found:
                raise
            batch = await self._batch_row(tenant_id=int(tenant_id), batch_id=int(found[0].batch_id))
            return batch, found

    async def _open_batch(
        self,
        *,
        tenant_id: int,
        owner_account_id: int,
        asset_ids: list[int],
        preset: dict,
        batch_key: str,
        review: str,
        detect: str,
    ) -> tuple[RealphotosBatch, list[RealphotosImageTask]]:
        batch = RealphotosBatch(
            tenant_id=int(tenant_id),
            owner_account_id=int(owner_account_id),
            image_count=len(asset_ids),
            preset_code=preset["code"],
        )
        self.db.add(batch)
        await self.db.flush()
        setting = await self.get_redo_setting(tenant_id=int(tenant_id))
        tasks: list[RealphotosImageTask] = []
        for index, asset_id in enumerate(asset_ids):
            chain = RealphotosTaskChain(
                tenant_id=int(tenant_id), batch_id=int(batch.id), round_no=1
            )
            self.db.add(chain)
            await self.db.flush()
            task = RealphotosImageTask(
                tenant_id=int(tenant_id),
                owner_account_id=int(owner_account_id),
                batch_id=int(batch.id),
                chain_id=int(chain.id),
                asset_id=int(asset_id),
                status=TASK_SUBMITTED,
                preset_code=preset["code"],
                preset_snapshot=preset,
                pre_review_mode=review,
                detection_mode=detect,
                idempotency_key=f"batch:{batch_key}:{index}",
                pipeline_version=_PIPELINE,
            )
            self.db.add(task)
            await self.db.flush()
            self.db.add(
                RealphotosTaskSnapshot(
                    tenant_id=int(tenant_id), task_id=int(task.id), snapshot=preset
                )
            )
            self.db.add(
                RealphotosChainPolicy(
                    tenant_id=int(tenant_id),
                    chain_id=int(chain.id),
                    enabled=bool(setting.enabled),
                    score_threshold=int(setting.score_threshold),
                    extra_rounds=int(setting.extra_rounds),
                    execution_count=1,
                    origin="submit",
                )
            )
            await self.credits.freeze(
                tenant_id=int(tenant_id),
                amount=PROCESS_UNIT_CREDITS,
                operator_user_id=int(owner_account_id),
                event_key=f"freeze:task:{int(task.id)}",
                reference={"taskId": int(task.id), "images": 1, "batchId": int(batch.id)},
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
            await self.db.flush()
            if await self._precheck_failed(tenant_id=int(tenant_id), owner_account_id=int(owner_account_id), asset_id=int(asset_id)):
                task.status = TASK_PRE_REVIEW_FAILED
                task.failure_class = "precheck"
                await self._release(task, disposition="released_precheck")
            else:
                await self.jobs.enqueue_process(
                    tenant_id=int(tenant_id),
                    owner_account_id=int(owner_account_id),
                    payload={"task_id": int(task.id)},
                )
            tasks.append(task)
        await self.db.flush()
        return batch, tasks

    async def _precheck_failed(self, *, tenant_id: int, owner_account_id: int, asset_id: int) -> bool:
        asset = (
            await self.db.execute(
                select(RealphotosAsset).where(
                    RealphotosAsset.id == int(asset_id),
                    RealphotosAsset.tenant_id == int(tenant_id),
                    RealphotosAsset.owner_account_id == int(owner_account_id),
                    RealphotosAsset.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if asset is None:
            return True
        try:
            handle = get_storage_adapter().open_read(asset.object_key)
            try:
                data = handle.read()
            finally:
                handle.close()
            inspect_upload(data)
        except (OSError, AOJUException):
            return True
        return False

    async def list_batch_tasks(
        self, *, tenant_id: int, owner_account_id: int, batch_id: int
    ) -> list[RealphotosImageTask]:
        rows = (
            await self.db.execute(
                select(RealphotosImageTask)
                .where(
                    RealphotosImageTask.tenant_id == int(tenant_id),
                    RealphotosImageTask.owner_account_id == int(owner_account_id),
                    RealphotosImageTask.batch_id == int(batch_id),
                    RealphotosImageTask.deleted_at.is_(None),
                )
                .order_by(RealphotosImageTask.id.asc())
            )
        ).scalars().all()
        if not rows:
            raise NotFoundError(message="任务不存在")
        return list(rows)

    async def selected_download_items(
        self,
        *,
        tenant_id: int,
        owner_account_id: int,
        task_ids: list[int],
        pack: str = "files",
    ) -> list[dict]:
        if str(pack or "").strip().lower() == "zip":
            raise BusinessError(message="不生成 ZIP", code="ZIP_REJECTED")
        items: list[dict] = []
        for raw in task_ids:
            task = (
                await self.db.execute(
                    select(RealphotosImageTask).where(
                        RealphotosImageTask.id == int(raw),
                        RealphotosImageTask.tenant_id == int(tenant_id),
                        RealphotosImageTask.owner_account_id == int(owner_account_id),
                        RealphotosImageTask.deleted_at.is_(None),
                    )
                )
            ).scalar_one_or_none()
            if task is None or not task.output_object_key:
                continue
            items.append(
                {
                    "taskId": str(int(task.id)),
                    "objectKey": task.output_object_key,
                    "pack": "file",
                }
            )
        return items

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
            # 管理员 2026-11-06：技术失败保持冻结，等到开发技术客服时再释放。
            reservation = await self._chain_reservation(task)
            if reservation.state == "reserved":
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
            reservation = await self._chain_reservation(task)
            if reservation.state == "reserved":
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
        if task.detection_mode == DETECT_GEMINI:
            return await self._settle_gemini(task, jpeg)
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

    async def read_object_for_gateway(
        self, *, tenant_id: int, object_key: str, owner_account_id: int | None = None
    ) -> tuple[str, bytes]:
        key = object_key.strip().lstrip("/")
        now = _utcnow()
        if "/output/" in key:
            filters = [
                RealphotosImageTask.tenant_id == int(tenant_id),
                RealphotosImageTask.output_object_key == key,
                RealphotosImageTask.deleted_at.is_(None),
            ]
            if owner_account_id is not None:
                filters.append(RealphotosImageTask.owner_account_id == int(owner_account_id))
            result = await self.db.execute(select(RealphotosImageTask).where(*filters))
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

    async def get_task(
        self, *, tenant_id: int, task_id: int, owner_account_id: int
    ) -> RealphotosImageTask:
        return await self._task(
            tenant_id=tenant_id, task_id=task_id, owner_account_id=owner_account_id
        )

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

        source_key = await self._round_input_key(task)
        if source_key is None:
            asset = await self._asset(tenant_id=int(task.tenant_id), asset_id=int(task.asset_id))
            source_key = asset.object_key
        handle = get_storage_adapter().open_read(source_key)
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

    async def get_redo_setting(self, *, tenant_id: int) -> RealphotosRedoSetting:
        row = (
            await self.db.execute(
                select(RealphotosRedoSetting).where(
                    RealphotosRedoSetting.tenant_id == int(tenant_id),
                    RealphotosRedoSetting.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if row is not None:
            return row
        row = RealphotosRedoSetting(tenant_id=int(tenant_id), enabled=False, score_threshold=70, extra_rounds=1)
        self.db.add(row)
        await self.db.flush()
        return row

    async def save_redo_setting(
        self, *, tenant_id: int, enabled: bool, threshold: int, extra_rounds: int
    ) -> RealphotosRedoSetting:
        validate_setting(threshold=int(threshold), extra_rounds=int(extra_rounds))
        row = await self.get_redo_setting(tenant_id=int(tenant_id))
        row.enabled = bool(enabled)
        row.score_threshold = int(threshold)
        row.extra_rounds = int(extra_rounds)
        await self.db.flush()
        return row

    async def retry_technical(
        self, *, tenant_id: int, task_id: int, owner_account_id: int
    ) -> RealphotosImageTask:
        task = await self._task(
            tenant_id=tenant_id, task_id=task_id, owner_account_id=owner_account_id
        )
        if task.failure_class not in _RETRYABLE_FAILURES:
            raise BusinessError(message="只有技术失败可以沿用原任务重试", code="RETRY_REJECTED")
        policy = await self._policy(task)
        if int(policy.execution_count) >= MAX_EXECUTIONS:
            raise BusinessError(message="技术重试次数已用尽，请转技术客服", code="RETRY_LIMIT")
        policy.execution_count = int(policy.execution_count) + 1
        task.status = TASK_SUBMITTED
        task.failure_class = None
        task.output_object_key = None
        await self.jobs.enqueue_process(
            tenant_id=int(task.tenant_id),
            owner_account_id=int(task.owner_account_id),
            payload={"task_id": int(task.id)},
        )
        await self.db.flush()
        return task

    async def reprocess(
        self,
        *,
        tenant_id: int,
        owner_account_id: int,
        actor_role_codes: set[str],
        source_task_id: int,
        preset_code: str,
        idempotency_key: str,
    ) -> RealphotosImageTask:
        source = await self._task(
            tenant_id=tenant_id, task_id=source_task_id, owner_account_id=owner_account_id
        )
        report = await self.detection_payload(tenant_id=tenant_id, task_id=int(source.id))
        if report is None or report.get("detector") == "fixture" or report.get("accepted") is not False:
            raise BusinessError(message="只能对真实检测未通过的处理结果重处理", code="REPROCESS_REJECTED")
        if not source.output_object_key:
            raise BusinessError(message="没有可重处理的结果文件", code="REPROCESS_REJECTED")
        asset = await self._asset(tenant_id=tenant_id, asset_id=int(source.asset_id))
        if asset.deleted_at is not None:
            raise BusinessError(message="原图已删除，不能重处理", code="REPROCESS_REJECTED")
        created = await self.submit_single(
            tenant_id=tenant_id,
            owner_account_id=owner_account_id,
            actor_role_codes=actor_role_codes,
            asset_id=int(source.asset_id),
            preset_code=preset_code,
            idempotency_key=idempotency_key,
            detection_mode=DETECT_GEMINI,
        )
        policy = await self._policy(created)
        policy.source_task_id = int(source.id)
        policy.origin = "reprocess"
        self.db.add(
            RealphotosTaskSnapshot(
                tenant_id=int(created.tenant_id),
                task_id=int(created.id),
                snapshot={"kind": "s3_round_input", "objectKey": str(source.output_object_key)},
            )
        )
        await self.db.flush()
        return created

    async def _settle_gemini(self, task: RealphotosImageTask, jpeg: bytes) -> RealphotosImageTask:
        from app.capabilities.realphotos.services.gemini_detector import detect_jpeg

        try:
            report = detect_jpeg(jpeg)
        except BusinessError as exc:
            await self._hold_technical(task, code=exc.code, message=exc.message)
            return task
        out_key = f"tenant/{int(task.tenant_id)}/output/{int(task.id)}.jpg"
        stored = get_storage_adapter().put_bytes(out_key, jpeg, content_type="image/jpeg")
        task.output_object_key = stored.object_key
        task.output_byte_size = stored.size
        task.output_expires_at = _utcnow() + timedelta(hours=OUTPUT_TTL_HOURS)
        self.db.add(
            RealphotosDetectionResult(
                tenant_id=int(task.tenant_id),
                task_id=int(task.id),
                noise=int(report["noise"]),
                depth_of_field=int(report["depthOfField"]),
                lighting=int(report["lighting"]),
                color_realism=int(report["colorRealism"]),
                overall_realism=int(report["overallRealism"]),
                total_score=int(report["total_score"]),
                passed=bool(report["passed"]),
                reason=str(report["reason"] or ""),
                detector=str(report["detector"]),
            )
        )
        policy = await self._policy(task)
        redo_count = await self._prior_rounds(task)
        passed_now = accepted(passed=bool(report["passed"]), total_score=int(report["total_score"]))
        if should_auto_redo(
            enabled=bool(policy.enabled),
            total_score=int(report["total_score"]),
            threshold=int(policy.score_threshold),
            redo_count=redo_count,
            extra_rounds=int(policy.extra_rounds),
        ):
            if passed_now:
                await self._consume_chain(task, disposition="consumed_detection_pass")
                task.status = TASK_DELIVERED
            else:
                task.status = TASK_AUTO_REPROCESS_PENDING
            await self._enqueue_redo(task)
            await self.db.flush()
            return task
        if passed_now:
            await self._consume_chain(task, disposition="consumed_detection_pass")
            task.status = TASK_DELIVERED
            await self._notify(task, title="处理完成", body="最终检测通过，已结算 10 积分。")
        else:
            await self._release_chain(task, disposition="released_detection_not_passed")
            task.status = TASK_FAILED
            task.failure_class = "detection_not_passed"
            await self._notify(task, title="检测未通过", body="有效结果可下载，该张处理费为 0。")
        await self.db.flush()
        return task

    async def _hold_technical(self, task: RealphotosImageTask, *, code: str, message: str) -> None:
        reservation = await self._chain_reservation(task)
        if reservation.state == "reserved":
            reservation.state = "held"
        task.status = TASK_FAILED
        task.failure_class = code
        task.credit_disposition = "held_until_tech_support"
        task.output_object_key = None
        await self._notify(task, title="技术异常", body=message)
        await self.db.flush()

    async def _enqueue_redo(self, task: RealphotosImageTask) -> None:
        nxt = int(await self._prior_rounds(task)) + 2
        key = f"redo:{int(task.chain_id)}:{nxt}"
        existing = await self._task_by_idempotency(tenant_id=int(task.tenant_id), idempotency_key=key)
        if existing is not None:
            return
        created = RealphotosImageTask(
            tenant_id=int(task.tenant_id),
            owner_account_id=int(task.owner_account_id),
            batch_id=int(task.batch_id),
            chain_id=int(task.chain_id),
            asset_id=int(task.asset_id),
            status=TASK_SUBMITTED,
            preset_code=task.preset_code,
            preset_snapshot=dict(task.preset_snapshot or {}),
            pre_review_mode="pass",
            detection_mode=DETECT_GEMINI,
            idempotency_key=key,
            pipeline_version=_PIPELINE,
        )
        self.db.add(created)
        await self.db.flush()
        self.db.add(
            RealphotosTaskSnapshot(
                tenant_id=int(task.tenant_id),
                task_id=int(created.id),
                snapshot={"kind": "s3_round_input", "objectKey": str(task.output_object_key)},
            )
        )
        await self.jobs.enqueue_process(
            tenant_id=int(task.tenant_id),
            owner_account_id=int(task.owner_account_id),
            payload={"task_id": int(created.id)},
        )

    async def _round_input_key(self, task: RealphotosImageTask) -> str | None:
        rows = (
            await self.db.execute(
                select(RealphotosTaskSnapshot).where(RealphotosTaskSnapshot.task_id == int(task.id))
            )
        ).scalars().all()
        for row in rows:
            snap = row.snapshot if isinstance(row.snapshot, dict) else {}
            if snap.get("kind") == "s3_round_input" and snap.get("objectKey"):
                return str(snap["objectKey"])
        return None

    async def _policy(self, task: RealphotosImageTask) -> RealphotosChainPolicy:
        row = (
            await self.db.execute(
                select(RealphotosChainPolicy).where(RealphotosChainPolicy.chain_id == int(task.chain_id))
            )
        ).scalar_one_or_none()
        if row is None:
            raise BusinessError(message="缺少自动重做快照", code="REDO_SNAPSHOT_MISSING")
        return row

    async def _prior_rounds(self, task: RealphotosImageTask) -> int:
        rows = (
            await self.db.execute(
                select(RealphotosImageTask.id).where(RealphotosImageTask.chain_id == int(task.chain_id))
            )
        ).all()
        return max(len(rows) - 1, 0)

    async def _chain_reservation(self, task: RealphotosImageTask) -> RealphotosCreditReservation:
        first_id = (
            await self.db.execute(
                select(RealphotosImageTask.id)
                .where(RealphotosImageTask.chain_id == int(task.chain_id))
                .order_by(RealphotosImageTask.id.asc())
            )
        ).scalars().first()
        found = (
            await self.db.execute(
                select(RealphotosCreditReservation).where(
                    RealphotosCreditReservation.task_id == int(first_id),
                    RealphotosCreditReservation.deleted_at.is_(None),
                )
            )
        ).scalar_one()
        return found

    async def _consume_chain(self, task: RealphotosImageTask, *, disposition: str) -> None:
        reservation = await self._chain_reservation(task)
        if reservation.state != "reserved":
            return
        await self.credits.consume_reserved(
            tenant_id=int(task.tenant_id),
            amount=int(reservation.amount),
            operator_user_id=int(task.owner_account_id),
            event_key=f"consume:chain:{int(task.chain_id)}",
            reference={"chainId": int(task.chain_id), "disposition": disposition},
        )
        reservation.state = "consumed"
        task.credit_disposition = disposition

    async def _release_chain(self, task: RealphotosImageTask, *, disposition: str) -> None:
        reservation = await self._chain_reservation(task)
        if reservation.state != "reserved":
            return
        await self.credits.release_reserved(
            tenant_id=int(task.tenant_id),
            amount=int(reservation.amount),
            operator_user_id=int(task.owner_account_id),
            event_key=f"release:chain:{int(task.chain_id)}",
            reference={"chainId": int(task.chain_id), "disposition": disposition},
        )
        reservation.state = "released"
        task.credit_disposition = disposition

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
        policy = await self._policy(task)
        event_key = (
            f"inbox:task:{int(task.id)}:{task.failure_class or task.status}:{int(policy.execution_count)}"
        )
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

    async def _batch_row(self, *, tenant_id: int, batch_id: int) -> RealphotosBatch:
        row = (
            await self.db.execute(
                select(RealphotosBatch).where(
                    RealphotosBatch.id == int(batch_id),
                    RealphotosBatch.tenant_id == int(tenant_id),
                    RealphotosBatch.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError(message="任务不存在")
        return row

    async def _tasks_for_batch_key(
        self, *, tenant_id: int, batch_key: str
    ) -> list[RealphotosImageTask]:
        keys = [f"batch:{batch_key}:{index}" for index in range(S4_MAX_IMAGES)]
        rows = (
            await self.db.execute(
                select(RealphotosImageTask)
                .where(
                    RealphotosImageTask.tenant_id == int(tenant_id),
                    RealphotosImageTask.deleted_at.is_(None),
                    RealphotosImageTask.idempotency_key.in_(keys),
                )
                .order_by(RealphotosImageTask.id.asc())
            )
        ).scalars().all()
        return list(rows)

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

    async def _task(
        self, *, tenant_id: int, task_id: int, owner_account_id: int | None = None
    ) -> RealphotosImageTask:
        filters = [
            RealphotosImageTask.id == int(task_id),
            RealphotosImageTask.tenant_id == int(tenant_id),
            RealphotosImageTask.deleted_at.is_(None),
        ]
        if owner_account_id is not None:
            filters.append(RealphotosImageTask.owner_account_id == int(owner_account_id))
        row = (
            await self.db.execute(select(RealphotosImageTask).where(*filters))
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
