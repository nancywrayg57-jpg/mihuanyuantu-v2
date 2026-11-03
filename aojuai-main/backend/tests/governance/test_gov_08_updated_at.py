from pathlib import Path

import pytest

from governance_tools.alembic_checks import scan_updated_at_nullability
from governance_tools.common import assert_clean


def test_gov_08_all_migration_upgrades_keep_updated_at_nullable(backend_root: Path) -> None:
    result = scan_updated_at_nullability(backend_root)
    assert result.discovered
    assert_clean(result)


def test_gov_08_mutation_add_non_null_updated_at_makes_target_assertion_red(tmp_path: Path) -> None:
    backend = tmp_path / "backend"
    migration = backend / "alembic" / "versions" / "mutation.py"
    migration.parent.mkdir(parents=True)
    migration.write_text(
        "from alembic import op\n"
        "import sqlalchemy as sa\n"
        "def upgrade():\n"
        "    op.add_column('widgets', sa.Column('updated_at', sa.DateTime(), nullable=False))\n",
        encoding="utf-8",
    )

    result = scan_updated_at_nullability(backend)

    with pytest.raises(AssertionError, match='creates "updated_at" with nullable=False'):
        assert_clean(result)
