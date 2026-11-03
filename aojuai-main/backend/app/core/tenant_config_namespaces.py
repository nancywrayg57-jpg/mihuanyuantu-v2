"""
AOJU Backend - Tenant config namespace helpers.

Shared helpers for reading and writing module-scoped JSONB namespaces inside
Tenant.config without forcing every module to reimplement nested dict logic.
"""

from __future__ import annotations

from typing import Any


def safe_tenant_config_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def get_tenant_config_namespace(config: dict[str, Any] | None, path: tuple[str, ...]) -> dict[str, Any]:
    current: Any = safe_tenant_config_dict(config)
    for key in path:
        if not isinstance(current, dict):
            return {}
        current = current.get(key)
    return safe_tenant_config_dict(current)


def set_tenant_config_namespace(
    config: dict[str, Any] | None,
    path: tuple[str, ...],
    value: dict[str, Any] | None,
) -> dict[str, Any]:
    if not path:
        return safe_tenant_config_dict(value)

    root = safe_tenant_config_dict(config)
    cursor: Any = root

    for key in path[:-1]:
        next_value = cursor.get(key)
        if not isinstance(next_value, dict):
            next_value = {}
        next_value = dict(next_value)
        cursor[key] = next_value
        cursor = next_value

    cursor[path[-1]] = safe_tenant_config_dict(value)
    return root
