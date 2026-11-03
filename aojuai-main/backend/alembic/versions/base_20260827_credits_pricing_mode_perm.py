"""积分计价模式回填（存量租户显式 legacy）+ 按钮权限 credits:pricing:update（存量租户补齐）

Revision ID: base_20260827_credits_pricing_mode_perm
Revises: base_20260827_credit_price_items
Create Date: 2026-08-26

方案：devdocs/plans/UNIFIED_CREDIT_PRICING_PLAN_20260826.md §4.4 / P1-2 / P1-4。
- `tenants.config.credits.pricingMode`：缺失的一律写 `legacy`（代码缺省也是 legacy，
  回填是为了让"当前是什么模式"在数据里可见、可审计，不靠隐式）。已有值不动。
- `/system/credits` 页面下新增按钮权限 `credits:pricing:update`（配置计费模式与费率），
  授权 admin / tenant_admin；seed 与建租户链路由 app/core/system_menus.py 的声明覆盖，
  本迁移只负责存量租户。幂等：已存在的不重复插入。
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import bindparam, text

revision: str = "base_20260827_credits_pricing_mode_perm"
down_revision: str | Sequence[str] | None = "base_20260827_credit_price_items"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PAGE_PATH = "/system/credits"
BUTTON_PERMS = "credits:pricing:update"
BUTTON_TITLE = "配置计费模式与费率"
BUTTON_SORT_ORDER = 5
GRANT_ROLE_CODES = ("admin", "tenant_admin")


def upgrade() -> None:
    conn = op.get_bind()
    # 1) 计价模式回填：缺失才写 legacy
    is_sqlite = conn.dialect.name == "sqlite"
    if is_sqlite:
        conn.execute(
            text(
                """
                UPDATE tenants
                SET config = json_set(COALESCE(config, '{}'), '$.credits.pricingMode', 'legacy')
                WHERE deleted_at IS NULL
                  AND json_extract(config, '$.credits.pricingMode') IS NULL
                """
            )
        )
    else:
        conn.execute(
            text(
                """
                UPDATE tenants
                SET config = jsonb_set(
                    COALESCE(config, '{}'::jsonb),
                    '{credits}',
                    COALESCE(config->'credits', '{}'::jsonb) || '{"pricingMode": "legacy"}'::jsonb,
                    true
                )
                WHERE deleted_at IS NULL
                  AND (config->'credits'->>'pricingMode') IS NULL
                """
            )
        )
    # 2) 按钮权限（挂在 /system/credits 页面下）
    conn.execute(
        text(
            """
            WITH pages AS (
              SELECT id, tenant_id FROM menus
              WHERE deleted_at IS NULL AND path = :page AND menu_type = '1'
            )
            INSERT INTO menus (
              tenant_id, title, parent_id, level, sort_order, menu_type,
              perms, is_visible, is_cache, is_frame, is_active, no_cache,
              breadcrumb, affix, no_tags_view, can_to, always_show, meta
            )
            SELECT
              p.tenant_id, :title, p.id, 3, :sort_order, '2',
              :perms, true, false, false, true, false,
              true, false, false, false, false, '{"title": "配置计费模式与费率"}'{cast}
            FROM pages p
            WHERE NOT EXISTS (
              SELECT 1 FROM menus b
              WHERE b.tenant_id = p.tenant_id AND b.deleted_at IS NULL
                AND b.parent_id = p.id AND b.perms = :perms AND b.menu_type = '2'
            )
            """
        .replace("{cast}", "" if is_sqlite else "::jsonb")
        ),
        {"page": PAGE_PATH, "title": BUTTON_TITLE, "sort_order": BUTTON_SORT_ORDER, "perms": BUTTON_PERMS},
    )
    # 3) 授权 admin / tenant_admin
    conn.execute(
        text(
            """
            WITH buttons AS (
              SELECT b.id, b.tenant_id
              FROM menus b
              JOIN menus page ON page.tenant_id = b.tenant_id
                              AND page.path = :page AND page.menu_type = '1'
                              AND page.deleted_at IS NULL
              WHERE b.deleted_at IS NULL AND b.parent_id = page.id
                AND b.perms = :perms AND b.menu_type = '2'
            )
            INSERT INTO role_menus (tenant_id, role_id, menu_id)
            SELECT r.tenant_id, r.id, bt.id
            FROM roles r
            JOIN buttons bt ON bt.tenant_id = r.tenant_id
            WHERE r.deleted_at IS NULL AND r.is_active IS TRUE
              AND r.code IN :roles
              AND NOT EXISTS (
                SELECT 1 FROM role_menus x WHERE x.role_id = r.id AND x.menu_id = bt.id
              )
            """
        ).bindparams(bindparam("roles", expanding=True)),
        {"page": PAGE_PATH, "perms": BUTTON_PERMS, "roles": list(GRANT_ROLE_CODES)},
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text(
            """
            DELETE FROM role_menus rm
            USING menus b
            WHERE rm.menu_id = b.id AND b.perms = :perms AND b.menu_type = '2'
            """
        ),
        {"perms": BUTTON_PERMS},
    )
    conn.execute(text("DELETE FROM menus WHERE perms = :perms AND menu_type = '2'"), {"perms": BUTTON_PERMS})
    # pricingMode 回填不回滚：legacy 与"缺失"语义一致，留着无害且可审计
