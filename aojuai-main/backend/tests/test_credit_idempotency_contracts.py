from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.dialects import postgresql

from app.domain.credits.billing import charge_user_credits
from app.domain.credits.models import CreditTransaction
from app.domain.credits.service import CreditService


class _DummyResult:
    def __init__(self, *, scalar_value: object | None = None, scalar: object | None = None) -> None:
        self._scalar_value = scalar_value
        self._scalar = scalar

    def scalar_one_or_none(self) -> object | None:
        return self._scalar_value

    def scalar(self) -> object | None:
        return self._scalar


class _RecordingSession:
    def __init__(self, results: list[_DummyResult]) -> None:
        self._results = list(results)
        self.statements: list[object] = []

    async def execute(self, statement):  # noqa: ANN001
        if "alembic_version" in str(statement):
            # SQLite 档 escalate_to_write_lock() 的无副作用写语句，不属于本合同关心的查询序列
            return None
        self.statements.append(statement)
        if not self._results:
            raise AssertionError("unexpected execute() call without prepared result")
        return self._results.pop(0)


def _compiled_sql(statement: object) -> str:
    return str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


def _index_map(model: object) -> dict[str, object]:
    table = model.__table__  # type: ignore[attr-defined]
    return {index.name: index for index in table.indexes}


def test_credit_transaction_model_declares_tenant_scoped_idempotency_index() -> None:
    indexes = _index_map(CreditTransaction)

    unique_index = indexes["uq_credit_transactions_tenant_idempotency_key"]
    assert unique_index.unique is True
    assert [str(expr) for expr in unique_index.expressions] == [
        "credit_transactions.tenant_id",
        "credit_transactions.idempotency_key",
    ]
    assert str(unique_index.dialect_options["postgresql"]["where"]) == (
        "deleted_at IS NULL AND idempotency_key IS NOT NULL"
    )
    assert "idempotency_key" in CreditTransaction.__table__.c


@pytest.mark.asyncio
async def test_credit_consume_returns_existing_transaction_for_same_idempotency_key() -> None:
    existing = SimpleNamespace(
        id=91,
        account_id=15,
        amount=Decimal("2.00"),
        reference_type="assistant_chat",
        reference_id=3001,
        transaction_type="consume",
        direction="out",
    )
    session = _RecordingSession([_DummyResult(scalar_value=existing)])
    service = CreditService(session)  # type: ignore[arg-type]
    service._get_account_for_update = AsyncMock(side_effect=AssertionError("should not lock account again"))  # type: ignore[method-assign]
    service._apply_transaction = AsyncMock(side_effect=AssertionError("should not create a new transaction"))  # type: ignore[method-assign]

    result = await service.consume(
        tenant_id=7,
        account_id=15,
        amount=Decimal("2.00"),
        reference_type="assistant_chat",
        reference_id=3001,
        idempotency_key="assistant_chat:3001",
    )

    assert result is existing
    sql = _compiled_sql(session.statements[0])
    assert "credit_transactions.tenant_id = 7" in sql
    assert "credit_transactions.idempotency_key = 'assistant_chat:3001'" in sql


@pytest.mark.asyncio
async def test_charge_user_credits_passes_idempotency_key_through_to_credit_service() -> None:
    credit_service = SimpleNamespace(
        get_account_by_id=AsyncMock(return_value=SimpleNamespace(id=12)),
        consume=AsyncMock(return_value=SimpleNamespace(id=44, account_id=12, amount=Decimal("3"), extra={})),
    )

    result = await charge_user_credits(
        credit_service=credit_service,  # type: ignore[arg-type]
        tenant_id=5,
        user_id=21,
        account_id=12,
        amount=Decimal("3"),
        reference_type="agents_chat",
        reference_id=88,
        idempotency_key="agents_chat:88",
        remark="应用调用消耗",
    )

    credit_service.consume.assert_awaited_once()
    kwargs = credit_service.consume.await_args.kwargs
    assert kwargs["idempotency_key"] == "agents_chat:88"
    assert kwargs["reference_id"] == 88
    assert result.transaction_id == 44


@pytest.mark.asyncio
async def test_credit_refund_returns_existing_transaction_for_same_idempotency_key() -> None:
    original = SimpleNamespace(
        id=101,
        account_id=15,
        amount=Decimal("2.00"),
        reference_type="aippt_image",
        reference_id=3001,
        transaction_type="consume",
        direction="out",
    )
    existing_refund = SimpleNamespace(
        id=102,
        amount=Decimal("2.00"),
        reference_type="aippt_image",
        reference_id=3001,
        transaction_type="refund",
        direction="in",
        extra={"original_transaction_id": 101},
    )
    service = CreditService(object())  # type: ignore[arg-type]
    service.get_transaction_by_id = AsyncMock(return_value=original)  # type: ignore[method-assign]
    service.get_transaction_by_idempotency_key = AsyncMock(return_value=existing_refund)  # type: ignore[method-assign]
    service._get_account_for_update = AsyncMock(side_effect=AssertionError("should not lock account again"))  # type: ignore[method-assign]
    service._apply_transaction = AsyncMock(side_effect=AssertionError("should not create a new refund"))  # type: ignore[method-assign]

    result = await service.refund(
        tenant_id=7,
        transaction_id=101,
        amount=Decimal("2.00"),
        idempotency_key="aippt:image:generate:batch_item:99:refund",
    )

    assert result is existing_refund
