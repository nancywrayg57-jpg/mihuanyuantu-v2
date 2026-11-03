"""Discovery and metadata contracts for self-registering capability packages."""

from __future__ import annotations

import importlib
import pkgutil
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

CAPABILITY_CODE_RE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
VERSION_TABLE_RE = re.compile(r"^alembic_version_cap_[a-z][a-z0-9_]*$")
BASE_DEPENDENCIES = frozenset({"core", "assistant", "speech", "public_site"})


@dataclass(frozen=True, slots=True)
class CapabilityDefinition:
    """Everything the base needs to assemble one optional business module."""

    code: str
    label: str
    description: str
    layer: Literal["pack", "sample"]
    version: str
    # 前端只翻译 system./common./auth. 开头的键，其余原样显示。能力包不声明这两个键，
    # 模块开关列表在 en/es 下就会漏出中文——样例包因为 layer="sample" 不进 catalog
    # 所以碰不到，第一个真实 pack 才会踩到。label 本身保留服务端显示名：
    # 助手会把它拼进给用户看的自然语言，那里不能漏出 i18n key。
    label_key: str = ""
    description_key: str = ""
    dependencies: tuple[str, ...] = ()
    default_enabled: bool = False
    route_prefixes: tuple[str, ...] = ()
    api_prefix: str = ""
    permission_prefixes: tuple[str, ...] = ()
    router_module: str = ""
    router_attribute: str = "router"
    seed_module: str = ""
    migration_directory: str = "migrations"
    version_table: str = ""
    production_blocked: bool = False

    def validate(self, package_name: str) -> None:
        if not CAPABILITY_CODE_RE.fullmatch(self.code):
            raise ValueError(f"invalid capability code {self.code!r}")
        if package_name.rsplit(".", 1)[-1] != self.code:
            raise ValueError(
                f"capability package {package_name!r} must match code {self.code!r}"
            )
        if self.layer not in {"pack", "sample"}:
            raise ValueError(f"invalid capability layer for {self.code}: {self.layer!r}")
        if self.layer == "sample" and not self.production_blocked:
            raise ValueError(
                f"sample capability {self.code!r} must set production_blocked=True"
            )
        if self.layer == "sample":
            package = importlib.import_module(package_name)
            package_file = getattr(package, "__file__", None)
            marker = Path(package_file).resolve().parent / "PRODUCTION_BLOCKED" if package_file else None
            if marker is None or not marker.is_file():
                raise ValueError(f"sample capability {self.code!r} is missing PRODUCTION_BLOCKED")
        if self.default_enabled:
            raise ValueError(
                f"deployable capability {self.code!r} must be installation-default-off"
            )
        if not self.api_prefix.startswith("/"):
            raise ValueError(f"capability {self.code!r} api_prefix must start with '/'")
        if not self.router_module.startswith(f"{package_name}."):
            raise ValueError(f"capability {self.code!r} router must stay inside its package")
        if not self.seed_module.startswith(f"{package_name}."):
            raise ValueError(f"capability {self.code!r} seed must stay inside its package")
        if not VERSION_TABLE_RE.fullmatch(self.version_table):
            raise ValueError(
                f"capability {self.code!r} has invalid version table {self.version_table!r}"
            )
        expected_prefix = f"{self.code}:"
        if any(not prefix.startswith(expected_prefix) and prefix != self.code for prefix in self.permission_prefixes):
            raise ValueError(f"capability {self.code!r} has an invalid permission prefix")

    def package_directory(self) -> Path:
        module = importlib.import_module(f"app.capabilities.{self.code}")
        module_file = getattr(module, "__file__", None)
        if not module_file:
            raise RuntimeError(f"cannot resolve package directory for {self.code}")
        return Path(module_file).resolve().parent

    def migration_path(self) -> Path:
        return self.package_directory() / self.migration_directory


@lru_cache(maxsize=1)
def discover_capabilities() -> tuple[CapabilityDefinition, ...]:
    """Import direct child packages and return their validated declarations."""

    import app.capabilities as capabilities_package

    discovered: list[CapabilityDefinition] = []
    seen: set[str] = set()
    for module_info in sorted(
        pkgutil.iter_modules(capabilities_package.__path__),
        key=lambda item: item.name,
    ):
        if not module_info.ispkg or module_info.name.startswith("_"):
            continue
        package_name = f"{capabilities_package.__name__}.{module_info.name}"
        package = importlib.import_module(package_name)
        declaration = getattr(package, "CAPABILITY", None)
        if not isinstance(declaration, CapabilityDefinition):
            raise TypeError(f"{package_name} must expose a CapabilityDefinition as CAPABILITY")
        declaration.validate(package_name)
        if declaration.code in seen:
            raise ValueError(f"duplicate capability code: {declaration.code}")
        seen.add(declaration.code)
        discovered.append(declaration)
    return tuple(discovered)


def capability_by_code(code: str) -> CapabilityDefinition | None:
    normalized = str(code or "").strip().lower().replace("-", "_")
    return next(
        (item for item in discover_capabilities() if item.code == normalized),
        None,
    )


def order_capabilities(
    definitions: tuple[CapabilityDefinition, ...],
) -> tuple[CapabilityDefinition, ...]:
    """Topologically order installed packs and reject missing/cyclic dependencies."""

    by_code = {definition.code: definition for definition in definitions}
    ordered: list[CapabilityDefinition] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(code: str) -> None:
        if code in visited:
            return
        if code in visiting:
            raise ValueError(f"cyclic capability dependency involving {code!r}")
        visiting.add(code)
        definition = by_code[code]
        for dependency in definition.dependencies:
            if dependency in BASE_DEPENDENCIES:
                continue
            if dependency not in by_code:
                raise ValueError(f"{code}: missing installed dependency {dependency!r}")
            visit(dependency)
        visiting.remove(code)
        visited.add(code)
        ordered.append(definition)

    for code in sorted(by_code):
        visit(code)
    return tuple(ordered)
