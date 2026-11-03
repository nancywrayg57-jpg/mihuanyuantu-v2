"""Service 层的基座约定：租户过滤在本层、软删除过滤在基类，两者都不能丢。"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from app.capabilities.support import service as service_module
from app.capabilities.support.service import SupportService
from app.infrastructure.repository import RepositoryBase

SERVICE_PATH = Path(inspect.getsourcefile(service_module))

#: 不需要 tenant 条件的内部方法（要么没查库，要么参数里根本没有 tenant）。
TENANT_FREE_METHODS = {
    "options",
    "sla_fields",
    "ticket_payload",
    "_apply_status",
    "_refresh_for_response",
    "user_briefs",
    "__init__",
}


def test_service_inherits_the_base_repository() -> None:
    """软删除过滤、分页与计数都在基类里；不继承就等于自己重写一套。"""
    assert issubclass(SupportService, RepositoryBase)


def test_every_tenant_scoped_method_filters_by_tenant() -> None:
    """租户过滤必须显式写在每个方法里：基类不知道"当前租户是谁"。"""
    tree = ast.parse(SERVICE_PATH.read_text(encoding="utf-8"), filename=str(SERVICE_PATH))
    service_node = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == "SupportService"
    )
    missing: list[str] = []
    for node in service_node.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name in TENANT_FREE_METHODS:
            continue
        argument_names = {
            argument.arg for argument in node.args.args + node.args.kwonlyargs
        }
        if "tenant_id" not in argument_names:
            missing.append(f"{node.name}: 没有 tenant_id 参数")
            continue
        if "tenant_id" not in ast.unparse(node):
            missing.append(f"{node.name}: 参数拿到了却没用在查询里")
    assert not missing, missing


# 这里**故意不写**"源码里出现过 `SupportTicket.tenant_id == tenant_id`"这类断言：
# 变异验证时它是绿的——把某一处 where 清空，别处还留着同样的字面量，扫描器就瞎了。
# 真正挡住这条的是 test_support_tenant_isolation.py 里跑真 SQL 的用例
# （同一处变异会让它红两条）。静态检查只保留上面那条"方法必须拿到并用上 tenant_id"。


@pytest.mark.parametrize(
    "method",
    ["list_tickets", "get_ticket", "summary", "create_ticket", "update_ticket"],
)
def test_public_methods_are_keyword_only(method: str) -> None:
    """位置参数会让 `service.get_ticket(ticket_id, tenant_id)` 这种顺序写反
    在类型检查里也看不出来——租户参数写反就是跨租户读。"""
    signature = inspect.signature(getattr(SupportService, method))
    positional = [
        name for name, parameter in signature.parameters.items()
        if parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD and name != "self"
    ]
    assert positional == []


def test_notification_failures_never_break_the_ticket_write() -> None:
    """站内通知是尽力而为的副作用：投递失败不能把工单写入一起拖挂。"""
    source = inspect.getsource(SupportService._notify_users)
    assert "try:" in source and "except Exception" in source

@pytest.mark.asyncio
async def test_manager_notifications_skip_disabled_users_and_roles(db) -> None:
    """停用的账号登不进来读工单，停用的角色也不再授予这个按钮。

    收件人是按「谁的角色带 support:manage 菜单」算出来的，原来只排除了软删，
    于是被停用的账号和被停用的角色照样收到工单通知——收件人永远处理不了，
    通知栏被这类噪音填满之后，真正要处理的那条也就被淹了。
    """

    from app.capabilities.support.permissions import MANAGE
    from app.capabilities.support.service import SupportService
    from app.domain.menus.models import Menu
    from app.domain.roles.models import Role, RoleMenu
    from app.domain.users.models import User, UserRole, UserStatus

    tenant_id = 1
    menu = Menu(tenant_id=tenant_id, title="工单管理", path="/support/admin/tickets",
                menu_type="2", perms=MANAGE, parent_id=None, level=1)
    db.add(menu)
    await db.flush()

    async def member(username: str, *, status: int, role_active: bool) -> int:
        user = User(tenant_id=tenant_id, username=username, nickname=username,
                    password_hash="x", status=status)
        role = Role(tenant_id=tenant_id, name=f"role-{username}",
                    code=f"role_{username}", is_active=role_active)
        db.add_all((user, role))
        await db.flush()
        db.add_all((
            UserRole(tenant_id=tenant_id, user_id=user.id, role_id=role.id),
            RoleMenu(tenant_id=tenant_id, role_id=role.id, menu_id=menu.id),
        ))
        await db.flush()
        return int(user.id)

    active = await member("active_agent", status=UserStatus.ENABLED, role_active=True)
    disabled_user = await member("left_the_company", status=UserStatus.DISABLED, role_active=True)
    retired_role = await member("moved_teams", status=UserStatus.ENABLED, role_active=False)

    recipients = await SupportService(db)._manager_user_ids(tenant_id=tenant_id)

    assert active in recipients
    assert disabled_user not in recipients
    assert retired_role not in recipients
