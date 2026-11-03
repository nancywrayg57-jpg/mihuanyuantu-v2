"""Shared cache keys and invalidation helpers for base runtime views."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.infrastructure.cache.runtime_cache import delete, delete_prefix

SITE_PUBLIC_CONFIG_PREFIX = "site_public_config:"
TENANT_PROFILE_PREFIX = "tenant_profile:"
TENANT_SETTINGS_PREFIX = "tenant_settings:"
TENANT_FEATURE_CATALOG_PREFIX = "tenant_feature_catalog:"
TENANT_FEATURE_SWITCHES_PREFIX = "tenant_feature_switches:"
MENU_TREE_OPTIONS_PREFIX = "menu_tree_options:"
MENU_ROUTES_PREFIX = "menu_routes:"
ASSISTANT_SCOPE_DIRECTORY_PREFIX = "assistant_scope_directory:"
SPEECH_CONFIG_PREFIX = "speech_config:"
SPEECH_PROVIDERS_CACHE_KEY = "speech_providers_catalog:v1"

SITE_PUBLIC_CONFIG_TTL_SECONDS = 300
TENANT_RUNTIME_CACHE_TTL_SECONDS = 180
MENU_TREE_OPTIONS_TTL_SECONDS = 600
MENU_ROUTES_TTL_SECONDS = 180
SPEECH_CONFIG_TTL_SECONDS = 180
SPEECH_PROVIDERS_TTL_SECONDS = 3600


def build_site_public_config_cache_key(host: str) -> str:
    normalized_host = str(host or "").strip().lower() or "__default__"
    return f"{SITE_PUBLIC_CONFIG_PREFIX}{normalized_host}"


def build_tenant_profile_cache_key(tenant_id: int, *, view: str) -> str:
    normalized_view = str(view or "detail").strip().lower() or "detail"
    return f"{TENANT_PROFILE_PREFIX}{tenant_id}:{normalized_view}"


def build_tenant_settings_cache_key(tenant_id: int) -> str:
    return f"{TENANT_SETTINGS_PREFIX}{tenant_id}"


#: 目录载荷结构版本：字段增减时 +1，避免旧结构的缓存在 TTL 内继续下发（2026-08-27 加 databaseDialect/unavailableFeatures）
TENANT_FEATURE_CATALOG_PAYLOAD_VERSION = "v2"


def build_tenant_feature_catalog_cache_key(tenant_id: int) -> str:
    return f"{TENANT_FEATURE_CATALOG_PREFIX}{tenant_id}:{TENANT_FEATURE_CATALOG_PAYLOAD_VERSION}"


def build_tenant_feature_switches_cache_key(tenant_id: int) -> str:
    return f"{TENANT_FEATURE_SWITCHES_PREFIX}{tenant_id}"


def build_menu_tree_options_cache_key(*, exclude_superuser_menus: bool) -> str:
    return f"{MENU_TREE_OPTIONS_PREFIX}{1 if exclude_superuser_menus else 0}"


def build_user_route_scope_digest(current_user: Any) -> str:
    if bool(getattr(current_user, "is_superuser", False)):
        return "superuser"

    role_ids: set[int] = set()
    menu_ids: set[int] = set()
    for role in list(getattr(current_user, "roles", []) or []):
        if getattr(role, "deleted_at", None) is not None or not bool(getattr(role, "is_active", False)):
            continue
        role_id = getattr(role, "id", None)
        if isinstance(role_id, int):
            role_ids.add(role_id)
        for menu in list(getattr(role, "menus", []) or []):
            if getattr(menu, "deleted_at", None) is not None:
                continue
            menu_id = getattr(menu, "id", None)
            if isinstance(menu_id, int):
                menu_ids.add(menu_id)

    payload = {
        "roleIds": sorted(role_ids),
        "menuIds": sorted(menu_ids),
    }
    digest = hashlib.sha1(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return digest[:16]


def build_async_routes_cache_key(current_user: Any) -> str:
    tenant_id = int(getattr(current_user, "tenant_id", 0) or 0)
    user_id = int(getattr(current_user, "id", 0) or 0)
    is_superuser = 1 if bool(getattr(current_user, "is_superuser", False)) else 0
    scope_digest = build_user_route_scope_digest(current_user)
    return (
        f"{MENU_ROUTES_PREFIX}tenant:{tenant_id}:user:{user_id}:"
        f"super:{is_superuser}:scope:{scope_digest}"
    )


def build_assistant_scope_directory_cache_key(*, tenant_id: int, user_id: int) -> str:
    return f"{ASSISTANT_SCOPE_DIRECTORY_PREFIX}tenant:{int(tenant_id)}:user:{int(user_id)}"


def build_speech_config_cache_key(tenant_id: int) -> str:
    return f"{SPEECH_CONFIG_PREFIX}{tenant_id}"


async def invalidate_site_public_config_cache() -> None:
    await delete_prefix(SITE_PUBLIC_CONFIG_PREFIX)


async def invalidate_tenant_runtime_cache(tenant_id: int) -> None:
    await delete(build_tenant_profile_cache_key(tenant_id, view="detail"))
    await delete(build_tenant_profile_cache_key(tenant_id, view="summary"))
    await delete(build_tenant_settings_cache_key(tenant_id))
    await delete(build_tenant_feature_catalog_cache_key(tenant_id))
    await delete(build_tenant_feature_switches_cache_key(tenant_id))
    await delete(build_speech_config_cache_key(tenant_id))
    await delete_prefix(f"{MENU_ROUTES_PREFIX}tenant:{tenant_id}:")
    await delete_prefix(f"{ASSISTANT_SCOPE_DIRECTORY_PREFIX}tenant:{tenant_id}:")
    await invalidate_site_public_config_cache()


async def invalidate_menu_runtime_cache(*, tenant_id: int | None = None) -> None:
    await delete_prefix(MENU_TREE_OPTIONS_PREFIX)
    if tenant_id is None:
        await delete_prefix(MENU_ROUTES_PREFIX)
        await delete_prefix(ASSISTANT_SCOPE_DIRECTORY_PREFIX)
        return
    await delete_prefix(f"{MENU_ROUTES_PREFIX}tenant:{tenant_id}:")
    await delete_prefix(f"{ASSISTANT_SCOPE_DIRECTORY_PREFIX}tenant:{tenant_id}:")


async def invalidate_speech_runtime_cache(tenant_id: int) -> None:
    await delete(build_speech_config_cache_key(tenant_id))
    await delete(build_tenant_settings_cache_key(tenant_id))
    await delete(build_tenant_profile_cache_key(tenant_id, view="detail"))
