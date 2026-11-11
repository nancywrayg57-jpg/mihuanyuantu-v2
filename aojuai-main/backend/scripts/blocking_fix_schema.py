"""DEPRECATED compatibility helper for older e2e scripts.

Prefer ``alembic upgrade head`` on the realphotos chain
(``realphotos_0004+``). Do not treat this module as the schema source of truth.
Does not create or write ``copy_latch_*`` (AD-005 residual retired to guard table).
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

ALTERS = (
    "ALTER TABLE cap_realphotos_assets ADD COLUMN IF NOT EXISTS meta_name VARCHAR(255)",
    "ALTER TABLE cap_realphotos_assets ADD COLUMN IF NOT EXISTS meta_seller VARCHAR(255)",
    "ALTER TABLE cap_realphotos_assets ADD COLUMN IF NOT EXISTS meta_sku VARCHAR(128)",
    "ALTER TABLE cap_realphotos_assets ADD COLUMN IF NOT EXISTS meta_asn VARCHAR(128)",
    "ALTER TABLE cap_realphotos_assets ADD COLUMN IF NOT EXISTS meta_price VARCHAR(64)",
    "ALTER TABLE cap_realphotos_assets ADD COLUMN IF NOT EXISTS meta_website VARCHAR(255)",
    "ALTER TABLE cap_realphotos_assets ADD COLUMN IF NOT EXISTS meta_url VARCHAR(512)",
    "ALTER TABLE cap_realphotos_assets ADD COLUMN IF NOT EXISTS requested_width INTEGER",
    "ALTER TABLE cap_realphotos_assets ADD COLUMN IF NOT EXISTS requested_height INTEGER",
    "ALTER TABLE cap_realphotos_image_tasks ADD COLUMN IF NOT EXISTS copied_from_task_id BIGINT",
    "ALTER TABLE cap_realphotos_image_tasks ADD COLUMN IF NOT EXISTS billing_mode VARCHAR(32) DEFAULT 'normal'",
    "ALTER TABLE cap_realphotos_generation_tasks ADD COLUMN IF NOT EXISTS requested_seed VARCHAR(64)",
    "ALTER TABLE cap_realphotos_generation_tasks ADD COLUMN IF NOT EXISTS supplier_trace JSONB DEFAULT '{}'::jsonb",
    "ALTER TABLE cap_realphotos_generation_items ADD COLUMN IF NOT EXISTS actual_width INTEGER",
    "ALTER TABLE cap_realphotos_generation_items ADD COLUMN IF NOT EXISTS actual_height INTEGER",
    "ALTER TABLE cap_realphotos_detection_results ALTER COLUMN detector TYPE VARCHAR(128)",
)


async def ensure_blocking_fix_schema(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        dialect = conn.dialect.name
        if dialect != "postgresql":
            return
        for statement in ALTERS:
            await conn.execute(text(statement))
