"""Self-registering ``support`` capability: tenant-scoped help-desk tickets.

安装即得到一条完整链路：独立迁移链建表、路由按安装状态挂载、菜单/权限由
`access.py` 声明并经 reconciler 三写收敛、前端页面按权限码渲染按钮。
未安装时整包不 import、不建表、不出现在目录里。
"""

from app.core.capability_registry import CapabilityDefinition

CAPABILITY = CapabilityDefinition(
    code="support",
    # label/description 是**服务端显示名**：助手会把它拼进给用户看的自然语言，
    # 那里不能漏出 i18n key。前端展示用下面两个 key（登记在包自己的语言包里）。
    label="工单中心",
    description="可选工单能力：分类/状态/优先级的工单、回复线程、匿名公开提单，并可选桥接公开站留言",
    label_key="system.moduleCatalog.support.label",
    description_key="system.moduleCatalog.support.description",
    layer="pack",
    version="1.0.0",
    # 只依赖内核。公开站/CMS 是**可选**的下游联动，不写进 dependencies——
    # 写进去就等于"没装 CMS 就装不了工单"，而工单在没有公开站时完全可用。
    dependencies=("core",),
    default_enabled=False,
    route_prefixes=("/support",),
    api_prefix="/support",
    permission_prefixes=("support",),
    router_module="app.capabilities.support.api",
    seed_module="app.capabilities.support.seed",
    migration_directory="migrations",
    version_table="alembic_version_cap_support",
)

__all__ = ["CAPABILITY"]
