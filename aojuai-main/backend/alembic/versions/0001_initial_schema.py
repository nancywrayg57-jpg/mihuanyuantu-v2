"""initial schema (squashed)

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-01-28

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --------------------
    # Tenants (system table)
    # --------------------
    op.create_table(
        "tenants",
        sa.Column("name", sa.String(length=100), nullable=False, comment="Tenant name"),
        sa.Column("code", sa.String(length=50), nullable=False, comment="Tenant code (unique identifier)"),
        sa.Column("domain", sa.String(length=255), nullable=True, comment="Custom domain for tenant"),
        sa.Column("description", sa.Text(), nullable=True, comment="Tenant description"),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
            comment="Is tenant active",
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True, comment="Subscription expiry date"),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
            comment="Tenant configuration",
        ),
        sa.Column(
            "quota",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
            comment="Tenant quota limits",
        ),
        sa.Column("contact_name", sa.String(length=100), nullable=True, comment="Contact person name"),
        sa.Column("contact_phone", sa.String(length=20), nullable=True, comment="Contact phone"),
        sa.Column("contact_email", sa.String(length=100), nullable=True, comment="Contact email"),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tenants_code"), "tenants", ["code"], unique=True)

    # --------------------
    # Organizations (tree)
    # NOTE: leader_id FK is added after users are created to break the cycle.
    # --------------------
    op.create_table(
        "organizations",
        sa.Column("name", sa.String(length=100), nullable=False, comment="Organization name"),
        sa.Column("code", sa.String(length=50), nullable=True, comment="Organization code"),
        sa.Column("description", sa.Text(), nullable=True, comment="Organization description"),
        sa.Column("parent_id", sa.BigInteger(), nullable=True, comment="Parent organization ID"),
        sa.Column("path", sa.String(length=500), nullable=True, comment="Materialized path (e.g., '1/2/3')"),
        sa.Column("level", sa.Integer(), server_default="1", nullable=False, comment="Tree level (1 = root)"),
        sa.Column(
            "sort_order",
            sa.Integer(),
            server_default="0",
            nullable=False,
            comment="Sort order within same parent",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
            comment="Is organization active",
        ),
        sa.Column("leader_id", sa.BigInteger(), nullable=True, comment="Team leader user ID"),
        sa.Column(
            "extra",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
            comment="Extra attributes",
        ),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="Tenant ID"),
        sa.ForeignKeyConstraint(["parent_id"], ["organizations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_organizations_leader_id"), "organizations", ["leader_id"], unique=False)
    op.create_index(op.f("ix_organizations_parent_id"), "organizations", ["parent_id"], unique=False)
    op.create_index(op.f("ix_organizations_path"), "organizations", ["path"], unique=False)
    op.create_index(op.f("ix_organizations_tenant_id"), "organizations", ["tenant_id"], unique=False)

    # --------------------
    # Users
    # --------------------
    op.create_table(
        "users",
        sa.Column("username", sa.String(length=50), nullable=False, comment="Login username"),
        sa.Column("password_hash", sa.String(length=255), nullable=False, comment="Hashed password"),
        sa.Column("nickname", sa.String(length=50), nullable=True, comment="Display nickname"),
        sa.Column("avatar", sa.String(length=500), nullable=True, comment="Avatar URL"),
        sa.Column("email", sa.String(length=100), nullable=True, comment="Email address"),
        sa.Column("phone", sa.String(length=20), nullable=True, comment="Phone number"),
        sa.Column(
            "sex",
            sa.Integer(),
            server_default="0",
            nullable=False,
            comment="Sex: 0=unknown, 1=male, 2=female",
        ),
        sa.Column("description", sa.Text(), nullable=True, comment="User bio/description"),
        sa.Column(
            "status",
            sa.Integer(),
            server_default="1",
            nullable=False,
            comment="Status: 0=disabled, 1=enabled, 2=pending, 3=rejected",
        ),
        sa.Column(
            "register_source",
            sa.String(length=50),
            server_default="admin",
            nullable=True,
            comment="Registration source: admin, self, invite",
        ),
        sa.Column("audit_remark", sa.Text(), nullable=True, comment="Audit remark (for approval/rejection)"),
        sa.Column("audited_at", sa.DateTime(timezone=True), nullable=True, comment="Audit timestamp"),
        sa.Column("audited_by", sa.BigInteger(), nullable=True, comment="Audited by user ID"),
        sa.Column(
            "is_superuser",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
            comment="Is superuser (bypass all permissions)",
        ),
        sa.Column("organization_id", sa.BigInteger(), nullable=True, comment="Organization/Team ID"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True, comment="Last login timestamp"),
        sa.Column("last_login_ip", sa.String(length=50), nullable=True, comment="Last login IP address"),
        sa.Column(
            "failed_login_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
            comment="Failed login attempts",
        ),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True, comment="Account locked until this time"),
        sa.Column("remark", sa.Text(), nullable=True, comment="Admin remark"),
        sa.Column(
            "extra",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
            comment="Extra attributes",
        ),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="Tenant ID"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=False)
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=False)
    op.create_index(op.f("ix_users_phone"), "users", ["phone"], unique=False)
    op.create_index(op.f("ix_users_organization_id"), "users", ["organization_id"], unique=False)
    op.create_index(op.f("ix_users_tenant_id"), "users", ["tenant_id"], unique=False)

    # soft-delete aware unique contacts
    op.create_index(
        "uq_users_phone_active",
        "users",
        ["phone"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND phone IS NOT NULL AND phone <> ''"),
    )
    op.create_index(
        "uq_users_email_lower_active",
        "users",
        [sa.text("lower(email)")],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND email IS NOT NULL AND email <> ''"),
    )

    # Add FK for organizations.leader_id now that users exist.
    op.create_foreign_key(
        "fk_organizations_leader_id",
        "organizations",
        "users",
        ["leader_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # --------------------
    # Roles
    # --------------------
    op.create_table(
        "roles",
        sa.Column("name", sa.String(length=50), nullable=False, comment="Role name"),
        sa.Column("created_by", sa.BigInteger(), nullable=True, comment="Created by user ID"),
        sa.Column("code", sa.String(length=50), nullable=False, comment="Role code (e.g., 'admin', 'user')"),
        sa.Column("description", sa.Text(), nullable=True, comment="Role description"),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False, comment="Sort order"),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
            comment="Is role active",
        ),
        sa.Column(
            "is_system",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
            comment="Is system built-in role (cannot be deleted)",
        ),
        sa.Column(
            "data_range",
            sa.Integer(),
            server_default="4",
            nullable=False,
            comment="数据权限范围: 0=仅本人, 1=本团队, 2=本团队及以下, 3=自定义团队, 4=全部",
        ),
        sa.Column(
            "data_permissions",
            sa.Integer(),
            server_default="0",
            nullable=False,
            comment="数据操作权限(位运算: 1=只读, 2=编辑, 4=删除)",
        ),
        sa.Column(
            "extra",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
            comment="Extra attributes",
        ),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="Tenant ID"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_roles_code"), "roles", ["code"], unique=False)
    op.create_index(op.f("ix_roles_tenant_id"), "roles", ["tenant_id"], unique=False)

    # --------------------
    # Menus (dynamic routing + perms)
    # --------------------
    op.create_table(
        "menus",
        sa.Column("title", sa.String(length=100), nullable=False, comment="Display title (菜单名称)"),
        sa.Column("path", sa.String(length=200), nullable=True, comment="Route path (e.g., '/system/user')"),
        sa.Column(
            "component",
            sa.String(length=200),
            nullable=True,
            comment="Component path (e.g., 'views/system/user/index')",
        ),
        sa.Column("redirect", sa.String(length=200), nullable=True, comment="Redirect path"),
        sa.Column("parent_id", sa.BigInteger(), nullable=True, comment="Parent menu ID"),
        sa.Column("level", sa.Integer(), server_default="1", nullable=False, comment="Menu level (1 = top level)"),
        sa.Column("icon", sa.String(length=50), nullable=True, comment="Icon name"),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False, comment="Sort order (order/rank)"),
        sa.Column(
            "menu_type",
            sa.String(length=8),
            server_default="1",
            nullable=False,
            comment="Menu type: 0=directory, 1=menu, 2=button",
        ),
        sa.Column(
            "perms",
            sa.String(length=100),
            nullable=True,
            comment="Permission identifier (e.g., 'user:create', 'auth.menu.list')",
        ),
        sa.Column(
            "is_visible",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
            comment="Show in menu (showLink, opposite of hidden)",
        ),
        sa.Column(
            "is_cache",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
            comment="Enable keep-alive (keepAlive, opposite of noCache)",
        ),
        sa.Column(
            "is_frame",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
            comment="Is iframe/external link",
        ),
        sa.Column("frame_src", sa.String(length=500), nullable=True, comment="Iframe source URL"),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
            comment="Is menu active (opposite of disabled)",
        ),
        sa.Column(
            "no_cache",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
            comment="If true, will not be cached by <keep-alive>",
        ),
        sa.Column(
            "breadcrumb",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
            comment="If false, will not show in breadcrumb",
        ),
        sa.Column(
            "affix",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
            comment="If true, will always be fixed in tag",
        ),
        sa.Column(
            "no_tags_view",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
            comment="If true, will not appear in tag",
        ),
        sa.Column(
            "can_to",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
            comment="If true, can navigate even if hidden",
        ),
        sa.Column(
            "always_show",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
            comment="Always show root route regardless of children count",
        ),
        sa.Column(
            "meta",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
            comment="Route meta info (additional attributes)",
        ),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="Tenant ID"),
        sa.ForeignKeyConstraint(["parent_id"], ["menus.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_menus_parent_id"), "menus", ["parent_id"], unique=False)
    op.create_index(op.f("ix_menus_perms"), "menus", ["perms"], unique=False)
    op.create_index(op.f("ix_menus_tenant_id"), "menus", ["tenant_id"], unique=False)

    # --------------------
    # Teams (data scope)
    # --------------------
    op.create_table(
        "teams",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="Tenant ID"),
        sa.Column("name", sa.String(length=100), nullable=False, comment="团队名称"),
        sa.Column("code", sa.String(length=50), nullable=False, comment="团队编码/标识"),
        sa.Column("status", sa.Integer(), server_default="1", nullable=False, comment="状态: 0=禁用, 1=启用"),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=True, comment="显示排序"),
        sa.Column("description", sa.String(length=500), nullable=True, comment="团队描述"),
        sa.Column("leader", sa.String(length=100), nullable=True, comment="团队负责人"),
        sa.Column("phone", sa.String(length=50), nullable=True, comment="联系电话"),
        sa.Column("email", sa.String(length=100), nullable=True, comment="邮箱"),
        sa.Column("parent_id", sa.BigInteger(), nullable=True, comment="上级团队ID"),
        sa.Column("created_by", sa.BigInteger(), nullable=True, comment="Created by user ID"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["parent_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="团队表",
    )
    op.create_index("ix_teams_name", "teams", ["name"], unique=False)
    op.create_index("ix_teams_code", "teams", ["code"], unique=False)
    op.create_index("ix_teams_tenant_id", "teams", ["tenant_id"], unique=False)
    op.create_index("ix_teams_deleted_at", "teams", ["deleted_at"], unique=False)

    # --------------------
    # User Groups (tree)
    # --------------------
    op.create_table(
        "user_groups",
        sa.Column("name", sa.String(length=100), nullable=False, comment="Group name"),
        sa.Column("code", sa.String(length=50), nullable=False, comment="Group code (unique within tenant)"),
        sa.Column("description", sa.Text(), nullable=True, comment="Group description"),
        sa.Column("parent_id", sa.BigInteger(), nullable=True, comment="Parent group ID"),
        sa.Column("path", sa.String(length=500), nullable=False, comment="Materialized path (e.g., '/1/2/3/')"),
        sa.Column("level", sa.Integer(), server_default="1", nullable=False, comment="Hierarchy level (1=root)"),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False, comment="Sort order"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False, comment="Is active"),
        sa.Column(
            "extra",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
            comment="Extra attributes",
        ),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="Tenant ID"),
        sa.ForeignKeyConstraint(["parent_id"], ["user_groups.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_groups_code"), "user_groups", ["code"], unique=False)
    op.create_index(op.f("ix_user_groups_parent_id"), "user_groups", ["parent_id"], unique=False)
    op.create_index(op.f("ix_user_groups_path"), "user_groups", ["path"], unique=False)
    op.create_index(op.f("ix_user_groups_tenant_id"), "user_groups", ["tenant_id"], unique=False)

    # --------------------
    # Association tables (no id, no timestamps)
    # --------------------
    op.create_table(
        "user_roles",
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="Tenant ID"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="User ID"),
        sa.Column("role_id", sa.BigInteger(), nullable=False, comment="Role ID"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "role_id"),
    )
    op.create_index(op.f("ix_user_roles_tenant_id"), "user_roles", ["tenant_id"], unique=False)

    op.create_table(
        "user_teams",
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="Tenant ID"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="User ID"),
        sa.Column("team_id", sa.BigInteger(), nullable=False, comment="Team ID"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "team_id"),
        comment="用户团队关联表",
    )
    op.create_index(op.f("ix_user_teams_tenant_id"), "user_teams", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_user_teams_team_id"), "user_teams", ["team_id"], unique=False)

    op.create_table(
        "role_menus",
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="Tenant ID"),
        sa.Column("role_id", sa.BigInteger(), nullable=False, comment="Role ID"),
        sa.Column("menu_id", sa.BigInteger(), nullable=False, comment="Menu ID"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["menu_id"], ["menus.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("role_id", "menu_id"),
        comment="Role-Menu Association Table",
    )
    op.create_index("ix_role_menus_tenant_id", "role_menus", ["tenant_id"], unique=False)

    op.create_table(
        "role_teams",
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="Tenant ID"),
        sa.Column("role_id", sa.BigInteger(), nullable=False, comment="Role ID"),
        sa.Column("team_id", sa.BigInteger(), nullable=False, comment="Team ID"),
        sa.Column(
            "permissions",
            sa.Integer(),
            server_default="0",
            nullable=False,
            comment="数据操作权限(位运算: 1=只读, 2=编辑, 4=删除)",
        ),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("role_id", "team_id"),
        comment="角色团队关联表",
    )
    op.create_index(op.f("ix_role_teams_tenant_id"), "role_teams", ["tenant_id"], unique=False)

    op.create_table(
        "user_group_members",
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="Tenant ID"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="User ID"),
        sa.Column("group_id", sa.BigInteger(), nullable=False, comment="Group ID"),
        sa.Column(
            "is_leader",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
            comment="Is group leader",
        ),
        sa.ForeignKeyConstraint(["group_id"], ["user_groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "group_id"),
    )
    op.create_index(op.f("ix_user_group_members_tenant_id"), "user_group_members", ["tenant_id"], unique=False)

    # --------------------
    # Credits
    # --------------------
    op.create_table(
        "credit_accounts",
        sa.Column("user_id", sa.BigInteger(), nullable=True, comment="User ID (nullable for tenant account)"),
        sa.Column("account_type", sa.String(length=20), nullable=False, comment="Account type: tenant | user"),
        sa.Column("balance", sa.Numeric(18, 2), server_default="0", nullable=False, comment="Current balance"),
        sa.Column("total_earned", sa.Numeric(18, 2), server_default="0", nullable=False, comment="Total earned amount"),
        sa.Column("total_spent", sa.Numeric(18, 2), server_default="0", nullable=False, comment="Total spent amount"),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False, comment="Status: active | frozen"),
        sa.Column(
            "extra",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
            comment="Extra attributes (JSONB)",
        ),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="Tenant ID"),
        sa.PrimaryKeyConstraint("id"),
        comment="积分账户表",
    )

    op.create_index(op.f("ix_credit_accounts_tenant_id"), "credit_accounts", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_credit_accounts_user_id"), "credit_accounts", ["user_id"], unique=False)
    op.create_index(op.f("ix_credit_accounts_account_type"), "credit_accounts", ["account_type"], unique=False)
    op.create_index(op.f("ix_credit_accounts_status"), "credit_accounts", ["status"], unique=False)

    op.create_check_constraint(
        "ck_credit_accounts_account_type_user_id",
        "credit_accounts",
        "(account_type = 'tenant' AND user_id IS NULL) OR (account_type = 'user' AND user_id IS NOT NULL)",
    )
    op.create_check_constraint("ck_credit_accounts_balance_non_negative", "credit_accounts", "balance >= 0")
    op.create_check_constraint("ck_credit_accounts_total_earned_non_negative", "credit_accounts", "total_earned >= 0")
    op.create_check_constraint("ck_credit_accounts_total_spent_non_negative", "credit_accounts", "total_spent >= 0")

    op.create_index(
        "uq_credit_accounts_tenant_account",
        "credit_accounts",
        ["tenant_id"],
        unique=True,
        postgresql_where=sa.text("account_type = 'tenant' AND user_id IS NULL AND deleted_at IS NULL"),
    )
    op.create_index(
        "uq_credit_accounts_user_account",
        "credit_accounts",
        ["tenant_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("account_type = 'user' AND user_id IS NOT NULL AND deleted_at IS NULL"),
    )

    op.create_table(
        "credit_transactions",
        sa.Column("account_id", sa.BigInteger(), nullable=False, comment="Credit account ID"),
        sa.Column("transaction_type", sa.String(length=30), nullable=False, comment="Transaction type"),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False, comment="Amount (positive)"),
        sa.Column("direction", sa.String(length=10), nullable=False, comment="Direction: in | out"),
        sa.Column("balance_before", sa.Numeric(18, 2), nullable=False, comment="Balance before transaction"),
        sa.Column("balance_after", sa.Numeric(18, 2), nullable=False, comment="Balance after transaction"),
        sa.Column("reference_type", sa.String(length=50), nullable=True, comment="Business reference type"),
        sa.Column("reference_id", sa.BigInteger(), nullable=True, comment="Business reference ID"),
        sa.Column("remark", sa.Text(), nullable=True, comment="Remark"),
        sa.Column("operator_id", sa.BigInteger(), nullable=True, comment="Operator user ID"),
        sa.Column(
            "extra",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
            comment="Extra attributes (JSONB)",
        ),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="Tenant ID"),
        sa.ForeignKeyConstraint(["account_id"], ["credit_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="积分流水表",
    )

    op.create_index(op.f("ix_credit_transactions_tenant_id"), "credit_transactions", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_credit_transactions_account_id"), "credit_transactions", ["account_id"], unique=False)
    op.create_index(op.f("ix_credit_transactions_transaction_type"), "credit_transactions", ["transaction_type"], unique=False)
    op.create_index(op.f("ix_credit_transactions_direction"), "credit_transactions", ["direction"], unique=False)
    op.create_index(op.f("ix_credit_transactions_reference_type"), "credit_transactions", ["reference_type"], unique=False)
    op.create_index(op.f("ix_credit_transactions_reference_id"), "credit_transactions", ["reference_id"], unique=False)
    op.create_index(op.f("ix_credit_transactions_operator_id"), "credit_transactions", ["operator_id"], unique=False)
    op.create_index(op.f("ix_credit_transactions_created_at"), "credit_transactions", ["created_at"], unique=False)

    op.create_check_constraint("ck_credit_transactions_amount_positive", "credit_transactions", "amount > 0")
    op.create_check_constraint(
        "ck_credit_transactions_direction",
        "credit_transactions",
        "direction IN ('in', 'out')",
    )

    op.create_table(
        "credit_rules",
        sa.Column("name", sa.String(length=100), nullable=False, comment="Rule name"),
        sa.Column("rule_type", sa.String(length=20), nullable=False, comment="Rule type: consume | earn | bonus"),
        sa.Column("module", sa.String(length=50), nullable=False, comment="Applicable module"),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False, comment="Credit amount"),
        sa.Column(
            "condition",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
            comment="Trigger condition (JSONB)",
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False, comment="Is active"),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="Tenant ID"),
        sa.PrimaryKeyConstraint("id"),
        comment="积分规则表",
    )

    op.create_index(op.f("ix_credit_rules_tenant_id"), "credit_rules", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_credit_rules_name"), "credit_rules", ["name"], unique=False)
    op.create_index(op.f("ix_credit_rules_rule_type"), "credit_rules", ["rule_type"], unique=False)
    op.create_index(op.f("ix_credit_rules_module"), "credit_rules", ["module"], unique=False)
    op.create_index(op.f("ix_credit_rules_is_active"), "credit_rules", ["is_active"], unique=False)

    # --------------------
    # Operation Logs
    # --------------------
    op.create_table(
        "operation_logs",
        sa.Column(
            "user_id",
            sa.BigInteger(),
            nullable=True,
            comment="Operator user ID (nullable for anonymous actions)",
        ),
        sa.Column("username", sa.String(length=50), nullable=True, comment="Operator username (denormalized)"),
        sa.Column("module", sa.String(length=50), nullable=False, comment="Module name (e.g., auth, users, roles)"),
        sa.Column("action", sa.String(length=50), nullable=False, comment="Action type (e.g., login, create, update, delete)"),
        sa.Column("target_type", sa.String(length=100), nullable=True, comment="Target type (e.g., User, Role)"),
        sa.Column("target_id", sa.BigInteger(), nullable=True, comment="Target ID"),
        sa.Column("method", sa.String(length=10), nullable=True, comment="HTTP method (GET/POST/PUT/DELETE)"),
        sa.Column("path", sa.String(length=500), nullable=True, comment="Request path"),
        sa.Column("ip", sa.String(length=50), nullable=True, comment="Client IP"),
        sa.Column("user_agent", sa.Text(), nullable=True, comment="User-Agent"),
        sa.Column("status", sa.String(length=20), nullable=False, comment='Status: "success" | "failure"'),
        sa.Column("status_code", sa.Integer(), nullable=True, comment="HTTP status code"),
        sa.Column("error_message", sa.Text(), nullable=True, comment="Error message (on failure)"),
        sa.Column(
            "request_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Request payload (JSONB, sanitized)",
        ),
        sa.Column(
            "response_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Response payload (JSONB, optional)",
        ),
        sa.Column("duration_ms", sa.Integer(), nullable=True, comment="Duration in milliseconds"),
        sa.Column(
            "extra",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
            comment="Extra attributes (JSONB)",
        ),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="Tenant ID"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(op.f("ix_operation_logs_tenant_id"), "operation_logs", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_operation_logs_user_id"), "operation_logs", ["user_id"], unique=False)
    op.create_index(op.f("ix_operation_logs_username"), "operation_logs", ["username"], unique=False)
    op.create_index(op.f("ix_operation_logs_module"), "operation_logs", ["module"], unique=False)
    op.create_index(op.f("ix_operation_logs_action"), "operation_logs", ["action"], unique=False)
    op.create_index(op.f("ix_operation_logs_target_id"), "operation_logs", ["target_id"], unique=False)
    op.create_index(op.f("ix_operation_logs_status"), "operation_logs", ["status"], unique=False)
    op.create_index(op.f("ix_operation_logs_created_at"), "operation_logs", ["created_at"], unique=False)

    # --------------------
    # Notifications
    # --------------------
    op.create_table(
        "notifications",
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="Recipient user ID"),
        sa.Column("category", sa.String(length=20), nullable=False, comment='Category: "notification" | "message" | "todo"'),
        sa.Column("title", sa.String(length=200), nullable=False, comment="Title"),
        sa.Column("content", sa.Text(), nullable=True, comment="Content"),
        sa.Column("avatar", sa.String(length=500), nullable=True, comment="Avatar URL"),
        sa.Column("is_read", sa.Boolean(), server_default=sa.text("false"), nullable=False, comment="Is read"),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True, comment="Read timestamp"),
        sa.Column("reference_type", sa.String(length=50), nullable=True, comment="Business reference type"),
        sa.Column("reference_id", sa.BigInteger(), nullable=True, comment="Business reference ID"),
        sa.Column("sender_id", sa.BigInteger(), nullable=True, comment="Sender user ID"),
        sa.Column("sender_name", sa.String(length=100), nullable=True, comment="Sender display name"),
        sa.Column(
            "priority",
            sa.String(length=20),
            server_default="normal",
            nullable=False,
            comment='Priority: "low" | "normal" | "high" | "urgent"',
        ),
        sa.Column("status", sa.String(length=50), nullable=True, comment='Custom status, e.g. "pending", "processing", "done"'),
        sa.Column("expire_at", sa.DateTime(timezone=True), nullable=True, comment="Expire timestamp"),
        sa.Column(
            "extra",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
            comment="Extra attributes (JSONB)",
        ),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="Tenant ID"),
        sa.PrimaryKeyConstraint("id"),
        comment="用户消息通知表",
    )

    op.create_index(op.f("ix_notifications_tenant_id"), "notifications", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_notifications_user_id"), "notifications", ["user_id"], unique=False)
    op.create_index(op.f("ix_notifications_category"), "notifications", ["category"], unique=False)
    op.create_index(op.f("ix_notifications_is_read"), "notifications", ["is_read"], unique=False)
    op.create_index(op.f("ix_notifications_reference_type"), "notifications", ["reference_type"], unique=False)
    op.create_index(op.f("ix_notifications_reference_id"), "notifications", ["reference_id"], unique=False)
    op.create_index(op.f("ix_notifications_sender_id"), "notifications", ["sender_id"], unique=False)
    op.create_index(op.f("ix_notifications_priority"), "notifications", ["priority"], unique=False)
    op.create_index(op.f("ix_notifications_status"), "notifications", ["status"], unique=False)
    op.create_index(op.f("ix_notifications_expire_at"), "notifications", ["expire_at"], unique=False)
    op.create_index(op.f("ix_notifications_created_at"), "notifications", ["created_at"], unique=False)

    op.create_index(
        "ix_notifications_tenant_user_is_read",
        "notifications",
        ["tenant_id", "user_id", "is_read"],
        unique=False,
    )
    op.create_index(
        "ix_notifications_tenant_user_created_at",
        "notifications",
        ["tenant_id", "user_id", "created_at"],
        unique=False,
    )

    op.create_check_constraint(
        "ck_notifications_category",
        "notifications",
        "category IN ('notification', 'message', 'todo')",
    )
    op.create_check_constraint(
        "ck_notifications_priority",
        "notifications",
        "priority IN ('low', 'normal', 'high', 'urgent')",
    )

    # --------------------
    # Verification Codes
    # --------------------
    op.create_table(
        "verification_codes",
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="User ID"),
        sa.Column("channel", sa.String(length=20), nullable=False, comment="Channel: sms/email"),
        sa.Column("purpose", sa.String(length=50), nullable=False, comment="Purpose: bind_phone/bind_email"),
        sa.Column("target", sa.String(length=200), nullable=False, comment="Target phone/email (normalized)"),
        sa.Column("code_hash", sa.String(length=64), nullable=False, comment="HMAC-SHA256 hex digest"),
        sa.Column("salt", sa.String(length=64), nullable=False, comment="Hash salt"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, comment="Expiry timestamp"),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True, comment="Used timestamp"),
        sa.Column(
            "attempts",
            sa.Integer(),
            server_default="0",
            nullable=False,
            comment="Failed verification attempts",
        ),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="Tenant ID"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_verification_codes_channel"), "verification_codes", ["channel"], unique=False)
    op.create_index(op.f("ix_verification_codes_expires_at"), "verification_codes", ["expires_at"], unique=False)
    op.create_index(op.f("ix_verification_codes_purpose"), "verification_codes", ["purpose"], unique=False)
    op.create_index(op.f("ix_verification_codes_target"), "verification_codes", ["target"], unique=False)
    op.create_index(op.f("ix_verification_codes_tenant_id"), "verification_codes", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_verification_codes_used_at"), "verification_codes", ["used_at"], unique=False)
    op.create_index(op.f("ix_verification_codes_user_id"), "verification_codes", ["user_id"], unique=False)

def downgrade() -> None:
    op.drop_table("verification_codes")
    op.drop_table("notifications")
    op.drop_table("operation_logs")
    op.drop_table("credit_rules")
    op.drop_table("credit_transactions")
    op.drop_table("credit_accounts")
    op.drop_table("user_group_members")
    op.drop_table("user_groups")
    op.drop_table("role_teams")
    op.drop_table("role_menus")
    op.drop_table("user_teams")
    op.drop_table("user_roles")
    op.drop_table("teams")
    op.drop_table("menus")
    op.drop_table("roles")
    op.drop_constraint("fk_organizations_leader_id", "organizations", type_="foreignkey")
    op.drop_table("users")
    op.drop_table("organizations")
    op.drop_table("tenants")
