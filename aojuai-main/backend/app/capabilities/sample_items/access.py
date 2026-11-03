"""Declarative menu, button permissions, and default role grants."""

from app.domain.menus.reconciler import (
    MenuDeclaration,
    MenuNodeSpec,
    RoleDefaults,
    RoleGrantSpec,
)

from .permissions import CREATE, DELETE, READ, UPDATE

ACCESS = MenuDeclaration(
    roots=(
        MenuNodeSpec(
            key="sample-items",
            title="样例条目",
            path="/sample-items",
            component="views/sample-items/index",
            icon="ep:collection",
            sort_order=90,
            menu_type="1",
            perms=READ,
            children=(
                MenuNodeSpec(
                    key="sample-items-create",
                    title="新建样例条目",
                    menu_type="2",
                    perms=CREATE,
                    is_visible=False,
                ),
                MenuNodeSpec(
                    key="sample-items-update",
                    title="编辑样例条目",
                    menu_type="2",
                    perms=UPDATE,
                    is_visible=False,
                ),
                MenuNodeSpec(
                    key="sample-items-delete",
                    title="删除样例条目",
                    menu_type="2",
                    perms=DELETE,
                    is_visible=False,
                ),
            ),
        ),
    ),
    roles=(
        RoleGrantSpec(code="admin", grant_all=True),
        RoleGrantSpec(code="tenant_admin", grant_all=True),
        RoleGrantSpec(
            code="sample_operator",
            menu_keys=(
                "sample-items",
                "sample-items-create",
                "sample-items-update",
            ),
            create=RoleDefaults(
                name="样例操作员",
                description="可查看、新建和编辑样例条目，不可删除",
                sort_order=90,
            ),
        ),
    ),
)

__all__ = ["ACCESS"]
