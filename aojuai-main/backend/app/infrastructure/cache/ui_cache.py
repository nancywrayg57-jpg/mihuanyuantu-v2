"""
AOJU Backend - UI Cache Namespaces

Versioned keys let us invalidate hot read paths without scanning Redis:
- menu routes
- menu permission tree
- site public config
"""

from __future__ import annotations

from urllib.parse import quote

from app.infrastructure.cache.redis import get_redis_cache

MENU_TREE_OPTIONS_TTL_SECONDS = 300
MENU_ROUTES_TTL_SECONDS = 300
SITE_PUBLIC_CONFIG_TTL_SECONDS = 300

MENU_STRUCTURE_VERSION_KEY = "aoju:cache:ver:menu-structure"
SITE_PUBLIC_CONFIG_VERSION_KEY = "aoju:cache:ver:site-public-config"


def tenant_ui_config_version_key(tenant_id: int) -> str:
    return f"aoju:cache:ver:tenant-ui-config:{tenant_id}"


def tenant_permissions_version_key(tenant_id: int) -> str:
    return f"aoju:cache:ver:tenant-permissions:{tenant_id}"


def build_menu_tree_options_cache_key(
    *, tenant_id: int, is_superuser: bool, menu_version: int
) -> str:
    # 必须含 tenant_id：菜单树按租户查（菜单行逐租户一份），
    # key 不带租户的话所有租户共用一份缓存，切租户会看到别人的菜单树。
    return (
        f"aoju:cache:menus:tree-options:tenant:{tenant_id}:"
        f"super:{int(is_superuser)}:mv:{menu_version}"
    )


def build_menu_routes_cache_key(
    *,
    tenant_id: int,
    user_id: int,
    is_superuser: bool,
    menu_version: int,
    tenant_ui_version: int,
    tenant_permissions_version: int,
) -> str:
    return (
        "aoju:cache:menus:routes:"
        f"tenant:{tenant_id}:user:{user_id}:super:{int(is_superuser)}:"
        f"mv:{menu_version}:tv:{tenant_ui_version}:pv:{tenant_permissions_version}"
    )


def build_site_public_config_cache_key(*, host: str, version: int) -> str:
    normalized_host = quote((host or "_").strip().lower() or "_", safe="")
    return f"aoju:cache:site:public-config:host:{normalized_host}:v:{version}"


async def get_menu_tree_options_cache_version(*, is_superuser: bool) -> int:
    del is_superuser
    cache = get_redis_cache()
    return await cache.get_int(MENU_STRUCTURE_VERSION_KEY, default=0)


async def get_menu_routes_cache_versions(tenant_id: int) -> tuple[int, int, int]:
    cache = get_redis_cache()
    menu_version, tenant_ui_version, tenant_permissions_version = await cache.get_ints(
        [
            MENU_STRUCTURE_VERSION_KEY,
            tenant_ui_config_version_key(tenant_id),
            tenant_permissions_version_key(tenant_id),
        ],
        default=0,
    )
    return menu_version, tenant_ui_version, tenant_permissions_version


async def get_site_public_config_cache_version() -> int:
    cache = get_redis_cache()
    return await cache.get_int(SITE_PUBLIC_CONFIG_VERSION_KEY, default=0)


async def bump_menu_structure_cache_version() -> int:
    cache = get_redis_cache()
    return await cache.incr(MENU_STRUCTURE_VERSION_KEY)


async def bump_tenant_ui_config_cache_version(tenant_id: int) -> int:
    cache = get_redis_cache()
    return await cache.incr(tenant_ui_config_version_key(int(tenant_id)))


async def bump_tenant_permissions_cache_version(tenant_id: int) -> int:
    cache = get_redis_cache()
    return await cache.incr(tenant_permissions_version_key(int(tenant_id)))


async def bump_site_public_config_cache_version() -> int:
    cache = get_redis_cache()
    return await cache.incr(SITE_PUBLIC_CONFIG_VERSION_KEY)
