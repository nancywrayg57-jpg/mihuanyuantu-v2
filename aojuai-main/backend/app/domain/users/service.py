"""
AOJU Backend - User Service

支持多租户用户管理:
- 租户管理员: 只能操作本租户的用户
- 系统管理员: 可以操作所有租户的用户

继承 RepositoryBase 复用通用数据访问方法。
"""
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Float, and_, cast, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from app.core.exceptions import BusinessError, ConflictError, NotFoundError
from app.core.security import hash_password, verify_password
from app.core.verification import normalize_email, normalize_phone
from app.domain.auth.models import Tenant
from app.domain.invitations.models import InviteRegistration
from app.domain.roles.models import Role
from app.domain.user_groups.models import UserGroupMember
from app.domain.users.models import RegisterSource, User, UserRole, UserStatus, UserTeam
from app.domain.users.profile_schema import (
    UserProfileCompletionState,
    UserProfileFieldDefinition,
    UserProfileFieldsConfig,
    build_user_profile_completion_state,
    build_user_profile_field_map,
    get_user_profile_config,
    sanitize_user_profile_payload,
)
from app.domain.users.schemas import (
    PasswordChange,
    PasswordReset,
    UserAudit,
    UserCreate,
    UserRegister,
    UserUpdate,
)
from app.infrastructure.cache import bump_tenant_permissions_cache_version
from app.infrastructure.repository import RepositoryBase


class UserService(RepositoryBase[User]):
    """
    用户业务逻辑层
    
    继承 RepositoryBase 获得通用的 CRUD 方法，
    同时提供用户相关的业务逻辑处理。
    """

    def __init__(self, db: AsyncSession):
        super().__init__(db, User)
        # 默认加载关系
        self._default_options = [
            selectinload(User.roles),
            selectinload(User.organization),
            selectinload(User.teams),
        ]

    async def _ensure_phone_available(self, *, phone: str, exclude_user_id: int | None) -> None:
        where = [User.phone == phone]
        if exclude_user_id is not None:
            where.append(User.id != exclude_user_id)
        existing = await self.get_one(where=where)
        if existing:
            raise ConflictError(message="Phone already exists")

    async def _ensure_email_available(self, *, email: str, exclude_user_id: int | None) -> None:
        where = [func.lower(User.email) == email]
        if exclude_user_id is not None:
            where.append(User.id != exclude_user_id)
        existing = await self.get_one(where=where)
        if existing:
            raise ConflictError(message="Email already exists")

    async def get_tenant_profile_config(self, tenant_id: int | None) -> UserProfileFieldsConfig:
        if tenant_id is None:
            return UserProfileFieldsConfig()

        tenant_repo = RepositoryBase(self.db, Tenant)
        tenant = await tenant_repo.get_by_id(tenant_id, raise_not_found=False)
        if not tenant:
            return UserProfileFieldsConfig()
        return get_user_profile_config(tenant.config)

    async def get_invitation_context_map(
        self,
        *,
        tenant_id: int,
        user_ids: list[int],
    ) -> dict[int, dict[str, Any]]:
        normalized_user_ids = sorted({int(user_id) for user_id in user_ids if int(user_id) > 0})
        if not normalized_user_ids:
            return {}

        inviter_alias = aliased(User)
        stmt = (
            select(
                InviteRegistration.invited_user_id.label("invited_user_id"),
                InviteRegistration.inviter_user_id.label("inviter_user_id"),
                InviteRegistration.invite_code.label("invite_code"),
                InviteRegistration.created_at.label("invited_at"),
                inviter_alias.username.label("inviter_username"),
                inviter_alias.nickname.label("inviter_nickname"),
            )
            .select_from(InviteRegistration)
            .outerjoin(
                inviter_alias,
                and_(
                    inviter_alias.id == InviteRegistration.inviter_user_id,
                    inviter_alias.deleted_at.is_(None),
                ),
            )
            .where(
                InviteRegistration.tenant_id == tenant_id,
                InviteRegistration.deleted_at.is_(None),
                InviteRegistration.invited_user_id.in_(normalized_user_ids),
            )
            .order_by(InviteRegistration.id.desc())
        )
        result = await self.db.execute(stmt)
        invitation_context: dict[int, dict[str, Any]] = {}
        for row in result.all():
            invited_user_id = row._mapping.get("invited_user_id")
            if invited_user_id is None:
                continue
            normalized_user_id = int(invited_user_id)
            if normalized_user_id in invitation_context:
                continue
            invitation_context[normalized_user_id] = {
                "invitedByUserId": row._mapping.get("inviter_user_id"),
                "invitedByUsername": row._mapping.get("inviter_username"),
                "invitedByNickname": row._mapping.get("inviter_nickname"),
                "invitedViaInviteCode": row._mapping.get("invite_code"),
                "invitedAt": (
                    row._mapping.get("invited_at").isoformat()
                    if row._mapping.get("invited_at")
                    else None
                ),
            }
        return invitation_context

    async def get_invitation_context(
        self,
        *,
        tenant_id: int,
        user_id: int,
    ) -> dict[str, Any] | None:
        return (await self.get_invitation_context_map(tenant_id=tenant_id, user_ids=[user_id])).get(int(user_id))

    @staticmethod
    def _safe_extra_dict(extra: Any) -> dict[str, Any]:
        return dict(extra) if isinstance(extra, dict) else {}

    @staticmethod
    def _read_profile(extra: Any) -> dict[str, Any]:
        extra_dict = UserService._safe_extra_dict(extra)
        profile = extra_dict.get("profile")
        return dict(profile) if isinstance(profile, dict) else {}

    @staticmethod
    def _read_profile_meta(extra: Any) -> dict[str, Any]:
        extra_dict = UserService._safe_extra_dict(extra)
        profile_meta = extra_dict.get("profileMeta")
        return dict(profile_meta) if isinstance(profile_meta, dict) else {}

    @staticmethod
    def build_user_profile_state(
        user: User,
        profile_config: UserProfileFieldsConfig | None = None,
    ) -> tuple[dict[str, Any], UserProfileCompletionState]:
        config = profile_config or UserProfileFieldsConfig()
        profile = UserService._read_profile(user.extra)
        state = build_user_profile_completion_state(
            config,
            profile,
            existing_meta=UserService._read_profile_meta(user.extra),
        )
        return profile, state

    @staticmethod
    def build_user_extra_with_profile(
        *,
        existing_extra: Any,
        profile: dict[str, Any],
        profile_state: UserProfileCompletionState,
    ) -> dict[str, Any]:
        extra = UserService._safe_extra_dict(existing_extra)
        extra["profile"] = dict(profile)
        extra["profileMeta"] = profile_state.model_dump(by_alias=True)
        return extra

    async def prepare_user_profile(
        self,
        *,
        tenant_id: int,
        raw_profile: dict[str, Any] | None,
        existing_extra: Any = None,
        enforce_required: bool = False,
        source: str | None = None,
    ) -> tuple[dict[str, Any], UserProfileCompletionState, UserProfileFieldsConfig]:
        profile_config = await self.get_tenant_profile_config(tenant_id)
        sanitized_profile, errors = sanitize_user_profile_payload(raw_profile, profile_config)
        if errors:
            raise BusinessError(message="；".join(errors))

        profile_state = build_user_profile_completion_state(
            profile_config,
            sanitized_profile,
            existing_meta=self._read_profile_meta(existing_extra),
            source=source,
        )

        if enforce_required and profile_config.enabled and profile_config.enforce_on_register and not profile_state.completed:
            field_map = build_user_profile_field_map(profile_config)
            missing_labels = [
                field_map[key].label
                for key in profile_state.missing_required_keys
                if key in field_map
            ]
            if missing_labels:
                raise BusinessError(message=f"请补充必填资料：{'、'.join(missing_labels)}")

        return sanitized_profile, profile_state, profile_config

    def _build_profile_filter_condition(
        self,
        *,
        field: UserProfileFieldDefinition,
        raw_value: Any,
    ):
        from app.domain.users.profile_schema import normalize_user_profile_value

        normalized = normalize_user_profile_value(field, raw_value)
        if normalized is None:
            return None

        json_value = User.extra["profile"][field.key]
        json_text = json_value.as_string()

        if field.type in {"text", "textarea"}:
            return json_text.ilike(f"%{normalized}%")
        if field.type in {"select", "date"}:
            return json_text == str(normalized)
        if field.type == "number":
            return cast(json_text, Float) == float(normalized)
        if field.type == "boolean":
            return json_text == ("true" if normalized else "false")
        if field.type == "multi_select":
            values = normalized if isinstance(normalized, list) else [normalized]
            return and_(*[json_text.ilike(f'%"{value}"%') for value in values])
        return None

    # ==================== 基础查询方法 ====================

    async def get_user_by_id(self, user_id: int, tenant_id: int) -> User | None:
        """Get user by ID (限定租户)"""
        return await self.get_one(
            where=[User.id == user_id, User.tenant_id == tenant_id],
            options=self._default_options,
        )

    async def get_user_by_id_any_tenant(self, user_id: int) -> User | None:
        """Get user by ID (跨租户，系统管理员用)"""
        return await self.get_one(
            where=[User.id == user_id],
            options=self._default_options,
        )

    async def get_by_username(self, username: str, tenant_id: int) -> User | None:
        """Get user by username (限定租户)"""
        return await self.get_one(
            where=[User.tenant_id == tenant_id],
            username=username,
        )

    async def get_by_username_global(self, username: str) -> User | None:
        """Get user by username globally across tenants."""
        return await self.get_one(username=username)

    # ==================== 列表查询 ====================

    async def list_users(
        self,
        tenant_id: int | None = None,
        page: int = 1,
        page_size: int = 10,
        username: str | None = None,
        nickname: str | None = None,
        phone: str | None = None,
        status: int | None = None,
        organization_id: int | None = None,
        profile_filters: dict[str, Any] | None = None,
        team_ids: list[int] | None = None,
        include_tenant_info: bool = False,
        sort_by: str | None = None,
        sort_order: str | None = None,
    ) -> tuple[list[User], int]:
        """
        List users with pagination

        Args:
            tenant_id: 租户ID
            page: 页码
            page_size: 每页数量
            username: 用户名（模糊搜索）
            nickname: 昵称（模糊搜索）
            phone: 手机号（模糊搜索）
            status: 状态
            organization_id: 组织架构ID（精确匹配）
            profile_filters: 自定义资料字段过滤
            team_ids: 团队ID列表（数据权限过滤，用户需属于这些团队之一）
            include_tenant_info: 是否包含租户信息
            sort_by: 排序字段 (id, username, nickname, created_at, status)
            sort_order: 排序方向 (asc, desc)
        """
        where = []
        filters = {}

        if tenant_id is not None:
            where.append(User.tenant_id == tenant_id)

        if username:
            filters["username"] = ("like", username)
        if nickname:
            filters["nickname"] = ("like", nickname)
        if phone:
            filters["phone"] = ("like", phone)
        if status is not None:
            filters["status"] = status
        if organization_id:
            filters["organization_id"] = organization_id

        if tenant_id is not None and profile_filters:
            profile_config = await self.get_tenant_profile_config(tenant_id)
            profile_field_map = build_user_profile_field_map(profile_config, filterable_only=True)
            for key, raw_value in profile_filters.items():
                field = profile_field_map.get(str(key))
                if not field:
                    continue
                try:
                    condition = self._build_profile_filter_condition(field=field, raw_value=raw_value)
                except ValueError as exc:
                    raise BusinessError(message=f"{field.label}: {exc}") from exc
                if condition is not None:
                    where.append(condition)

        # 数据权限过滤：用户需属于指定团队之一
        if team_ids is not None and len(team_ids) > 0:
            # 子查询：获取属于指定团队的用户ID
            subquery = (
                select(UserTeam.user_id)
                .where(UserTeam.team_id.in_(team_ids))
                .distinct()
            )
            where.append(User.id.in_(subquery))

        # 排序处理
        allowed_sort_fields = {"id", "username", "nickname", "created_at", "status"}
        order_field = sort_by if sort_by in allowed_sort_fields else "id"
        order_desc = sort_order and sort_order.lower() == "desc"

        users, total = await self.get_list(
            page=page,
            page_size=page_size,
            where=where if where else None,
            options=self._default_options,
            order_by=order_field,
            order_desc=order_desc,
            return_total=True,
            **filters,
        )

        if include_tenant_info and users:
            tenant_ids = list({u.tenant_id for u in users})
            tenant_repo = RepositoryBase(self.db, Tenant)
            tenants = await tenant_repo.get_list(
                page_size=0,
                where=[Tenant.id.in_(tenant_ids)],
            )
            tenant_map = {t.id: t for t in tenants}
            for user in users:
                user._tenant_info = tenant_map.get(user.tenant_id)

        return users, total

    async def list_pending_users(
        self,
        tenant_id: int | None = None,
        page: int = 1,
        page_size: int = 10,
        team_ids: list[int] | None = None,
    ) -> tuple[list[User], int]:
        """
        List pending registration users
        
        Args:
            tenant_id: 租户ID
            page: 页码
            page_size: 每页数量
            team_ids: 团队ID列表（数据权限过滤）
        """
        return await self.list_users(
            tenant_id=tenant_id,
            page=page,
            page_size=page_size,
            status=UserStatus.PENDING,
            team_ids=team_ids,
            include_tenant_info=tenant_id is None,
        )

    async def get_user_ids_by_tenant(self, tenant_id: int, user_ids: list[int]) -> list[int]:
        """Return existing user IDs within tenant (soft-deleted excluded)."""
        if not user_ids:
            return []

        from sqlalchemy import select

        stmt = (
            select(User.id)
            .where(
                User.tenant_id == tenant_id,
                User.id.in_(user_ids),
                User.deleted_at.is_(None),
            )
            .order_by(User.id)
        )
        result = await self.db.execute(stmt)
        return [int(user_id) for user_id in result.scalars().all()]

    async def get_existing_user_ids(self, *, tenant_id: int, user_ids: list[int]) -> set[int]:
        """Return existing user IDs within tenant (soft-deleted excluded)."""
        return set(await self.get_user_ids_by_tenant(tenant_id, user_ids))

    @staticmethod
    def _enabled_user_id_tenant_stmt():
        from sqlalchemy import select

        return (
            select(User.id, User.tenant_id)
            .where(
                User.status == int(UserStatus.ENABLED),
                User.deleted_at.is_(None),
            )
            .order_by(User.id)
        )

    async def get_all_enabled_users(self) -> list[tuple[int, int]]:
        """Return enabled (user_id, tenant_id) pairs across all tenants."""
        result = await self.db.execute(self._enabled_user_id_tenant_stmt())
        return [(int(user_id), int(tenant_id)) for user_id, tenant_id in result.all()]

    async def list_enabled_user_id_tenant_pairs(
        self,
        *,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[tuple[int, int]]:
        """List enabled (user_id, tenant_id) pairs across all tenants."""
        stmt = self._enabled_user_id_tenant_stmt().limit(limit).offset(offset)
        result = await self.db.execute(stmt)
        return [(int(user_id), int(tenant_id)) for user_id, tenant_id in result.all()]

    # ==================== 创建用户 ====================

    async def create_user(
        self,
        data: UserCreate,
        tenant_id: int,
        created_by: int | None = None,
    ) -> User:
        """Create user (by admin)"""
        existing = await self.get_by_username_global(data.username)
        if existing:
            raise ConflictError(message=f"Username '{data.username}' already exists")

        email = None
        if data.email and str(data.email).strip():
            email = normalize_email(str(data.email))
            await self._ensure_email_available(email=email, exclude_user_id=None)

        phone = None
        if data.phone and str(data.phone).strip():
            phone = normalize_phone(str(data.phone))
            await self._ensure_phone_available(phone=phone, exclude_user_id=None)

        profile, profile_state, _ = await self.prepare_user_profile(
            tenant_id=tenant_id,
            raw_profile=data.profile,
            source=RegisterSource.ADMIN,
        )

        user = await self.create({
            "tenant_id": tenant_id,
            "username": data.username,
            "password_hash": hash_password(data.password),
            "nickname": data.nickname,
            "email": email,
            "phone": phone,
            "sex": data.sex,
            "description": data.description,
            "organization_id": data.organization_id,
            "status": data.status,
            "register_source": "admin",
            "remark": data.remark,
            "extra": self.build_user_extra_with_profile(
                existing_extra=None,
                profile=profile,
                profile_state=profile_state,
            ),
        })

        if data.role_ids:
            await self._assign_roles(user, data.role_ids, tenant_id)
        else:
            # Assign default "user" role if no roles specified
            from app.domain.roles.service import RoleService
            role_service = RoleService(self.db)
            default_role = await role_service.get_by_code("user", tenant_id)
            if default_role:
                await self._assign_roles(user, [default_role.id], tenant_id)

        if data.group_ids:
            await self._assign_groups(user, data.group_ids, tenant_id)

        team_ids = sorted({int(x) for x in (data.team_ids or []) if int(x) > 0})
        if not team_ids:
            from app.domain.teams.service import TeamService

            team_service = TeamService(self.db)
            default_team = await team_service.ensure_default_team(tenant_id=tenant_id, created_by=created_by)
            team_ids = [int(default_team.id)]

        await self._assign_teams(user, team_ids, tenant_id)

        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def register_user(
        self,
        data: UserRegister,
        tenant_id: int,
        *,
        register_source: str | None = None,
    ) -> User:
        """Self-registration (pending approval)"""
        existing = await self.get_by_username_global(data.username)
        if existing:
            raise ConflictError(message=f"Username '{data.username}' already exists")

        email = None
        if data.email and str(data.email).strip():
            email = normalize_email(str(data.email))
            await self._ensure_email_available(email=email, exclude_user_id=None)

        phone = None
        if data.phone and str(data.phone).strip():
            phone = normalize_phone(str(data.phone))
            await self._ensure_phone_available(phone=phone, exclude_user_id=None)

        profile, profile_state, _ = await self.prepare_user_profile(
            tenant_id=tenant_id,
            raw_profile=data.profile,
            enforce_required=True,
            source=register_source or RegisterSource.SELF,
        )

        user = await self.create({
            "tenant_id": tenant_id,
            "username": data.username,
            "password_hash": hash_password(data.password),
            "nickname": data.nickname or data.username,
            "email": email,
            "phone": phone,
            "status": UserStatus.PENDING,
            "register_source": register_source or RegisterSource.SELF,
            "extra": self.build_user_extra_with_profile(
                existing_extra=None,
                profile=profile,
                profile_state=profile_state,
            ),
        })
        from app.domain.teams.service import TeamService

        team_service = TeamService(self.db)
        default_team = await team_service.ensure_default_team(tenant_id=tenant_id, created_by=None)
        await self._assign_teams(user, [int(default_team.id)], tenant_id)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    # ==================== 审核用户 ====================

    async def audit_user(
        self,
        user_id: int,
        tenant_id: int,
        audit_data: UserAudit,
        auditor_id: int,
    ) -> User:
        """Audit user registration (限定租户)"""
        user = await self.get_user_by_id(user_id, tenant_id)
        if not user:
            raise NotFoundError(message="User not found")
        return await self._do_audit(user, audit_data, auditor_id)

    async def audit_user_any_tenant(
        self,
        user_id: int,
        audit_data: UserAudit,
        auditor_id: int,
    ) -> User:
        """Audit user registration (跨租户，系统管理员用)"""
        user = await self.get_user_by_id_any_tenant(user_id)
        if not user:
            raise NotFoundError(message="User not found")
        return await self._do_audit(user, audit_data, auditor_id)

    async def _do_audit(
        self,
        user: User,
        audit_data: UserAudit,
        auditor_id: int,
    ) -> User:
        """执行审核操作"""
        if user.status != UserStatus.PENDING:
            raise BusinessError(message="User is not in pending status")

        await self.update(user, {
            "status": UserStatus.ENABLED if audit_data.approved else UserStatus.REJECTED,
            "audit_remark": audit_data.remark,
            "audited_at": datetime.now(UTC),
            "audited_by": auditor_id,
        })

        if audit_data.approved:
            tenant_repo = RepositoryBase(self.db, Tenant)
            tenant = await tenant_repo.get_by_id(user.tenant_id, raise_not_found=False)
            role_code = tenant.registration_default_role if tenant else "user"
            default_role = await self._get_default_role(user.tenant_id, role_code=role_code)
            if not default_role and role_code != "user":
                default_role = await self._get_default_role(user.tenant_id, role_code="user")
            if default_role:
                await self._assign_roles(user, [default_role.id], user.tenant_id)

        await self.db.flush()
        await self.db.refresh(user)
        return user

    # ==================== 更新用户 ====================

    async def update_user(
        self,
        user_id: int,
        data: UserUpdate,
        tenant_id: int,
    ) -> User:
        """Update user (限定租户)"""
        user = await self.get_user_by_id(user_id, tenant_id)
        if not user:
            raise NotFoundError(message="User not found")
        return await self._do_update(user, data)

    async def update_user_any_tenant(
        self,
        user_id: int,
        data: UserUpdate,
    ) -> User:
        """Update user (跨租户，系统管理员用)"""
        user = await self.get_user_by_id_any_tenant(user_id)
        if not user:
            raise NotFoundError(message="User not found")
        return await self._do_update(user, data)

    async def _do_update(self, user: User, data: UserUpdate) -> User:
        """执行更新操作"""
        update_data = data.model_dump(exclude_unset=True, exclude={"role_ids", "group_ids", "team_ids"})
        raw_profile = update_data.pop("profile", None) if "profile" in update_data else None

        if "email" in update_data:
            raw_email = update_data.get("email")
            if raw_email is None or not str(raw_email).strip():
                update_data["email"] = None
            else:
                email = normalize_email(str(raw_email))
                await self._ensure_email_available(email=email, exclude_user_id=user.id)
                update_data["email"] = email

        if "phone" in update_data:
            raw_phone = update_data.get("phone")
            if raw_phone is None or not str(raw_phone).strip():
                update_data["phone"] = None
            else:
                phone = normalize_phone(str(raw_phone))
                await self._ensure_phone_available(phone=phone, exclude_user_id=user.id)
                update_data["phone"] = phone

        if raw_profile is not None:
            profile, profile_state, _ = await self.prepare_user_profile(
                tenant_id=user.tenant_id,
                raw_profile=raw_profile,
                existing_extra=user.extra,
                source=user.register_source or RegisterSource.ADMIN,
            )
            update_data["extra"] = self.build_user_extra_with_profile(
                existing_extra=user.extra,
                profile=profile,
                profile_state=profile_state,
            )

        await self.update(user, update_data)

        if data.role_ids is not None:
            await self._clear_roles(user)
            await self._assign_roles(user, data.role_ids, user.tenant_id)
            await bump_tenant_permissions_cache_version(user.tenant_id)

        if data.group_ids is not None:
            await self._clear_groups(user)
            await self._assign_groups(user, data.group_ids, user.tenant_id)

        if data.team_ids is not None:
            team_ids = sorted({int(x) for x in (data.team_ids or []) if int(x) > 0})
            if not team_ids:
                from app.domain.teams.service import TeamService

                team_service = TeamService(self.db)
                default_team = await team_service.ensure_default_team(tenant_id=user.tenant_id, created_by=None)
                team_ids = [int(default_team.id)]

            await self._clear_teams(user)
            await self._assign_teams(user, team_ids, user.tenant_id)

        await self.db.flush()
        await self.db.refresh(user)
        return user

    # ==================== 删除用户 ====================

    async def delete_user(self, user_id: int, tenant_id: int) -> None:
        """Soft delete user (限定租户)"""
        user = await self.get_user_by_id(user_id, tenant_id)
        if not user:
            raise NotFoundError(message="User not found")
        await self.delete(user)

    async def delete_user_any_tenant(self, user_id: int) -> None:
        """Soft delete user (跨租户，系统管理员用)"""
        user = await self.get_user_by_id_any_tenant(user_id)
        if not user:
            raise NotFoundError(message="User not found")
        await self.delete(user)

    # ==================== 密码管理 ====================

    async def change_password(
        self,
        user_id: int,
        tenant_id: int,
        data: PasswordChange,
    ) -> None:
        """Change user password"""
        user = await self.get_user_by_id(user_id, tenant_id)
        if not user:
            raise NotFoundError(message="User not found")

        if not verify_password(data.old_password, user.password_hash):
            raise BusinessError(message="Old password is incorrect")

        await self.update(user, {"password_hash": hash_password(data.new_password)})

    async def reset_password(
        self,
        user_id: int,
        tenant_id: int,
        data: PasswordReset,
    ) -> None:
        """Reset user password (by admin, 限定租户)"""
        user = await self.get_user_by_id(user_id, tenant_id)
        if not user:
            raise NotFoundError(message="User not found")
        await self.update(user, {"password_hash": hash_password(data.new_password)})

    async def reset_password_any_tenant(
        self,
        user_id: int,
        data: PasswordReset,
    ) -> None:
        """Reset user password (by admin, 跨租户)"""
        user = await self.get_user_by_id_any_tenant(user_id)
        if not user:
            raise NotFoundError(message="User not found")
        await self.update(user, {"password_hash": hash_password(data.new_password)})

    # ==================== 登录相关方法 ====================

    async def record_login_failure(self, user: User) -> None:
        """Record login failure and lock account if needed"""
        from datetime import timedelta
        user.failed_login_count += 1
        if user.failed_login_count >= 5:
            user.locked_until = datetime.now(UTC) + timedelta(minutes=30)
        await self.db.flush()

    async def record_login_success(self, user: User) -> None:
        """Record successful login"""
        user.failed_login_count = 0
        user.last_login_at = datetime.now(UTC)
        await self.db.flush()

    # ==================== 权限管理 ====================

    async def get_user_role_codes(
        self,
        user_id: int,
        tenant_id: int | None = None,
    ) -> list[str]:
        """Return active role codes for a user, optionally scoped by tenant."""
        stmt = (
            select(Role.code)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(
                UserRole.user_id == user_id,
                Role.deleted_at.is_(None),
                Role.is_active.is_(True),
            )
            .order_by(Role.sort_order, Role.id)
        )
        if tenant_id is not None:
            stmt = stmt.where(UserRole.tenant_id == tenant_id, Role.tenant_id == tenant_id)
        result = await self.db.execute(stmt)
        return list(
            dict.fromkeys(
                str(code).strip()
                for code in result.scalars().all()
                if str(code or "").strip()
            )
        )

    async def get_user_permissions(self, user_id: int, tenant_id: int | None = None) -> set[str]:
        """
        Get all permission codes for a user.
        
        Collects permissions from all active roles' menus assigned to the user.
        (itrainer design: permissions are stored in menu.perms field)
        
        Args:
            user_id: User ID to get permissions for
            tenant_id: Optional tenant ID for tenant-scoped permission lookup
            
        Returns:
            Set of permission codes (e.g., {"user:create", "role:read"})
        """
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        # Load user with roles and menus
        stmt = (
            select(User)
            .options(
                selectinload(User.roles).selectinload(Role.menus)
            )
            .where(User.id == user_id, User.deleted_at.is_(None))
        )
        if tenant_id is not None:
            stmt = stmt.where(User.tenant_id == tenant_id)
        result = await self.db.execute(stmt)
        user_with_perms = result.scalar_one_or_none()

        if user_with_perms and bool(getattr(user_with_perms, "is_superuser", False)):
            return {"*:*:*"}

        if not user_with_perms and tenant_id is not None:
            superuser_result = await self.db.execute(
                select(User)
                .where(User.id == user_id, User.deleted_at.is_(None), User.is_superuser.is_(True))
                .limit(1)
            )
            superuser = superuser_result.scalar_one_or_none()
            if superuser is not None:
                return {"*:*:*"}

        if not user_with_perms:
            return set()

        # Collect all permission codes from active roles' menus
        permissions = set()
        for role in user_with_perms.roles:
            # Skip inactive roles
            if not role.is_active:
                continue

            # Collect permissions from this role's menus
            for menu in role.menus:
                # Only include active menus with perms
                if menu.is_active and menu.perms:
                    permissions.add(menu.perms)

        return permissions

    # ==================== 辅助方法 ====================

    async def _get_default_role(self, tenant_id: int, *, role_code: str = "user") -> Role | None:
        """Get a tenant role by code (defaults to `user`)"""
        role_repo = RepositoryBase(self.db, Role)
        return await role_repo.get_one(
            where=[Role.tenant_id == tenant_id],
            code=role_code,
        )

    async def _assign_roles(
        self,
        user: User,
        role_ids: list[int],
        tenant_id: int,
    ) -> None:
        """Assign roles to user"""
        for role_id in role_ids:
            user_role = UserRole(
                user_id=user.id,
                role_id=role_id,
                tenant_id=tenant_id,
            )
            self.db.add(user_role)
        await self.db.flush()

    async def _clear_roles(self, user: User) -> None:
        """Clear all roles from user"""
        await self.db.execute(
            delete(UserRole).where(UserRole.user_id == user.id)
        )
        await self.db.flush()

    async def _assign_groups(
        self,
        user: User,
        group_ids: list[int],
        tenant_id: int,
    ) -> None:
        """Assign groups to user"""
        for group_id in group_ids:
            member = UserGroupMember(
                user_id=user.id,
                group_id=group_id,
                tenant_id=tenant_id,
            )
            self.db.add(member)
        await self.db.flush()

    async def _clear_groups(self, user: User) -> None:
        """Clear all groups from user"""
        await self.db.execute(
            delete(UserGroupMember).where(UserGroupMember.user_id == user.id)
        )
        await self.db.flush()

    async def _assign_teams(
        self,
        user: User,
        team_ids: list[int],
        tenant_id: int,
    ) -> None:
        """Assign teams to user"""
        for team_id in team_ids:
            user_team = UserTeam(
                user_id=user.id,
                team_id=team_id,
                tenant_id=tenant_id,
            )
            self.db.add(user_team)
        await self.db.flush()

    async def _clear_teams(self, user: User) -> None:
        """Clear all teams from user"""
        await self.db.execute(
            delete(UserTeam).where(UserTeam.user_id == user.id)
        )
        await self.db.flush()

    # ==================== 数据转换 ====================

    @staticmethod
    def to_list_item(
        user: User,
        include_tenant: bool = False,
        *,
        profile_config: UserProfileFieldsConfig | None = None,
        invitation_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Convert user to list item dict"""
        profile, profile_state = UserService.build_user_profile_state(user, profile_config)
        invitation_context = invitation_context or {}
        result = {
            "id": user.id,
            "username": user.username,
            "nickname": user.nickname,
            "avatar": user.avatar,
            "email": user.email,
            "phone": user.phone,
            "sex": user.sex,
            "status": user.status,
            "registerSource": user.register_source,
            "organization": {
                "id": user.organization.id,
                "name": user.organization.name,
            } if user.organization else None,
            "teams": [
                {"id": team.id, "name": team.name}
                for team in user.teams
            ] if hasattr(user, "teams") and user.teams else [],
            "roles": [role.code for role in user.roles] if user.roles else [],
            "remark": user.remark,
            "profile": profile,
            "profileMeta": profile_state.model_dump(by_alias=True),
            "createdAt": user.created_at.isoformat() if user.created_at else None,
            "invitedByUserId": invitation_context.get("invitedByUserId"),
            "invitedByUsername": invitation_context.get("invitedByUsername"),
            "invitedByNickname": invitation_context.get("invitedByNickname"),
            "invitedViaInviteCode": invitation_context.get("invitedViaInviteCode"),
            "invitedAt": invitation_context.get("invitedAt"),
        }

        if include_tenant:
            result["tenantId"] = user.tenant_id
            tenant_info = getattr(user, "_tenant_info", None)
            result["tenantName"] = tenant_info.name if tenant_info else None

        return result

    @staticmethod
    def to_response(
        user: User,
        *,
        profile_config: UserProfileFieldsConfig | None = None,
        invitation_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Convert user to response dict"""
        profile, profile_state = UserService.build_user_profile_state(user, profile_config)
        invitation_context = invitation_context or {}
        return {
            "id": user.id,
            "username": user.username,
            "nickname": user.nickname,
            "avatar": user.avatar,
            "email": user.email,
            "phone": user.phone,
            "sex": user.sex,
            "status": user.status,
            "description": user.description,
            "registerSource": user.register_source,
            "tenantId": user.tenant_id,
            "organizationId": user.organization_id,
            "remark": user.remark,
            "createdAt": user.created_at.isoformat() if user.created_at else None,
            "lastLoginAt": user.last_login_at.isoformat() if user.last_login_at else None,
            "organization": {
                "id": user.organization.id,
                "name": user.organization.name,
            } if user.organization else None,
            "teams": [
                {"id": team.id, "name": team.name}
                for team in user.teams
            ] if hasattr(user, "teams") and user.teams else [],
            "roles": [
                {"id": role.id, "name": role.name, "code": role.code}
                for role in user.roles
            ] if user.roles else [],
            "groups": [
                {"id": m.group.id, "name": m.group.name, "code": m.group.code}
                for m in user.group_memberships
            ] if hasattr(user, "group_memberships") and user.group_memberships else [],
            "profile": profile,
            "profileMeta": profile_state.model_dump(by_alias=True),
            "mustCompleteProfile": bool(profile_config and profile_config.enabled and profile_config.enforce_after_login and not profile_state.completed),
            "invitedByUserId": invitation_context.get("invitedByUserId"),
            "invitedByUsername": invitation_context.get("invitedByUsername"),
            "invitedByNickname": invitation_context.get("invitedByNickname"),
            "invitedViaInviteCode": invitation_context.get("invitedViaInviteCode"),
            "invitedAt": invitation_context.get("invitedAt"),
        }
