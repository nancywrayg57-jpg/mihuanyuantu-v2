"""support 能力包的装/卸合同。

要证明的不是"关掉之后访问被拒绝"，而是**未安装时那条路由压根不存在**：
路由不进 route table（404 而不是 403，403 会泄漏"这里有功能但关了"）、
连 HTTP 适配层都不 import、表由独立迁移链管理所以不装就不建。
"""

from __future__ import annotations

import importlib
import sys

import pytest
from fastapi import APIRouter

from app.api import v1
from app.capabilities.support import CAPABILITY
from app.core import feature_switches
from app.core.capability_registry import discover_capabilities

CODE = "support"
API_MODULE = "app.capabilities.support.api"


def _install(codes: str) -> None:
    feature_switches.settings.AOJ_ENABLED_MODULES = codes
    feature_switches.clear_module_install_caches()


def test_declaration_is_a_deployable_pack() -> None:
    assert CAPABILITY.code == CODE
    assert CAPABILITY.layer == "pack"
    # 真实可选包，不是样例：不能带发布阻断标记。
    assert CAPABILITY.production_blocked is False
    assert CAPABILITY.default_enabled is False
    assert CAPABILITY.version_table == "alembic_version_cap_support"
    assert CAPABILITY.route_prefixes == ("/support",)
    assert CAPABILITY.api_prefix == "/support"
    assert CAPABILITY.permission_prefixes == ("support",)
    # 第一个真实 pack 才会踩到的坑：模块开关列表只翻译 system./common./auth. 开头的键，
    # 不声明这两个 key，en/es 下的模块目录就漏中文。
    assert CAPABILITY.label_key.startswith("system.")
    assert CAPABILITY.description_key.startswith("system.")


def test_capability_is_discovered_and_installation_is_deployment_controlled() -> None:
    """安装是**部署**决定，租户开关是另一层。

    `AOJ_ENABLED_MODULES` 留空是 base 的 legacy「全装」语义（`public_site` 也一样），
    所以包会被视为已安装；但 `default_enabled=False` 保证租户侧仍然默认关着。
    真正的"不装"是显式 `none`，或把它从 allowlist 里去掉。
    """
    assert CODE in {definition.code for definition in discover_capabilities()}

    _install("none")
    assert feature_switches.is_module_installed(CODE) is False

    _install("speech")
    assert feature_switches.is_module_installed(CODE) is False, "allowlist 没点名就不该装上"

    _install(CODE)
    assert feature_switches.is_module_installed(CODE) is True
    assert feature_switches.MODULE_SWITCH_DEFAULTS[CODE] is False, (
        "装上之后租户仍要显式打开：可选包不许默认开"
    )


def test_uninstalled_router_is_not_registered_and_never_imported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install("none")
    monkeypatch.delitem(sys.modules, API_MODULE, raising=False)
    monkeypatch.setattr(v1, "api_router", APIRouter())

    registered = v1.register_discovered_capability_routers()

    assert CODE not in registered
    assert API_MODULE not in sys.modules, "未安装的能力包连 HTTP 适配层都不该被 import"


def test_installed_router_exposes_the_pack_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(CODE)
    router = APIRouter()
    monkeypatch.setattr(v1, "api_router", router)

    registered = v1.register_discovered_capability_routers()

    assert CODE in registered
    paths = {getattr(route, "path", "") for route in router.routes}
    assert "/support/tickets" in paths
    assert "/support/admin/tickets" in paths
    assert "/support/public/tickets" in paths


def test_uninstalled_pack_disappears_from_the_catalog() -> None:
    _install("none")
    codes = {item["code"] for item in feature_switches.list_module_catalog()}
    assert CODE not in codes

    _install(CODE)
    entry = next(
        item
        for item in feature_switches.list_module_catalog()
        if item["code"] == CODE
    )
    assert entry["layer"] == "pack"
    assert entry["defaultEnabled"] is False
    assert entry["routePrefixes"] == ["/support"]


def test_migration_chain_is_independent_from_core() -> None:
    initial = importlib.import_module(
        "app.capabilities.support.migrations.versions.support_0001_initial"
    )
    assert initial.down_revision is None, (
        "能力包的迁移链不能挂到 core 链上，否则不装也会建表"
    )
    assert CAPABILITY.version_table != "alembic_version"


def test_pack_tables_are_invisible_to_core_autogenerate() -> None:
    """`cap_` 前缀是硬约定：换个前缀，核心链第一次 autogenerate 就会 DROP 掉这两张表。"""
    from app.core import module_manifest

    from app.capabilities.support.models import SupportTicket, SupportTicketMessage

    for model in (SupportTicket, SupportTicketMessage):
        assert model.__tablename__.startswith(module_manifest.CAPABILITY_TABLE_PREFIX)
        assert module_manifest.is_unmanaged_table(model.__tablename__) is True


def test_purge_refuses_while_the_pack_is_still_installed() -> None:
    """卸载是显式动作：还装着就拒绝销毁数据，避免"改错开关顺手删库"。"""
    from scripts import capability

    _install(CODE)
    with pytest.raises(RuntimeError, match="still installed"):
        capability.purge_database(CODE, purge=True)


def test_purge_requires_the_explicit_acknowledgement() -> None:
    from scripts import capability

    _install("none")
    with pytest.raises(RuntimeError, match="refusing destructive downgrade"):
        capability.purge_database(CODE, purge=False)
