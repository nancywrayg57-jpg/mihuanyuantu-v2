from __future__ import annotations

from dataclasses import dataclass

from app.core.feature_switches import (
    MODULE_CATALOG,
    MODULE_SWITCH_EXPANSIONS,
    canonicalize_module_code,
    get_installed_module_codes,
    is_module_installed,
    resolve_module_from_route_path,
)
from app.core.feature_switches import (
    clear_module_install_caches as clear_feature_switch_module_caches,
)


@dataclass(frozen=True, slots=True)
class ModuleDefinition:
    id: str
    route_prefixes: tuple[str, ...]


MODULES: tuple[ModuleDefinition, ...] = tuple(
    ModuleDefinition(
        id=item.code,
        route_prefixes=tuple(prefix for prefix in item.route_prefixes if prefix),
    )
    for item in MODULE_CATALOG
)

MODULE_EXPANSIONS: dict[str, tuple[str, ...]] = dict(MODULE_SWITCH_EXPANSIONS)


def clear_module_install_caches() -> None:
    clear_feature_switch_module_caches()


def get_enabled_module_ids() -> set[str] | None:
    return get_installed_module_codes()


def is_module_enabled(module_id: str) -> bool:
    normalized = canonicalize_module_code(module_id)
    if normalized is None:
        return True
    return is_module_installed(normalized)


def get_disabled_module_id_for_path(pathname: str | None) -> str | None:
    module_id = resolve_module_from_route_path(pathname)
    if not module_id:
        return None
    if is_module_enabled(module_id):
        return None
    return module_id
