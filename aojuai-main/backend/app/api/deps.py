"""
AOJU Backend - API Dependencies

提供以下依赖注入:
- CurrentUser: 当前认证用户
- CurrentSuperuser: 当前超级管理员
- CurrentTenantAdmin: 当前租户管理员
- DBSession: 数据库会话
- TenantContext: 租户上下文（支持超级管理员切换租户）
- PermissionChecker: 权限检查器
- DataScopeCtx: 数据权限上下文
"""
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Depends, Header, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import lazyload

from app.core.auth_cookies import get_access_cookie
from app.core.data_permission import DataScope, get_user_data_scope
from app.core.exceptions import ForbiddenError, NotFoundError, UnauthorizedError
from app.core.feature_switches import (
    is_module_enabled,
    label_for_module,
    resolve_module_from_api_path,
    resolve_modules_from_permissions,
)
from app.core.module_guards import (
    ensure_module_enabled_for_tenant,
    ensure_public_module_enabled_for_tenant,
)
from app.core.role_semantics import TENANT_ADMIN_ROLE_CODES, has_tenant_admin_role
from app.core.security import decode_token
from app.domain.users.models import User
from app.infrastructure.database import get_db

# HTTP Bearer token security
security = HTTPBearer(auto_error=False)


def _resolve_access_token(
    *,
    credentials: HTTPAuthorizationCredentials | None,
    request: Request,
) -> str | None:
    if credentials and str(credentials.scheme or "").lower() == "bearer":
        token = str(credentials.credentials or "").strip()
        if token:
            return token
    return get_access_cookie(request)


def _current_user_load_options() -> tuple[Any, ...]:
    """Authentication only needs scalar fields, but later permission checks may load relations."""

    return (
        lazyload(User.organization),
        lazyload(User.roles),
        lazyload(User.teams),
        lazyload(User.group_memberships),
    )


async def _load_authenticated_user(*, db: AsyncSession, token: str) -> User:
    payload = decode_token(token)

    if payload.get("type") != "access":
        raise UnauthorizedError(message="Invalid token type")

    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError(message="Invalid token payload")

    from sqlalchemy import select

    stmt = (
        select(User)
        .options(*_current_user_load_options())
        .where(User.id == int(user_id), User.deleted_at.is_(None))
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise UnauthorizedError(message="User not found")

    if not user.is_active:
        raise UnauthorizedError(message="User is not active")

    return user


@dataclass
class TenantContext:
    """
    租户上下文 - 用于确定当前操作的目标租户
    
    对于超级管理员:
    - 可以通过 X-Tenant-Id 请求头指定目标租户
    - 可以通过 tenant_id 查询参数指定目标租户
    - 如果都未指定，使用用户自身的租户ID
    
    对于普通用户:
    - 始终使用用户自身的租户ID
    """
    tenant_id: int
    is_superuser: bool
    user_tenant_id: int  # 用户原始租户ID
    
    @property
    def is_cross_tenant(self) -> bool:
        """是否跨租户操作"""
        return self.tenant_id != self.user_tenant_id


@dataclass
class TenantScopedUser:
    """Wrap an authenticated user with an effective tenant for superuser tenant switching."""

    _user: User
    tenant_id: int
    user_tenant_id: int

    def __getattr__(self, item: str):
        return getattr(self._user, item)


@dataclass(frozen=True)
class CurrentUserSnapshot:
    user_id: int
    tenant_id: int
    user_tenant_id: int
    username: str | None
    nickname: str | None
    is_superuser: bool


def _get_user_tenant_id(current_user: User | TenantScopedUser | Any) -> int:
    return int(getattr(current_user, "user_tenant_id", getattr(current_user, "tenant_id", 0)) or 0)


def snapshot_current_user(current_user: User | TenantScopedUser | Any) -> CurrentUserSnapshot:
    user_tenant_id = _get_user_tenant_id(current_user)
    tenant_id = int(getattr(current_user, "tenant_id", 0) or 0)
    if tenant_id <= 0:
        tenant_id = user_tenant_id
    return CurrentUserSnapshot(
        user_id=int(getattr(current_user, "id", 0) or 0),
        tenant_id=int(tenant_id),
        user_tenant_id=int(user_tenant_id),
        username=str(getattr(current_user, "username", "") or "").strip() or None,
        nickname=str(getattr(current_user, "nickname", "") or "").strip() or None,
        is_superuser=bool(getattr(current_user, "is_superuser", False)),
    )


def _parse_target_tenant_id(current_user: User | TenantScopedUser | Any, request: Request) -> int:
    target_tenant_id = int(getattr(current_user, "tenant_id", 0) or 0)
    if not bool(getattr(current_user, "is_superuser", False)):
        return target_tenant_id

    x_tenant_id = str(request.headers.get("X-Tenant-Id") or "").strip()
    if x_tenant_id:
        try:
            return int(x_tenant_id)
        except ValueError:
            pass

    tenant_id = str(request.query_params.get("tenant_id") or "").strip()
    if tenant_id:
        try:
            return int(tenant_id)
        except ValueError:
            pass

    tenant_id_camel = str(request.query_params.get("tenantId") or "").strip()
    if tenant_id_camel:
        try:
            return int(tenant_id_camel)
        except ValueError:
            pass

    return target_tenant_id


def _with_effective_tenant(current_user: User, request: Request) -> User | TenantScopedUser:
    target_tenant_id = _parse_target_tenant_id(current_user, request)
    current_tenant_id = int(getattr(current_user, "tenant_id", 0) or 0)
    is_superuser = bool(getattr(current_user, "is_superuser", False))
    if not is_superuser or current_tenant_id <= 0 or int(target_tenant_id) == current_tenant_id:
        return current_user
    return TenantScopedUser(
        _user=current_user,
        tenant_id=int(target_tenant_id),
        user_tenant_id=current_tenant_id,
    )


async def _enforce_module_switch_for_request(
    *,
    db: AsyncSession,
    current_user: User,
    request: Request,
) -> None:
    module_code = resolve_module_from_api_path(request.url.path)
    if not module_code:
        return

    target_tenant_id = _parse_target_tenant_id(current_user, request)
    await ensure_module_enabled_for_tenant(
        db=db,
        tenant_id=target_tenant_id,
        module_code=module_code,
    )


async def _enforce_public_module_switch_for_request(
    *,
    db: AsyncSession,
    request: Request,
    current_user: User | None,
) -> None:
    module_code = resolve_module_from_api_path(request.url.path)
    if not module_code:
        return

    if current_user is None:
        # 匿名请求打到模块路径上时，**不许在这里猜租户**。
        # 曾经的实现是 host → code="default" → 第一个活跃租户，
        # 未知 Host 会拿别的租户的开关来判定当前请求，是跨租户误判。
        # 公开端点必须自己声明租户解析（见 app/core/public_site.resolve_public_tenant），
        # 没声明就 fail closed。
        raise NotFoundError()

    tenant_id = _parse_target_tenant_id(current_user, request)
    if not tenant_id:
        raise NotFoundError()
    await ensure_public_module_enabled_for_tenant(
        db=db,
        tenant_id=tenant_id,
        module_code=module_code,
    )


async def _get_user_via_api_key(db: AsyncSession, request: Request) -> User | None:
    """X-API-Key 机器凭证认证（本地同步客户端、外部自动化等）。无该头时返回 None。

    回流自 nextjs-plugins 745c74bf / 4c26e9cf。
    """
    api_key_header = request.headers.get("x-api-key")
    if not api_key_header:
        return None

    from sqlalchemy import select

    from app.domain.auth.api_key_service import ApiKeyService

    api_key = await ApiKeyService.validate_key(db, api_key_header.strip(), request.url.path)

    stmt = (
        select(User)
        .options(*_current_user_load_options())
        .where(User.id == api_key.user_id, User.deleted_at.is_(None))
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise UnauthorizedError(message="API key owner not found")
    if not user.is_active:
        raise UnauthorizedError(message="API key owner is not active")
    if user.tenant_id != api_key.tenant_id:
        raise UnauthorizedError(message="API key tenant mismatch")

    # 标记本请求经 API Key 认证（api-keys 管理端点据此拒绝，防止密钥自我复制）；
    # 并记下**是哪一把** key——同一用户会为不同外部应用各发一把，不区分的话一把泄露就能读到另一把的数据。
    request.state.auth_via_api_key = True
    request.state.api_key_id = int(api_key.id)

    await _enforce_module_switch_for_request(
        db=db,
        current_user=user,
        request=request,
    )
    # API Key 恒用其属主租户，不参与 superuser 的 X-Tenant-Id 跨租户切换：
    # 跨租户切换是交互式会话（JWT，有过期/登出生命周期）的特权；机器凭证是长期的，泄露后不应能漫游任意租户。
    return user


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    request: Request,
) -> User:
    """
    Get current authenticated user from JWT token or X-API-Key.

    优先级：先解析交互式会话凭证（JWT / cookie），存在即用会话身份；仅在无会话凭证时才回退到 X-API-Key。
    这样浏览器请求（总带 cookie）永远走会话，即使被注入 x-api-key 头也不会被顶替为 Key 属主身份。
    """
    token = _resolve_access_token(credentials=credentials, request=request)
    if not token:
        api_key_user = await _get_user_via_api_key(db, request)
        if api_key_user is not None:
            return api_key_user
        raise UnauthorizedError(message="Not authenticated")

    user = await _load_authenticated_user(db=db, token=token)

    await _enforce_module_switch_for_request(
        db=db,
        current_user=user,
        request=request,
    )

    return _with_effective_tenant(user, request)


async def _resolve_optional_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    request: Request,
) -> User | None:
    token = _resolve_access_token(credentials=credentials, request=request)
    user: User | None = None
    if token:
        try:
            user = await _load_authenticated_user(db=db, token=token)
        except UnauthorizedError:
            user = None

    return _with_effective_tenant(user, request) if user is not None else None


async def get_optional_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    request: Request,
) -> User | None:
    """
    Get current authenticated user from JWT token (optional).

    - No credentials: returns None
    - Invalid credentials: returns None (treated as anonymous)
    """
    user = await _resolve_optional_current_user(
        db=db,
        credentials=credentials,
        request=request,
    )

    await _enforce_public_module_switch_for_request(
        db=db,
        request=request,
        current_user=user,
    )
    return user


async def get_public_share_viewer(
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    request: Request,
) -> User | None:
    """Resolve an optional viewer for token-bound public-share routes.

    These routes resolve the authoritative tenant from their share token and
    enforce that tenant's module switch in the share service. Running the
    generic path-based guard before token resolution would reject every
    anonymous visitor because no tenant is known yet.
    """
    return await _resolve_optional_current_user(
        db=db,
        credentials=credentials,
        request=request,
    )


async def get_current_active_superuser(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """
    Get current user and verify they are a superuser.
    """
    if not current_user.is_superuser:
        raise UnauthorizedError(message="Superuser required")
    return current_user


async def get_current_tenant_admin(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """
    Get current user and verify they are a tenant admin (have admin role).
    Superusers are also allowed.
    """
    # 超级管理员自动通过
    actor = snapshot_current_user(current_user)
    if actor.is_superuser:
        return current_user

    # Check if user has tenant admin role
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    stmt = (
        select(User)
        .options(selectinload(User.roles))
        .where(User.id == actor.user_id, User.deleted_at.is_(None))
    )
    result = await db.execute(stmt)
    user_with_roles = result.scalar_one_or_none()

    if user_with_roles:
        active_role_codes = [
            role.code
            for role in user_with_roles.roles
            if getattr(role, "is_active", False) and getattr(role, "deleted_at", None) is None
        ]
        if has_tenant_admin_role(active_role_codes):
            return current_user

    raise UnauthorizedError(message="Tenant admin required")


async def get_tenant_context(
    current_user: Annotated[User, Depends(get_current_user)],
    x_tenant_id: Annotated[int | None, Header(alias="X-Tenant-Id")] = None,
    tenant_id: Annotated[int | None, Query()] = None,
    tenant_id_camel: Annotated[int | None, Query(alias="tenantId")] = None,
) -> TenantContext:
    """
    获取租户上下文 - 确定当前操作的目标租户
    
    优先级（仅对超级管理员有效）:
    1. X-Tenant-Id 请求头
    2. tenant_id 查询参数
    3. 用户自身的租户ID
    
    对于普通用户，始终使用用户自身的租户ID
    
    Args:
        current_user: 当前认证用户
        x_tenant_id: X-Tenant-Id 请求头（可选）
        tenant_id: tenant_id 查询参数（可选）
    
    Returns:
        TenantContext: 租户上下文对象
    
    Example:
        ```python
        @router.get("/users")
        async def list_users(
            tenant_ctx: Annotated[TenantContext, Depends(get_tenant_context)],
            db: DBSession,
        ):
            # 超级管理员可以通过 X-Tenant-Id 或 tenant_id 指定目标租户
            # 普通用户只能操作自己的租户
            users = await service.list_users(tenant_ctx.tenant_id)
            return users
        ```
    """
    actor = snapshot_current_user(current_user)
    user_tenant_id = actor.user_tenant_id
    target_tenant_id = actor.tenant_id

    if actor.is_superuser:
        # 超级管理员可以指定目标租户
        # 优先级: X-Tenant-Id > tenant_id 参数 > tenantId 参数 > 用户自身租户
        if x_tenant_id is not None:
            target_tenant_id = x_tenant_id
        elif tenant_id is not None:
            target_tenant_id = tenant_id
        elif tenant_id_camel is not None:
            target_tenant_id = tenant_id_camel

    return TenantContext(
        tenant_id=int(target_tenant_id),
        is_superuser=bool(actor.is_superuser),
        user_tenant_id=user_tenant_id,
    )


class PermissionChecker:
    """
    Permission checker dependency - 权限检查器依赖项

    Validates that the current user has at least one of the required permissions.
    Superusers automatically pass all permission checks.

    Usage:
        @router.post("/users")
        async def create_user(
            current_user: CurrentUser,
            db: DBSession,
            _: None = Depends(PermissionChecker(["user:create"])),
        ):
            # Only users with 'user:create' permission can access
            ...

    Args:
        required_permissions: List of permission codes. User needs at least one.

    Raises:
        ForbiddenError: If user doesn't have any of the required permissions.
    """

    def __init__(self, required_permissions: list[str]):
        """
        Initialize permission checker.

        Args:
            required_permissions: List of permission codes (e.g., ["user:create", "user:manage"])
        """
        self.required_permissions = set(required_permissions)

    async def __call__(
        self,
        current_user: Annotated[User, Depends(get_current_user)],
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> None:
        """
        Check if current user has required permissions.

        Args:
            current_user: Current authenticated user
            db: Database session

        Raises:
            ForbiddenError: If user lacks required permissions
        """
        # Superusers have all permissions
        actor = snapshot_current_user(current_user)
        if actor.is_superuser:
            return

        required_modules = resolve_modules_from_permissions(self.required_permissions)
        if required_modules:
            from sqlalchemy import select

            from app.domain.auth.models import Tenant

            tenant_config = await db.scalar(
                select(Tenant.config).where(
                    Tenant.id == actor.tenant_id,
                    Tenant.deleted_at.is_(None),
                )
            )
            disabled_modules = [
                module_code
                for module_code in sorted(required_modules)
                if not is_module_enabled(tenant_config, module_code)
            ]
            if disabled_modules:
                module_labels = "、".join(label_for_module(code) for code in disabled_modules)
                raise ForbiddenError(message=f"模块已关闭：{module_labels}")

        # Get user's permissions through UserService
        from app.domain.users.service import UserService

        user_service = UserService(db)
        user_permissions = await user_service.get_user_permissions(actor.user_id, tenant_id=actor.tenant_id)

        # Check for wildcard permission (all permissions)
        if "*:*:*" in user_permissions or "*.*.*" in user_permissions:
            return

        # Check if user has at least one of the required permissions
        if not (self.required_permissions & user_permissions):
            raise ForbiddenError(
                message=f"需要以下权限之一: {', '.join(sorted(self.required_permissions))}"
            )


class TenantAdminOrPermissionChecker(PermissionChecker):
    """
    Tenant-admin OR permission checker dependency.

    - Superusers automatically pass
    - Users with tenant-admin role pass
    - Otherwise, require at least one configured permission
    """

    def __init__(self, required_permissions: list[str], *, admin_role_code: str | None = None):
        super().__init__(required_permissions)
        self.admin_role_codes = (admin_role_code,) if admin_role_code else TENANT_ADMIN_ROLE_CODES

    async def __call__(
        self,
        current_user: Annotated[User, Depends(get_current_user)],
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> None:
        actor = snapshot_current_user(current_user)
        if actor.is_superuser:
            return

        from sqlalchemy import select

        from app.domain.roles.models import Role
        from app.domain.users.models import UserRole

        stmt = (
            select(Role.id)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(
                UserRole.tenant_id == actor.tenant_id,
                UserRole.user_id == actor.user_id,
                Role.tenant_id == actor.tenant_id,
                Role.code.in_(self.admin_role_codes),
                Role.is_active.is_(True),
                Role.deleted_at.is_(None),
            )
            .limit(1)
        )
        result = await db.execute(stmt)
        if result.scalar_one_or_none() is not None:
            return

        await super().__call__(current_user=current_user, db=db)


async def get_data_scope(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DataScope:
    """
    获取当前用户的数据权限范围
    
    返回用户可以读取、编辑、删除的团队ID列表。
    
    Args:
        current_user: 当前认证用户
        db: 数据库会话
    
    Returns:
        DataScope: 数据权限范围对象
    
    Example:
        ```python
        @router.get("/items")
        async def list_items(
            data_scope: DataScopeCtx,
            db: DBSession,
        ):
            # 根据数据权限过滤数据
            if data_scope.has_all_read_access:
                # 可以看到所有数据
                items = await service.list_all()
            else:
                # 只能看到指定团队的数据
                items = await service.list_by_team_ids(data_scope.read_team_ids)
            return items
        ```
    """
    return await get_user_data_scope(db, current_user)


# Type aliases for dependency injection
CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalCurrentUser = Annotated[User | None, Depends(get_optional_current_user)]
PublicShareViewer = Annotated[User | None, Depends(get_public_share_viewer)]
CurrentSuperuser = Annotated[User, Depends(get_current_active_superuser)]
CurrentTenantAdmin = Annotated[User, Depends(get_current_tenant_admin)]
DBSession = Annotated[AsyncSession, Depends(get_db)]
TenantCtx = Annotated[TenantContext, Depends(get_tenant_context)]
DataScopeCtx = Annotated[DataScope, Depends(get_data_scope)]
