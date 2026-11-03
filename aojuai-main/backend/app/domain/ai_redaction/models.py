from __future__ import annotations

from typing import Any

from sqlalchemy import BigInteger, Boolean, Index, Integer, String, Text, false, text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import BaseModel
from app.infrastructure.database.types import PortableJSON

#: 租户通用策略的 scope：实体类别、白名单、守卫姿态等与具体模块无关的口径
SHARED_SCOPE = "*"


class TenantRedactionPolicy(BaseModel):
    """出云脱敏策略（版本化、只追加）。审计要能回答"当时按哪套规则脱的敏"，所以旧版本永不删除。

    设计见 `docs/dev/reference/LLM_OUTBOUND_REDACTION.md` §5。
    """

    __tablename__ = "tenant_redaction_policies"
    __table_args__ = (
        Index(
            "uq_tenant_redaction_policies_version",
            "tenant_id",
            "scope",
            "version",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index("ix_tenant_redaction_policies_active", "tenant_id", "scope", "is_active"),
        {"comment": "租户级 AI 出站脱敏策略（按 scope 版本化）"},
    )

    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(64), nullable=False, default=SHARED_SCOPE, server_default=SHARED_SCOPE)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    rules: Mapped[dict[str, Any]] = mapped_column(PortableJSON, nullable=False, default=dict, server_default=text("'{}'"))
    approved_by: Mapped[str] = mapped_column(String(64), nullable=False, default="", server_default="")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
