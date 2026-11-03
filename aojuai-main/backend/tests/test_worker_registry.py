"""Worker 声明与发现的契约。

最重要的一条是**模块没装就不该启动它的 worker**——否则会出现
"路由没挂载、菜单没有，但后台有个进程在轮询它的表"这种荒唐状态。
这与路由挂载用的是同一个判据（`is_module_installed`），不能各判各的。
"""

from __future__ import annotations

import pytest

from app.core import feature_switches
from app.core.worker_registry import (
    WorkerDefinition,
    clear_worker_caches,
    discover_workers,
    installed_workers,
    resolve_concurrency,
    worker_by_code,
)


@pytest.fixture(autouse=True)
def _reset_caches():
    clear_worker_caches()
    feature_switches.clear_module_install_caches()
    yield
    clear_worker_caches()
    feature_switches.clear_module_install_caches()


def test_sample_worker_is_discovered() -> None:
    codes = {item.code for item in discover_workers()}
    assert "sample_items_review" in codes, "样例 worker 是给新模块照抄的模板，不能丢"


def test_worker_of_an_uninstalled_module_is_not_started() -> None:
    feature_switches.settings.AOJ_ENABLED_MODULES = "none"
    feature_switches.clear_module_install_caches()
    assert discover_workers(), "声明仍在"
    assert installed_workers() == (), "模块没装时不该有任何 worker 被认为该启动"


def test_worker_of_an_installed_module_is_started() -> None:
    feature_switches.settings.AOJ_ENABLED_MODULES = "sample_items"
    feature_switches.clear_module_install_caches()
    codes = {item.code for item in installed_workers()}
    assert "sample_items_review" in codes


def test_concurrency_is_capped_by_the_declaration() -> None:
    """并发上限由声明给，不能被配置顶穿——一个 worker 起 50 个槽会打满连接池。"""
    definition = worker_by_code("sample_items_review")
    assert definition is not None
    original = feature_switches.settings.AOJ_WORKER_CONCURRENCY
    try:
        feature_switches.settings.AOJ_WORKER_CONCURRENCY = "sample_items_review:999"
        assert resolve_concurrency(definition) == definition.max_concurrency
        feature_switches.settings.AOJ_WORKER_CONCURRENCY = "sample_items_review:3"
        assert resolve_concurrency(definition) == 3
    finally:
        feature_switches.settings.AOJ_WORKER_CONCURRENCY = original


def test_concurrency_config_is_one_generic_field_not_one_per_worker() -> None:
    """加一个 worker 不该需要改 Settings。

    第一版把并发度设计成"每个 worker 一个 Settings 字段"，但 Settings 是 pydantic
    模型、拒绝未声明字段——于是那个字段永远取不到值，等于并发度根本没法配。
    测试当场就抓到了。现在统一走 AOJ_WORKER_CONCURRENCY 这一个映射字段。
    """
    from app.core.worker_registry import parse_concurrency_map

    assert parse_concurrency_map("a:2, b:4") == {"a": 2, "b": 4}
    # 单个条目写错不该让整份配置失效
    assert parse_concurrency_map("a:2,坏条目,b:x,c:3") == {"a": 2, "c": 3}
    assert parse_concurrency_map("") == {}
    assert parse_concurrency_map(None) == {}


def test_factory_path_must_be_module_colon_attr() -> None:
    """工厂路径写成字符串是为了发现阶段不 import 业务代码，格式错了要当场报错。"""
    with pytest.raises(ValueError, match="task_source_factory"):
        WorkerDefinition(
            code="bad",
            label="bad",
            task_source_factory="app.capabilities.x.worker.build",  # 少了冒号
        ).validate(source="test")


def test_declaration_rejects_inverted_concurrency_bounds() -> None:
    with pytest.raises(ValueError, match="max_concurrency"):
        WorkerDefinition(
            code="bad",
            label="bad",
            task_source_factory="a.b:c",
            default_concurrency=5,
            max_concurrency=2,
        ).validate(source="test")


def test_manifest_matches_the_registry() -> None:
    """导出的清单必须与声明一致，否则运维侧起的和代码里声明的是两回事。"""
    from scripts.export_worker_manifest import build_manifest

    manifest = build_manifest(installed_only=False)
    assert {item["code"] for item in manifest["workers"]} == {
        item.code for item in discover_workers()
    }
