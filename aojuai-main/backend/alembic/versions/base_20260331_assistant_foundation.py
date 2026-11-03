"""add assistant foundation tables

Revision ID: base_20260331_assistant_foundation
Revises: base_20260330_invitation_admin_menu
Create Date: 2026-03-31

说明：
- 为 nextjs-base 引入可插拔 AI 助手底座的规范化表结构
- 保留 tenant.config.assistant 作为兼容兜底读取来源
- 新增 canonical tables:
  - assistant_tenant_configs
  - assistant_sessions
  - assistant_messages
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "base_20260331_assistant_foundation"
down_revision: Union[str, None] = "base_20260330_invitation_admin_menu"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "assistant_tenant_configs",
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False, comment="是否启用 AI 助手"),
        sa.Column("deduct_credits", sa.Boolean(), server_default=sa.text("false"), nullable=False, comment="是否扣除积分"),
        sa.Column("credits_per_call", sa.Integer(), server_default="1", nullable=False, comment="每次调用扣除积分数"),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
            comment="Non-secret configuration (JSONB)",
        ),
        sa.Column(
            "secrets",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
            comment="Secret configuration (JSONB)",
        ),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="Tenant ID"),
        sa.PrimaryKeyConstraint("id"),
        comment="租户 AI 助手配置表",
    )
    op.create_index(
        "ix_assistant_tenant_configs_tenant_id",
        "assistant_tenant_configs",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "uq_assistant_tenant_configs_tenant",
        "assistant_tenant_configs",
        ["tenant_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "assistant_sessions",
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="用户ID"),
        sa.Column("module_code", sa.String(length=50), nullable=False, comment="模块标识"),
        sa.Column("route_path", sa.String(length=255), nullable=False, comment="当前路由"),
        sa.Column(
            "context_data",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
            comment="上下文数据",
        ),
        sa.Column("agent_app_id", sa.BigInteger(), nullable=True, comment="关联的 Agent 应用 ID"),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="Tenant ID"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        comment="AI 助手会话表",
    )
    op.create_index("ix_assistant_sessions_tenant_id", "assistant_sessions", ["tenant_id"], unique=False)
    op.create_index("ix_assistant_sessions_user_id", "assistant_sessions", ["user_id"], unique=False)
    op.create_index("ix_assistant_sessions_module_code", "assistant_sessions", ["module_code"], unique=False)

    op.create_table(
        "assistant_messages",
        sa.Column("session_id", sa.BigInteger(), nullable=False, comment="会话ID"),
        sa.Column("role", sa.String(length=20), nullable=False, comment="消息角色: user/assistant/system"),
        sa.Column("content", sa.Text(), nullable=False, comment="消息内容"),
        sa.Column("action_type", sa.String(length=50), nullable=True, comment="操作类型"),
        sa.Column(
            "action_result",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="操作结果",
        ),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="Tenant ID"),
        sa.ForeignKeyConstraint(["session_id"], ["assistant_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
        comment="AI 助手消息表",
    )
    op.create_index("ix_assistant_messages_tenant_id", "assistant_messages", ["tenant_id"], unique=False)
    op.create_index("ix_assistant_messages_session_id", "assistant_messages", ["session_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_assistant_messages_session_id", table_name="assistant_messages")
    op.drop_index("ix_assistant_messages_tenant_id", table_name="assistant_messages")
    op.drop_table("assistant_messages")

    op.drop_index("ix_assistant_sessions_module_code", table_name="assistant_sessions")
    op.drop_index("ix_assistant_sessions_user_id", table_name="assistant_sessions")
    op.drop_index("ix_assistant_sessions_tenant_id", table_name="assistant_sessions")
    op.drop_table("assistant_sessions")

    op.drop_index("uq_assistant_tenant_configs_tenant", table_name="assistant_tenant_configs")
    op.drop_index("ix_assistant_tenant_configs_tenant_id", table_name="assistant_tenant_configs")
    op.drop_table("assistant_tenant_configs")
