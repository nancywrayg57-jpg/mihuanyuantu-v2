"""Ensure PRODUCT-GAP-A columns exist on development PostgreSQL."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

ALTERS = (
    "ALTER TABLE cap_realphotos_device_presets ADD COLUMN IF NOT EXISTS ai_positive_prompt TEXT DEFAULT ''",
    "ALTER TABLE cap_realphotos_device_presets ADD COLUMN IF NOT EXISTS ai_negative_prompt TEXT DEFAULT ''",
    "ALTER TABLE cap_realphotos_device_presets ADD COLUMN IF NOT EXISTS maker_note TEXT DEFAULT ''",
    "ALTER TABLE cap_realphotos_device_presets ADD COLUMN IF NOT EXISTS legacy_source_id VARCHAR(64) DEFAULT ''",
    "ALTER TABLE cap_realphotos_device_presets ADD COLUMN IF NOT EXISTS legacy_template_ref VARCHAR(120) DEFAULT ''",
    "ALTER TABLE cap_realphotos_device_presets ADD COLUMN IF NOT EXISTS legacy_visibility VARCHAR(32) DEFAULT ''",
    "ALTER TABLE cap_realphotos_device_presets ADD COLUMN IF NOT EXISTS legacy_review_bucket VARCHAR(64) DEFAULT ''",
)


async def ensure_product_gap_a_schema(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        if conn.dialect.name != "postgresql":
            return
        for statement in ALTERS:
            await conn.execute(text(statement))
