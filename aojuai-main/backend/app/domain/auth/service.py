"""
AOJU Backend - Tenant Service
"""
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, not_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BusinessError, ConflictError, NotFoundError
from app.core.role_semantics import (
    TENANT_ADMIN_ROLE_CODES,
    has_tenant_admin_role,
    is_tenant_admin_role_code,
)
from app.core.security import hash_password
from app.core.tenant_config_namespaces import (
    get_tenant_config_namespace,
    safe_tenant_config_dict,
    set_tenant_config_namespace,
)
from app.domain.auth.config_security import sanitize_tenant_config
from app.domain.auth.models import Tenant
from app.domain.auth.schemas import (
    InitialAdminCreate,
    RegistrationConfigUpdate,
    TenantCreate,
    TenantCreateWithAdmin,
    TenantUpdate,
)
from app.infrastructure.cache import bump_tenant_permissions_cache_version
from app.domain.users.models import RegisterSource
from app.infrastructure.repository.base import RepositoryBase


class TenantService(RepositoryBase[Tenant]):
    """Tenant business logic"""

    def __init__(self, db: AsyncSession):
        super().__init__(db, Tenant)

    async def get_by_id(self, tenant_id: int) -> Tenant | None:
        """Get tenant by ID"""
        return await super().get_by_id(tenant_id, raise_not_found=False)

    async def get_by_code(self, code: str) -> Tenant | None:
        """Get tenant by code"""
        return await self.get_one(code=code)

    async def get_all_tenants(
        self,
        is_active: bool | None = True,
    ) -> list[Tenant]:
        """Get all tenants (for dropdown select)"""
        where = []
        if is_active is not None:
            where.append(Tenant.is_active == is_active)

        return await self.get_list(
            page_size=0,  # No pagination
            where=where if where else None,
            order_by="name",
        )

    async def list_tenants(
        self,
        page: int = 1,
        page_size: int = 10,
        name: str | None = None,
        is_active: bool | None = None,
        sort_by: str | None = None,
        sort_order: str | None = None,
    ) -> tuple[list[Tenant], int]:
        """List tenants with pagination"""
        where = []

        if name:
            where.append(Tenant.name.ilike(f"%{name}%"))
        if is_active is not None:
            where.append(Tenant.is_active == is_active)

        # 排序处理
        allowed_sort_fields = {"id", "name", "code", "created_at"}
        order_field = sort_by if sort_by in allowed_sort_fields else "id"
        order_desc = sort_order and sort_order.lower() == "desc"

        return await self.get_list(
            page=page,
            page_size=page_size,
            where=where if where else None,
            order_by=order_field,
            order_desc=order_desc,
            return_total=True,
        )

    async def create_tenant(self, data: TenantCreate) -> Tenant:
        """Create tenant"""
        # Check code exists
        existing = await self.get_by_code(data.code)
        if existing:
            raise ConflictError(message=f"Tenant code '{data.code}' already exists")

        tenant_data = {
            "name": data.name,
            "code": data.code,
            "domain": data.domain,
            "description": data.description,
            "is_active": data.is_active,
            "expires_at": data.expires_at,
            "config": data.config.model_dump(by_alias=True),
            "quota": data.quota.model_dump(by_alias=True),
            "contact_name": data.contact_name,
            "contact_phone": data.contact_phone,
            "contact_email": data.contact_email,
        }
        return await self.create(tenant_data)

    async def update_tenant(
        self,
        tenant_id: int,
        data: TenantUpdate,
    ) -> Tenant:
        """Update tenant"""
        tenant = await super().get_by_id(tenant_id, raise_not_found=True)

        update_data = data.model_dump(exclude_unset=True, exclude={"config", "quota"})

        # Handle config update
        if data.config is not None:
            update_data["config"] = data.config.model_dump(by_alias=True)

        # Handle quota update
        if data.quota is not None:
            update_data["quota"] = data.quota.model_dump(by_alias=True)

        return await self.update(tenant, update_data, exclude_unset=False)

    async def update_registration_config(
        self,
        tenant_id: int,
        data: RegistrationConfigUpdate,
    ) -> Tenant:
        """Update tenant registration configuration"""
        tenant = await super().get_by_id(tenant_id, raise_not_found=True)

        # Get current config
        config = safe_tenant_config_dict(tenant.config)
        registration = get_tenant_config_namespace(config, ("registration",))

        # Update registration settings
        if data.enabled is not None:
            registration["enabled"] = data.enabled
        if data.require_audit is not None:
            registration["requireAudit"] = data.require_audit
        if data.default_role is not None:
            registration["defaultRole"] = data.default_role
        if data.basic_fields is not None:
            registration["basicFields"] = data.basic_fields.model_dump(by_alias=True)
        if data.invitation is not None:
            registration["invitation"] = data.invitation.model_dump(by_alias=True)
        if data.user_profile_fields is not None:
            registration["userProfileFields"] = data.user_profile_fields.model_dump(by_alias=True)

        next_config = set_tenant_config_namespace(config, ("registration",), registration)
        return await self.update(tenant, {"config": next_config}, exclude_unset=False)

    async def delete_tenant(self, tenant_id: int) -> None:
        """Soft delete tenant"""
        await self.delete_by_id(tenant_id)

    @staticmethod
    def to_response(tenant: Tenant) -> dict[str, Any]:
        """Convert tenant to response dict"""
        return {
            "id": tenant.id,
            "name": tenant.name,
            "code": tenant.code,
            "domain": tenant.domain,
            "description": tenant.description,
            "isActive": tenant.is_active,
            "expiresAt": tenant.expires_at.isoformat() if tenant.expires_at else None,
            "config": sanitize_tenant_config(tenant.config),
            "quota": tenant.quota,
            "contactName": tenant.contact_name,
            "contactPhone": tenant.contact_phone,
            "contactEmail": tenant.contact_email,
            "createdAt": tenant.created_at.isoformat() if tenant.created_at else None,
        }

    @staticmethod
    def to_list_item(tenant: Tenant) -> dict[str, Any]:
        """Convert tenant to list item dict"""
        return {
            "id": tenant.id,
            "name": tenant.name,
            "code": tenant.code,
            "domain": tenant.domain,
            "isActive": tenant.is_active,
            "expiresAt": tenant.expires_at.isoformat() if tenant.expires_at else None,
            "contactName": tenant.contact_name,
            "contactPhone": tenant.contact_phone,
            "contactEmail": tenant.contact_email,
            "description": tenant.description,
            "config": sanitize_tenant_config(tenant.config),
            "createdAt": tenant.created_at.isoformat() if tenant.created_at else None,
        }

    async def create_tenant_with_admin(
        self,
        data: TenantCreateWithAdmin,
    ) -> tuple[Tenant, Any]:
        """Create tenant with initial admin user"""
        from app.domain.cms.access import CMS_MENU_DECLARATION
        from app.domain.menus.reconciler import reconcile_menu_declaration
        from app.core.system_menus import SYSTEM_MENU_DECLARATION, SYSTEM_ROLE_DEFAULTS
        from app.core.capability_runtime import provision_installed_capabilities
        from app.domain.roles.models import Role
        from app.domain.teams.service import TeamService
        from app.domain.users.models import User, UserRole, UserStatus, UserTeam

        # Check code exists
        existing = await self.get_by_code(data.code)
        if existing:
            raise ConflictError(message=f"Tenant code '{data.code}' already exists")

        # Create tenant
        tenant = Tenant(
            name=data.name,
            code=data.code,
            domain=data.domain,
            description=data.description,
            is_active=data.is_active,
            expires_at=data.expires_at,
            config=data.config.model_dump(by_alias=True),
            quota=data.quota.model_dump(by_alias=True),
            contact_name=data.contact_name,
            contact_phone=data.contact_phone,
            contact_email=data.contact_email,
        )
        self.db.add(tenant)
        await self.db.flush()  # Get tenant ID

        # Create default roles for this tenant
        # 角色字段一律取自 SYSTEM_ROLE_DEFAULTS（唯一真源），不要在这里另写一套。
        # 原来这里手写且不填 data_range/data_permissions，于是吃了模型默认值
        # DataRangeEnum.ALL —— 新租户的普通 user 拿到了「全部数据」的可见范围。
        def _role(code: str) -> Role:
            defaults = SYSTEM_ROLE_DEFAULTS[code]
            return Role(
                tenant_id=tenant.id,
                code=code,
                name=defaults.name,
                description=defaults.description,
                sort_order=defaults.sort_order,
                is_active=defaults.is_active,
                is_system=defaults.is_system,
                data_range=defaults.data_range,
                data_permissions=defaults.data_permissions,
            )

        admin_role = _role("admin")
        user_role = _role("user")
        self.db.add(admin_role)
        self.db.add(user_role)
        await self.db.flush()  # Get role IDs

        # 新租户必须拿到与 seed **相同**的终态，否则只有 default 租户是完整的。
        # 系统菜单在前：CMS 与能力包都挂在它建出来的角色上。
        # 原来这里只 reconcile 了 CMS——结果新租户管理员只看得见内容管理，
        # user 角色一条授权都没有。三场景对账（scripts/check_scenario_parity.py）
        # 就是为了让这种掉队一跑就现形。
        await reconcile_menu_declaration(
            self.db,
            tenant_id=tenant.id,
            declaration=SYSTEM_MENU_DECLARATION,
            role_id_overrides={"admin": admin_role.id, "user": user_role.id},
        )
        await reconcile_menu_declaration(
            self.db,
            tenant_id=tenant.id,
            declaration=CMS_MENU_DECLARATION,
            role_id_overrides={"admin": admin_role.id},
        )
        await provision_installed_capabilities(
            self.db,
            tenant_id=tenant.id,
            role_id_overrides={"admin": admin_role.id},
        )

        team_service = TeamService(self.db)
        default_team = await team_service.ensure_default_team(tenant_id=tenant.id, created_by=None)

        admin_user = None
        # Create initial admin if provided
        if data.initial_admin:
            # Check if username exists
            stmt = select(User).where(
                User.username == data.initial_admin.username,
                User.deleted_at.is_(None),
            )
            result = await self.db.execute(stmt)
            if result.scalar_one_or_none():
                raise ConflictError(
                    message=f"Username '{data.initial_admin.username}' already exists"
                )

            admin_user = User(
                tenant_id=tenant.id,
                username=data.initial_admin.username,
                password_hash=hash_password(data.initial_admin.password),
                nickname=data.initial_admin.nickname or data.initial_admin.username,
                email=data.initial_admin.email,
                phone=data.initial_admin.phone,
                status=UserStatus.ENABLED,
                is_superuser=False,
                register_source=RegisterSource.ADMIN,
            )
            self.db.add(admin_user)
            await self.db.flush()  # Get user ID

            # Assign admin role
            user_role_link = UserRole(
                tenant_id=tenant.id,
                user_id=admin_user.id,
                role_id=admin_role.id,
            )
            self.db.add(user_role_link)
            self.db.add(
                UserTeam(
                    tenant_id=tenant.id,
                    user_id=admin_user.id,
                    team_id=default_team.id,
                )
            )

        await self.db.flush()
        await self.db.refresh(tenant)
        if admin_user:
            await self.db.refresh(admin_user)

        return tenant, admin_user

    async def get_tenant_users(
        self,
        tenant_id: int,
        page: int = 1,
        page_size: int = 10,
        username: str | None = None,
        is_admin: bool | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """Get users belonging to a tenant"""
        from app.domain.roles.models import Role
        from app.domain.users.models import User
        from app.infrastructure.repository.base import RepositoryBase as UserRepo

        # Use a temporary repository for User model
        user_repo = UserRepo(self.db, User)

        where = [User.tenant_id == tenant_id]
        if username:
            where.append(User.username.ilike(f"%{username}%"))
        if is_admin is not None:
            tenant_admin_filter = User.roles.any(
                and_(
                    Role.tenant_id == tenant_id,
                    Role.deleted_at.is_(None),
                    Role.is_active.is_(True),
                    Role.code.in_(TENANT_ADMIN_ROLE_CODES),
                )
            )
            where.append(tenant_admin_filter if is_admin else not_(tenant_admin_filter))

        users, total = await user_repo.get_list(
            page=page,
            page_size=page_size,
            where=where,
            options=[selectinload(User.roles)],
            order_by="created_at",
            order_desc=True,
            return_total=True,
        )

        # Convert to dict with is_admin flag
        user_list = []
        for user in users:
            roles = [role.code for role in user.roles] if user.roles else []
            active_role_codes = [
                role.code
                for role in (user.roles or [])
                if getattr(role, "is_active", False) and getattr(role, "deleted_at", None) is None
            ]
            user_list.append({
                "id": user.id,
                "username": user.username,
                "nickname": user.nickname,
                "email": user.email,
                "phone": user.phone,
                "status": user.status,
                "isAdmin": has_tenant_admin_role(active_role_codes),
                "roles": roles,
                "createdAt": user.created_at.isoformat() if user.created_at else None,
            })

        return user_list, total

    async def set_user_admin(
        self,
        tenant_id: int,
        user_id: int,
        is_admin: bool,
    ) -> dict[str, Any]:
        """Set or remove admin role for a user"""
        from app.domain.roles.models import Role
        from app.domain.users.models import User, UserRole

        # Get user
        stmt = (
            select(User)
            .options(selectinload(User.roles))
            .where(
                User.id == user_id,
                User.tenant_id == tenant_id,
                User.deleted_at.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise NotFoundError(message="User not found in this tenant")

        # Get tenant-admin roles for this tenant.
        role_stmt = select(Role).where(
            Role.tenant_id == tenant_id,
            Role.code.in_(TENANT_ADMIN_ROLE_CODES),
            Role.deleted_at.is_(None),
        )
        role_result = await self.db.execute(role_stmt)
        tenant_admin_roles = list(role_result.scalars().all())
        active_tenant_admin_roles = [role for role in tenant_admin_roles if role.is_active]
        admin_role = next((role for role in active_tenant_admin_roles if role.code == "admin"), None)
        if admin_role is None and active_tenant_admin_roles:
            admin_role = active_tenant_admin_roles[0]

        if is_admin and not admin_role:
            raise BusinessError(message="Admin role not found for this tenant")

        # Check current admin status
        active_role_codes = [
            role.code
            for role in (user.roles or [])
            if getattr(role, "is_active", False) and getattr(role, "deleted_at", None) is None
        ]
        linked_tenant_admin_role_ids = {
            role.id
            for role in (user.roles or [])
            if is_tenant_admin_role_code(getattr(role, "code", None))
        }
        tenant_admin_role_ids = {role.id for role in tenant_admin_roles}
        has_admin = has_tenant_admin_role(active_role_codes)

        if is_admin and not has_admin and admin_role.id not in linked_tenant_admin_role_ids:
            # Add admin role
            user_role = UserRole(
                tenant_id=tenant_id,
                user_id=user_id,
                role_id=admin_role.id,
            )
            self.db.add(user_role)
            await self.db.flush()
        elif not is_admin and tenant_admin_role_ids:
            # Remove all tenant-admin role variants.
            del_stmt = select(UserRole).where(
                UserRole.tenant_id == tenant_id,
                UserRole.user_id == user_id,
                UserRole.role_id.in_(tenant_admin_role_ids),
            )
            del_result = await self.db.execute(del_stmt)
            for user_role in del_result.scalars().all():
                await self.db.delete(user_role)
            await self.db.flush()

        # Re-query to return fresh role state after add/remove.
        refreshed_result = await self.db.execute(stmt.execution_options(populate_existing=True))
        refreshed_user = refreshed_result.scalar_one_or_none()
        if not refreshed_user:
            raise NotFoundError(message="User not found in this tenant")
        roles = [role.code for role in refreshed_user.roles] if refreshed_user.roles else []
        active_roles = [
            role.code
            for role in (refreshed_user.roles or [])
            if getattr(role, "is_active", False) and getattr(role, "deleted_at", None) is None
        ]
        await bump_tenant_permissions_cache_version(tenant_id)

        return {
            "id": refreshed_user.id,
            "username": refreshed_user.username,
            "nickname": refreshed_user.nickname,
            "isAdmin": has_tenant_admin_role(active_roles),
            "roles": roles,
        }
