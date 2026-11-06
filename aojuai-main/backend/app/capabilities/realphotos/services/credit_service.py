"""Integer credit ledger — isolated from base Decimal credits."""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.realphotos.constants import (
    LEDGER_TYPE_ADMIN_ADJUST,
    LEDGER_TYPE_CONSUME,
    LEDGER_TYPE_FREEZE,
    LEDGER_TYPE_RECHARGE_CONFIRM,
    LEDGER_TYPE_RELEASE,
)
from app.capabilities.realphotos.models import (
    RealphotosCreditAccount,
    RealphotosCreditLedgerEntry,
)
from app.core.exceptions import BusinessError, NotFoundError


class RealphotosCreditService:
    """唯一余额真相：cap_realphotos_credit_* 整数流水。

    禁止桥接底座 Decimal CreditService；本服务不 import 该模块。
    """

    DECIMAL_BRIDGE_FORBIDDEN = True

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_or_create_account(self, *, tenant_id: int) -> RealphotosCreditAccount:
        result = await self.db.execute(
            select(RealphotosCreditAccount).where(
                RealphotosCreditAccount.tenant_id == int(tenant_id),
                RealphotosCreditAccount.deleted_at.is_(None),
            )
        )
        account = result.scalar_one_or_none()
        if account is None:
            account = RealphotosCreditAccount(
                tenant_id=int(tenant_id),
                available_integer=0,
                reserved_integer=0,
                version=1,
            )
            self.db.add(account)
            await self.db.flush()
        return account

    async def get_wallet(self, *, tenant_id: int) -> dict:
        account = await self.get_or_create_account(tenant_id=tenant_id)
        return {
            "availableInteger": str(int(account.available_integer)),
            "reservedInteger": str(int(account.reserved_integer)),
            "version": str(int(account.version)),
            "ledgerSource": "rp_credit_integer",
            "decimalBridge": False,
        }

    async def list_ledger(
        self, *, tenant_id: int, page: int = 1, page_size: int = 20
    ) -> tuple[list[RealphotosCreditLedgerEntry], int]:
        base = select(RealphotosCreditLedgerEntry).where(
            RealphotosCreditLedgerEntry.tenant_id == int(tenant_id),
            RealphotosCreditLedgerEntry.deleted_at.is_(None),
        )
        count_result = await self.db.execute(base)
        rows_all = list(count_result.scalars().all())
        total = len(rows_all)
        offset = max(page - 1, 0) * page_size
        page_rows = (
            await self.db.execute(
                base.order_by(RealphotosCreditLedgerEntry.id.desc())
                .offset(offset)
                .limit(page_size)
            )
        ).scalars().all()
        return list(page_rows), total

    async def admin_adjust(
        self,
        *,
        tenant_id: int,
        delta_available: int,
        operator_user_id: int,
        reason: str,
        event_key: str,
        target_user_id: int | None = None,
    ) -> dict:
        if not reason or not str(reason).strip():
            raise BusinessError(message="加减分必须填写原因", code="INPUT_INVALID")
        if not event_key or not str(event_key).strip():
            raise BusinessError(message="缺少幂等键", code="INPUT_INVALID")
        delta = int(delta_available)
        if delta == 0:
            raise BusinessError(message="调整额不能为 0", code="INPUT_INVALID")

        existing = await self.db.execute(
            select(RealphotosCreditLedgerEntry).where(
                RealphotosCreditLedgerEntry.tenant_id == int(tenant_id),
                RealphotosCreditLedgerEntry.event_key == str(event_key).strip(),
                RealphotosCreditLedgerEntry.deleted_at.is_(None),
            )
        )
        if existing.scalar_one_or_none() is not None:
            # 幂等重放：返回当前钱包快照
            return await self.get_wallet(tenant_id=tenant_id)

        account = await self.get_or_create_account(tenant_id=tenant_id)
        before_available = int(account.available_integer)
        before_reserved = int(account.reserved_integer)
        after_available = before_available + delta
        if after_available < 0 or before_reserved < 0:
            raise BusinessError(message="余额不足或非法", code="INSUFFICIENT_CREDITS")

        expected_version = int(account.version)
        account.available_integer = after_available
        account.version = expected_version + 1
        await self.db.flush()
        if int(account.version) != expected_version + 1:
            raise BusinessError(message="版本冲突", code="VERSION_CONFLICT")

        entry = RealphotosCreditLedgerEntry(
            tenant_id=int(tenant_id),
            event_key=str(event_key).strip(),
            entry_type=LEDGER_TYPE_ADMIN_ADJUST,
            delta_available=delta,
            delta_reserved=0,
            before_available=before_available,
            after_available=after_available,
            before_reserved=before_reserved,
            after_reserved=before_reserved,
            operator_user_id=int(operator_user_id),
            target_user_id=int(target_user_id) if target_user_id else None,
            reason=str(reason).strip(),
            reference={"source": "admin_adjust"},
        )
        self.db.add(entry)
        await self.db.flush()
        return await self.get_wallet(tenant_id=tenant_id)

    async def freeze(
        self,
        *,
        tenant_id: int,
        amount: int,
        operator_user_id: int,
        event_key: str,
        reference: dict | None = None,
    ) -> dict:
        return await self._move(
            tenant_id=tenant_id,
            delta_available=-int(amount),
            delta_reserved=int(amount),
            operator_user_id=operator_user_id,
            event_key=event_key,
            entry_type=LEDGER_TYPE_FREEZE,
            reference=reference,
            require_available=int(amount),
        )

    async def consume_available(
        self,
        *,
        tenant_id: int,
        amount: int,
        operator_user_id: int,
        event_key: str,
        reference: dict | None = None,
    ) -> dict:
        """生图成功入库后从可用余额扣减。不写预留，也不动 reserved。"""
        return await self._move(
            tenant_id=tenant_id,
            delta_available=-int(amount),
            delta_reserved=0,
            operator_user_id=operator_user_id,
            event_key=event_key,
            entry_type=LEDGER_TYPE_CONSUME,
            reference=reference,
            require_available=int(amount),
        )

    async def consume_reserved(
        self,
        *,
        tenant_id: int,
        amount: int,
        operator_user_id: int,
        event_key: str,
        reference: dict | None = None,
    ) -> dict:
        return await self._move(
            tenant_id=tenant_id,
            delta_available=0,
            delta_reserved=-int(amount),
            operator_user_id=operator_user_id,
            event_key=event_key,
            entry_type=LEDGER_TYPE_CONSUME,
            reference=reference,
            require_reserved=int(amount),
        )

    async def release_reserved(
        self,
        *,
        tenant_id: int,
        amount: int,
        operator_user_id: int,
        event_key: str,
        reference: dict | None = None,
    ) -> dict:
        return await self._move(
            tenant_id=tenant_id,
            delta_available=int(amount),
            delta_reserved=-int(amount),
            operator_user_id=operator_user_id,
            event_key=event_key,
            entry_type=LEDGER_TYPE_RELEASE,
            reference=reference,
            require_reserved=int(amount),
        )

    async def confirm_recharge(
        self,
        *,
        tenant_id: int,
        amount: int,
        operator_user_id: int,
        target_user_id: int,
        event_key: str,
        reference: dict | None = None,
    ) -> dict:
        return await self._move(
            tenant_id=tenant_id,
            delta_available=int(amount),
            delta_reserved=0,
            operator_user_id=operator_user_id,
            target_user_id=target_user_id,
            event_key=event_key,
            entry_type=LEDGER_TYPE_RECHARGE_CONFIRM,
            reference=reference,
        )

    async def _move(
        self,
        *,
        tenant_id: int,
        delta_available: int,
        delta_reserved: int,
        operator_user_id: int,
        event_key: str,
        entry_type: str,
        reference: dict | None = None,
        target_user_id: int | None = None,
        require_available: int = 0,
        require_reserved: int = 0,
    ) -> dict:
        key = str(event_key).strip()
        for _attempt in range(5):
            existing = await self.db.execute(
                select(RealphotosCreditLedgerEntry).where(
                    RealphotosCreditLedgerEntry.tenant_id == int(tenant_id),
                    RealphotosCreditLedgerEntry.event_key == key,
                    RealphotosCreditLedgerEntry.deleted_at.is_(None),
                )
            )
            if existing.scalar_one_or_none() is not None:
                return await self.get_wallet(tenant_id=tenant_id)
            account = await self.get_or_create_account(tenant_id=tenant_id)
            await self.db.refresh(account)
            before_available = int(account.available_integer)
            before_reserved = int(account.reserved_integer)
            if before_available < int(require_available) or before_reserved < int(require_reserved):
                raise BusinessError(message="余额或冻结额不足", code="INSUFFICIENT_CREDITS")
            after_available = before_available + int(delta_available)
            after_reserved = before_reserved + int(delta_reserved)
            if after_available < 0 or after_reserved < 0:
                raise BusinessError(message="余额或冻结额不足", code="INSUFFICIENT_CREDITS")
            expected = int(account.version)
            updated = await self.db.execute(
                update(RealphotosCreditAccount)
                .where(
                    RealphotosCreditAccount.id == int(account.id),
                    RealphotosCreditAccount.version == expected,
                )
                .values(
                    available_integer=after_available,
                    reserved_integer=after_reserved,
                    version=expected + 1,
                )
            )
            if int(getattr(updated, "rowcount", 0) or 0) != 1:
                self.db.expire(account)
                continue
            await self.db.refresh(account)
            self.db.add(
                RealphotosCreditLedgerEntry(
                    tenant_id=int(tenant_id),
                    event_key=key,
                    entry_type=entry_type,
                    delta_available=int(delta_available),
                    delta_reserved=int(delta_reserved),
                    before_available=before_available,
                    after_available=after_available,
                    before_reserved=before_reserved,
                    after_reserved=after_reserved,
                    operator_user_id=int(operator_user_id),
                    target_user_id=int(target_user_id) if target_user_id else None,
                    reason=entry_type,
                    reference=dict(reference or {}),
                )
            )
            await self.db.flush()
            return await self.get_wallet(tenant_id=tenant_id)
        raise BusinessError(message="积分版本冲突", code="VERSION_CONFLICT")

    async def require_account_for_tenant(self, *, tenant_id: int) -> RealphotosCreditAccount:
        result = await self.db.execute(
            select(RealphotosCreditAccount).where(
                RealphotosCreditAccount.tenant_id == int(tenant_id),
                RealphotosCreditAccount.deleted_at.is_(None),
            )
        )
        account = result.scalar_one_or_none()
        if account is None:
            raise NotFoundError(message="积分账户不存在")
        return account

    @staticmethod
    def reject_decimal_bridge() -> None:
        """显式拒绝旧 Decimal 入口接入 realphotos。"""
        raise BusinessError(
            message="旧 Decimal 积分入口对 realphotos 不可用",
            code="DECIMAL_BRIDGE_FORBIDDEN",
        )
