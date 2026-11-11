"""AD-005 / §6.2：复制处理账号执行门闩（路径 A：guard_epoch）。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import TenantBaseModel
from app.infrastructure.database.types import PortableDateTime


class RealphotosCopyExecutionGuard(TenantBaseModel):
    """每账号最多一个有效复制批次；不修改余额或冻结额。"""

    __tablename__ = "cap_realphotos_copy_execution_guards"
    __table_args__ = (
        Index(
            "uq_cap_realphotos_copy_guard_active_owner",
            "tenant_id",
            "owner_account_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND state = 'active'"),
            sqlite_where=text("deleted_at IS NULL AND state = 'active'"),
        ),
        Index(
            "ix_cap_realphotos_copy_guard_batch",
            "tenant_id",
            "batch_id",
        ),
        {"comment": "realphotos copy execution guards (AD-005)"},
    )

    owner_account_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    guard_epoch: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    state: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active", server_default="active"
    )
    lease_until: Mapped[datetime | None] = mapped_column(PortableDateTime(), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
