"""Read-only checker for declared CMS menu and role-grant state."""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter
from pathlib import Path

from sqlalchemy import text

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.domain.cms.access import CMS_MENU_DECLARATION  # noqa: E402
from app.domain.menus.reconciler import (  # noqa: E402
    SQLAlchemyMenuStateStore,
    inspect_menu_declaration,
)
from app.infrastructure.database import get_db_context  # noqa: E402

ISSUE_LABELS = {
    "duplicate_menu": "重复菜单",
    "missing_grant": "缺失授权",
    "parent_closure": "父级闭包断层",
    "drift": "与声明终态漂移",
}


async def check(*, tenant_id: int | None = None) -> int:
    async with get_db_context() as db:
        if tenant_id is None:
            tenant_result = await db.execute(
                text("SELECT id FROM tenants WHERE deleted_at IS NULL ORDER BY id")
            )
        else:
            tenant_result = await db.execute(
                text("SELECT id FROM tenants WHERE deleted_at IS NULL AND id = :tenant_id ORDER BY id"),
                {"tenant_id": tenant_id},
            )
        tenant_ids = [int(value) for value in tenant_result.scalars().all()]
        store = SQLAlchemyMenuStateStore(db)
        issues = []
        for current_tenant_id in tenant_ids:
            state = await store.load_state(current_tenant_id)
            issues.extend(
                inspect_menu_declaration(
                    state,
                    tenant_id=current_tenant_id,
                    declaration=CMS_MENU_DECLARATION,
                )
            )

        for issue in issues:
            print(f"[{ISSUE_LABELS[issue.kind]}] tenant={issue.tenant_id}: {issue.detail}")
        counts = Counter(issue.kind for issue in issues)
        summary = ", ".join(f"{label}={counts.get(kind, 0)}" for kind, label in ISSUE_LABELS.items())
        print(f"checked tenants={len(tenant_ids)}; {summary}")
        return 1 if issues else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-id", type=int, help="check one tenant instead of all active tenants")
    args = parser.parse_args()
    return asyncio.run(check(tenant_id=args.tenant_id))


if __name__ == "__main__":
    raise SystemExit(main())
