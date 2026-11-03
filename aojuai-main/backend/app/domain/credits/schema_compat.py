"""
Best-effort schema compatibility repairs for credits.

Why:
- Some deployed environments restart with newer code but older PostgreSQL schema.
- The `credit_transactions.idempotency_key` column is nullable and safe to add
  in place, so we can repair it automatically at startup.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.portable_sql import column_exists as portable_column_exists
from app.infrastructure.database.portable_sql import index_exists as portable_index_exists
from app.infrastructure.database.portable_sql import table_exists as portable_table_exists


async def ensure_credit_transaction_idempotency_schema(db: AsyncSession) -> dict[str, Any]:
    table_exists = await portable_table_exists(db, "credit_transactions")

    result = {
        "table_exists": table_exists,
        "column_added": False,
        "index_added": False,
    }
    if not table_exists:
        return result

    column_exists = await portable_column_exists(db, "credit_transactions", "idempotency_key")
    if not column_exists:
        await db.execute(
            text(
                """
                ALTER TABLE credit_transactions
                ADD COLUMN idempotency_key VARCHAR(120)
                """
            )
        )
        result["column_added"] = True

    index_exists = await portable_index_exists(
        db,
        "credit_transactions",
        "uq_credit_transactions_tenant_idempotency_key",
    )
    if not index_exists:
        await db.execute(
            text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_credit_transactions_tenant_idempotency_key
                ON credit_transactions (tenant_id, idempotency_key)
                WHERE deleted_at IS NULL AND idempotency_key IS NOT NULL
                """
            )
        )
        result["index_added"] = True

    return result
