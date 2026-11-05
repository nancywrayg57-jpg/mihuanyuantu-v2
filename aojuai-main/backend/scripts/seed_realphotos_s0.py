#!/usr/bin/env python3
"""Bootstrap S0 acceptance accounts for realphotos (idempotent).

用法（在 backend 目录）:
  AOJ_ENABLED_MODULES=realphotos .venv/bin/python -m scripts.seed_realphotos_s0
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


async def main() -> int:
    from app.capabilities.realphotos.seed import sync as sync_menus
    from app.capabilities.realphotos.services.bootstrap import (
        DEFAULT_PASSWORD,
        bootstrap_s0_accounts,
    )
    from app.infrastructure.database.session import async_session_factory

    async with async_session_factory() as db:
        summary = await bootstrap_s0_accounts(db)
        await sync_menus(db)
        await db.commit()

    print("S0 accounts ready (password shared):", DEFAULT_PASSWORD)
    for username, meta in summary.items():
        print(f"  {username}: tenant={meta['tenantId']} role={meta['roleCode']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
