"""并发扣费不得丢失更新：各会话先加载过账户对象，再并发 consume，余额必须减去总和且流水前后余额链式一致。"""

from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import bindparam, text

from app.domain.credits.service import CreditService
from app.infrastructure.database import get_db_context

# 真库集成测试：断言的是真实 PostgreSQL 的行为，没有可连接的库时跳过（守卫见 tests/conftest.py）
pytestmark = pytest.mark.requires_database


@pytest.mark.asyncio
async def test_concurrent_consumes_do_not_lose_updates() -> None:
    async with get_db_context() as db:
        svc = CreditService(db)
        account = await svc.init_user_account(tenant_id=1, user_id=1)
        if Decimal(account.balance) < Decimal("10"):
            await svc.recharge(tenant_id=1, account_id=account.id, amount=Decimal("10"), operator_id=1)
        await db.commit()
        account_id = int(account.id)
        before = Decimal((await db.execute(text("select balance from credit_accounts where id=:a"), {"a": account_id})).scalar())

    run_id = uuid.uuid4().hex[:8]

    async def one(i: int) -> int:
        async with get_db_context() as session:
            svc2 = CreditService(session)
            await svc2.get_user_account(tenant_id=1, user_id=1)  # 先把账户对象加载进会话（复现丢失更新的前置条件）
            await asyncio.sleep(0.01 * i)
            tx = await svc2.consume(tenant_id=1, account_id=account_id, amount=Decimal("1"), reference_type="unit_concurrent", idempotency_key=f"unit-concurrent-{run_id}-{i}")
            await session.commit()
            return int(tx.id)

    ids = await asyncio.gather(*[one(i) for i in range(3)])
    try:
        async with get_db_context() as db:
            after = Decimal((await db.execute(text("select balance from credit_accounts where id=:a"), {"a": account_id})).scalar())
            rows = (await db.execute(text("select balance_before, balance_after from credit_transactions where id in :ids order by id").bindparams(bindparam("ids", expanding=True)), {"ids": list(ids)})).all()
        assert after == before - Decimal("3"), (before, after, rows)
        befores = sorted(Decimal(r[0]) for r in rows)
        assert len(set(befores)) == 3, rows  # 三笔的 balance_before 必须各不相同（串行化）
    finally:
        async with get_db_context() as db:
            svc = CreditService(db)
            for tx_id in ids:
                await svc.refund(tenant_id=1, transaction_id=tx_id, amount=Decimal("1"), idempotency_key=f"unit-concurrent-refund-{tx_id}", remark="unit cleanup")
            await db.commit()
