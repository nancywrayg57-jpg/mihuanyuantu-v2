"""计价模式：解析缺省 legacy、非法值拒绝、租户读写；迁移契约：存量租户回填 legacy、按钮权限与授权存在。"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.domain.credits.pricing_mode import (
    get_tenant_pricing_mode,
    normalize_pricing_mode,
    resolve_pricing_mode,
    set_tenant_pricing_mode,
)
from app.infrastructure.database import get_db_context


def test_resolve_defaults_to_legacy_and_accepts_known_modes() -> None:
    assert resolve_pricing_mode(None) == "legacy"
    assert resolve_pricing_mode({}) == "legacy"
    assert resolve_pricing_mode({"credits": {"pricingMode": "bogus"}}) == "legacy"
    assert resolve_pricing_mode({"credits": {"pricingMode": "Shadow"}}) == "shadow"
    assert resolve_pricing_mode({"credits": {"pricingMode": "unified"}}) == "unified"
    assert normalize_pricing_mode(" UNIFIED ") == "unified"
    from app.core.exceptions import BusinessError

    with pytest.raises(BusinessError):
        normalize_pricing_mode("turbo")


@pytest.mark.skipif(__import__("app.core.config", fromlist=["settings"]).settings.IS_SQLITE, reason="迁移契约/回填校验依赖 PostgreSQL information_schema 与迁移链，SQLite 档由 create_all 建表")
@pytest.mark.requires_database  # 真库集成测试，没有可连接的库时跳过（守卫见 tests/conftest.py）
@pytest.mark.asyncio
async def test_tenant_mode_roundtrip_and_migration_backfill() -> None:
    async with get_db_context() as db:
        try:
            # 迁移回填：存量租户 config.credits.pricingMode 显式为 legacy（除非已被改过）
            rows = (await db.execute(text("select id, config->'credits'->>'pricingMode' from tenants where deleted_at is null"))).all()
            assert rows and all(mode in {"legacy", "shadow", "unified"} for _, mode in rows)
            tenant_id = int(rows[0][0])
            before = await get_tenant_pricing_mode(db, tenant_id=tenant_id)
            assert await set_tenant_pricing_mode(db, tenant_id=tenant_id, mode="shadow") == "shadow"
            assert await get_tenant_pricing_mode(db, tenant_id=tenant_id) == "shadow"
            stamp = (await db.execute(text("select config->'credits'->>'pricingModeUpdatedAt' from tenants where id=:t"), {"t": tenant_id})).scalar()
            assert stamp
            await set_tenant_pricing_mode(db, tenant_id=tenant_id, mode=before)
        finally:
            await db.rollback()


@pytest.mark.requires_database  # 真库集成测试，没有可连接的库时跳过（守卫见 tests/conftest.py）
@pytest.mark.asyncio
async def test_pricing_permission_button_exists_and_granted_to_admins() -> None:
    async with get_db_context() as db:
        buttons = (await db.execute(text(
            "select b.tenant_id, b.id from menus b join menus p on p.id = b.parent_id "
            "where b.deleted_at is null and b.menu_type = '2' and b.perms = 'credits:pricing:update' and p.path = '/system/credits'"
        ))).all()
        tenants = {int(r[0]) for r in (await db.execute(text("select id from tenants where deleted_at is null"))).all()}
        assert tenants and {int(t) for t, _ in buttons} >= tenants  # 每个租户都有该按钮
        granted = (await db.execute(text(
            "select r.code from role_menus rm join roles r on r.id = rm.role_id join menus b on b.id = rm.menu_id "
            "where b.perms = 'credits:pricing:update' and b.menu_type = '2' and r.deleted_at is null"
        ))).all()
        assert {"admin", "tenant_admin"} <= {str(c[0]) for c in granted}
