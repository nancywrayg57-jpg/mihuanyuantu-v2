"""
API Key 数据模型（机器凭证，供本地同步客户端等非浏览器端使用）

- 明文 key 只在创建时返回一次，库中仅存 SHA-256 哈希
- scopes 为允许访问的 API 路径前缀列表（PortableJSON），空列表表示不限制
"""
from datetime import datetime

from sqlalchemy import text, BigInteger, Index, String
from app.infrastructure.database.types import PortableDateTime, PortableJSON
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import TenantBaseModel


class ApiKey(TenantBaseModel):
    """API Key"""
    __tablename__ = "api_keys"

    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="属主用户ID")
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="用途名称")
    key_prefix: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="明文前缀(仅用于列表展示识别)"
    )
    key_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="SHA-256(明文key)"
    )
    scopes: Mapped[list[str]] = mapped_column(
        PortableJSON, nullable=False, default=list, server_default=text("'[]'"),
        comment="允许的 API 路径前缀列表；空=不限制",
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        PortableDateTime(), nullable=True, comment="过期时间(空=永不过期)"
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        PortableDateTime(), nullable=True, comment="最近使用时间"
    )

    __table_args__ = (
        Index(
            "uq_api_keys_key_hash",
            "key_hash",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index("ix_api_keys_tenant_user", "tenant_id", "user_id"),
        {"comment": "API Key 表"},
    )
