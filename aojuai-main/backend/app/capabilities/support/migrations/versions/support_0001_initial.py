"""create the support ticket tables

Revision ID: support_0001
Revises: None

能力包的迁移链是**独立**的：`down_revision=None`，写自己的 version table
（`alembic_version_cap_support`）。不挂在 core 链上——挂上去就意味着"不装也建表"。

只建表。菜单 / 权限 / 模块开关一律不在迁移里写：那三条链路走
`app/capabilities/support/seed.py` 的同一个 reconciler。

双方言：JSON 列用 `sa.JSON().with_variant(JSONB, 'postgresql')`，时间列用
`sa.DateTime(timezone=True)`（SQLite 侧由 PortableDateTime 在应用层补 tzinfo），
部分唯一索引同时给 `postgresql_where` 与 `sqlite_where`。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "support_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "cap_support_tickets",
        # PortablePK：PostgreSQL 用 BIGINT；SQLite 只有 INTEGER PRIMARY KEY 才是可靠的 ROWID 自增。
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="Tenant ID"),
        sa.Column("ticket_no", sa.String(length=40), nullable=True),
        sa.Column("requester_user_id", sa.BigInteger(), nullable=False),
        sa.Column("assignee_user_id", sa.BigInteger(), nullable=True),
        sa.Column("category", sa.String(length=32), server_default="other", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="open", nullable=False),
        sa.Column("priority", sa.String(length=20), server_default="normal", nullable=False),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("related_type", sa.String(length=40), nullable=True),
        sa.Column("related_id", sa.String(length=80), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_replied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("extra", _JSON, server_default="{}", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        comment="Support capability tickets",
    )
    op.create_index("ix_cap_support_tickets_tenant_id", "cap_support_tickets", ["tenant_id"])
    op.create_index("ix_cap_support_tickets_ticket_no", "cap_support_tickets", ["ticket_no"])
    op.create_index(
        "ix_cap_support_tickets_requester_user_id", "cap_support_tickets", ["requester_user_id"]
    )
    op.create_index(
        "ix_cap_support_tickets_assignee_user_id", "cap_support_tickets", ["assignee_user_id"]
    )
    op.create_index("ix_cap_support_tickets_category", "cap_support_tickets", ["category"])
    op.create_index("ix_cap_support_tickets_status", "cap_support_tickets", ["status"])
    op.create_index("ix_cap_support_tickets_priority", "cap_support_tickets", ["priority"])
    op.create_index("ix_cap_support_tickets_related_type", "cap_support_tickets", ["related_type"])
    op.create_index("ix_cap_support_tickets_related_id", "cap_support_tickets", ["related_id"])
    op.create_index(
        "ix_cap_support_tickets_last_message_at", "cap_support_tickets", ["last_message_at"]
    )
    op.create_index(
        "ix_cap_support_tickets_tenant_status", "cap_support_tickets", ["tenant_id", "status"]
    )
    op.create_index(
        "ix_cap_support_tickets_tenant_requester",
        "cap_support_tickets",
        ["tenant_id", "requester_user_id"],
    )
    op.create_index(
        "ix_cap_support_tickets_tenant_assignee",
        "cap_support_tickets",
        ["tenant_id", "assignee_user_id", "status"],
    )
    op.create_index(
        "uq_cap_support_tickets_tenant_ticket_no",
        "cap_support_tickets",
        ["tenant_id", "ticket_no"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND ticket_no IS NOT NULL"),
        sqlite_where=sa.text("deleted_at IS NULL AND ticket_no IS NOT NULL"),
    )

    op.create_table(
        "cap_support_ticket_messages",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="Tenant ID"),
        sa.Column("ticket_id", sa.BigInteger(), nullable=False),
        sa.Column("author_user_id", sa.BigInteger(), nullable=True),
        sa.Column("author_role", sa.String(length=20), server_default="user", nullable=False),
        sa.Column("message_type", sa.String(length=24), server_default="reply", nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "is_internal", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("attachments", _JSON, server_default="[]", nullable=False),
        sa.Column("extra", _JSON, server_default="{}", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["ticket_id"], ["cap_support_tickets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="Support capability ticket messages",
    )
    op.create_index(
        "ix_cap_support_ticket_messages_tenant_id", "cap_support_ticket_messages", ["tenant_id"]
    )
    op.create_index(
        "ix_cap_support_ticket_messages_ticket_id", "cap_support_ticket_messages", ["ticket_id"]
    )
    op.create_index(
        "ix_cap_support_ticket_messages_author_user_id",
        "cap_support_ticket_messages",
        ["author_user_id"],
    )
    op.create_index(
        "ix_cap_support_ticket_messages_is_internal",
        "cap_support_ticket_messages",
        ["is_internal"],
    )
    op.create_index(
        "ix_cap_support_messages_tenant_ticket",
        "cap_support_ticket_messages",
        ["tenant_id", "ticket_id"],
    )
    op.create_index(
        "ix_cap_support_messages_tenant_author",
        "cap_support_ticket_messages",
        ["tenant_id", "author_user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_cap_support_messages_tenant_author", table_name="cap_support_ticket_messages"
    )
    op.drop_index(
        "ix_cap_support_messages_tenant_ticket", table_name="cap_support_ticket_messages"
    )
    op.drop_index(
        "ix_cap_support_ticket_messages_is_internal", table_name="cap_support_ticket_messages"
    )
    op.drop_index(
        "ix_cap_support_ticket_messages_author_user_id", table_name="cap_support_ticket_messages"
    )
    op.drop_index(
        "ix_cap_support_ticket_messages_ticket_id", table_name="cap_support_ticket_messages"
    )
    op.drop_index(
        "ix_cap_support_ticket_messages_tenant_id", table_name="cap_support_ticket_messages"
    )
    op.drop_table("cap_support_ticket_messages")

    op.drop_index("uq_cap_support_tickets_tenant_ticket_no", table_name="cap_support_tickets")
    op.drop_index("ix_cap_support_tickets_tenant_assignee", table_name="cap_support_tickets")
    op.drop_index("ix_cap_support_tickets_tenant_requester", table_name="cap_support_tickets")
    op.drop_index("ix_cap_support_tickets_tenant_status", table_name="cap_support_tickets")
    op.drop_index("ix_cap_support_tickets_last_message_at", table_name="cap_support_tickets")
    op.drop_index("ix_cap_support_tickets_related_id", table_name="cap_support_tickets")
    op.drop_index("ix_cap_support_tickets_related_type", table_name="cap_support_tickets")
    op.drop_index("ix_cap_support_tickets_priority", table_name="cap_support_tickets")
    op.drop_index("ix_cap_support_tickets_status", table_name="cap_support_tickets")
    op.drop_index("ix_cap_support_tickets_category", table_name="cap_support_tickets")
    op.drop_index("ix_cap_support_tickets_assignee_user_id", table_name="cap_support_tickets")
    op.drop_index("ix_cap_support_tickets_requester_user_id", table_name="cap_support_tickets")
    op.drop_index("ix_cap_support_tickets_ticket_no", table_name="cap_support_tickets")
    op.drop_index("ix_cap_support_tickets_tenant_id", table_name="cap_support_tickets")
    op.drop_table("cap_support_tickets")
