"""可选能力包的安装合同 —— 这是整套装配机制的验收测试。

要证明的不是"关掉之后访问会被拒绝"，而是**未安装时那条路由压根不存在**：
- 未安装：路由不进 route table，请求得到 404（不是 403，403 会泄漏"这里有功能但关了"）
- 未安装：连它的 HTTP 适配层模块都不 import
- 已安装：路由出现、可达

用 sample_items 当被测对象：它是 sample 层，默认不安装，
即使部署变量留空（普通模块的 legacy "全装" 语义）也不会被带上。
"""

from __future__ import annotations

import importlib
import sys

import pytest
from fastapi import FastAPI

from app.api import v1
from app.core.capability_registry import discover_capabilities
from app.core import feature_switches

SAMPLE_CODE = "sample_items"
SAMPLE_API_MODULE = "app.capabilities.sample_items.api"


def _install(codes: str) -> None:
    feature_switches.settings.AOJ_ENABLED_MODULES = codes
    feature_switches.clear_module_install_caches()


def _mounted_paths(registered_codes: tuple[str, ...]) -> set[str]:
    app = FastAPI()
    app.include_router(v1.api_router)
    _ = registered_codes
    return {getattr(route, "path", "") for route in app.routes}


def test_sample_capability_is_discovered_but_not_installed_by_default() -> None:
    """样例包必须能被发现（否则装不上），但默认不能被认为已安装。"""
    _install("")

    codes = {definition.code for definition in discover_capabilities()}
    assert SAMPLE_CODE in codes, "能力包必须能被自注册发现"

    assert feature_switches.is_module_installed(SAMPLE_CODE) is False, (
        "部署变量留空的 legacy「全装」语义绝不能把样例模块也装上"
    )


def test_uninstalled_capability_router_is_not_registered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install("")

    router = pytest.importorskip("fastapi").APIRouter()
    monkeypatch.setattr(v1, "api_router", router)

    registered = v1.register_discovered_capability_routers()

    assert SAMPLE_CODE not in registered
    assert not any(
        "/sample-items" in getattr(route, "path", "") for route in router.routes
    ), "未安装的能力包不得出现在 route table 里"


def test_uninstalled_capability_http_adapter_is_never_imported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """未安装时不应该只是"挂了再拦"，而是根本不 import 它的适配层。"""
    _install("")

    monkeypatch.delitem(sys.modules, SAMPLE_API_MODULE, raising=False)

    router = pytest.importorskip("fastapi").APIRouter()
    monkeypatch.setattr(v1, "api_router", router)
    v1.register_discovered_capability_routers()

    assert SAMPLE_API_MODULE not in sys.modules, (
        "未安装的能力包连 HTTP 适配层都不该被 import"
    )


def test_installed_capability_router_is_registered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(SAMPLE_CODE)

    router = pytest.importorskip("fastapi").APIRouter()
    monkeypatch.setattr(v1, "api_router", router)

    registered = v1.register_discovered_capability_routers()

    assert SAMPLE_CODE in registered
    paths = {getattr(route, "path", "") for route in router.routes}
    assert any(path.startswith("/sample-items") for path in paths), (
        f"安装后路由必须出现，实际有：{sorted(paths)}"
    )


def test_sample_capability_declares_isolated_migration_chain() -> None:
    """样例包的迁移必须是独立链：独立 version_table，且不挂在 core 链上。"""
    definition = next(
        item for item in discover_capabilities() if item.code == SAMPLE_CODE
    )
    assert definition.version_table == "alembic_version_cap_sample_items"
    assert definition.version_table != "alembic_version"

    initial = importlib.import_module(
        "app.capabilities.sample_items.migrations.versions.sample_items_0001_initial"
    )
    assert initial.down_revision is None, (
        "能力包的迁移链不能挂到 core 链上，否则不装也会建表"
    )


def test_sample_layer_is_blocked_from_production() -> None:
    definition = next(
        item for item in discover_capabilities() if item.code == SAMPLE_CODE
    )
    assert definition.layer == "sample"
    assert definition.production_blocked is True


def test_capability_packs_follow_base_layer_conventions() -> None:
    """能力包必须跟基座的既有约定一致，不能自成一套。

    这两条都是复盘时真踩到的：样例模块曾经手写 service（基座 14 个域里 12 个
    继承 RepositoryBase）、曾经返回裸 dict（21 个内置 endpoint 文件无一例外
    用 SuccessResponse）。样例是新模块要照抄的模板，偏离会随每个新模块扩散。
    """
    import inspect
    from pathlib import Path

    from app.core.capability_registry import discover_capabilities
    from app.infrastructure.repository import RepositoryBase

    backend_root = Path(__file__).resolve().parents[1]
    definitions = discover_capabilities()
    assert definitions, "至少要能发现样例能力包，否则这条检查是空转"

    for definition in definitions:
        package_dir = backend_root / "app" / "capabilities" / definition.code

        service_path = package_dir / "service.py"
        if service_path.exists():
            module = importlib.import_module(f"app.capabilities.{definition.code}.service")
            services = [
                obj
                for _, obj in inspect.getmembers(module, inspect.isclass)
                if obj.__module__ == module.__name__ and obj.__name__.endswith("Service")
            ]
            assert services, f"{definition.code}: 没找到 Service 类"
            for service in services:
                assert issubclass(service, RepositoryBase), (
                    f"{definition.code}.{service.__name__} 必须继承 RepositoryBase"
                    "（软删除过滤与分页都在基类里）"
                )

        api_path = package_dir / "api.py"
        if api_path.exists():
            source = api_path.read_text(encoding="utf-8")
            assert '"success": True' not in source, (
                f"{definition.code}: 端点不许手动拼 dict，统一用 SuccessResponse"
            )
