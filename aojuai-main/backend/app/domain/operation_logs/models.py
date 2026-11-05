"""
AOJU Backend - Operation Log Models

System-level operation logs for auditing critical actions.
"""

from typing import Any

from sqlalchemy import BigInteger, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import TenantBaseModel
from app.infrastructure.database.types import PortableJSON


class OperationLog(TenantBaseModel):
    """
    OperationLog Model - 操作日志

    Multi-tenant isolated system operation logs.
    """

    __tablename__ = "operation_logs"

    user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        index=True,
        comment="Operator user ID (nullable for anonymous actions)",
    )
    username: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="Operator username (denormalized)",
    )

    # Operation info
    module: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Module name (e.g., auth, users, roles)",
    )
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Action type (e.g., login, create, update, delete)",
    )
    target_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Target type (e.g., User, Role)",
    )
    target_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        index=True,
        comment="Target ID",
    )

    # Request info
    method: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        comment="HTTP method (GET/POST/PUT/DELETE)",
    )
    path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Request path",
    )
    ip: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Client IP",
    )
    user_agent: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="User-Agent",
    )

    # Result info
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment='Status: "success" | "failure"',
    )
    status_code: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="HTTP status code",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error message (on failure)",
    )

    # Details
    request_data: Mapped[dict[str, Any] | None] = mapped_column(
        PortableJSON,
        nullable=True,
        comment="Request payload (JSONB, sanitized)",
    )
    response_data: Mapped[dict[str, Any] | None] = mapped_column(
        PortableJSON,
        nullable=True,
        comment="Response payload (JSONB, optional)",
    )
    duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Duration in milliseconds",
    )
    extra: Mapped[dict[str, Any]] = mapped_column(
        PortableJSON,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Extra attributes (JSONB)",
    )

