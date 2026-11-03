"""Official end-to-end example capability."""

from app.core.capability_registry import CapabilityDefinition

CAPABILITY = CapabilityDefinition(
    code="sample_items",
    label="样例条目",
    description="官方可选模块样例：独立迁移、租户 CRUD、权限、菜单与前端页面",
    layer="sample",
    version="1.0.0",
    dependencies=("core",),
    default_enabled=False,
    route_prefixes=("/sample-items",),
    api_prefix="/sample-items",
    permission_prefixes=("sample_items",),
    router_module="app.capabilities.sample_items.api",
    seed_module="app.capabilities.sample_items.seed",
    migration_directory="migrations",
    version_table="alembic_version_cap_sample_items",
    production_blocked=True,
)

__all__ = ["CAPABILITY"]
