"""S6 ops: content review without a supplier call, freeze desk, users, presets, metrics.

`provider=fixture` is an in-process stand-in. It is not a connected supplier.
"""

from __future__ import annotations

import hashlib
import io
from datetime import UTC, datetime
from typing import Any

from PIL import Image
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.realphotos.constants import DEVICE_TYPE_ALIASES, DEVICE_TYPES
from app.capabilities.realphotos.models import (
    RealphotosAccountLog,
    RealphotosAsset,
    RealphotosAuthGuard,
    RealphotosContentReview,
    RealphotosCreditAccount,
    RealphotosCreditReservation,
    RealphotosDetectionResult,
    RealphotosDevicePreset,
    RealphotosExecutionJob,
    RealphotosGenerationItem,
    RealphotosImageLock,
    RealphotosImageTask,
    RealphotosMerchantProfile,
    RealphotosPresetVersion,
    RealphotosPromptOptimization,
    RealphotosReviewStreak,
    RealphotosSupportTicket,
)
from app.capabilities.realphotos.permissions import ROLE_ADMIN, ROLE_ORDER_SUPPORT, ROLE_TECH_SUPPORT
from app.capabilities.realphotos.services.credit_service import RealphotosCreditService
from app.capabilities.realphotos.services.s1_catalog import S1_ENABLED_PRESETS
from app.capabilities.realphotos.services.s1_upload import inspect_upload
from app.core.exceptions import BusinessError, ForbiddenError
from app.core.security import hash_password
from app.domain.auth.models import Tenant
from app.domain.roles.models import Role
from app.domain.users.models import User, UserRole, UserStatus

FIXTURE_PROVIDER = "fixture"
UNCONFIGURED_PROVIDER = "unconfigured"
USER_PAGE_SIZE = 10
LOG_PAGE_SIZE = 20
GPS_MODES = {"none", "fixed", "random_by_scene"}
# PRESET-BULK-IMPORT B1: stop injecting Honeybadger s1-* into merchant enabled list.
INJECT_S1_CATALOG_INTO_ENABLED = False
PROTECTED_USERNAME = "rp_admin"
PLACEHOLDER_BRAND_BLOCKLIST = {"honeybadger"}
ACCOUNT_LOG_ACTION_ZH = {
    "create": "创建账号",
    "credit": "加减积分",
    "status": "启停账号",
    "delete": "删除账号",
    "reset_password": "重置密码",
    "permission": "调整权限",
}
ACCOUNT_LOG_RESULT_ZH = {
    "success": "成功",
    "ok": "成功",
    "failed": "失败",
    "error": "失败",
    "denied": "拒绝",
}


def normalize_device_type(raw: str | None) -> tuple[str, str | None]:
    """Return (canonical_type, mapped_from_or_None). Reject undocumented names on write."""
    label = str(raw or "").strip()
    if label in DEVICE_TYPES:
        return label, None
    if label in DEVICE_TYPE_ALIASES:
        return DEVICE_TYPE_ALIASES[label], label
    raise BusinessError(
        message=f"设备类型无效，允许：{', '.join(DEVICE_TYPES)}",
        code="INPUT_INVALID",
        details={"deviceType": label, "allowed": list(DEVICE_TYPES)},
    )


def pixel_identity(data: bytes) -> str:
    """Decoded RGB bytes. EXIF-only edits do not become a new image."""
    inspect_upload(data)
    with Image.open(io.BytesIO(data)) as image:
        raw = image.convert("RGB").tobytes()
    return hashlib.sha256(raw).hexdigest()


class RealphotosOpsService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def review_content(
        self,
        *,
        tenant_id: int,
        owner_account_id: int,
        data: bytes,
        subject: str,
        provider: str = UNCONFIGURED_PROVIDER,
        verdict: str = "reject",
    ) -> dict[str, Any]:
        kind = str(subject or "").strip()
        if kind not in {"processing", "reference"}:
            raise BusinessError(message="预审对象无效", code="INPUT_INVALID")
        identity = pixel_identity(data)
        chosen = str(provider or UNCONFIGURED_PROVIDER).strip() or UNCONFIGURED_PROVIDER
        if chosen not in {FIXTURE_PROVIDER, "dashscope"}:
            raise BusinessError(message="缺少供应商合同与接口证据", code="SERVICE_NOT_CONFIGURED")
        label = str(verdict or "").strip()
        if label not in {"pass", "reject", "uncertain"}:
            raise BusinessError(message="预审结论无效", code="INPUT_INVALID")
        passed = label == "pass"
        row = RealphotosContentReview(
            tenant_id=int(tenant_id),
            owner_account_id=int(owner_account_id),
            subject=kind,
            image_identity=identity,
            verdict=label,
            passed=passed,
            provider=chosen,
            counts_for_streak=kind == "processing" and not passed,
        )
        self.db.add(row)
        await self.db.flush()
        locked = False
        frozen = False
        ticket_id = None
        if kind == "reference":
            if not passed:
                locked = await self._lock_on_second(tenant_id, owner_account_id, identity, kind)
            return self._review_payload(row, locked=locked, frozen=False, ticket_id=None)
        if passed:
            await self._reset_streak(tenant_id, owner_account_id)
            return self._review_payload(row, locked=False, frozen=False, ticket_id=None)
        locked = await self._lock_on_second(tenant_id, owner_account_id, identity, kind)
        frozen, ticket_id = await self._note_distinct_failure(tenant_id, owner_account_id, identity)
        return self._review_payload(row, locked=locked, frozen=frozen, ticket_id=ticket_id)

    async def assert_can_create_task(self, *, tenant_id: int, owner_account_id: int) -> None:
        profile = await self._profile(tenant_id, owner_account_id)
        if profile is not None and bool(profile.pre_review_frozen):
            raise BusinessError(message="账号已因预审冻结，不能新建任务", code="ACCOUNT_FROZEN")

    async def release_held_credit(
        self,
        *,
        actor_role_codes: set[str],
        operator_user_id: int,
        tenant_id: int,
        task_id: int,
        reason: str,
    ) -> dict[str, Any]:
        self._require_tech_or_admin(actor_role_codes)
        note = str(reason or "").strip()
        if not note:
            raise BusinessError(message="释放必须填写原因", code="INPUT_INVALID")
        task = await self.db.get(RealphotosImageTask, int(task_id))
        if task is None or task.deleted_at is not None or int(task.tenant_id) != int(tenant_id):
            raise BusinessError(message="任务不存在", code="NOT_FOUND")
        if task.credit_disposition != "held_until_tech_support":
            raise BusinessError(message="这笔不是待技术客服释放的冻结", code="INPUT_INVALID")
        reservation = (
            await self.db.execute(
                select(RealphotosCreditReservation).where(
                    RealphotosCreditReservation.task_id == int(task.id),
                    RealphotosCreditReservation.tenant_id == int(tenant_id),
                    RealphotosCreditReservation.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if reservation is None or reservation.state != "held":
            raise BusinessError(message="没有保持中的预留", code="INPUT_INVALID")
        await RealphotosCreditService(self.db).release_reserved(
            tenant_id=int(tenant_id),
            amount=int(reservation.amount),
            operator_user_id=int(operator_user_id),
            event_key=f"tech-release:{int(task.id)}",
            reference={"taskId": int(task.id), "source": "tech_audit"},
        )
        reservation.state = "released"
        task.credit_disposition = "released_tech_audit"
        await self.db.flush()
        return {"taskId": int(task.id), "disposition": task.credit_disposition}

    async def unfreeze_account(
        self,
        *,
        actor_role_codes: set[str],
        operator_user_id: int,
        tenant_id: int,
        user_id: int,
        reason: str,
    ) -> dict[str, Any]:
        self._require_tech_or_admin(actor_role_codes)
        note = str(reason or "").strip()
        if not note:
            raise BusinessError(message="解冻必须填写原因", code="INPUT_INVALID")
        profile = await self._profile(tenant_id, user_id)
        if profile is None:
            raise BusinessError(message="账号档案不存在", code="NOT_FOUND")
        profile.pre_review_frozen = False
        closed = await self._close_open_tickets(
            tenant_id=int(tenant_id),
            owner_account_id=int(user_id),
            ticket_type="account_freeze",
            operator_user_id=int(operator_user_id),
            resolution_note=note,
            resolution_outcome="unfrozen",
        )
        await self.db.flush()
        return {
            "userId": int(user_id),
            "preReviewFrozen": False,
            "closedFreezeTickets": closed,
        }

    async def _close_open_tickets(
        self,
        *,
        tenant_id: int,
        owner_account_id: int,
        ticket_type: str,
        operator_user_id: int,
        resolution_note: str,
        resolution_outcome: str,
    ) -> int:
        from datetime import UTC, datetime

        rows = (
            await self.db.execute(
                select(RealphotosSupportTicket).where(
                    RealphotosSupportTicket.tenant_id == int(tenant_id),
                    RealphotosSupportTicket.owner_account_id == int(owner_account_id),
                    RealphotosSupportTicket.ticket_type == str(ticket_type),
                    RealphotosSupportTicket.status == "open",
                    RealphotosSupportTicket.deleted_at.is_(None),
                )
            )
        ).scalars().all()
        now = datetime.now(UTC)
        for row in rows:
            row.status = "resolved"
            row.resolved_at = now
            row.resolved_by_user_id = int(operator_user_id)
            row.resolution_note = str(resolution_note or "")
            row.resolution_outcome = str(resolution_outcome or "")
        return len(rows)

    async def resolve_ticket(
        self,
        *,
        actor_role_codes: set[str],
        operator_user_id: int,
        ticket_id: int,
        outcome: str,
        note: str,
    ) -> dict[str, Any]:
        """Close image_appeal (or other non-freeze) tickets. Does not unlock images."""
        from datetime import UTC, datetime

        self._require_tech_or_admin(actor_role_codes)
        result = str(outcome or "").strip()
        if result not in {"accepted", "rejected", "resolved"}:
            raise BusinessError(message="办结结果无效", code="INPUT_INVALID")
        text = str(note or "").strip()
        if not text:
            raise BusinessError(message="办结原因必填", code="INPUT_INVALID")
        row = await self.db.get(RealphotosSupportTicket, int(ticket_id))
        if row is None or row.deleted_at is not None:
            raise BusinessError(message="工单不存在", code="NOT_FOUND")
        if row.ticket_type == "account_freeze":
            raise BusinessError(
                message="账号冻结工单须通过解冻动作办结，不能单独标记",
                code="INPUT_INVALID",
            )
        if row.status != "open":
            raise BusinessError(message="工单已办结", code="INPUT_INVALID")
        row.status = "resolved"
        row.resolved_at = datetime.now(UTC)
        row.resolved_by_user_id = int(operator_user_id)
        row.resolution_note = text
        row.resolution_outcome = result
        await self.db.flush()
        return self._ticket_dict(row)

    @staticmethod
    def _ticket_dict(row: RealphotosSupportTicket) -> dict[str, Any]:
        return {
            "id": int(row.id),
            "tenantId": int(row.tenant_id),
            "ownerAccountId": int(row.owner_account_id),
            "ticketType": row.ticket_type,
            "status": row.status,
            "reason": row.reason,
            "createdAt": row.created_at.isoformat() if row.created_at else None,
            "resolvedAt": row.resolved_at.isoformat() if getattr(row, "resolved_at", None) else None,
            "resolvedByUserId": (
                int(row.resolved_by_user_id)
                if getattr(row, "resolved_by_user_id", None) is not None
                else None
            ),
            "resolutionNote": getattr(row, "resolution_note", "") or "",
            "resolutionOutcome": getattr(row, "resolution_outcome", "") or "",
        }

    async def list_tickets(self, *, actor_role_codes: set[str]) -> dict[str, Any]:
        self._require_tech_or_admin(actor_role_codes)
        rows = (
            await self.db.execute(
                select(RealphotosSupportTicket)
                .where(RealphotosSupportTicket.deleted_at.is_(None))
                .order_by(RealphotosSupportTicket.id.desc())
            )
        ).scalars().all()
        return {"items": [self._ticket_dict(row) for row in rows]}

    async def create_ticket(
        self,
        *,
        tenant_id: int,
        owner_account_id: int,
        ticket_type: str,
        reason: str,
        actor_role_codes: set[str] | None = None,
    ) -> dict[str, Any]:
        kind = str(ticket_type or "").strip()
        if kind not in {"order", "image_appeal", "account_freeze"}:
            raise BusinessError(message="工单类型无效", code="INPUT_INVALID")
        text = str(reason or "").strip()
        if not text:
            raise BusinessError(message="原因必填", code="INPUT_INVALID")
        # 商家仅可创建申诉；解冻类仅技术/管理员可建（通常由系统建）
        if kind == "account_freeze":
            self._require_tech_or_admin(actor_role_codes or set())
        row = RealphotosSupportTicket(
            tenant_id=int(tenant_id),
            owner_account_id=int(owner_account_id),
            ticket_type=kind,
            status="open",
            reason=text,
        )
        self.db.add(row)
        await self.db.flush()
        return self._ticket_dict(row)

    async def list_merchant_tickets(
        self, *, tenant_id: int, owner_account_id: int
    ) -> dict[str, Any]:
        rows = (
            await self.db.execute(
                select(RealphotosSupportTicket)
                .where(
                    RealphotosSupportTicket.tenant_id == int(tenant_id),
                    RealphotosSupportTicket.owner_account_id == int(owner_account_id),
                    RealphotosSupportTicket.deleted_at.is_(None),
                )
                .order_by(RealphotosSupportTicket.id.desc())
            )
        ).scalars().all()
        return {"items": [self._ticket_dict(row) for row in rows]}

    async def list_held_credit_tasks(self, *, actor_role_codes: set[str]) -> dict[str, Any]:
        self._require_tech_or_admin(actor_role_codes)
        from app.capabilities.realphotos.models import RealphotosImageTask

        rows = (
            await self.db.execute(
                select(RealphotosImageTask)
                .where(
                    RealphotosImageTask.deleted_at.is_(None),
                    RealphotosImageTask.credit_disposition == "held_until_tech_support",
                )
                .order_by(RealphotosImageTask.id.desc())
                .limit(100)
            )
        ).scalars().all()
        return {
            "items": [
                {
                    "taskId": int(row.id),
                    "tenantId": int(row.tenant_id),
                    "ownerAccountId": int(row.owner_account_id),
                    "status": row.status,
                    "failureClass": row.failure_class,
                    "creditDisposition": row.credit_disposition,
                }
                for row in rows
            ]
        }

    async def list_preset_versions(self, *, actor_role_codes: set[str], code: str) -> list[dict]:
        if ROLE_ADMIN not in actor_role_codes and "admin" not in actor_role_codes:
            raise ForbiddenError(message="只有平台管理员可以浏览预设版本")
        rows = (
            await self.db.execute(
                select(RealphotosPresetVersion)
                .where(
                    RealphotosPresetVersion.preset_code == str(code),
                    RealphotosPresetVersion.deleted_at.is_(None),
                )
                .order_by(RealphotosPresetVersion.version_no.desc())
            )
        ).scalars().all()
        return [
            {
                "presetCode": row.preset_code,
                "versionNo": int(row.version_no),
                "snapshot": dict(row.snapshot or {}),
                "createdAt": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]

    async def enabled_preset(self, code: str) -> dict | None:
        row = await self._preset_row(code)
        if row is not None:
            if not row.enabled:
                return None
            latest = (
                await self.db.execute(
                    select(RealphotosPresetVersion)
                    .where(
                        RealphotosPresetVersion.preset_code == row.code,
                        RealphotosPresetVersion.deleted_at.is_(None),
                    )
                    .order_by(RealphotosPresetVersion.version_no.desc())
                )
            ).scalars().first()
            gps_config = None
            extra: dict = {}
            if latest is not None:
                snap = dict(latest.snapshot or {})
                if snap.get("gpsConfig"):
                    gps_config = dict(snap["gpsConfig"])
                if "gpsWriteConnected" in snap:
                    extra["gpsWriteConnected"] = bool(snap["gpsWriteConnected"])
                if isinstance(snap.get("legacyParameters"), dict):
                    extra["legacyParameters"] = dict(snap["legacyParameters"])
                if isinstance(snap.get("legacyGpsMeta"), dict):
                    extra["legacyGpsMeta"] = dict(snap["legacyGpsMeta"])
            payload = self._preset_dict(row, gps_config=gps_config)
            payload.update(extra)
            return payload
        # B1: catalog placeholders are no longer auto-enabled for processing preview.
        if INJECT_S1_CATALOG_INTO_ENABLED:
            for item in S1_ENABLED_PRESETS:
                if item["code"] == code:
                    from app.capabilities.realphotos.services.gps_write import gps_writability

                    payload = dict(item)
                    writable = gps_writability(
                        gps_mode=str(payload.get("gpsMode") or "none"),
                        gps_config=payload.get("gpsConfig")
                        if isinstance(payload.get("gpsConfig"), dict)
                        else None,
                    )
                    payload["gpsWritable"] = bool(writable["gpsWritable"])
                    payload["gpsWritableReason"] = str(writable["gpsWritableReason"] or "")
                    return payload
        return None

    async def list_admin_presets(self, *, actor_role_codes: set[str]) -> list[dict]:
        if ROLE_ADMIN not in actor_role_codes and "admin" not in actor_role_codes:
            raise ForbiddenError(message="只有平台管理员可以浏览预设台账")
        rows = {
            row.code: row
            for row in (await self.db.execute(select(RealphotosDevicePreset))).scalars().all()
            if row.deleted_at is None
        }
        items: list[dict] = []
        seen: set[str] = set()
        # Do not invent catalog rows; only show DB truth. Honeybadger placeholders should be soft-deleted.
        for code, row in rows.items():
            if str(row.brand or "").strip().lower() in PLACEHOLDER_BRAND_BLOCKLIST:
                continue
            gps_config = await self._latest_gps_config(code)
            items.append(self._preset_dict(row, gps_config=gps_config))
            seen.add(code)
        if INJECT_S1_CATALOG_INTO_ENABLED:
            for item in S1_ENABLED_PRESETS:
                if item["code"] in seen:
                    continue
                payload = dict(item)
                payload["enabled"] = False
                payload["placeholder"] = True
                items.append(payload)
        return items

    async def get_admin_preset(self, *, actor_role_codes: set[str], code: str) -> dict[str, Any]:
        if ROLE_ADMIN not in actor_role_codes and "admin" not in actor_role_codes:
            raise ForbiddenError(message="只有平台管理员可以浏览预设台账")
        row = await self._preset_row(code)
        if row is None or row.deleted_at is not None:
            raise BusinessError(message="预设不存在", code="NOT_FOUND")
        snap = await self._latest_snapshot(code)
        gps_config = None
        if isinstance(snap.get("gpsConfig"), dict):
            gps_config = dict(snap["gpsConfig"])
        payload = self._preset_dict(row, gps_config=gps_config)
        if isinstance(snap.get("legacyParameters"), dict):
            payload["legacyParameters"] = dict(snap["legacyParameters"])
        else:
            payload["legacyParameters"] = {}
        if isinstance(snap.get("legacyGpsMeta"), dict):
            payload["legacyGpsMeta"] = dict(snap["legacyGpsMeta"])
        if "gpsWriteConnected" in snap:
            payload["gpsWriteConnected"] = bool(snap["gpsWriteConnected"])
        payload["copyrightPolicy"] = "excluded_prd_no_author_copyright_ip_geo"
        return payload

    async def list_enabled_presets(self) -> list[dict]:
        from app.capabilities.realphotos.services.gps_write import gps_writability

        items: list[dict] = []
        if INJECT_S1_CATALOG_INTO_ENABLED:
            disabled = {
                row.code
                for row in (await self.db.execute(select(RealphotosDevicePreset))).scalars().all()
                if row.deleted_at is None and not row.enabled
            }
            for raw in S1_ENABLED_PRESETS:
                if raw["code"] in disabled:
                    continue
                payload = dict(raw)
                writable = gps_writability(
                    gps_mode=str(payload.get("gpsMode") or "none"),
                    gps_config=payload.get("gpsConfig")
                    if isinstance(payload.get("gpsConfig"), dict)
                    else None,
                )
                payload["gpsWritable"] = bool(writable["gpsWritable"])
                payload["gpsWillSkip"] = bool(writable.get("gpsWillSkip"))
                payload["gpsWritableReason"] = str(writable["gpsWritableReason"] or "")
                items.append(payload)
        extra = (
            await self.db.execute(
                select(RealphotosDevicePreset).where(
                    RealphotosDevicePreset.deleted_at.is_(None),
                    RealphotosDevicePreset.enabled.is_(True),
                    RealphotosDevicePreset.source.in_(("admin", "legacy_import", "catalog")),
                )
            )
        ).scalars().all()
        seen = {item["code"] for item in items}
        catalog_codes = {item["code"] for item in S1_ENABLED_PRESETS}
        for row in extra:
            # Skip catalog / Honeybadger placeholders (R1: no demo brand in merchant list).
            if str(row.source) == "catalog":
                continue
            if str(row.brand or "").strip().lower() in PLACEHOLDER_BRAND_BLOCKLIST:
                continue
            if row.code in catalog_codes and str(row.brand or "") == "Honeybadger":
                continue
            if str(row.code).startswith(("pa-gps-", "bf-", "s1-", "pga-")):
                # Historical placeholder code prefixes — hide unless real legacy_import.
                if str(row.source) != "legacy_import":
                    continue
            if row.code not in seen:
                gps_config = await self._latest_gps_config(row.code)
                items.append(self._preset_dict(row, gps_config=gps_config))
        return items

    async def save_preset(
        self,
        *,
        actor_role_codes: set[str],
        code: str,
        device_type: str,
        brand: str,
        model_name: str,
        gps_mode: str = "none",
        enabled: bool = True,
        maker_note: str | None = None,
        author: str | None = None,
        ip_geo: str | None = None,
        iso: str | None = None,
        shutter: str | None = None,
        aperture: str | None = None,
        focal_length: str | None = None,
        gps_config: dict | None = None,
        ai_positive_prompt: str | None = None,
        ai_negative_prompt: str | None = None,
        source: str | None = None,
        legacy_source_id: str | None = None,
        legacy_template_ref: str | None = None,
        legacy_visibility: str | None = None,
        legacy_review_bucket: str | None = None,
        snapshot_extra: dict | None = None,
        legacy_parameters: dict | None = None,
    ) -> dict[str, Any]:
        if ROLE_ADMIN not in actor_role_codes and "admin" not in actor_role_codes:
            raise ForbiddenError(message="只有平台管理员可以维护设备预设")
        # PRODUCT-GAP A7：管理员 2026-11-07 授权 MakerNote 写入；作者/IP-GEO 仍禁止。
        if author or ip_geo:
            raise BusinessError(message="第一版不接收作者或 IP-GEO", code="INPUT_INVALID")
        mode = str(gps_mode or "none").strip()
        if mode not in GPS_MODES:
            raise BusinessError(message="GPS 模式无效", code="INPUT_INVALID")
        dtype, mapped_from = normalize_device_type(device_type)
        label = str(code or "").strip()
        if not label or not str(brand or "").strip() or not str(model_name or "").strip():
            raise BusinessError(message="预设编号、品牌和型号必填", code="INPUT_INVALID")
        if str(brand).strip().lower() in PLACEHOLDER_BRAND_BLOCKLIST:
            raise BusinessError(
                message="禁止使用 Honeybadger 占位品牌；请填写真实设备品牌",
                code="INPUT_INVALID",
            )
        row = await self._preset_row(label)
        if row is None:
            row = RealphotosDevicePreset(
                tenant_id=0,
                code=label,
                device_type=dtype,
                brand=str(brand).strip(),
                model_name=str(model_name).strip(),
                gps_mode=mode,
                enabled=bool(enabled),
                version_no=1,
                source=str(source or ("catalog" if label in {item["code"] for item in S1_ENABLED_PRESETS} else "admin")),
            )
            self.db.add(row)
        else:
            row.device_type = dtype
            row.brand = str(brand).strip()
            row.model_name = str(model_name).strip()
            row.gps_mode = mode
            row.enabled = bool(enabled)
            row.version_no = int(row.version_no) + 1
            if source:
                row.source = str(source)
        if iso is not None:
            row.iso = str(iso)
        if shutter is not None:
            row.shutter = str(shutter)
        if aperture is not None:
            row.aperture = str(aperture)
        if focal_length is not None:
            row.focal_length = str(focal_length)
        if ai_positive_prompt is not None:
            row.ai_positive_prompt = str(ai_positive_prompt)
        if ai_negative_prompt is not None:
            row.ai_negative_prompt = str(ai_negative_prompt)
        if maker_note is not None:
            row.maker_note = str(maker_note)
        if legacy_source_id is not None:
            row.legacy_source_id = str(legacy_source_id)
        if legacy_template_ref is not None:
            row.legacy_template_ref = str(legacy_template_ref)
        if legacy_visibility is not None:
            row.legacy_visibility = str(legacy_visibility)
        if legacy_review_bucket is not None:
            row.legacy_review_bucket = str(legacy_review_bucket)
        # R2: enabling incomplete EXIF presets is refused (check merged row; no silent defaults).
        if bool(enabled):
            from app.capabilities.realphotos.services.five_layer import assert_preset_exif_ready

            assert_preset_exif_ready(
                {
                    "brand": row.brand,
                    "model": row.model_name,
                    "iso": row.iso,
                    "shutter": row.shutter,
                    "aperture": row.aperture,
                    "focalLength": row.focal_length,
                }
            )
        await self.db.flush()
        snapshot = self._preset_dict(row, gps_config=gps_config)
        if mapped_from:
            snapshot["deviceTypeMappedFrom"] = mapped_from
        if snapshot_extra:
            for key, value in dict(snapshot_extra).items():
                snapshot[key] = value
        # Merge legacy parameter snapshot; strip PRD-forbidden author/copyright/ip_geo keys.
        if legacy_parameters is not None:
            cleaned = {
                str(k): v
                for k, v in dict(legacy_parameters).items()
                if str(k).lower() not in {"author", "copyright", "ip_geo", "ipgeo"}
            }
            # Keep column mirrors honest when present.
            cleaned.setdefault("camera_make", row.brand)
            cleaned.setdefault("camera_model", row.model_name)
            cleaned.setdefault("iso", row.iso)
            cleaned.setdefault("shutter_speed", row.shutter)
            cleaned.setdefault("aperture", row.aperture)
            cleaned.setdefault("focal_length", row.focal_length)
            cleaned.setdefault("gps_mode", row.gps_mode)
            if row.maker_note:
                cleaned.setdefault("maker_note_template", row.maker_note)
            if row.ai_positive_prompt:
                cleaned.setdefault("ai_positive_prompt", row.ai_positive_prompt)
            if row.ai_negative_prompt:
                cleaned.setdefault("ai_negative_prompt", row.ai_negative_prompt)
            snapshot["legacyParameters"] = cleaned
        elif isinstance((snapshot_extra or {}).get("legacyParameters"), dict):
            pass
        else:
            # Preserve previous legacyParameters on edit when caller omits them.
            prev = await self._latest_snapshot(row.code)
            if isinstance(prev.get("legacyParameters"), dict) and "legacyParameters" not in snapshot:
                snapshot["legacyParameters"] = dict(prev["legacyParameters"])
        # When fixed/random without coords, still mark write path connected but honesty lives in legacyGpsMeta.
        snapshot["gpsWriteConnected"] = True
        self.db.add(
            RealphotosPresetVersion(
                tenant_id=int(row.tenant_id or 0),
                preset_code=row.code,
                version_no=int(row.version_no),
                snapshot=snapshot,
            )
        )
        await self.db.flush()
        payload = self._preset_dict(row, gps_config=gps_config)
        if mapped_from:
            payload["deviceTypeMappedFrom"] = mapped_from
        if snapshot_extra:
            for key, value in dict(snapshot_extra).items():
                payload[key] = value
        if isinstance(snapshot.get("legacyParameters"), dict):
            payload["legacyParameters"] = dict(snapshot["legacyParameters"])
        payload["gpsWriteConnected"] = True
        return payload

    async def set_preset_enabled(
        self, *, actor_role_codes: set[str], code: str, enabled: bool
    ) -> dict[str, Any]:
        current = await self.enabled_preset(code) if enabled else None
        catalog = next((dict(item) for item in S1_ENABLED_PRESETS if item["code"] == code), None)
        base = current or catalog
        if base is None:
            # Disabled admin presets are not in enabled_preset/catalog; still must re-enable.
            row = await self._preset_row(code)
            if row is None:
                raise BusinessError(message="预设不存在", code="NOT_FOUND")
            base = self._preset_dict(row)
        return await self.save_preset(
            actor_role_codes=actor_role_codes,
            code=code,
            device_type=str(base.get("deviceType") or "phone"),
            brand=str(base.get("brand") or ""),
            model_name=str(base.get("model") or ""),
            gps_mode=str(base.get("gpsMode") or "none"),
            enabled=bool(enabled),
            iso=base.get("iso"),
            shutter=base.get("shutter"),
            aperture=base.get("aperture"),
            focal_length=base.get("focalLength"),
            gps_config=base.get("gpsConfig") if isinstance(base.get("gpsConfig"), dict) else None,
        )

    async def create_user(
        self,
        *,
        actor_role_codes: set[str],
        operator_user_id: int,
        tenant_id: int,
        username: str,
        password: str,
        role_code: str,
    ) -> dict[str, Any]:
        self._require_tech_or_admin(actor_role_codes)
        name = str(username or "").strip()
        if not name or not str(password or ""):
            raise BusinessError(message="用户名和密码必填", code="INPUT_INVALID")
        exists = (
            await self.db.execute(select(User).where(User.username == name, User.deleted_at.is_(None)))
        ).scalar_one_or_none()
        if exists is not None:
            raise BusinessError(message="用户名已存在", code="INPUT_INVALID")
        role = await self._role(tenant_id, role_code)
        user = User(
            tenant_id=int(tenant_id),
            username=name,
            password_hash=hash_password(password),
            nickname=name,
            status=int(UserStatus.ENABLED),
        )
        self.db.add(user)
        await self.db.flush()
        self.db.add(UserRole(tenant_id=int(tenant_id), user_id=int(user.id), role_id=int(role.id)))
        self.db.add(
            RealphotosMerchantProfile(
                tenant_id=int(tenant_id), user_id=int(user.id), display_name=name
            )
        )
        await self._log(
            operator_user_id=operator_user_id,
            target=user,
            action="create",
            before={},
            after={"username": name, "status": "enabled", "role": role_code},
            reason="",
        )
        return {"id": int(user.id), "username": name}

    async def adjust_credits(
        self,
        *,
        actor_role_codes: set[str],
        operator_user_id: int,
        tenant_id: int,
        user_id: int,
        delta: object,
        reason: str,
        event_key: str,
    ) -> dict[str, Any]:
        self._require_tech_or_admin(actor_role_codes)
        if isinstance(delta, bool) or not isinstance(delta, int):
            raise BusinessError(message="积分必须是整数", code="INPUT_INVALID")
        target = await self._managed_user(actor_role_codes, operator_user_id, user_id, allow_self=True)
        before = int((await RealphotosCreditService(self.db).get_wallet(tenant_id=tenant_id))["availableInteger"])
        await RealphotosCreditService(self.db).admin_adjust(
            tenant_id=int(tenant_id),
            delta_available=int(delta),
            operator_user_id=int(operator_user_id),
            reason=reason,
            event_key=event_key,
            target_user_id=int(user_id),
        )
        after = int((await RealphotosCreditService(self.db).get_wallet(tenant_id=tenant_id))["availableInteger"])
        await self._log(
            operator_user_id=operator_user_id,
            target=target,
            action="credit",
            before={"availableInteger": before},
            after={"availableInteger": after, "delta": int(delta)},
            reason=reason,
        )
        return {"availableInteger": after}

    async def set_roles(
        self,
        *,
        actor_role_codes: set[str],
        operator_user_id: int,
        tenant_id: int,
        user_id: int,
        role_codes: list[str],
    ) -> dict[str, Any]:
        self._require_tech_or_admin(actor_role_codes)
        target = await self._managed_user(actor_role_codes, operator_user_id, user_id, allow_self=False)
        before = await self._role_codes(int(target.id), int(target.tenant_id))
        await self.db.execute(
            delete(UserRole).where(
                UserRole.user_id == int(target.id),
                UserRole.tenant_id == int(tenant_id),
            )
        )
        for code in role_codes:
            role = await self._role(tenant_id, code)
            self.db.add(UserRole(tenant_id=int(tenant_id), user_id=int(target.id), role_id=int(role.id)))
        await self.db.flush()
        after = await self._role_codes(int(target.id), int(tenant_id))
        await self._log(
            operator_user_id=operator_user_id,
            target=target,
            action="permission",
            before={"roles": before},
            after={"roles": after},
            reason="",
        )
        return {"roles": after}

    async def set_status(
        self,
        *,
        actor_role_codes: set[str],
        operator_user_id: int,
        user_id: int,
        enabled: bool,
    ) -> dict[str, Any]:
        self._require_tech_or_admin(actor_role_codes)
        target = await self._managed_user(actor_role_codes, operator_user_id, user_id, allow_self=False)
        before = int(target.status)
        target.status = int(UserStatus.ENABLED if enabled else UserStatus.DISABLED)
        await self.db.flush()
        await self._log(
            operator_user_id=operator_user_id,
            target=target,
            action="status",
            before={"status": before},
            after={"status": int(target.status)},
            reason="",
        )
        return {"status": int(target.status)}

    async def reset_password(
        self,
        *,
        actor_role_codes: set[str],
        operator_user_id: int,
        user_id: int,
        password: str,
        confirm: str,
    ) -> dict[str, Any]:
        self._require_tech_or_admin(actor_role_codes)
        if str(password or "") == "" or str(password) != str(confirm or ""):
            raise BusinessError(message="两次密码不一致", code="INPUT_INVALID")
        target = await self._managed_user(actor_role_codes, operator_user_id, user_id, allow_self=True)
        target.password_hash = hash_password(password)
        await self.db.flush()
        await self._log(
            operator_user_id=operator_user_id,
            target=target,
            action="reset_password",
            before={},
            after={"passwordStored": "hash_only"},
            reason="",
        )
        return {"reset": True}

    async def delete_user(
        self,
        *,
        actor_role_codes: set[str],
        operator_user_id: int,
        user_id: int,
        confirm_username: str,
    ) -> dict[str, Any]:
        self._require_tech_or_admin(actor_role_codes)
        target = await self._managed_user(actor_role_codes, operator_user_id, user_id, allow_self=False)
        if str(confirm_username or "").strip() != target.username:
            raise BusinessError(message="须输入登录名确认删除", code="INPUT_INVALID")
        if target.username == PROTECTED_USERNAME:
            raise ForbiddenError(message="不能删除受保护的平台管理员")
        target.deleted_at = datetime.now(UTC)
        await self.db.flush()
        await self._log(
            operator_user_id=operator_user_id,
            target=target,
            action="delete",
            before={"username": target.username},
            after={"deleted": True},
            reason="",
        )
        return {"deleted": True}

    async def list_users(self, *, actor_role_codes: set[str], page: int = 1) -> dict[str, Any]:
        self._require_tech_or_admin(actor_role_codes)
        size = USER_PAGE_SIZE
        index = max(int(page), 1)
        rows = (
            await self.db.execute(
                select(User).where(User.deleted_at.is_(None)).order_by(User.id.asc())
            )
        ).scalars().all()
        start = (index - 1) * size
        page_rows = rows[start : start + size]
        return {
            "pageSize": size,
            "items": [{"id": int(row.id), "username": row.username, "status": int(row.status)} for row in page_rows],
        }

    async def list_logs(self, *, actor_role_codes: set[str], page: int = 1) -> dict[str, Any]:
        self._require_tech_or_admin(actor_role_codes)
        size = LOG_PAGE_SIZE
        index = max(int(page), 1)
        rows = (
            await self.db.execute(
                select(RealphotosAccountLog)
                .where(RealphotosAccountLog.deleted_at.is_(None))
                .order_by(RealphotosAccountLog.id.desc())
            )
        ).scalars().all()
        start = (index - 1) * size
        page_rows = rows[start : start + size]
        user_ids = {int(r.operator_user_id) for r in page_rows} | {int(r.target_user_id) for r in page_rows}
        tenant_ids = {int(r.tenant_id) for r in page_rows}
        users = {}
        if user_ids:
            for user in (
                await self.db.execute(select(User).where(User.id.in_(user_ids)))
            ).scalars().all():
                users[int(user.id)] = user
        tenants = {}
        if tenant_ids:
            for tenant in (
                await self.db.execute(select(Tenant).where(Tenant.id.in_(tenant_ids)))
            ).scalars().all():
                tenants[int(tenant.id)] = tenant

        def _user_display(uid: int) -> str:
            user = users.get(int(uid))
            if user is None or getattr(user, "deleted_at", None) is not None:
                return f"已删除用户 #{int(uid)}"
            return str(user.username)

        def _tenant_display(tid: int) -> str:
            tenant = tenants.get(int(tid))
            if tenant is None or getattr(tenant, "deleted_at", None) is not None:
                return f"已删除租户 #{int(tid)}"
            code = str(getattr(tenant, "code", "") or "")
            name = str(getattr(tenant, "name", "") or "")
            if code and name:
                return f"{name}（{code}）"
            return name or code or f"租户 #{int(tid)}"

        def _action_zh(raw: str) -> str:
            key = str(raw or "").strip()
            return ACCOUNT_LOG_ACTION_ZH.get(key, f"未知（{key or '空'}）")

        def _result_zh(raw: str) -> str:
            key = str(raw or "").strip().lower()
            return ACCOUNT_LOG_RESULT_ZH.get(key, f"未知（{raw or '空'}）")

        return {
            "pageSize": size,
            "items": [
                {
                    "id": int(row.id),
                    "operatorUserId": int(row.operator_user_id),
                    "targetUserId": int(row.target_user_id),
                    "tenantId": int(row.tenant_id),
                    "operatorDisplay": _user_display(int(row.operator_user_id)),
                    "targetDisplay": _user_display(int(row.target_user_id)),
                    "tenantDisplay": _tenant_display(int(row.tenant_id)),
                    "action": row.action,
                    "actionLabel": _action_zh(str(row.action or "")),
                    "before": dict(row.before_state or {}),
                    "after": dict(row.after_state or {}),
                    "createdAt": row.created_at.isoformat() if row.created_at else None,
                    "reason": row.reason,
                    "result": row.result,
                    "resultLabel": _result_zh(str(row.result or "")),
                }
                for row in page_rows
            ],
        }

    async def metrics(self, *, actor_role_codes: set[str]) -> dict[str, Any]:
        if ROLE_ADMIN not in actor_role_codes and "admin" not in actor_role_codes:
            raise ForbiddenError(message="运营指标只对平台管理员开放")
        storage_bytes = await self.db.scalar(
            select(func.coalesce(func.sum(RealphotosAsset.byte_size), 0)).where(
                RealphotosAsset.deleted_at.is_(None)
            )
        )
        queued = await self.db.scalar(
            select(func.count())
            .select_from(RealphotosExecutionJob)
            .where(RealphotosExecutionJob.status.in_(("queued", "running")), RealphotosExecutionJob.deleted_at.is_(None))
        )
        tasks = int(
            await self.db.scalar(
                select(func.count()).select_from(RealphotosImageTask).where(RealphotosImageTask.deleted_at.is_(None))
            )
            or 0
        )
        failed = int(
            await self.db.scalar(
                select(func.count())
                .select_from(RealphotosImageTask)
                .where(RealphotosImageTask.deleted_at.is_(None), RealphotosImageTask.status == "FAILED")
            )
            or 0
        )
        detected = int(
            await self.db.scalar(select(func.count()).select_from(RealphotosDetectionResult))
            or 0
        )
        passed = int(
            await self.db.scalar(
                select(func.count())
                .select_from(RealphotosDetectionResult)
                .where(RealphotosDetectionResult.passed.is_(True))
            )
            or 0
        )
        balance = await self.db.scalar(select(func.coalesce(func.sum(RealphotosCreditAccount.available_integer), 0)))
        reserved = await self.db.scalar(select(func.coalesce(func.sum(RealphotosCreditAccount.reserved_integer), 0)))
        reviews = int(await self.db.scalar(select(func.count()).select_from(RealphotosContentReview)) or 0)
        generations = int(
            await self.db.scalar(
                select(func.count())
                .select_from(RealphotosGenerationItem)
                .where(RealphotosGenerationItem.deleted_at.is_(None))
            )
            or 0
        )
        prompt_opts = int(
            await self.db.scalar(
                select(func.count())
                .select_from(RealphotosPromptOptimization)
                .where(RealphotosPromptOptimization.deleted_at.is_(None))
            )
            or 0
        )
        model_calls = reviews + generations + prompt_opts
        from app.capabilities.realphotos.services.provider_usage import RealphotosProviderUsageService

        cost_block = await RealphotosProviderUsageService(self.db).ops_cost_summary()
        return {
            "availableInteger": int(balance or 0),
            "reservedInteger": int(reserved or 0),
            "queueDepth": int(queued or 0),
            "failureRate": None if tasks == 0 else failed / tasks,
            "detectionPassRate": None if detected == 0 else passed / detected,
            # Call-time upstream ledger; never invent 0 when price/calls missing.
            "cost": cost_block.get("cost"),
            "costReason": cost_block.get("costReason"),
            "costKnownAmount": cost_block.get("costKnownAmount"),
            "costUnknownCount": cost_block.get("costUnknownCount"),
            "costSource": cost_block.get("costSource"),
            "creditsNotUsedForCost": True,
            "modelCalls": int(model_calls),
            "modelCallsSource": "content_review+generation_item+prompt_optimization",
            "storageBytes": int(storage_bytes or 0),
            "storageBytesSource": "sum(cap_realphotos_asset.byte_size where deleted_at is null)",
            "merchantCards": False,
        }

    async def _lock_on_second(self, tenant_id: int, owner_id: int, identity: str, subject: str) -> bool:
        prior = int(
            await self.db.scalar(
                select(func.count())
                .select_from(RealphotosContentReview)
                .where(
                    RealphotosContentReview.tenant_id == int(tenant_id),
                    RealphotosContentReview.owner_account_id == int(owner_id),
                    RealphotosContentReview.image_identity == identity,
                    RealphotosContentReview.subject == subject,
                    RealphotosContentReview.passed.is_(False),
                    RealphotosContentReview.deleted_at.is_(None),
                )
            )
            or 0
        )
        if prior < 2:
            return False
        existing = (
            await self.db.execute(
                select(RealphotosImageLock).where(
                    RealphotosImageLock.tenant_id == int(tenant_id),
                    RealphotosImageLock.owner_account_id == int(owner_id),
                    RealphotosImageLock.image_identity == identity,
                    RealphotosImageLock.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            self.db.add(
                RealphotosImageLock(
                    tenant_id=int(tenant_id),
                    owner_account_id=int(owner_id),
                    image_identity=identity,
                    reason="second_content_failure",
                )
            )
            await self.db.flush()
        return True

    async def _note_distinct_failure(self, tenant_id: int, owner_id: int, identity: str) -> tuple[bool, int | None]:
        streak = (
            await self.db.execute(
                select(RealphotosReviewStreak).where(
                    RealphotosReviewStreak.tenant_id == int(tenant_id),
                    RealphotosReviewStreak.owner_account_id == int(owner_id),
                    RealphotosReviewStreak.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if streak is None:
            streak = RealphotosReviewStreak(
                tenant_id=int(tenant_id), owner_account_id=int(owner_id), identities=[]
            )
            self.db.add(streak)
            await self.db.flush()
        identities = [str(item) for item in list(streak.identities or [])]
        added = identity not in identities
        if added:
            identities.append(identity)
        streak.identities = identities
        await self.db.flush()
        if len(identities) < 3 or not added or len(identities) != 3:
            return False, None
        profile = await self._profile(tenant_id, owner_id)
        if profile is None:
            profile = RealphotosMerchantProfile(
                tenant_id=int(tenant_id), user_id=int(owner_id), display_name="", pre_review_frozen=True
            )
            self.db.add(profile)
        else:
            profile.pre_review_frozen = True
        ticket = RealphotosSupportTicket(
            tenant_id=int(tenant_id),
            owner_account_id=int(owner_id),
            ticket_type="account_freeze",
            status="open",
            reason="三张不同图连续预审未通过",
        )
        self.db.add(ticket)
        await self.db.flush()
        return True, int(ticket.id)

    async def _reset_streak(self, tenant_id: int, owner_id: int) -> None:
        streak = (
            await self.db.execute(
                select(RealphotosReviewStreak).where(
                    RealphotosReviewStreak.tenant_id == int(tenant_id),
                    RealphotosReviewStreak.owner_account_id == int(owner_id),
                    RealphotosReviewStreak.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if streak is not None:
            streak.identities = []
            await self.db.flush()

    async def _profile(self, tenant_id: int, user_id: int) -> RealphotosMerchantProfile | None:
        return (
            await self.db.execute(
                select(RealphotosMerchantProfile).where(
                    RealphotosMerchantProfile.tenant_id == int(tenant_id),
                    RealphotosMerchantProfile.user_id == int(user_id),
                    RealphotosMerchantProfile.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()

    async def _preset_row(self, code: str) -> RealphotosDevicePreset | None:
        return (
            await self.db.execute(
                select(RealphotosDevicePreset).where(
                    RealphotosDevicePreset.code == code,
                    RealphotosDevicePreset.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()

    async def _role(self, tenant_id: int, code: str) -> Role:
        role = (
            await self.db.execute(
                select(Role).where(
                    Role.tenant_id == int(tenant_id),
                    Role.code == str(code),
                    Role.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if role is None:
            raise BusinessError(message="角色不存在", code="INPUT_INVALID")
        return role

    async def _role_codes(self, user_id: int, tenant_id: int) -> list[str]:
        rows = (
            await self.db.execute(
                select(Role.code)
                .join(UserRole, UserRole.role_id == Role.id)
                .where(UserRole.user_id == int(user_id), UserRole.tenant_id == int(tenant_id))
            )
        ).all()
        return sorted(str(code) for (code,) in rows)

    async def _managed_user(
        self, actor_roles: set[str], operator_user_id: int, user_id: int, *, allow_self: bool
    ) -> User:
        user = await self.db.get(User, int(user_id))
        if user is None or user.deleted_at is not None:
            raise BusinessError(message="用户不存在", code="NOT_FOUND")
        if user.username == PROTECTED_USERNAME and ROLE_ADMIN not in actor_roles and "admin" not in actor_roles:
            raise ForbiddenError(message="不能改受保护的平台管理员")
        if int(user.id) == int(operator_user_id) and not allow_self:
            raise ForbiddenError(message="不能对自己做这项操作")
        return user

    async def _log(
        self,
        *,
        operator_user_id: int,
        target: User,
        action: str,
        before: dict,
        after: dict,
        reason: str,
    ) -> None:
        self.db.add(
            RealphotosAccountLog(
                tenant_id=int(target.tenant_id),
                operator_user_id=int(operator_user_id),
                target_user_id=int(target.id),
                action=action,
                before_state=before,
                after_state=after,
                reason=str(reason or ""),
                result="success",
            )
        )
        await self.db.flush()

    def _require_tech_or_admin(self, roles: set[str]) -> None:
        if ROLE_TECH_SUPPORT in roles or ROLE_ADMIN in roles or "admin" in roles:
            return
        if ROLE_ORDER_SUPPORT in roles:
            raise ForbiddenError(message="订单客服不能做这项操作")
        raise ForbiddenError(message="没有这项权限")

    @staticmethod
    def _review_payload(row: RealphotosContentReview, *, locked: bool, frozen: bool, ticket_id: int | None) -> dict:
        return {
            "verdict": row.verdict,
            "passed": bool(row.passed),
            "provider": row.provider,
            "supplierConnected": False,
            "locked": locked,
            "frozen": frozen,
            "ticketId": ticket_id,
        }

    @staticmethod
    def _preset_dict(
        row: RealphotosDevicePreset,
        *,
        gps_config: dict | None = None,
    ) -> dict:
        from app.capabilities.realphotos.services.gps_write import gps_writability

        dtype = str(row.device_type or "")
        mapped_from = None
        if dtype in DEVICE_TYPE_ALIASES:
            mapped_from = dtype
            dtype = DEVICE_TYPE_ALIASES[dtype]
        elif dtype not in DEVICE_TYPES:
            # Undocumented historical value: keep visible but mark disabled for honesty.
            mapped_from = dtype
        mode = str(row.gps_mode or "none")
        config = dict(gps_config or {})
        writable = gps_writability(gps_mode=mode, gps_config=config)
        payload = {
            "code": row.code,
            "deviceType": dtype if dtype in DEVICE_TYPES else str(row.device_type or ""),
            "brand": row.brand,
            "model": row.model_name,
            "iso": row.iso,
            "shutter": row.shutter,
            "aperture": row.aperture,
            "focalLength": row.focal_length,
            "gpsMode": mode,
            "enabled": bool(row.enabled),
            "source": row.source,
            "aiPositivePrompt": getattr(row, "ai_positive_prompt", "") or "",
            "aiNegativePrompt": getattr(row, "ai_negative_prompt", "") or "",
            "makerNote": getattr(row, "maker_note", "") or "",
            "legacySourceId": getattr(row, "legacy_source_id", "") or "",
            "legacyTemplateRef": getattr(row, "legacy_template_ref", "") or "",
            "legacyVisibility": getattr(row, "legacy_visibility", "") or "",
            "legacyReviewBucket": getattr(row, "legacy_review_bucket", "") or "",
            "deviceTypeMappedFrom": mapped_from,
            "deviceTypeUnsupported": bool(dtype not in DEVICE_TYPES and mapped_from),
            "gpsWritable": bool(writable["gpsWritable"]),
            "gpsWillSkip": bool(writable.get("gpsWillSkip")),
            "gpsWritableReason": str(writable["gpsWritableReason"] or ""),
        }
        if config:
            payload["gpsConfig"] = config
        return payload

    async def _latest_snapshot(self, code: str) -> dict[str, Any]:
        latest = (
            await self.db.execute(
                select(RealphotosPresetVersion)
                .where(
                    RealphotosPresetVersion.preset_code == str(code),
                    RealphotosPresetVersion.deleted_at.is_(None),
                )
                .order_by(RealphotosPresetVersion.version_no.desc())
            )
        ).scalars().first()
        if latest is None:
            return {}
        return dict(latest.snapshot or {})

    async def _latest_gps_config(self, code: str) -> dict | None:
        snap = await self._latest_snapshot(code)
        raw = snap.get("gpsConfig")
        return dict(raw) if isinstance(raw, dict) else None

    async def fixed_gps_missing_coords_count(self) -> int:
        """Count presets with gpsMode=fixed but no usable lat/lng in latest snapshot.

        Runtime may still process them (GPS skipped, legacy-aligned); this count is
        for ops visibility of incomplete fixed configs.
        """
        rows = (
            await self.db.execute(
                select(RealphotosDevicePreset).where(RealphotosDevicePreset.deleted_at.is_(None))
            )
        ).scalars().all()
        missing = 0
        for row in rows:
            if str(row.gps_mode or "") != "fixed":
                continue
            config = await self._latest_gps_config(row.code) or {}
            try:
                lat = float(config.get("latitude"))
                lon = float(config.get("longitude"))
            except (TypeError, ValueError):
                missing += 1
                continue
            if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
                missing += 1
        return missing


def login_lock_untouched(guard: RealphotosAuthGuard | None, previous: object) -> bool:
    if guard is None:
        return previous is None
    return guard.locked_until == previous
