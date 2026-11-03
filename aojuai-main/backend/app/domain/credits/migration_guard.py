"""
Credits DB migration guard.

Convert known missing-column runtime errors into actionable BusinessError
messages so user-facing pages do not expose raw SQLAlchemy/asyncpg errors.
"""

from __future__ import annotations

from app.core.exceptions import BusinessError


def raise_if_credits_schema_not_upgraded(exc: Exception) -> None:
    msg = str(exc) or ""
    if "does not exist" not in msg and "UndefinedColumnError" not in msg:
        return

    missing: list[str] = []

    if "credit_transactions.idempotency_key" in msg or (
        "credit_transactions" in msg and "idempotency_key" in msg
    ):
        missing.append("credit_transactions.idempotency_key")

    if not missing:
        return

    missing_text = ", ".join(sorted(set(missing)))
    raise BusinessError(
        code="DB_MIGRATION_REQUIRED",
        message=(
            f"数据库未升级（缺少字段: {missing_text}）。"
            "请在后端执行数据库迁移：`cd backend && alembic upgrade head`"
            "（至少包含 plugins_20260411_credit_transaction_idempotency）后重试。"
            "当前服务也会在启动时尝试自动补齐该字段；若仍报错，请检查数据库账号是否具备 ALTER TABLE / CREATE INDEX 权限。"
        ),
        details={
            "missingColumns": sorted(set(missing)),
            "requiredRevision": "plugins_20260411_credit_transaction_idempotency",
        },
    )
