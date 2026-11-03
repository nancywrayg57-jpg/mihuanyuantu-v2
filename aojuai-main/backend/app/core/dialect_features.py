"""按数据库方言禁用的能力（SQLite 轻量档）。

设计：轻量档不是"功能悄悄少一块"，而是**显式登记 + 统一拒绝 + 前端可见**：
- 功能级：`PG_ONLY_FEATURES` 登记依赖 PostgreSQL 专有能力的功能码；端点用 `require_postgresql("<code>")`
  依赖，SQLite 下返回统一错误码 `FEATURE_REQUIRES_POSTGRESQL`；`unavailable_features()` 随公共配置下发给前端隐藏入口。
- 模块级：`ModuleCatalogItem.requires_postgresql=True` 的模块在 SQLite 下视为**未安装**（目录不出现、路由不挂、
  菜单不显示），与硬卸载走同一条链路，不需要各处再判。
"""

from __future__ import annotations

from collections.abc import Callable

from app.infrastructure.database.dialect import get_dialect

#: 功能码 → 为什么需要 PostgreSQL（给排查与文档用，不是给用户看的文案）
PG_ONLY_FEATURES: dict[str, str] = {
    "credits.pricing_reconciliation": "灰度对账 SQL 依赖 jsonb_array_elements / FILTER / interval 聚合",
}


def feature_requires_postgresql(code: str) -> bool:
    return code in PG_ONLY_FEATURES


def is_feature_available(code: str) -> bool:
    """SQLite 下登记为 PG 专有的功能不可用；其余功能与方言无关。"""
    return not (get_dialect().name == "sqlite" and feature_requires_postgresql(code))


def unavailable_features() -> list[str]:
    """当前方言下不可用的功能码（前端据此隐藏入口）。"""
    return sorted(code for code in PG_ONLY_FEATURES if not is_feature_available(code))


def database_dialect() -> str:
    return get_dialect().name


def require_postgresql(code: str) -> Callable[[], None]:
    """FastAPI 依赖：`Depends(require_postgresql("credits.pricing_reconciliation"))`。"""
    if code not in PG_ONLY_FEATURES:
        raise ValueError(f"unknown PG-only feature code: {code!r}（先登记到 PG_ONLY_FEATURES）")

    def _dependency() -> None:
        if not is_feature_available(code):
            from app.core.exceptions import BusinessError

            raise BusinessError(
                message="该功能需要 PostgreSQL 部署，SQLite 轻量档不可用",
                code="FEATURE_REQUIRES_POSTGRESQL",
                details={"feature": code, "dialect": database_dialect()},
            )

    return _dependency
