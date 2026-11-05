"""AOJU Backend - API V1 router assembly."""

import importlib
from collections.abc import Sequence

from fastapi import APIRouter

# 内核端点：无条件加载。内置能力（assistant / speech / cms）改为**按需 import**，
# 见 register_builtin_capability_router——未安装时连模块都不会被 import。
from app.api.v1.endpoints import (
    api_keys,
    auth,
    credits,
    invitations,
    menus,
    message_channels,
    message_gateways,
    notifications,
    operation_logs,
    roles,
    site,
    teams,
    tenant_profile,
    tenants,
    upload,
    user_groups,
    users,
)
from app.core.capability_registry import discover_capabilities
from app.core.feature_switches import is_module_installed

api_router = APIRouter()


def register_capability_router(
    code: str,
    router: APIRouter,
    prefix: str,
    tags: Sequence[str],
) -> bool:
    """Mount a deployable pack router only when its catalog module is installed.

    Returning the registration decision makes assembly tests and future pack
    startup diagnostics explicit. Uninstalled routers never enter the FastAPI
    route table, so they are also absent from OpenAPI.
    """
    if not is_module_installed(code):
        return False
    api_router.include_router(router, prefix=prefix, tags=list(tags))
    return True


def register_builtin_capability_router(
    code: str,
    module_path: str,
    prefix: str,
    tags: Sequence[str],
    *,
    attribute: str = "router",
) -> bool:
    """按需挂载**内置能力**的 router。

    内置能力（assistant / speech / cms）过去是顶层 import + 无条件挂载，
    于是 `AOJ_ENABLED_MODULES=none` 时它们的代码照样被加载——开关只是把菜单藏了，
    进程里该占的还是占。这里改成与能力包同样的语义：
    **未安装就不 import、不挂载**，请求得到 404 而不是 403。

    注意：表仍由 core 迁移链建出（内置能力的迁移在 core 链上）。
    要做到连表都没有，模块得转成独立迁移链的能力包。
    """
    if not is_module_installed(code):
        return False
    module = importlib.import_module(module_path)
    api_router.include_router(getattr(module, attribute), prefix=prefix, tags=list(tags))
    return True


def register_discovered_capability_routers() -> tuple[str, ...]:
    """Discover and mount installed capability packages without a central list."""

    registered: list[str] = []
    for definition in discover_capabilities():
        # Do not even import the HTTP adapter for an uninstalled module.
        if not is_module_installed(definition.code):
            continue
        module = importlib.import_module(definition.router_module)
        router = getattr(module, definition.router_attribute)
        if register_capability_router(
            definition.code,
            router,
            prefix=definition.api_prefix,
            tags=[definition.label],
        ):
            registered.append(definition.code)
    return tuple(registered)


# Kernel and built-in capability routers remain assembled unconditionally.
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
register_builtin_capability_router(
    "assistant", "app.api.v1.endpoints.assistant", "/assistant", ["Assistant"]
)
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(roles.router, prefix="/roles", tags=["Roles"])
api_router.include_router(menus.router, prefix="/menus", tags=["Menus"])
api_router.include_router(teams.router, prefix="/teams", tags=["Teams"])
api_router.include_router(tenants.router, prefix="/tenants", tags=["Tenants"])
api_router.include_router(tenant_profile.router, prefix="/tenant/profile", tags=["Tenant Profile"])
api_router.include_router(site.router, prefix="/site", tags=["Site"])
register_builtin_capability_router(
    "public_site", "app.api.v1.endpoints.cms_public", "/site/cms", ["CMS Public"]
)
register_builtin_capability_router("public_site", "app.api.v1.endpoints.cms", "/cms", ["CMS Admin"])
register_builtin_capability_router(
    "public_site", "app.api.v1.endpoints.cms_ai", "/cms/ai", ["CMS AI"]
)
api_router.include_router(user_groups.router, prefix="/user-groups", tags=["User Groups"])
api_router.include_router(credits.router, prefix="/credits", tags=["Credits"])
api_router.include_router(invitations.router, prefix="/invitations", tags=["Invitations"])
api_router.include_router(operation_logs.router, prefix="/operation-logs", tags=["Operation Logs"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])
api_router.include_router(api_keys.router, prefix="/api-keys", tags=["API Keys"])
api_router.include_router(message_channels.router, prefix="/message-channels", tags=["Message Channels"])
api_router.include_router(message_gateways.router, prefix="/message-gateways", tags=["Message Gateways"])
api_router.include_router(upload.router, prefix="/upload", tags=["Upload"])
register_builtin_capability_router("speech", "app.api.v1.endpoints.speech", "/speech", ["Speech"])

# Optional packs are assembled last. Their own declarations are the source of
# truth; new modules never add an import or include_router call to this file.
REGISTERED_CAPABILITY_ROUTERS = register_discovered_capability_routers()
