"""蜜獾原图 realphotos 业务能力包（正式 pack，默认关闭、显式安装）。

S0 范围：会话登录适配、租户商家档案、RBAC 角色种子、整数积分流水、
LocalDisk 存储适配器 + 鉴权网关、PostgreSQL 持久队列 + 同机 worker 骨架。
"""

from app.core.capability_registry import CapabilityDefinition

CAPABILITY = CapabilityDefinition(
    code="realphotos",
    label="蜜獾原图",
    description="电商商家图片资源、相机参数处理与整数积分流水",
    label_key="system.moduleCatalog.realphotos.label",
    description_key="system.moduleCatalog.realphotos.description",
    layer="pack",
    version="0.1.0-s0",
    dependencies=("core",),
    default_enabled=False,
    route_prefixes=("/realphotos",),
    api_prefix="/realphotos",
    permission_prefixes=("realphotos",),
    router_module="app.capabilities.realphotos.api",
    seed_module="app.capabilities.realphotos.seed",
    migration_directory="migrations",
    version_table="alembic_version_cap_realphotos",
)

__all__ = ["CAPABILITY"]
