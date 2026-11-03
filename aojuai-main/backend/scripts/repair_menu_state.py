"""Explicitly repair declared CMS menus, permissions, and role grants."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import text

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.domain.cms.access import CMS_MENU_DECLARATION  # noqa: E402
from app.domain.menus.reconciler import reconcile_menu_declaration  # noqa: E402
from app.infrastructure.database import get_db_context  # noqa: E402


async def repair(*, tenant_id: int | None = None) -> int:
    async with get_db_context() as db:
        if tenant_id is None:
            result = await db.execute(
                text("SELECT id FROM tenants WHERE deleted_at IS NULL ORDER BY id")
            )
        else:
            result = await db.execute(
                text("SELECT id FROM tenants WHERE deleted_at IS NULL AND id = :tenant_id ORDER BY id"),
                {"tenant_id": tenant_id},
            )
        tenant_ids = [int(value) for value in result.scalars().all()]
        changed = 0
        for current_tenant_id in tenant_ids:
            outcome = await reconcile_menu_declaration(
                db,
                tenant_id=current_tenant_id,
                declaration=CMS_MENU_DECLARATION,
            )
            changed += int(outcome.changed)
            print(
                f"tenant={current_tenant_id}: created_menus={outcome.created_menus}, "
                f"updated_menus={outcome.updated_menus}, merged_menus={outcome.merged_menus}, "
                f"created_roles={outcome.created_roles}, added_grants={outcome.added_grants}"
            )
        print(f"repair complete: tenants={len(tenant_ids)}, changed_tenants={changed}")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-id", type=int, help="repair one tenant instead of all active tenants")
    args = parser.parse_args()
    return asyncio.run(repair(tenant_id=args.tenant_id))


if __name__ == "__main__":
    raise SystemExit(main())
