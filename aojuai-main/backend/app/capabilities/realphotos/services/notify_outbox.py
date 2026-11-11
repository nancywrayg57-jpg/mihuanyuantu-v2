"""FR-023 / AD-001：outbox → inbox 投递（可独立进程轮询，最多 3 次 attempt）。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.realphotos.constants import INBOX_TTL_DAYS, NOTIFY_MAX_ATTEMPTS, NOTIFY_RETRY_SECONDS
from app.capabilities.realphotos.models import RealphotosInboxMessage, RealphotosOutbox
from app.core.config import settings


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _force_fail_until() -> int:
    """E2E 钩：REALPHOTOS_NOTIFY_FORCE_FAIL_UNTIL=N 时前 N 次 attempt 强制失败。"""
    raw = str(settings.REALPHOTOS_NOTIFY_FORCE_FAIL_UNTIL or "").strip()
    if not raw:
        return 0
    try:
        return max(0, int(raw))
    except ValueError:
        return 0


class RealphotosNotifyOutboxService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def enqueue_inbox(
        self,
        *,
        tenant_id: int,
        recipient_user_id: int,
        event_key: str,
        title: str,
        body: str,
        extra: dict[str, Any] | None = None,
    ) -> RealphotosOutbox:
        """业务事务内只写 outbox，不算投递完成。"""
        existing = (
            await self.db.execute(
                select(RealphotosOutbox).where(
                    RealphotosOutbox.tenant_id == int(tenant_id),
                    RealphotosOutbox.event_key == str(event_key),
                    RealphotosOutbox.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        payload = {
            "title": title,
            "body": body,
            "recipientUserId": int(recipient_user_id),
            **(extra or {}),
        }
        row = RealphotosOutbox(
            tenant_id=int(tenant_id),
            event_key=str(event_key),
            event_type="inbox",
            payload=payload,
            status="pending",
            recipient_user_id=int(recipient_user_id),
            attempt_count=0,
            next_attempt_at=_utcnow(),
            last_error=None,
        )
        self.db.add(row)
        await self.db.flush()
        return row

    async def claim_one(self) -> RealphotosOutbox | None:
        now = _utcnow()
        stmt = (
            select(RealphotosOutbox)
            .where(
                RealphotosOutbox.deleted_at.is_(None),
                RealphotosOutbox.status == "pending",
                or_(
                    RealphotosOutbox.next_attempt_at.is_(None),
                    RealphotosOutbox.next_attempt_at <= now,
                ),
            )
            .order_by(RealphotosOutbox.created_at.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        try:
            row = (await self.db.execute(stmt)).scalar_one_or_none()
        except Exception:
            # SQLite 等不支持 skip_locked 时降级
            stmt = (
                select(RealphotosOutbox)
                .where(
                    RealphotosOutbox.deleted_at.is_(None),
                    RealphotosOutbox.status == "pending",
                    or_(
                        RealphotosOutbox.next_attempt_at.is_(None),
                        RealphotosOutbox.next_attempt_at <= now,
                    ),
                )
                .order_by(RealphotosOutbox.created_at.asc())
                .limit(1)
            )
            row = (await self.db.execute(stmt)).scalar_one_or_none()
        return row

    async def deliver_claimed(self, row: RealphotosOutbox) -> dict[str, Any]:
        """对已认领行执行一次投递：成功标 sent；失败递增 attempt，满 3 次标 dead。"""
        attempt = int(row.attempt_count or 0) + 1
        row.attempt_count = attempt
        force_until = _force_fail_until()
        try:
            if force_until and attempt <= force_until:
                raise RuntimeError(f"forced_notify_fail attempt={attempt}")
            await self._write_inbox(row)
            row.status = "sent"
            row.last_error = None
            row.next_attempt_at = None
            await self.db.flush()
            return {"id": int(row.id), "status": "sent", "attemptCount": attempt}
        except Exception as exc:  # noqa: BLE001 — 投递失败要记账并重试
            row.last_error = str(exc)[:500]
            if attempt >= NOTIFY_MAX_ATTEMPTS:
                row.status = "dead"
                row.next_attempt_at = None
            else:
                delay = NOTIFY_RETRY_SECONDS[min(attempt - 1, len(NOTIFY_RETRY_SECONDS) - 1)]
                row.status = "pending"
                row.next_attempt_at = _utcnow() + timedelta(seconds=delay)
            await self.db.flush()
            return {
                "id": int(row.id),
                "status": row.status,
                "attemptCount": attempt,
                "error": row.last_error,
            }

    async def deliver_one(self) -> dict[str, Any] | None:
        row = await self.claim_one()
        if row is None:
            return None
        return await self.deliver_claimed(row)

    async def _write_inbox(self, row: RealphotosOutbox) -> RealphotosInboxMessage:
        payload = dict(row.payload or {})
        recipient = int(row.recipient_user_id or payload.get("recipientUserId") or 0)
        if recipient <= 0:
            raise RuntimeError("outbox missing recipient_user_id")
        title = str(payload.get("title") or "").strip() or "通知"
        body = str(payload.get("body") or "")
        existing = (
            await self.db.execute(
                select(RealphotosInboxMessage).where(
                    RealphotosInboxMessage.tenant_id == int(row.tenant_id),
                    RealphotosInboxMessage.event_key == str(row.event_key),
                    RealphotosInboxMessage.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        msg = RealphotosInboxMessage(
            tenant_id=int(row.tenant_id),
            recipient_user_id=recipient,
            event_key=str(row.event_key),
            title=title,
            body=body,
            expires_at=_utcnow() + timedelta(days=INBOX_TTL_DAYS),
        )
        self.db.add(msg)
        await self.db.flush()
        return msg
