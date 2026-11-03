"""GOV-20: `(app)` 下的每个业务页面都必须被某个模块的 route_prefix 覆盖。

`ModuleRouteGuard` 靠"路径 → 声明的模块"来判断能不能进。判断依据是模块目录里的
`routePrefixes`。所以**只要有人加了页面却没在声明里登记路由前缀，守卫就拦不住它**：
模块明明没安装，手敲 URL 照样能进去，接口全 404，界面一堆报错。

这是"覆盖率"类问题——今天恰好全覆盖，明天加个页面就破了，而且破了没有任何征兆。
所以做成门禁，而不是靠一次人工核对。

内核页面（system/personal/tenant/…）不属于任何模块，显式列在 KERNEL_ROUTE_ROOTS 里。
往这个名单里加东西要想清楚：加进来就等于宣布"这个页面任何租户任何部署都必须有"。
"""

from __future__ import annotations

import json
from pathlib import Path

from .common import ScanResult, Violation, require_discovered, validate_allowlist

PAGE_GUARD_ALLOWLIST: dict[str, str] = {}

# 内核页面的顶层路由段：它们不可卸载，也就不需要模块声明覆盖。
KERNEL_ROUTE_ROOTS = frozenset(
    {
        "system",
        "personal",
        "tenant",
        "permission",
        "welcome",
        "schedule",
    }
)


def _catalog_prefixes(repo_root: Path) -> tuple[str, ...]:
    path = repo_root / "frontend" / "src" / "generated" / "module-catalog.json"
    if not path.is_file():
        return ()
    catalog = json.loads(path.read_text(encoding="utf-8"))
    return tuple(
        str(prefix)
        for module in catalog.get("modules", [])
        for prefix in (module.get("routePrefixes") or [])
        if str(prefix).strip()
    )


def discover_app_pages(repo_root: Path) -> tuple[str, ...]:
    app_root = repo_root / "frontend" / "src" / "app" / "(app)"
    if not app_root.is_dir():
        return ()
    routes = []
    for page in sorted(app_root.rglob("page.tsx")):
        relative = page.relative_to(app_root).parent.as_posix()
        routes.append("/" if relative == "." else f"/{relative}")
    return tuple(routes)


def _covered(route: str, prefixes: tuple[str, ...]) -> bool:
    for prefix in prefixes:
        normalized = "/" + prefix.strip("/")
        if route == normalized or route.startswith(f"{normalized}/"):
            return True
    return False


def scan_page_guard_coverage(
    repo_root: Path,
    *,
    allowlist: dict[str, str] | None = None,
) -> ScanResult:
    allowed = PAGE_GUARD_ALLOWLIST if allowlist is None else allowlist
    validate_allowlist("GOV-20", allowed)

    routes = discover_app_pages(repo_root)
    require_discovered("GOV-20", routes, "pages under frontend/src/app/(app)")

    prefixes = _catalog_prefixes(repo_root)
    violations: list[Violation] = []
    for route in routes:
        if route in allowed or route == "/":
            continue
        top = route.strip("/").split("/")[0]
        if top in KERNEL_ROUTE_ROOTS:
            continue
        if _covered(route, prefixes):
            continue
        violations.append(
            Violation(
                "GOV-20",
                f"frontend/src/app/(app){route}/page.tsx",
                0,
                f"页面 {route} 既不属于内核，也没有任何模块声明覆盖它的路由前缀；"
                "ModuleRouteGuard 拦不住它——模块没装时手敲 URL 照样能进。"
                "要么在模块的 route_prefixes 里登记，要么加进 KERNEL_ROUTE_ROOTS 并说明理由",
            )
        )

    return ScanResult(rule="GOV-20", discovered=routes, violations=tuple(violations))
