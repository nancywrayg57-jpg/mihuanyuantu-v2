---
title: Alembic 迁移模板（Schema + 数据迁移）
---

# Alembic 迁移模板（Schema + 数据迁移）

> 目的：提供一份可直接复制的 Alembic revision 模板，用于“表结构变更 + 必要的数据补齐”。
>
> 关键原则：**seed 只负责初始化**；后续分支的升级必须通过 **新增 Alembic revision** 完成。

## 1) 何时写“数据迁移”

当你做了以下类型变更，除了 schema migration，还需要 data migration：

- 新增菜单/按钮 perms（老租户也要看到）
- 新增默认配置/默认记录（老租户也要有合理默认值）
- 需要回填字段、补齐索引前的清洗、从旧字段迁移到新字段

反之，仅新装需要的数据，应该放在 `backend/scripts/seed_data.py` 或 `seed_<module>.py`，不要写进迁移里。

## 2) 创建 revision（推荐）

在 `backend/` 目录下执行：

```bash
alembic revision -m "add <module> schema and backfill"
```

如需 autogenerate（仍必须人工 review）：

```bash
alembic revision --autogenerate -m "add <module> schema and backfill"
```

## 3) 可复制模板：schema + 数据迁移（遍历租户、幂等、no-op）

将下面内容复制到新生成的 `backend/alembic/versions/<rev>_<slug>.py` 并替换占位符。

> 说明：
> - 迁移文件建议 **不用 ORM model**（避免未来模型变动导致历史迁移不可执行）
> - 数据迁移使用 `op.get_bind()` 获取 sync connection
> - 幂等策略：**先查再插** 或 `ON CONFLICT DO NOTHING`

```python
\"\"\"<TITLE>

Revision ID: <REVISION_ID>
Revises: <DOWN_REVISION>
Create Date: <YYYY-MM-DD>

\"\"\"

from __future__ import annotations

import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "<REVISION_ID>"
down_revision: Union[str, None] = "<DOWN_REVISION>"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _fetch_scalar(conn: sa.Connection, sql: str, params: dict[str, object] | None = None) -> object | None:
    result = conn.execute(sa.text(sql), params or {})
    return result.scalar_one_or_none()


def _fetch_all_scalars(conn: sa.Connection, sql: str, params: dict[str, object] | None = None) -> list[object]:
    result = conn.execute(sa.text(sql), params or {})
    return list(result.scalars().all())


def upgrade() -> None:
    # --------------------
    # 1) Schema migration（可选）
    # --------------------
    # op.add_column("xxx", sa.Column("new_col", sa.String(length=50), nullable=True))
    # op.create_index("ix_xxx_new_col", "xxx", ["new_col"], unique=False)

    # --------------------
    # 2) Data migration（可选）
    # --------------------
    conn = op.get_bind()

    tenant_ids = _fetch_all_scalars(
        conn,
        \"\"\"
        SELECT id
        FROM tenants
        WHERE deleted_at IS NULL
        ORDER BY id
        \"\"\",
    )
    if not tenant_ids:
        # 安全 no-op：新装环境可能尚未 seed 任何租户
        return

    for tenant_id in tenant_ids:
        # 示例：为每个租户补齐一条默认配置（幂等）
        # 你需要把 table/where 条件替换为真实业务
        existing_id = _fetch_scalar(
            conn,
            \"\"\"
            SELECT id
            FROM <TABLE_NAME>
            WHERE tenant_id = :tenant_id AND deleted_at IS NULL
            LIMIT 1
            \"\"\",
            {\"tenant_id\": tenant_id},
        )
        if existing_id:
            continue

        conn.execute(
            sa.text(
                \"\"\"
                INSERT INTO <TABLE_NAME> (tenant_id, <COL_A>, <COL_B>, extra)
                VALUES (:tenant_id, :col_a, :col_b, cast(:extra as jsonb))
                \"\"\"
            ),
            {
                \"tenant_id\": tenant_id,
                \"col_a\": \"<DEFAULT_A>\",
                \"col_b\": \"<DEFAULT_B>\",
                \"extra\": json.dumps({}),
            },
        )


def downgrade() -> None:
    # 优先保证 schema 可回滚；数据迁移通常 best-effort（按实际需要决定是否删除）
    # op.drop_index("ix_xxx_new_col", table_name="xxx")
    # op.drop_column("xxx", "new_col")
    pass
```

## 4) 可复制模板：菜单/权限数据迁移（三条链路中的“迁移侧”）

> 适用：新增页面菜单/按钮 perms，需要补齐到“已有租户”，并给 `admin` 角色默认授权。
>
> 注意：这只是三条链路里的一条；**seed 侧**与**建租户 reconciler 侧**都要同步
> （见 `docs/dev/templates/SEED_PATTERNS.md` 与 `docs/dev/flows/MENUS_PERMS_DUALWRITE.md`）。

```python
from __future__ import annotations

import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "<REVISION_ID>"
down_revision: Union[str, None] = "<DOWN_REVISION>"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _fetch_scalar(conn: sa.Connection, sql: str, params: dict[str, object] | None = None) -> object | None:
    return conn.execute(sa.text(sql), params or {}).scalar_one_or_none()


def _fetch_all_scalars(conn: sa.Connection, sql: str, params: dict[str, object] | None = None) -> list[object]:
    return list(conn.execute(sa.text(sql), params or {}).scalars().all())


def _ensure_menu(
    conn: sa.Connection,
    *,
    tenant_id: int,
    path: str | None,
    menu_type: str,
    title: str,
    parent_id: int | None,
    component: str | None = None,
    perms: str | None = None,
    level: int = 1,
    sort_order: int = 0,
    icon: str | None = None,
    meta: dict | None = None,
) -> int:
    # 幂等 key：对页面用 path，对按钮用 perms（当前 schema 未强制唯一约束，因此用“先查后插”）
    if menu_type == "2" and perms:
        existing_id = _fetch_scalar(
            conn,
            \"\"\"
            SELECT id FROM menus
            WHERE tenant_id = :tenant_id
              AND menu_type = '2'
              AND perms = :perms
              AND deleted_at IS NULL
            ORDER BY id
            LIMIT 1
            \"\"\",
            {\"tenant_id\": tenant_id, \"perms\": perms},
        )
    else:
        existing_id = _fetch_scalar(
            conn,
            \"\"\"
            SELECT id FROM menus
            WHERE tenant_id = :tenant_id
              AND path = :path
              AND menu_type = :menu_type
              AND deleted_at IS NULL
            ORDER BY id
            LIMIT 1
            \"\"\",
            {\"tenant_id\": tenant_id, \"path\": path, \"menu_type\": menu_type},
        )

    if existing_id:
        return int(existing_id)

    inserted_id = conn.execute(
        sa.text(
            \"\"\"
            INSERT INTO menus (
              tenant_id, title, path, component, parent_id, level, icon, sort_order,
              menu_type, perms,
              is_visible, is_cache, is_frame, is_active,
              no_cache, breadcrumb, affix, no_tags_view, can_to, always_show,
              meta
            )
            VALUES (
              :tenant_id, :title, :path, :component, :parent_id, :level, :icon, :sort_order,
              :menu_type, :perms,
              true, false, false, true,
              false, true, false, false, false, false,
              cast(:meta as jsonb)
            )
            RETURNING id
            \"\"\"
        ),
        {
            \"tenant_id\": tenant_id,
            \"title\": title,
            \"path\": path,
            \"component\": component,
            \"parent_id\": parent_id,
            \"level\": level,
            \"icon\": icon,
            \"sort_order\": sort_order,
            \"menu_type\": menu_type,
            \"perms\": perms,
            \"meta\": json.dumps(meta or {}),
        },
    ).scalar_one()

    return int(inserted_id)


def _grant_admin(conn: sa.Connection, *, tenant_id: int, menu_id: int) -> None:
    admin_role_id = _fetch_scalar(
        conn,
        \"\"\"
        SELECT id FROM roles
        WHERE tenant_id = :tenant_id
          AND code = 'admin'
          AND deleted_at IS NULL
        ORDER BY id
        LIMIT 1
        \"\"\",
        {\"tenant_id\": tenant_id},
    )
    if not admin_role_id:
        # 极端情况：租户没有 admin 角色（数据异常）；允许安全 no-op
        return

    # role_menus 主键为 (role_id, menu_id)，可直接 ON CONFLICT DO NOTHING
    conn.execute(
        sa.text(
            \"\"\"
            INSERT INTO role_menus (tenant_id, role_id, menu_id)
            VALUES (:tenant_id, :role_id, :menu_id)
            ON CONFLICT DO NOTHING
            \"\"\"
        ),
        {\"tenant_id\": tenant_id, \"role_id\": int(admin_role_id), \"menu_id\": menu_id},
    )


def upgrade() -> None:
    conn = op.get_bind()
    tenant_ids = _fetch_all_scalars(
        conn,
        \"\"\"
        SELECT id FROM tenants
        WHERE deleted_at IS NULL
        ORDER BY id
        \"\"\",
    )
    if not tenant_ids:
        return

    for tenant_id in tenant_ids:
        tenant_id = int(tenant_id)

        # 1) 确保 /system 父菜单存在（若不存在，可选择创建或跳过）
        system_id = _fetch_scalar(
            conn,
            \"\"\"
            SELECT id FROM menus
            WHERE tenant_id = :tenant_id
              AND path = '/system'
              AND menu_type = '0'
              AND deleted_at IS NULL
            ORDER BY id
            LIMIT 1
            \"\"\",
            {\"tenant_id\": tenant_id},
        )
        if not system_id:
            # 这里选择 no-op：不强行修复历史数据；你也可以改为 _ensure_menu 创建父菜单
            continue

        system_id = int(system_id)

        # 2) 新增“模块设置入口”（租户级配置统一放 /system/<module>-settings）
        settings_menu_id = _ensure_menu(
            conn,
            tenant_id=tenant_id,
            parent_id=system_id,
            level=2,
            sort_order=99,
            menu_type="1",
            title="<模块设置>",
            path="/system/<module>-settings",
            component="views/system/<module>-settings/index",
            perms=None,
            icon="ep:setting",
            meta={},
        )
        _grant_admin(conn, tenant_id=tenant_id, menu_id=settings_menu_id)

        # 3) （可选）新增按钮 perms（menu_type=2）
        btn_id = _ensure_menu(
            conn,
            tenant_id=tenant_id,
            parent_id=settings_menu_id,
            level=3,
            sort_order=1,
            menu_type="2",
            title="保存设置",
            path=None,
            component=None,
            perms="<module_settings:update>",
            meta={\"title\": \"保存设置\"},
        )
        _grant_admin(conn, tenant_id=tenant_id, menu_id=btn_id)


def downgrade() -> None:
    # 数据迁移的回滚通常 best-effort；按需实现删除（注意不要误删用户自定义菜单）
    pass
```

## 5) 关联规范

- 菜单/权限双写流程：`docs/dev/flows/MENUS_PERMS_DUALWRITE.md`
- 菜单/权限落地指南：`docs/dev/guide_docs/MENU_SEED_MIGRATION_GUIDE.md`
- Seed 增量脚本模式：`docs/dev/templates/SEED_PATTERNS.md`

