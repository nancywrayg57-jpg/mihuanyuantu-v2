from pathlib import Path

import pytest

from governance_tools.alembic_checks import scan_single_alembic_head
from governance_tools.common import assert_clean


def test_gov_13_repository_has_exactly_one_alembic_head(backend_root: Path) -> None:
    result = scan_single_alembic_head(backend_root)
    assert result.discovered
    assert_clean(result)


def test_gov_13_mutation_two_heads_makes_target_assertion_red(tmp_path: Path) -> None:
    backend = tmp_path / "backend"
    versions = backend / "alembic" / "versions"
    versions.mkdir(parents=True)
    (backend / "alembic.ini").write_text("[alembic]\nscript_location = alembic\n", encoding="utf-8")
    (versions / "head_a.py").write_text('revision = "head_a"\ndown_revision = None\n', encoding="utf-8")
    (versions / "head_b.py").write_text('revision = "head_b"\ndown_revision = None\n', encoding="utf-8")

    result = scan_single_alembic_head(backend)

    with pytest.raises(AssertionError, match="expected exactly one Alembic head"):
        assert_clean(result)
