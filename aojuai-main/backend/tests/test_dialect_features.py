"""SQLite 轻量档的"显式禁用"机制：功能级登记 + 统一拒绝 + 模块级视为未安装 + 目录下发方言信息。"""

from __future__ import annotations

import pytest

from app.core import dialect_features as df
from app.core import feature_switches as fs
from app.core.config import settings
from app.core.exceptions import BusinessError


def test_registered_pg_only_feature_is_unavailable_only_on_sqlite(monkeypatch) -> None:
    monkeypatch.setattr(settings, "DB_DRIVER", "sqlite")
    assert settings.IS_SQLITE
    assert df.is_feature_available("credits.pricing_reconciliation") is False
    assert "credits.pricing_reconciliation" in df.unavailable_features()
    assert df.database_dialect() == "sqlite"

    monkeypatch.setattr(settings, "DB_DRIVER", "postgresql")
    assert df.is_feature_available("credits.pricing_reconciliation") is True
    assert df.unavailable_features() == []


def test_unregistered_feature_is_always_available(monkeypatch) -> None:
    monkeypatch.setattr(settings, "DB_DRIVER", "sqlite")
    assert df.is_feature_available("something.portable") is True


def test_require_postgresql_dependency_rejects_with_stable_code(monkeypatch) -> None:
    dep = df.require_postgresql("credits.pricing_reconciliation")
    monkeypatch.setattr(settings, "DB_DRIVER", "postgresql")
    dep()  # PG：放行
    monkeypatch.setattr(settings, "DB_DRIVER", "sqlite")
    with pytest.raises(BusinessError) as excinfo:
        dep()
    assert excinfo.value.code == "FEATURE_REQUIRES_POSTGRESQL"
    assert excinfo.value.details["feature"] == "credits.pricing_reconciliation"


def test_require_postgresql_refuses_unregistered_code() -> None:
    with pytest.raises(ValueError):
        df.require_postgresql("not.registered")


def test_pg_only_module_counts_as_uninstalled_on_sqlite(monkeypatch) -> None:
    item = fs.ModuleCatalogItem(code="pgonly_demo", label="demo", description="", requires_postgresql=True)
    monkeypatch.setattr(settings, "DB_DRIVER", "postgresql")
    assert fs._is_catalog_item_installed(item, frozenset({"pgonly_demo"})) is True
    monkeypatch.setattr(settings, "DB_DRIVER", "sqlite")
    assert fs._is_catalog_item_installed(item, frozenset({"pgonly_demo"})) is False


def test_feature_catalog_carries_dialect_but_not_in_digest(monkeypatch) -> None:
    monkeypatch.setattr(settings, "DB_DRIVER", "postgresql")
    pg = fs.build_feature_catalog_definition()
    monkeypatch.setattr(settings, "DB_DRIVER", "sqlite")
    lite = fs.build_feature_catalog_definition()
    assert pg["databaseDialect"] == "postgresql" and lite["databaseDialect"] == "sqlite"
    assert lite["unavailableFeatures"] == ["credits.pricing_reconciliation"]
    assert pg["catalogDigest"] == lite["catalogDigest"], "方言信息不得改变目录 digest"


def test_sqlite_gets_its_own_cache_namespace_by_default(monkeypatch) -> None:
    """轻量档缺省 DB_NAME 常与同机 PG 实例相同，共用 Redis 时会互相投毒：SQLite 按库路径派生命名空间。"""
    monkeypatch.setattr(settings, "AOJU_CACHE_NAMESPACE", "")
    monkeypatch.setattr(settings, "DB_DRIVER", "sqlite")
    assert settings.CACHE_NAMESPACE.startswith("sqlite-")
    monkeypatch.setattr(settings, "DB_DRIVER", "postgresql")
    assert settings.CACHE_NAMESPACE == str(settings.DB_NAME or "aoju")
    monkeypatch.setattr(settings, "AOJU_CACHE_NAMESPACE", "explicit-ns")
    assert settings.CACHE_NAMESPACE == "explicit-ns"

