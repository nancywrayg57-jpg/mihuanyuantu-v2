from __future__ import annotations

from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.capabilities.sample_items import CAPABILITY
from app.capabilities.sample_items.models import SampleItem


def migration_source() -> str:
    return (CAPABILITY.migration_path() / "versions" / "sample_items_0001_initial.py").read_text(encoding="utf-8")


def assert_source_contract(source: str) -> None:
    assert 'sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True)' in source
    assert 'unique=True,\n        postgresql_where=sa.text("deleted_at IS NULL")' in source
    assert "reconcile_menu_declaration" not in source
    assert "AOJ_ENABLED_MODULES" not in source
    assert "create_all" not in source


def test_migration_schema_contract_is_mutation_sensitive() -> None:
    source = migration_source()
    assert_source_contract(source)

    bad_updated_at = source.replace(
        'sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True)',
        'sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False)',
    )
    with pytest.raises(AssertionError):
        assert_source_contract(bad_updated_at)

    bad_unique = source.replace(
        '        postgresql_where=sa.text("deleted_at IS NULL"),\n',
        "",
    )
    with pytest.raises(AssertionError):
        assert_source_contract(bad_unique)

    assert_source_contract(source)


def test_migration_chain_has_one_independent_head_and_detects_extra_head(
    tmp_path: Path,
) -> None:
    config = Config()
    config.set_main_option("script_location", str(CAPABILITY.migration_path()))
    script = ScriptDirectory.from_config(config)

    assert script.get_bases() == ["sample_items_0001"]
    assert script.get_heads() == ["sample_items_0001"]
    assert script.get_revision("sample_items_0001").down_revision is None

    copied = tmp_path / "migrations"
    versions = copied / "versions"
    versions.mkdir(parents=True)
    (copied / "env.py").write_text("", encoding="utf-8")
    (versions / "head_a.py").write_text('revision = "a"\ndown_revision = None\n', encoding="utf-8")
    (versions / "head_b.py").write_text('revision = "b"\ndown_revision = None\n', encoding="utf-8")
    bad_config = Config()
    bad_config.set_main_option("script_location", str(copied))
    bad_script = ScriptDirectory.from_config(bad_config)
    with pytest.raises(AssertionError):
        assert len(bad_script.get_heads()) == 1
    assert script.get_heads() == ["sample_items_0001"]


def test_model_business_uniqueness_is_partial_and_updated_at_nullable() -> None:
    assert SampleItem.__table__.c.updated_at.nullable is True
    unique_indexes = [index for index in SampleItem.__table__.indexes if index.unique]
    assert len(unique_indexes) == 1
    where = unique_indexes[0].dialect_options["postgresql"].get("where")
    assert where is not None
    assert "deleted_at IS NULL" in str(where)
