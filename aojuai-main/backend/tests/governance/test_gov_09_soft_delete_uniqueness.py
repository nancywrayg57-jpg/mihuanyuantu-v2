from pathlib import Path

import pytest
from sqlalchemy import DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from governance_tools.common import assert_clean
from governance_tools.soft_delete_uniqueness import scan_soft_delete_uniqueness


def test_gov_09_repository_business_uniqueness_is_partial(backend_root: Path) -> None:
    result = scan_soft_delete_uniqueness(backend_root)
    assert result.discovered
    assert_clean(result)


def test_gov_09_mutation_unique_constraint_makes_target_assertion_red() -> None:
    class MutationBase(DeclarativeBase):
        pass

    class BadWidget(MutationBase):
        __tablename__ = "gov_mutation_unique_constraint"
        __table_args__ = (UniqueConstraint("code", name="uq_gov_mutation_code"),)

        id: Mapped[int] = mapped_column(Integer, primary_key=True)
        deleted_at: Mapped[object | None] = mapped_column(DateTime(), nullable=True)
        code: Mapped[str] = mapped_column(String(20), nullable=False)

    result = scan_soft_delete_uniqueness(registry=MutationBase.registry, allowlist={})

    with pytest.raises(AssertionError, match="unique without postgresql_where"):
        assert_clean(result)


def test_gov_09_mutation_unique_index_makes_target_assertion_red() -> None:
    class MutationBase(DeclarativeBase):
        pass

    class BadWidget(MutationBase):
        __tablename__ = "gov_mutation_unique_index"
        __table_args__ = (Index("ix_gov_mutation_code", "code", unique=True),)

        id: Mapped[int] = mapped_column(Integer, primary_key=True)
        deleted_at: Mapped[object | None] = mapped_column(DateTime(), nullable=True)
        code: Mapped[str] = mapped_column(String(20), nullable=False)

    result = scan_soft_delete_uniqueness(registry=MutationBase.registry, allowlist={})

    with pytest.raises(AssertionError, match="unique without postgresql_where"):
        assert_clean(result)
