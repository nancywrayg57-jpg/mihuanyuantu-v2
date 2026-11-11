"""Ensure PRODUCT-GAP-FIX outbox delivery columns on development PostgreSQL / SQLite."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

PG_ALTERS = (
    "ALTER TABLE cap_realphotos_outbox ADD COLUMN IF NOT EXISTS recipient_user_id BIGINT",
    "ALTER TABLE cap_realphotos_outbox ADD COLUMN IF NOT EXISTS attempt_count INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE cap_realphotos_outbox ADD COLUMN IF NOT EXISTS next_attempt_at TIMESTAMPTZ",
    "ALTER TABLE cap_realphotos_outbox ADD COLUMN IF NOT EXISTS last_error TEXT",
)


async def ensure_product_gap_fix_schema(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        dialect = conn.dialect.name
        if dialect == "postgresql":
            for statement in PG_ALTERS:
                await conn.execute(text(statement))
            return
        # SQLite：无 IF NOT EXISTS；列已存在则忽略
        for name, ddl in (
            ("recipient_user_id", "ALTER TABLE cap_realphotos_outbox ADD COLUMN recipient_user_id INTEGER"),
            ("attempt_count", "ALTER TABLE cap_realphotos_outbox ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0"),
            ("next_attempt_at", "ALTER TABLE cap_realphotos_outbox ADD COLUMN next_attempt_at DATETIME"),
            ("last_error", "ALTER TABLE cap_realphotos_outbox ADD COLUMN last_error TEXT"),
        ):
            exists = await conn.execute(text(f"PRAGMA table_info(cap_realphotos_outbox)"))
            cols = {str(row[1]) for row in exists.fetchall()}
            if name in cols:
                continue
            await conn.execute(text(ddl))
