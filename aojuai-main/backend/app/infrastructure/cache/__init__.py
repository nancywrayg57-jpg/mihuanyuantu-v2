"""AOJU Backend - Infrastructure Cache Package"""

from app.infrastructure.cache.redis import close_redis_cache, get_redis_cache
from app.infrastructure.cache.runtime_cache import delete, delete_prefix, get_json, remember_json, set_json
from app.infrastructure.cache.ui_cache import (
    MENU_ROUTES_TTL_SECONDS,
    MENU_TREE_OPTIONS_TTL_SECONDS,
    SITE_PUBLIC_CONFIG_TTL_SECONDS,
    build_menu_routes_cache_key,
    build_menu_tree_options_cache_key,
    build_site_public_config_cache_key,
    bump_menu_structure_cache_version,
    bump_site_public_config_cache_version,
    bump_tenant_permissions_cache_version,
    bump_tenant_ui_config_cache_version,
    get_menu_routes_cache_versions,
    get_menu_tree_options_cache_version,
    get_site_public_config_cache_version,
)

__all__ = [
    "delete",
    "delete_prefix",
    "get_json",
    "remember_json",
    "set_json",
    "MENU_TREE_OPTIONS_TTL_SECONDS",
    "MENU_ROUTES_TTL_SECONDS",
    "SITE_PUBLIC_CONFIG_TTL_SECONDS",
    "get_redis_cache",
    "close_redis_cache",
    "build_menu_tree_options_cache_key",
    "build_menu_routes_cache_key",
    "build_site_public_config_cache_key",
    "get_menu_tree_options_cache_version",
    "get_menu_routes_cache_versions",
    "get_site_public_config_cache_version",
    "bump_menu_structure_cache_version",
    "bump_tenant_permissions_cache_version",
    "bump_tenant_ui_config_cache_version",
    "bump_site_public_config_cache_version",
]
