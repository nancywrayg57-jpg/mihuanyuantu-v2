"""Capability discovery / install contract for realphotos."""

from __future__ import annotations

from app.core import feature_switches
from app.core.capability_registry import capability_by_code, discover_capabilities
from app.core.worker_registry import clear_worker_caches, worker_by_code


def test_realphotos_capability_is_discoverable() -> None:
    codes = {item.code for item in discover_capabilities()}
    assert "realphotos" in codes
    cap = capability_by_code("realphotos")
    assert cap is not None
    assert cap.api_prefix == "/realphotos"
    assert cap.version_table == "alembic_version_cap_realphotos"
    assert cap.layer == "pack"
    assert cap.default_enabled is False
    assert cap.production_blocked is False


def test_realphotos_worker_declared_and_gated_by_install() -> None:
    clear_worker_caches()
    feature_switches.settings.AOJ_ENABLED_MODULES = "none"
    feature_switches.clear_module_install_caches()
    assert worker_by_code("realphotos_heartbeat") is not None
    assert all(w.code != "realphotos_heartbeat" for w in feature_switches_installed_workers())

    feature_switches.settings.AOJ_ENABLED_MODULES = "realphotos"
    feature_switches.clear_module_install_caches()
    clear_worker_caches()
    from app.core.worker_registry import installed_workers

    assert any(w.code == "realphotos_heartbeat" for w in installed_workers())

    feature_switches.settings.AOJ_ENABLED_MODULES = ""
    feature_switches.clear_module_install_caches()
    clear_worker_caches()


def feature_switches_installed_workers():
    from app.core.worker_registry import installed_workers

    return installed_workers()


def test_permission_prefix_maps_to_realphotos_module() -> None:
    feature_switches.settings.AOJ_ENABLED_MODULES = "realphotos"
    feature_switches.clear_module_install_caches()
    assert feature_switches.resolve_module_from_permission("realphotos:wallet:read") == "realphotos"
    feature_switches.settings.AOJ_ENABLED_MODULES = ""
    feature_switches.clear_module_install_caches()
