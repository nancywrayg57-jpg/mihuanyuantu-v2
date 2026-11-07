"""Ensure BROWSER-E2E-FIX columns exist on development PostgreSQL."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

STATEMENTS = (
    "ALTER TABLE cap_realphotos_support_tickets ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMPTZ",
    "ALTER TABLE cap_realphotos_support_tickets ADD COLUMN IF NOT EXISTS resolved_by_user_id BIGINT",
    "ALTER TABLE cap_realphotos_support_tickets ADD COLUMN IF NOT EXISTS resolution_note TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE cap_realphotos_support_tickets ADD COLUMN IF NOT EXISTS resolution_outcome VARCHAR(32) NOT NULL DEFAULT ''",
)


async def ensure_browser_e2e_fix_schema(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        for stmt in STATEMENTS:
            await conn.execute(text(stmt))
