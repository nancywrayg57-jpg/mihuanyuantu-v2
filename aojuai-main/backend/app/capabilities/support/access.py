"""Declarative menu, button permissions, and default role grants.

三条链路（seed / 已有租户升级 / 运行时建租户）共用这一份声明 + 同一个 reconciler，
入口在 `seed.py`；能力包的表由包内独立迁移链建，菜单不写进迁移
（`scripts/capability db upgrade` 之后跑 `scripts/capability sync` 收敛）。

标题是中文原文；每个标题都必须在 `frontend/src/lib/i18n/locales/{en-US,es-ES}.ts`
里有 `menu.<标题原文>` 键，否则 GOV-19 变红、界面切到 en/es 会静默显示中文。
"""

from app.domain.menus.reconciler import (
    MenuDeclaration,
    MenuNodeSpec,
    RoleGrantSpec,
)

from .permissions import CREATE, MANAGE, READ

ACCESS = MenuDeclaration(
    roots=(
        MenuNodeSpec(
            key="support",
            title="工单中心",
            path="/support",
            menu_type="0",
            icon="ep:service",
            sort_order=95,
            always_show=True,
            children=(
                MenuNodeSpec(
                    key="support-tickets",
                    title="我的工单",
                    path="/support/tickets",
                    component="views/support/tickets/index",
                    icon="ep:tickets",
                    sort_order=1,
                    menu_type="1",
                    perms=READ,
                    children=(
                        MenuNodeSpec(
                            key="support-tickets-create",
                            title="提交工单",
                            menu_type="2",
                            perms=CREATE,
                            is_visible=False,
                        ),
                    ),
                ),
                MenuNodeSpec(
                    key="support-admin-tickets",
                    title="工单管理",
                    path="/support/admin/tickets",
                    component="views/support/admin/tickets/index",
                    icon="ep:chat-dot-round",
                    sort_order=2,
                    menu_type="1",
                    perms=MANAGE,
                    children=(
                        MenuNodeSpec(
                            key="support-admin-tickets-manage",
                            title="处理工单",
                            menu_type="2",
                            perms=MANAGE,
                            is_visible=False,
                        ),
                    ),
                ),
            ),
        ),
    ),
    roles=(
        RoleGrantSpec(code="admin", grant_all=True),
        RoleGrantSpec(code="tenant_admin", grant_all=True),
        # 普通用户只拿"提自己的工单"，拿不到客服台。
        # 只能点名角色码：自定义角色仍需在角色管理里手动授权。
        RoleGrantSpec(
            code="user",
            menu_keys=("support-tickets", "support-tickets-create"),
        ),
    ),
)

__all__ = ["ACCESS"]
