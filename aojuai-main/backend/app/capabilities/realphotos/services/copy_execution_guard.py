"""AD-005 / §6.2 路径 A：复制执行门闩（guard_epoch / ACCOUNT_SPEND_BUSY）。

LEASE_TTL_DEFERRED（AUDIT-REMAIN B2 书面降级）：
首版不启用 lease_until 心跳 / TTL 废止；acquire 写入 lease_until=None；
仅 batch 全部子项终态后 release_for_batch。架构 §6.2 同步注明。
业务路径禁止读写 merchant.copy_latch_*（遗留列仅历史兼容）。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.realphotos.models.copy_guard import RealphotosCopyExecutionGuard
from app.core.exceptions import BusinessError

ACCOUNT_SPEND_BUSY = "ACCOUNT_SPEND_BUSY"
COPY_BUSY_MESSAGE = "复制任务进行中，请稍后再试"
GUARD_STATE_ACTIVE = "active"
GUARD_STATE_RELEASED = "released"
LEASE_TTL_DEFERRED = True


class RealphotosCopyExecutionGuardService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_active(
        self, *, tenant_id: int, owner_account_id: int
    ) -> RealphotosCopyExecutionGuard | None:
        return (
            await self.db.execute(
                select(RealphotosCopyExecutionGuard).where(
                    RealphotosCopyExecutionGuard.tenant_id == int(tenant_id),
                    RealphotosCopyExecutionGuard.owner_account_id == int(owner_account_id),
                    RealphotosCopyExecutionGuard.state == GUARD_STATE_ACTIVE,
                    RealphotosCopyExecutionGuard.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()

    async def reject_if_busy(self, *, tenant_id: int, owner_account_id: int) -> None:
        guard = await self.get_active(tenant_id=tenant_id, owner_account_id=owner_account_id)
        if guard is None:
            return
        raise BusinessError(
            message=COPY_BUSY_MESSAGE,
            code=ACCOUNT_SPEND_BUSY,
            details={
                "batchId": int(guard.batch_id),
                "guardEpoch": int(guard.guard_epoch),
            },
        )

    async def acquire(
        self, *, tenant_id: int, owner_account_id: int, batch_id: int
    ) -> RealphotosCopyExecutionGuard:
        await self.reject_if_busy(tenant_id=tenant_id, owner_account_id=owner_account_id)
        prior = (
            await self.db.execute(
                select(RealphotosCopyExecutionGuard)
                .where(
                    RealphotosCopyExecutionGuard.tenant_id == int(tenant_id),
                    RealphotosCopyExecutionGuard.owner_account_id == int(owner_account_id),
                    RealphotosCopyExecutionGuard.deleted_at.is_(None),
                )
                .order_by(RealphotosCopyExecutionGuard.guard_epoch.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        epoch = int(prior.guard_epoch if prior is not None else 0) + 1
        # LEASE_TTL_DEFERRED：首版不写 TTL；解除仅靠 batch 终态 release。
        row = RealphotosCopyExecutionGuard(
            tenant_id=int(tenant_id),
            owner_account_id=int(owner_account_id),
            batch_id=int(batch_id),
            guard_epoch=epoch,
            state=GUARD_STATE_ACTIVE,
            lease_until=None,
            version=1,
        )
        self.db.add(row)
        await self.db.flush()
        return row

    async def release_for_batch(
        self, *, tenant_id: int, owner_account_id: int, batch_id: int
    ) -> bool:
        guard = await self.get_active(tenant_id=tenant_id, owner_account_id=owner_account_id)
        if guard is None:
            return False
        if int(guard.batch_id) != int(batch_id):
            return False
        guard.state = GUARD_STATE_RELEASED
        guard.version = int(guard.version or 1) + 1
        await self.db.flush()
        return True

    async def force_clear_active(self, *, tenant_id: int, owner_account_id: int) -> bool:
        """端测/运维清理残留 active guard；生产业务路径勿用。"""
        guard = await self.get_active(tenant_id=tenant_id, owner_account_id=owner_account_id)
        if guard is None:
            return False
        guard.state = GUARD_STATE_RELEASED
        guard.version = int(guard.version or 1) + 1
        await self.db.flush()
        return True
