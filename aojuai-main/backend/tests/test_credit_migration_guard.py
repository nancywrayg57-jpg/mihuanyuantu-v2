from app.core.exceptions import BusinessError
from app.domain.credits.migration_guard import raise_if_credits_schema_not_upgraded


def test_raise_if_credits_schema_not_upgraded_detects_missing_idempotency_key() -> None:
    try:
        raise_if_credits_schema_not_upgraded(
            Exception(
                '(sqlalchemy.dialects.postgresql.asyncpg.ProgrammingError) '
                "<class 'asyncpg.exceptions.UndefinedColumnError'>: "
                "column credit_transactions.idempotency_key does not exist"
            )
        )
    except BusinessError as exc:
        assert exc.code == "DB_MIGRATION_REQUIRED"
        assert "credit_transactions.idempotency_key" in exc.message
        assert exc.details["requiredRevision"] == "plugins_20260411_credit_transaction_idempotency"
    else:
        raise AssertionError("Expected BusinessError")
