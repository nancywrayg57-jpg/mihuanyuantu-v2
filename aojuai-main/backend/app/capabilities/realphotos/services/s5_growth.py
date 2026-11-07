"""S5 growth: generation stores assets only; prompts; URL stays unconfigured.

Fixture generation is an in-process stand-in for billing and storage. It does
not call a supplier and is not a production sample. The default provider is
unconfigured and returns before any ledger or asset write.
"""

from __future__ import annotations

import hashlib
import io
import json

from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.realphotos.adapters.storage import get_storage_adapter
from app.capabilities.realphotos.constants import (
    GENERATION_MAX_EDGE,
    GENERATION_MAX_QUANTITY,
    GENERATION_MIN_EDGE,
    GENERATION_MIN_QUANTITY,
    GENERATION_UNIT_CREDITS,
    PROMPT_OPT_CREDITS,
    URL_IMPORT_MAX,
)
from app.capabilities.realphotos.models import (
    RealphotosAsset,
    RealphotosGenerationItem,
    RealphotosGenerationTask,
    RealphotosImageTask,
    RealphotosPromptOptimization,
    RealphotosPromptTemplate,
)
from app.capabilities.realphotos.permissions import ROLE_ADMIN, ROLE_ORDER_SUPPORT
from app.capabilities.realphotos.services.credit_service import RealphotosCreditService
from app.capabilities.realphotos.services.s1_upload import inspect_upload
from app.core.exceptions import BusinessError, NotFoundError

FIXTURE_PROVIDER = "fixture"
UNCONFIGURED_PROVIDER = "unconfigured"


def _import_entry_count(payload: object) -> int:
    if isinstance(payload, list):
        entries = payload
    else:
        text = str(payload or "").strip()
        if not text:
            raise BusinessError(message="导入内容为空", code="INPUT_INVALID")
        if text.startswith("["):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError as exc:
                raise BusinessError(message="JSON 无法解析", code="INPUT_INVALID") from exc
            if not isinstance(parsed, list):
                raise BusinessError(message="JSON 须为数组", code="INPUT_INVALID")
            entries = parsed
        else:
            entries = [line for line in text.splitlines() if line.strip()]
    if len(entries) < 1:
        raise BusinessError(message="导入内容为空", code="INPUT_INVALID")
    return len(entries)


class RealphotosGrowthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def submit_generation(
        self,
        *,
        tenant_id: int,
        owner_account_id: int,
        mode: str,
        positive_prompt: str,
        negative_prompt: str = "",
        width: int,
        height: int,
        quantity: int,
        idempotency_key: str,
        provider: str = UNCONFIGURED_PROVIDER,
        template_id: int | None = None,
        reference_asset_id: int | None = None,
        reference_bytes: bytes | None = None,
        fail_indexes: set[int] | None = None,
    ) -> RealphotosGenerationTask:
        kind = str(mode or "").strip()
        if kind not in {"text_to_image", "image_to_image"}:
            raise BusinessError(message="生图模式无效", code="INPUT_INVALID")
        prompt = str(positive_prompt or "").strip()
        if not prompt:
            raise BusinessError(message="正向提示词必填", code="INPUT_INVALID")
        edge_w = int(width)
        edge_h = int(height)
        if not GENERATION_MIN_EDGE <= edge_w <= GENERATION_MAX_EDGE:
            raise BusinessError(message="宽度须在 256–2048", code="INPUT_INVALID")
        if not GENERATION_MIN_EDGE <= edge_h <= GENERATION_MAX_EDGE:
            raise BusinessError(message="高度须在 256–2048", code="INPUT_INVALID")
        count = int(quantity)
        if count < GENERATION_MIN_QUANTITY or count > GENERATION_MAX_QUANTITY:
            raise BusinessError(message="数量须为 1–10，超出则整单拒绝", code="INPUT_INVALID")
        key = str(idempotency_key or "").strip()
        if not key:
            raise BusinessError(message="缺少幂等键", code="INPUT_INVALID")
        existing = await self._generation_by_key(tenant_id=tenant_id, idempotency_key=key)
        if existing is not None:
            return existing
        from app.capabilities.realphotos.services.s6_ops import RealphotosOpsService

        await RealphotosOpsService(self.db).assert_can_create_task(
            tenant_id=int(tenant_id), owner_account_id=int(owner_account_id)
        )

        if kind == "image_to_image":
            await self._check_reference(
                tenant_id=tenant_id,
                owner_account_id=owner_account_id,
                reference_asset_id=reference_asset_id,
                reference_bytes=reference_bytes,
            )

        chosen = str(provider or UNCONFIGURED_PROVIDER).strip() or UNCONFIGURED_PROVIDER
        if chosen == UNCONFIGURED_PROVIDER:
            from app.capabilities.realphotos.services.supplier_config import RealphotosSupplierConfigService

            contract = await RealphotosSupplierConfigService(self.db).enabled("generation")
            if contract is None:
                raise BusinessError(
                    message="缺少供应商合同与接口证据",
                    code="SERVICE_NOT_CONFIGURED",
                )
            return await self._submit_live_generation(
                tenant_id=tenant_id,
                owner_account_id=owner_account_id,
                kind=kind,
                prompt=prompt,
                negative_prompt=negative_prompt,
                edge_w=edge_w,
                edge_h=edge_h,
                count=count,
                key=key,
                template_id=template_id,
                reference_asset_id=reference_asset_id,
                reference_bytes=reference_bytes,
                model_id=contract.model_id,
            )
        if chosen != FIXTURE_PROVIDER:
            raise BusinessError(
                message="缺少供应商合同与接口证据",
                code="SERVICE_NOT_CONFIGURED",
            )

        credits = RealphotosCreditService(self.db)
        wallet = await credits.get_wallet(tenant_id=tenant_id)
        if int(wallet["availableInteger"]) < count * GENERATION_UNIT_CREDITS:
            raise BusinessError(message="余额不足，整单拒绝", code="INSUFFICIENT_CREDITS")

        task = RealphotosGenerationTask(
            tenant_id=int(tenant_id),
            owner_account_id=int(owner_account_id),
            mode=kind,
            quantity=count,
            width=edge_w,
            height=edge_h,
            positive_prompt=prompt,
            negative_prompt=str(negative_prompt or ""),
            provider=FIXTURE_PROVIDER,
            idempotency_key=key,
            template_id=int(template_id) if template_id else None,
        )
        self.db.add(task)
        await self.db.flush()
        failures = {int(index) for index in (fail_indexes or set())}
        for index in range(count):
            if index in failures:
                self.db.add(
                    RealphotosGenerationItem(
                        tenant_id=int(tenant_id),
                        task_id=int(task.id),
                        item_index=index,
                        status="failed",
                        asset_id=None,
                        credits_consumed=0,
                    )
                )
                continue
            try:
                await credits.consume_available(
                    tenant_id=int(tenant_id),
                    amount=GENERATION_UNIT_CREDITS,
                    operator_user_id=int(owner_account_id),
                    event_key=f"generation:{int(task.id)}:{index}",
                    reference={"source": "generation_store", "taskId": int(task.id)},
                )
            except BusinessError as exc:
                if exc.code != "INSUFFICIENT_CREDITS":
                    raise
                self.db.add(
                    RealphotosGenerationItem(
                        tenant_id=int(tenant_id),
                        task_id=int(task.id),
                        item_index=index,
                        status="failed",
                        asset_id=None,
                        credits_consumed=0,
                    )
                )
                continue
            asset = self._store_fixture(
                tenant_id=int(tenant_id),
                owner_account_id=int(owner_account_id),
                width=edge_w,
                height=edge_h,
                origin_kind=kind,
                token=f"{int(task.id)}-{index}",
            )
            self.db.add(asset)
            await self.db.flush()
            self.db.add(
                RealphotosGenerationItem(
                    tenant_id=int(tenant_id),
                    task_id=int(task.id),
                    item_index=index,
                    status="stored",
                    asset_id=int(asset.id),
                    credits_consumed=GENERATION_UNIT_CREDITS,
                )
            )
        await self.db.flush()
        return task

    async def list_generation_items(self, *, tenant_id: int, task_id: int) -> list[RealphotosGenerationItem]:
        rows = await self.db.execute(
            select(RealphotosGenerationItem)
            .where(
                RealphotosGenerationItem.tenant_id == int(tenant_id),
                RealphotosGenerationItem.task_id == int(task_id),
                RealphotosGenerationItem.deleted_at.is_(None),
            )
            .order_by(RealphotosGenerationItem.item_index.asc())
        )
        return list(rows.scalars().all())

    async def list_generation_tasks(
        self,
        *,
        tenant_id: int,
        owner_account_id: int,
        page: int = 1,
        page_size: int = 10,
        mode: str | None = None,
    ) -> tuple[list[RealphotosGenerationTask], int]:
        from sqlalchemy import func

        page_no = max(1, int(page or 1))
        size = min(50, max(1, int(page_size or 10)))
        filters = [
            RealphotosGenerationTask.tenant_id == int(tenant_id),
            RealphotosGenerationTask.owner_account_id == int(owner_account_id),
            RealphotosGenerationTask.deleted_at.is_(None),
        ]
        if mode and str(mode).strip() and str(mode).strip() != "all":
            filters.append(RealphotosGenerationTask.mode == str(mode).strip())
        total = int(
            await self.db.scalar(
                select(func.count()).select_from(RealphotosGenerationTask).where(*filters)
            )
            or 0
        )
        rows = (
            await self.db.execute(
                select(RealphotosGenerationTask)
                .where(*filters)
                .order_by(RealphotosGenerationTask.id.desc())
                .offset((page_no - 1) * size)
                .limit(size)
            )
        ).scalars().all()
        return list(rows), total

    async def processing_task_count_for_assets(self, *, tenant_id: int, asset_ids: list[int]) -> int:
        if not asset_ids:
            return 0
        rows = await self.db.execute(
            select(RealphotosImageTask.id).where(
                RealphotosImageTask.tenant_id == int(tenant_id),
                RealphotosImageTask.asset_id.in_([int(item) for item in asset_ids]),
                RealphotosImageTask.deleted_at.is_(None),
            )
        )
        return len(list(rows.scalars().all()))

    async def list_assets(self, *, tenant_id: int, owner_account_id: int) -> list[RealphotosAsset]:
        rows = await self.db.execute(
            select(RealphotosAsset)
            .where(
                RealphotosAsset.tenant_id == int(tenant_id),
                RealphotosAsset.owner_account_id == int(owner_account_id),
                RealphotosAsset.deleted_at.is_(None),
            )
            .order_by(RealphotosAsset.id.desc())
        )
        return list(rows.scalars().all())

    async def optimize_prompt(
        self,
        *,
        tenant_id: int,
        owner_account_id: int,
        original_text: str,
        provider: str = UNCONFIGURED_PROVIDER,
        succeed: bool = True,
    ) -> RealphotosPromptOptimization:
        original = str(original_text or "").strip()
        if not original:
            raise BusinessError(message="原文必填", code="INPUT_INVALID")
        chosen = str(provider or UNCONFIGURED_PROVIDER).strip() or UNCONFIGURED_PROVIDER
        if chosen == UNCONFIGURED_PROVIDER:
            from app.capabilities.realphotos.services.supplier_config import RealphotosSupplierConfigService

            contract = await RealphotosSupplierConfigService(self.db).enabled("prompt_opt")
            if contract is None:
                raise BusinessError(
                    message="缺少供应商合同与接口证据",
                    code="SERVICE_NOT_CONFIGURED",
                )
            return await self._optimize_live(
                tenant_id=tenant_id,
                owner_account_id=owner_account_id,
                original=original,
                model_id=contract.model_id,
            )
        if chosen != FIXTURE_PROVIDER:
            raise BusinessError(
                message="缺少供应商合同与接口证据",
                code="SERVICE_NOT_CONFIGURED",
            )
        credits = RealphotosCreditService(self.db)
        row = RealphotosPromptOptimization(
            tenant_id=int(tenant_id),
            owner_account_id=int(owner_account_id),
            original_text=original,
            optimized_text="",
            status="failed",
            confirmed=False,
            provider=FIXTURE_PROVIDER,
        )
        self.db.add(row)
        await self.db.flush()
        freeze_key = f"prompt-opt-freeze:{int(row.id)}"
        await credits.freeze(
            tenant_id=int(tenant_id),
            amount=PROMPT_OPT_CREDITS,
            operator_user_id=int(owner_account_id),
            event_key=freeze_key,
            reference={"source": "prompt_optimization", "id": int(row.id)},
        )
        if not succeed:
            await credits.release_reserved(
                tenant_id=int(tenant_id),
                amount=PROMPT_OPT_CREDITS,
                operator_user_id=int(owner_account_id),
                event_key=f"prompt-opt-release:{int(row.id)}",
                reference={"source": "prompt_optimization", "id": int(row.id)},
            )
            await self.db.flush()
            return row
        await credits.consume_reserved(
            tenant_id=int(tenant_id),
            amount=PROMPT_OPT_CREDITS,
            operator_user_id=int(owner_account_id),
            event_key=f"prompt-opt-consume:{int(row.id)}",
            reference={"source": "prompt_optimization", "id": int(row.id)},
        )
        row.optimized_text = f"优化：{original}"
        row.status = "succeeded"
        await self.db.flush()
        return row

    async def confirm_optimization(
        self, *, tenant_id: int, owner_account_id: int, optimization_id: int
    ) -> RealphotosPromptOptimization:
        row = await self.db.get(RealphotosPromptOptimization, int(optimization_id))
        if (
            row is None
            or row.deleted_at is not None
            or int(row.tenant_id) != int(tenant_id)
            or int(row.owner_account_id) != int(owner_account_id)
        ):
            raise NotFoundError(message="优化记录不存在")
        if row.status != "succeeded":
            raise BusinessError(message="失败的优化不能确认", code="INPUT_INVALID")
        row.confirmed = True
        await self.db.flush()
        return row

    async def save_template(
        self,
        *,
        tenant_id: int,
        owner_account_id: int,
        actor_role_codes: set[str],
        name: str,
        mode: str,
        positive_prompt: str,
        negative_prompt: str = "",
        scope: str = "tenant",
    ) -> RealphotosPromptTemplate:
        self._reject_order_support(actor_role_codes)
        label = str(name or "").strip()
        body = str(positive_prompt or "").strip()
        if not label or not body:
            raise BusinessError(message="模板名称和正向提示词必填", code="INPUT_INVALID")
        chosen_scope = str(scope or "tenant").strip()
        if chosen_scope not in {"tenant", "platform"}:
            raise BusinessError(message="模板范围无效", code="INPUT_INVALID")
        if chosen_scope == "platform" and ROLE_ADMIN not in actor_role_codes and "admin" not in actor_role_codes:
            raise BusinessError(message="平台模板仅管理员可写", code="FORBIDDEN")
        if str(mode or "").strip() not in {"text_to_image", "image_to_image", "general"}:
            raise BusinessError(message="模板模式无效", code="INPUT_INVALID")
        row = RealphotosPromptTemplate(
            tenant_id=int(tenant_id),
            owner_account_id=int(owner_account_id),
            name=label,
            mode=str(mode).strip(),
            positive_prompt=body,
            negative_prompt=str(negative_prompt or ""),
            scope=chosen_scope,
        )
        self.db.add(row)
        await self.db.flush()
        return row

    async def list_templates(
        self, *, tenant_id: int, actor_role_codes: set[str]
    ) -> list[RealphotosPromptTemplate]:
        self._reject_order_support(actor_role_codes)
        rows = await self.db.execute(
            select(RealphotosPromptTemplate).where(RealphotosPromptTemplate.deleted_at.is_(None))
        )
        visible: list[RealphotosPromptTemplate] = []
        for row in rows.scalars().all():
            if row.scope == "platform" or int(row.tenant_id) == int(tenant_id):
                visible.append(row)
        return visible

    async def import_resources(self, *, payload: object) -> None:
        """URL/JSON 导入。上限 100。缺供应商证据时不外呼、不入库。"""
        count = _import_entry_count(payload)
        if count > URL_IMPORT_MAX:
            raise BusinessError(message="第 101 条整单拒绝", code="INPUT_INVALID")
        raise BusinessError(
            message="缺少供应商合同与接口证据",
            code="SERVICE_NOT_CONFIGURED",
        )

    async def import_resource_file(self, *, raw: bytes) -> None:
        """上传的 JSON 文件按数组条数计。不抓取其中的 URL。"""
        try:
            text = bytes(raw).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise BusinessError(message="JSON 文件须为 UTF-8", code="INPUT_INVALID") from exc
        await self.import_resources(payload=text)

    async def _submit_live_generation(
        self,
        *,
        tenant_id: int,
        owner_account_id: int,
        kind: str,
        prompt: str,
        negative_prompt: str,
        edge_w: int,
        edge_h: int,
        count: int,
        key: str,
        template_id: int | None,
        reference_asset_id: int | None,
        reference_bytes: bytes | None,
        model_id: str,
    ) -> RealphotosGenerationTask:
        from app.capabilities.realphotos.services.supplier_clients import (
            SupplierCallError,
            generate_images,
            image_size,
        )
        from app.capabilities.realphotos.services.supplier_config import RealphotosSupplierConfigService

        credits = RealphotosCreditService(self.db)
        wallet = await credits.get_wallet(tenant_id=tenant_id)
        if int(wallet["availableInteger"]) < count * GENERATION_UNIT_CREDITS:
            raise BusinessError(message="余额不足，整单拒绝", code="INSUFFICIENT_CREDITS")
        reference = None
        if kind == "image_to_image":
            reference = await self._reference_bytes(
                tenant_id=tenant_id,
                owner_account_id=owner_account_id,
                reference_asset_id=reference_asset_id,
                reference_bytes=reference_bytes,
            )
            await self._review_reference(
                tenant_id=tenant_id,
                owner_account_id=owner_account_id,
                data=reference,
            )
        try:
            outcome = await generate_images(
                model_id=model_id,
                prompt=prompt,
                width=edge_w,
                height=edge_h,
                quantity=count,
                reference=reference,
            )
        except SupplierCallError as exc:
            raise BusinessError(
                message=f"生图失败，未扣积分（{exc.kind} {exc.status or ''}）".strip(),
                code="SUPPLIER_FAILED",
                details={
                    "kind": exc.kind,
                    "status": exc.status,
                    "contentType": exc.content_type,
                    "referenceReview": getattr(self, "_reference_review", None),
                },
            ) from exc
        images = list(outcome.get("images") or [])
        kinds = {str(item.get("kind")) for item in images if item.get("raw")}
        await RealphotosSupplierConfigService(self.db).note_response(
            duty="generation",
            model_id=str(outcome.get("model_id") or model_id),
            result_kind=",".join(sorted(kinds)) or "empty",
        )
        task = RealphotosGenerationTask(
            tenant_id=int(tenant_id),
            owner_account_id=int(owner_account_id),
            mode=kind,
            quantity=count,
            width=edge_w,
            height=edge_h,
            positive_prompt=prompt,
            negative_prompt=str(negative_prompt or ""),
            provider="aoju",
            idempotency_key=key,
            template_id=int(template_id) if template_id else None,
        )
        self.db.add(task)
        await self.db.flush()
        for index in range(count):
            raw = images[index].get("raw") if index < len(images) else None
            if not raw:
                self.db.add(
                    RealphotosGenerationItem(
                        tenant_id=int(tenant_id),
                        task_id=int(task.id),
                        item_index=index,
                        status="failed",
                        asset_id=None,
                        credits_consumed=0,
                    )
                )
                continue
            try:
                width, height = image_size(bytes(raw))
            except Exception:
                self.db.add(
                    RealphotosGenerationItem(
                        tenant_id=int(tenant_id),
                        task_id=int(task.id),
                        item_index=index,
                        status="failed",
                        asset_id=None,
                        credits_consumed=0,
                    )
                )
                continue
            await credits.consume_available(
                tenant_id=int(tenant_id),
                amount=GENERATION_UNIT_CREDITS,
                operator_user_id=int(owner_account_id),
                event_key=f"generation:{int(task.id)}:{index}",
                reference={"source": "generation_store", "taskId": int(task.id)},
            )
            asset = self._store_bytes(
                tenant_id=int(tenant_id),
                owner_account_id=int(owner_account_id),
                raw=bytes(raw),
                width=width,
                height=height,
                origin_kind=kind,
                token=f"{int(task.id)}-{index}",
            )
            self.db.add(asset)
            await self.db.flush()
            self.db.add(
                RealphotosGenerationItem(
                    tenant_id=int(tenant_id),
                    task_id=int(task.id),
                    item_index=index,
                    status="stored",
                    asset_id=int(asset.id),
                    credits_consumed=GENERATION_UNIT_CREDITS,
                )
            )
        await self.db.flush()
        task.supplier_trace = {
            "status": outcome.get("http_status"),
            "contentType": outcome.get("content_type"),
            "modelId": outcome.get("model_id"),
            "requestedSize": outcome.get("requested_size"),
            "seedSent": False,
            "resultKinds": sorted({str(item.get("kind")) for item in images}),
            "referenceReview": getattr(self, "_reference_review", None),
        }
        return task

    async def _review_reference(self, *, tenant_id: int, owner_account_id: int, data: bytes) -> None:
        from app.capabilities.realphotos.services.s6_ops import RealphotosOpsService
        from app.capabilities.realphotos.services.supplier_clients import SupplierCallError, review_image
        from app.capabilities.realphotos.services.supplier_config import RealphotosSupplierConfigService

        contract = await RealphotosSupplierConfigService(self.db).enabled("pre_review")
        if contract is None:
            raise BusinessError(message="缺少预审供应商合同与接口证据", code="SERVICE_NOT_CONFIGURED")
        mime = "image/png" if data.startswith(b"\x89PNG") else "image/jpeg"
        try:
            outcome = await review_image(model_id=contract.model_id, data=data, mime=mime)
        except SupplierCallError as exc:
            raise BusinessError(
                message="预审请求失败，未生图也未扣积分",
                code="PRE_REVIEW_FAILED",
                details={"kind": exc.kind, "status": exc.status, "contentType": exc.content_type},
            ) from exc
        self._reference_review = {
            "status": outcome.get("http_status"),
            "contentType": outcome.get("content_type"),
            "modelId": outcome.get("model_id"),
            "verdict": outcome.get("verdict"),
        }
        await RealphotosSupplierConfigService(self.db).note_response(
            duty="pre_review",
            model_id=str(outcome.get("model_id") or contract.model_id),
            result_kind=str(outcome.get("verdict")),
        )
        recorded = await RealphotosOpsService(self.db).review_content(
            tenant_id=int(tenant_id),
            owner_account_id=int(owner_account_id),
            data=data,
            subject="reference",
            provider="dashscope",
            verdict=str(outcome["verdict"]),
        )
        if not recorded["passed"]:
            raise BusinessError(message="参考图预审未通过，未生图也未扣积分", code="PRE_REVIEW_REJECTED")

    async def _optimize_live(
        self,
        *,
        tenant_id: int,
        owner_account_id: int,
        original: str,
        model_id: str,
    ) -> RealphotosPromptOptimization:
        from app.capabilities.realphotos.services.supplier_clients import SupplierCallError, optimize_text
        from app.capabilities.realphotos.services.supplier_config import RealphotosSupplierConfigService

        credits = RealphotosCreditService(self.db)
        wallet = await credits.get_wallet(tenant_id=tenant_id)
        if int(wallet["availableInteger"]) < PROMPT_OPT_CREDITS:
            raise BusinessError(message="余额不足", code="INSUFFICIENT_CREDITS")
        row = RealphotosPromptOptimization(
            tenant_id=int(tenant_id),
            owner_account_id=int(owner_account_id),
            original_text=original,
            optimized_text="",
            status="failed",
            confirmed=False,
            provider="deepseek",
        )
        self.db.add(row)
        await self.db.flush()
        await credits.freeze(
            tenant_id=int(tenant_id),
            amount=PROMPT_OPT_CREDITS,
            operator_user_id=int(owner_account_id),
            event_key=f"prompt-opt-freeze:{int(row.id)}",
            reference={"source": "prompt_optimization", "id": int(row.id)},
        )
        try:
            outcome = await optimize_text(model_id=model_id, original=original)
        except SupplierCallError as exc:
            row.supplier_trace = {
                "status": exc.status,
                "contentType": exc.content_type,
                "modelId": model_id,
                "kind": exc.kind,
            }
            await credits.release_reserved(
                tenant_id=int(tenant_id),
                amount=PROMPT_OPT_CREDITS,
                operator_user_id=int(owner_account_id),
                event_key=f"prompt-opt-release:{int(row.id)}",
                reference={"source": "prompt_optimization", "id": int(row.id)},
            )
            await self.db.flush()
            return row
        await credits.consume_reserved(
            tenant_id=int(tenant_id),
            amount=PROMPT_OPT_CREDITS,
            operator_user_id=int(owner_account_id),
            event_key=f"prompt-opt-consume:{int(row.id)}",
            reference={"source": "prompt_optimization", "id": int(row.id)},
        )
        row.optimized_text = outcome["text"]
        row.status = "succeeded"
        row.supplier_trace = {
            "status": outcome.get("http_status"),
            "contentType": outcome.get("content_type"),
            "modelId": outcome.get("model_id"),
            "kind": "text",
        }
        await RealphotosSupplierConfigService(self.db).note_response(
            duty="prompt_opt",
            model_id=str(outcome.get("model_id") or model_id),
            result_kind="text",
        )
        await self.db.flush()
        return row

    async def _reference_bytes(
        self,
        *,
        tenant_id: int,
        owner_account_id: int,
        reference_asset_id: int | None,
        reference_bytes: bytes | None,
    ) -> bytes:
        if reference_bytes:
            inspect_upload(bytes(reference_bytes))
            return bytes(reference_bytes)
        asset = await self.db.get(RealphotosAsset, int(reference_asset_id or 0))
        if (
            asset is None
            or asset.deleted_at is not None
            or int(asset.tenant_id) != int(tenant_id)
            or int(asset.owner_account_id) != int(owner_account_id)
        ):
            raise NotFoundError(message="参考图不存在")
        handle = get_storage_adapter().open_read(asset.object_key)
        try:
            return handle.read()
        finally:
            handle.close()

    def _store_bytes(
        self,
        *,
        tenant_id: int,
        owner_account_id: int,
        raw: bytes,
        width: int,
        height: int,
        origin_kind: str,
        token: str,
    ) -> RealphotosAsset:
        content_type = "image/png" if raw.startswith(b"\x89PNG") else "image/jpeg"
        suffix = "png" if content_type == "image/png" else "jpg"
        key = f"tenant/{int(tenant_id)}/generation/{token}.{suffix}"
        get_storage_adapter().put_bytes(key, raw, content_type=content_type)
        return RealphotosAsset(
            tenant_id=int(tenant_id),
            owner_account_id=int(owner_account_id),
            object_key=key,
            content_type=content_type,
            byte_size=len(raw),
            width=int(width),
            height=int(height),
            sha256=hashlib.sha256(raw).hexdigest(),
            origin_kind=origin_kind,
        )

    async def _check_reference(
        self,
        *,
        tenant_id: int,
        owner_account_id: int,
        reference_asset_id: int | None,
        reference_bytes: bytes | None,
    ) -> None:
        if reference_asset_id is None and not reference_bytes:
            raise BusinessError(message="图生图需要一张参考图", code="INPUT_INVALID")
        if reference_bytes:
            inspect_upload(bytes(reference_bytes))
            return
        asset = await self.db.get(RealphotosAsset, int(reference_asset_id or 0))
        if (
            asset is None
            or asset.deleted_at is not None
            or int(asset.tenant_id) != int(tenant_id)
            or int(asset.owner_account_id) != int(owner_account_id)
        ):
            raise NotFoundError(message="参考图不存在")

    def _store_fixture(
        self,
        *,
        tenant_id: int,
        owner_account_id: int,
        width: int,
        height: int,
        origin_kind: str,
        token: str,
    ) -> RealphotosAsset:
        buf = io.BytesIO()
        Image.new("RGB", (int(width), int(height)), (24, 36, 48)).save(buf, format="JPEG", quality=85)
        raw = buf.getvalue()
        key = f"tenant/{int(tenant_id)}/generation/{token}.jpg"
        get_storage_adapter().put_bytes(key, raw, content_type="image/jpeg")
        return RealphotosAsset(
            tenant_id=int(tenant_id),
            owner_account_id=int(owner_account_id),
            object_key=key,
            content_type="image/jpeg",
            byte_size=len(raw),
            width=int(width),
            height=int(height),
            sha256=hashlib.sha256(raw).hexdigest(),
            origin_kind=origin_kind,
        )

    async def _generation_by_key(
        self, *, tenant_id: int, idempotency_key: str
    ) -> RealphotosGenerationTask | None:
        row = await self.db.execute(
            select(RealphotosGenerationTask).where(
                RealphotosGenerationTask.tenant_id == int(tenant_id),
                RealphotosGenerationTask.idempotency_key == idempotency_key,
                RealphotosGenerationTask.deleted_at.is_(None),
            )
        )
        return row.scalar_one_or_none()

    def _reject_order_support(self, actor_role_codes: set[str]) -> None:
        if ROLE_ORDER_SUPPORT in actor_role_codes:
            raise BusinessError(message="订单客服不能查看提示词模板", code="FORBIDDEN")
