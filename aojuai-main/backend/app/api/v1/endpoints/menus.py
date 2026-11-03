"""
AOJU Backend - Menu Management Endpoints

权限设计:
- 菜单管理（CRUD）: 仅系统管理员 (is_superuser=True)
- 获取路由菜单: 所有已认证用户
- 获取菜单树选项: 租户管理员或系统管理员
"""
from functools import lru_cache
from typing import Any

from fastapi import APIRouter
from pydantic import AliasChoices, BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.api.deps import CurrentSuperuser, CurrentTenantAdmin, CurrentUser, DBSession, snapshot_current_user
from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.core.feature_switches import is_module_enabled, resolve_module_from_route_path
from app.core.response import SuccessResponse
from app.core.schemas import PageResponse, ResponseBase
from app.domain.auth.models import Tenant
from app.domain.menus.models import Menu
from app.domain.menus.service import MenuService
from app.domain.roles.models import Role, RoleMenu
from app.domain.users.models import UserRole
from app.infrastructure.cache import (
    MENU_ROUTES_TTL_SECONDS,
    MENU_TREE_OPTIONS_TTL_SECONDS,
    build_menu_routes_cache_key,
    build_menu_tree_options_cache_key,
    get_menu_routes_cache_versions,
    get_menu_tree_options_cache_version,
)
from app.infrastructure.cache.base_runtime_keys import invalidate_menu_runtime_cache
from app.infrastructure.cache.runtime_cache import remember_json

router = APIRouter()


async def _load_user_menu_ids(*, db: DBSession, tenant_id: int, user_id: int) -> set[int]:
    filters = [
        UserRole.tenant_id == tenant_id,
        UserRole.user_id == user_id,
        Role.tenant_id == tenant_id,
        Role.is_active.is_(True),
    ]
    if hasattr(UserRole, "deleted_at"):
        filters.append(UserRole.deleted_at.is_(None))
    if hasattr(Role, "deleted_at"):
        filters.append(Role.deleted_at.is_(None))
    if hasattr(RoleMenu, "deleted_at"):
        filters.append(RoleMenu.deleted_at.is_(None))

    result = await db.execute(
        select(RoleMenu.menu_id)
        .join(Role, Role.id == RoleMenu.role_id)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(*filters)
    )
    return {int(menu_id) for menu_id in result.scalars().all() if menu_id is not None}


# ============== Schemas ==============


class MenuListQuery(BaseModel):
    """Menu list query parameters
    
    Following itrainer design: no name field, only title for display
    """

    page: int = Field(1, ge=1, alias="currentPage")
    page_size: int = Field(
        100,
        ge=1,
        le=1000,
        alias="pageSize",
        validation_alias=AliasChoices("pageSize", "size"),
    )
    title: str | None = None
    is_active: bool | None = Field(None, alias="isActive")

    model_config = ConfigDict(populate_by_name=True)


class MenuCreate(BaseModel):
    """Create menu request
    
    Following itrainer design: no name field, only title for display
    """

    title: str = Field(..., min_length=1, max_length=100)
    path: str | None = Field(None, max_length=200)
    component: str | None = Field(None, max_length=200)
    redirect: str | None = Field(None, max_length=200)
    parent_id: int | None = Field(None, alias="parentId")
    icon: str | None = Field(None, max_length=50)
    sort_order: int = Field(0, alias="sortOrder")
    menu_type: str = Field("1", alias="menuType", pattern=r"^[012]$")
    perms: str | None = Field(None, max_length=100)
    is_visible: bool = Field(True, alias="isVisible")
    is_cache: bool = Field(False, alias="isCache")
    is_frame: bool = Field(False, alias="isFrame")
    frame_src: str | None = Field(None, alias="frameSrc", max_length=500)
    is_active: bool = Field(True, alias="isActive")
    no_cache: bool = Field(False, alias="noCache")
    breadcrumb: bool = Field(True)
    affix: bool = Field(False)
    no_tags_view: bool = Field(False, alias="noTagsView")
    can_to: bool = Field(False, alias="canTo")
    always_show: bool = Field(True, alias="alwaysShow")
    meta: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class MenuUpdate(BaseModel):
    """Update menu request
    
    Following itrainer design: no name field, only title for display
    """

    title: str | None = Field(None, min_length=1, max_length=100)
    path: str | None = Field(None, max_length=200)
    component: str | None = Field(None, max_length=200)
    redirect: str | None = Field(None, max_length=200)
    parent_id: int | None = Field(None, alias="parentId")
    icon: str | None = Field(None, max_length=50)
    sort_order: int | None = Field(None, alias="sortOrder")
    menu_type: str | None = Field(None, alias="menuType", pattern=r"^[012]$")
    perms: str | None = Field(None, max_length=100)
    is_visible: bool | None = Field(None, alias="isVisible")
    is_cache: bool | None = Field(None, alias="isCache")
    is_frame: bool | None = Field(None, alias="isFrame")
    frame_src: str | None = Field(None, alias="frameSrc", max_length=500)
    is_active: bool | None = Field(None, alias="isActive")
    no_cache: bool | None = Field(None, alias="noCache")
    breadcrumb: bool | None = None
    affix: bool | None = None
    no_tags_view: bool | None = Field(None, alias="noTagsView")
    can_to: bool | None = Field(None, alias="canTo")
    always_show: bool | None = Field(None, alias="alwaysShow")
    meta: dict[str, Any] | None = None

    model_config = ConfigDict(populate_by_name=True)


class MenuItem(BaseModel):
    """Menu item (flat list, vue-pure-admin compatible)
    
    Following itrainer design: no name field, only title for display
    """

    id: int
    title: str
    path: str | None = None
    component: str | None = None
    redirect: str | None = None
    parent_id: int | None = Field(None, alias="parentId")
    level: int = 1
    icon: str | None = None
    sort_order: int = Field(0, alias="sortOrder")
    menu_type: str = Field("1", alias="menuType")
    perms: str | None = None
    is_visible: bool = Field(True, alias="isVisible")
    is_cache: bool = Field(False, alias="isCache")
    is_frame: bool = Field(False, alias="isFrame")
    frame_src: str | None = Field(None, alias="frameSrc")
    is_active: bool = Field(True, alias="isActive")
    no_cache: bool = Field(False, alias="noCache")
    breadcrumb: bool = True
    affix: bool = False
    no_tags_view: bool = Field(False, alias="noTagsView")
    can_to: bool = Field(False, alias="canTo")
    always_show: bool = Field(True, alias="alwaysShow")
    meta: dict[str, Any] = {}
    created_at: str | None = Field(None, alias="createdAt")
    updated_at: str | None = Field(None, alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)


class MenuListResponse(ResponseBase[PageResponse[MenuItem]]):
    """Menu list response (paginated flat list)"""

    pass


class RouteItem(BaseModel):
    """Route item for frontend"""

    path: str
    name: str
    component: str | None = None
    redirect: str | None = None
    meta: dict[str, Any] = {}
    children: list["RouteItem"] = []


class RouteListResponse(ResponseBase[list[RouteItem]]):
    """Route list response"""

    pass


class MenuTreeItem(BaseModel):
    """Menu tree item for role permission assignment"""

    value: int
    label: str
    order: int = Field(0, alias="sortOrder")
    children: list["MenuTreeItem"] = []

    model_config = ConfigDict(populate_by_name=True)


class MenuTreeResponse(ResponseBase[list[MenuTreeItem]]):
    """Menu tree response"""

    pass


# ============== Helper Functions ==============

# 超级管理员专属菜单标题（非超级管理员不可见）
# 包括菜单管理和租户管理
# Following itrainer design: use title instead of name
SUPERUSER_ONLY_MENU_TITLES = {"菜单管理", "租户管理"}
# 路由菜单中过滤“系统级”菜单：租户管理员只应看到租户内配置，不显示租户平台管理入口
SUPERUSER_ONLY_ROUTE_MENU_TITLES = {"菜单管理", "租户管理", "租户列表"}
# 租户设置扩展页：以 Tab 承载，不再作为独立菜单入口
TENANT_SETTINGS_EXTENSION_PATHS = {
    "/system/ai-settings",
    "/system/speech-settings",
    "/system/tenant-settings?tab=ai",
    "/system/tenant-settings?tab=speech",
}

LEGACY_ROUTE_PATH_ALIASES: dict[str, str] = {
    "/system/ai-settings": "/system/tenant-settings?tab=ai",
    "/system/speech-settings": "/system/tenant-settings?tab=speech",
}

# 产品裁剪：用于隐藏已折叠为 tab 或已下线的路由入口
REMOVED_ROUTE_PATHS: set[str] = set()
REMOVED_ROUTE_TITLES: set[str] = set()
REMOVED_ROUTE_COMPONENTS: set[str] = set()


def _normalize_route_path(path: str | None) -> str | None:
    value = str(path or "").strip()
    if not value:
        return None

    if value.startswith("#/"):
        value = value[1:].strip()
    elif value.startswith("#"):
        value = value[1:].strip()

    if "#/" in value:
        value = "/" + value.split("#/", 1)[1].strip()
    elif "#" in value:
        value = value.split("#", 1)[0].strip()

    if not value:
        return None

    if not value.startswith("/"):
        value = f"/{value.lstrip('/')}"

    if len(value) > 1:
        value = value.rstrip("/")

    return value or "/"


def _canonical_legacy_route_path(path: str | None) -> str | None:
    normalized = _normalize_route_path(path)
    if not normalized:
        return normalized

    base_path, sep, query = normalized.partition("?")
    mapped_path = LEGACY_ROUTE_PATH_ALIASES.get(base_path, base_path)
    if not sep:
        return mapped_path
    if "?" in mapped_path:
        return f"{mapped_path}&{query}"
    return f"{mapped_path}?{query}"


@lru_cache(maxsize=1)
def _get_runtime_removed_paths() -> set[str]:
    paths = set(REMOVED_ROUTE_PATHS)
    raw = (settings.AOJ_ROUTE_EXCLUDE_PATHS or "").strip()
    if not raw:
        return paths

    for chunk in raw.replace("\n", ",").replace(";", ",").split(","):
        normalized = _normalize_route_path(chunk.strip())
        if normalized:
            paths.add(normalized)
    return paths


def _filter_routes_by_path(
    routes: list[dict[str, Any]], removed_paths: set[str]
) -> list[dict[str, Any]]:
    """
    Recursively filter routes by path.

    This is used to hide deprecated modules without requiring DB migrations.
    """
    filtered: list[dict[str, Any]] = []
    for route in routes or []:
        if not isinstance(route, dict):
            continue
        if route.get("path") in removed_paths:
            continue
        if route.get("component") in REMOVED_ROUTE_COMPONENTS:
            continue
        meta = route.get("meta") if isinstance(route.get("meta"), dict) else {}
        if meta.get("title") in REMOVED_ROUTE_TITLES:
            continue
        children = route.get("children")
        if isinstance(children, list) and children:
            route = dict(route)
            route["children"] = _filter_routes_by_path(children, removed_paths)
        filtered.append(route)
    return filtered


def _filter_routes_by_feature_switches(
    routes: list[dict[str, Any]],
    tenant_config: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Filter route tree by tenant module switches."""
    filtered: list[dict[str, Any]] = []
    for route in routes or []:
        if not isinstance(route, dict):
            continue

        module_code = resolve_module_from_route_path(route.get("path"))
        if module_code and not is_module_enabled(tenant_config, module_code):
            continue

        children = route.get("children")
        route_copy = dict(route)
        if isinstance(children, list):
            route_copy["children"] = _filter_routes_by_feature_switches(children, tenant_config)

        filtered.append(route_copy)

    return filtered


def _dedupe_sibling_menus(
    sibling_menus: list[Menu],
    prefer_ids: set[int] | None = None,
) -> list[Menu]:
    """Dedupe sibling route/page menus by path while keeping button menus intact."""

    deduped: dict[tuple[str, str], Menu] = {}

    def key_of(menu: Menu) -> tuple[str, str]:
        normalized_path = _normalize_route_path(menu.path)
        # 按钮菜单通常无 path，不能参与 path 去重
        if menu.menu_type == "2" or not normalized_path:
            return ("id", str(menu.id))
        return (menu.menu_type, normalized_path)

    for menu in sorted(sibling_menus, key=lambda m: (m.sort_order, m.id)):
        key = key_of(menu)
        current = deduped.get(key)
        if current is None:
            deduped[key] = menu
            continue
        if prefer_ids is None:
            continue
        current_visible = current.id in prefer_ids
        menu_visible = menu.id in prefer_ids
        if menu_visible and not current_visible:
            deduped[key] = menu

    return sorted(deduped.values(), key=lambda m: (m.sort_order, m.id))


def build_menu_tree(
    menus: list[Menu],
    parent_id: int | None = None,
    exclude_superuser_menus: bool = False,
) -> list[dict[str, Any]]:
    """
    Build menu tree for role permission assignment

    Args:
        menus: 菜单列表
        parent_id: 父菜单ID
        exclude_superuser_menus: 是否排除超级管理员专属菜单（菜单管理、租户管理）及其子菜单
    """
    # 如果需要排除超级管理员专属菜单，先找出这些菜单的ID
    excluded_ids: set[int] = set()
    if exclude_superuser_menus:
        # 找出超级管理员专属菜单的ID (use title instead of name, following itrainer design)
        superuser_menu_ids = {m.id for m in menus if m.title in SUPERUSER_ONLY_MENU_TITLES}
        excluded_ids.update(superuser_menu_ids)

        # 递归找出所有子菜单的ID
        def find_children_ids(parent_ids: set[int]) -> set[int]:
            children_ids = {m.id for m in menus if m.parent_id in parent_ids}
            if children_ids:
                children_ids.update(find_children_ids(children_ids))
            return children_ids

        excluded_ids.update(find_children_ids(superuser_menu_ids))

    children_map: dict[int | None, list[Menu]] = {}
    for menu in menus:
        # 跳过被排除的菜单
        if menu.id in excluded_ids:
            continue
        children_map.setdefault(menu.parent_id, []).append(menu)

    for pid, children in children_map.items():
        children_map[pid] = _dedupe_sibling_menus(children)

    def dfs(pid: int | None) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for menu in children_map.get(pid, []):
            if menu.deleted_at is not None:
                continue
            item = {
                "value": menu.id,
                "label": menu.title,
                "order": menu.sort_order,
            }
            children_items = dfs(menu.id)
            if children_items:
                item["children"] = children_items
            result.append(item)
        return result

    return dfs(parent_id)


def build_route_tree(
    menus: list[Menu],
    user_menu_ids: set[int] | None,
    is_superuser: bool,
) -> list[dict[str, Any]]:
    """
    Build route tree for frontend.
    
    Following itrainer design:
    - Route name is generated from path hierarchically
    - e.g., "/system" -> "System", "/system/user" -> "SystemUser"
    
    Args:
        menus: All available menus
        user_menu_ids: Set of menu IDs that user has access to (None for superuser = all access)
        is_superuser: Whether user is superuser
    """
    excluded_ids: set[int] = set()
    if not is_superuser:
        # 非超级管理员过滤系统级菜单（避免点进页面后 403）
        superuser_menu_ids = {m.id for m in menus if m.title in SUPERUSER_ONLY_ROUTE_MENU_TITLES}
        excluded_ids.update(superuser_menu_ids)

        def find_children_ids(parent_ids: set[int]) -> set[int]:
            children_ids = {m.id for m in menus if m.parent_id in parent_ids}
            if children_ids:
                children_ids.update(find_children_ids(children_ids))
            return children_ids

        excluded_ids.update(find_children_ids(superuser_menu_ids))

    children_map: dict[int | None, list[Menu]] = {}
    for menu in menus:
        if excluded_ids and menu.id in excluded_ids:
            continue
        children_map.setdefault(menu.parent_id, []).append(menu)

    for parent_id, children in children_map.items():
        children_map[parent_id] = _dedupe_sibling_menus(children, prefer_ids=user_menu_ids)

    def dfs(parent_id: int | None, parent_name: str = "") -> list[dict[str, Any]]:
        routes: list[dict[str, Any]] = []
        for menu in children_map.get(parent_id, []):
            normalized_menu_path = _normalize_route_path(menu.path)
            # Skip inactive or deleted menus
            # Note: is_visible 仅控制是否在菜单中展示（meta.showLink），隐藏路由仍应返回以支持跳转
            if not menu.is_active or menu.deleted_at is not None:
                continue
            # Skip buttons (menu_type="2") in route generation
            if menu.menu_type == "2":
                continue
            # Check superuser requirement
            if not is_superuser and (menu.meta or {}).get("requireSuperuser") is True:
                continue
            # Check permission: user must have this menu in their role's menu list
            if user_menu_ids is not None and menu.id not in user_menu_ids:
                continue

            route = menu.to_route_dict(parent_name)
            route_path = _canonical_legacy_route_path(route.get("path"))
            route_redirect = _canonical_legacy_route_path(route.get("redirect"))

            if route_path is not None:
                route["path"] = route_path
            elif route.get("path") is not None:
                route.pop("path", None)

            if route_redirect is not None:
                route["redirect"] = route_redirect
            elif route.get("redirect") is not None:
                route.pop("redirect", None)

            # Pass current route name as parent_name
            current_name = route.get("name") or parent_name
            children_routes = dfs(menu.id, current_name)

            if route_path is None:
                if not children_routes:
                    continue
                route_path = f"/__menu_group__/{menu.id}"
                route["path"] = route_path
                route["redirect"] = children_routes[0].get("path")
                route.setdefault("meta", {})
                route["meta"]["canTo"] = False

            normalized_route_path = (route.get("path") or "").rstrip("/")
            if normalized_route_path in TENANT_SETTINGS_EXTENSION_PATHS:
                route.setdefault("meta", {})
                route["meta"]["showLink"] = False
                route["meta"]["hidden"] = True
                route["meta"]["canTo"] = True
                route["meta"]["tenantSettingsExtension"] = True

            if children_routes:
                route["children"] = children_routes
                # pure-admin 通过子路由 meta.showParent 控制“即使只有一个子菜单也显示父级”
                if menu.always_show and len(children_routes) == 1:
                    children_routes[0].setdefault("meta", {})["showParent"] = True
            routes.append(route)
        return routes

    return dfs(None, "")


# ============== Endpoints ==============


@router.post("", response_model=MenuListResponse)
async def get_menu_list(
    query: MenuListQuery,
    current_user: CurrentSuperuser,
    db: DBSession,
) -> dict[str, Any]:
    """
    Get menu list with pagination (flat).

    仅系统管理员可访问。菜单**逐租户**一份，这里只列当前租户的。
    Following itrainer design: no name field, only title for display.
    """
    service = MenuService(db)
    menus, total = await service.list_menus_paginated(
        page=query.page,
        page_size=query.page_size,
        title=query.title,
        is_active=query.is_active,
        tenant_id=current_user.tenant_id,
    )

    return SuccessResponse(
        data={
            "list": [MenuService.to_list_item(m) for m in menus],
            "total": total,
            "pageSize": query.page_size,
            "currentPage": query.page,
        }
    )


@router.get("/tree/options", response_model=MenuTreeResponse)
async def get_menu_tree_options(
    current_user: CurrentTenantAdmin,
    db: DBSession,
) -> dict[str, Any]:
    """
    Get menu tree options for role permission assignment.
    Returns tree structure with value/label format.

    租户管理员可访问（用于配置角色权限）。菜单是系统级配置，所有租户共享。
    非超级管理员不返回菜单管理及其子菜单。
    """
    actor = snapshot_current_user(current_user)
    menu_version = await get_menu_tree_options_cache_version(is_superuser=actor.is_superuser)
    exclude_superuser_menus = not actor.is_superuser
    cache_key = build_menu_tree_options_cache_key(
        tenant_id=actor.tenant_id,
        is_superuser=actor.is_superuser,
        menu_version=menu_version,
    )

    async def _load_tree() -> list[dict[str, Any]]:
        # 菜单行是**逐租户**的（reconciler 按 tenant_id 读写，每租户一份副本），
        # 所以这里必须按租户过滤——**超管也一样**。
        # 不过滤的后果实测过：建第二个租户后，18 个 CMS 菜单标题各有 2 份，
        # 超管的菜单树里会重复出现。租户隔离是比菜单权限更外层的硬边界，
        # 不该由"超管不过滤"这条权限规则顺带绕过；超管要看别的租户请切租户。
        stmt = (
            select(Menu)
            .where(
                Menu.tenant_id == actor.tenant_id,
                Menu.deleted_at.is_(None),
                Menu.is_active.is_(True),
            )
            .order_by(Menu.sort_order)
        )
        result = await db.execute(stmt)
        menus = list(result.scalars().all())
        return build_menu_tree(menus, exclude_superuser_menus=exclude_superuser_menus)

    tree = await remember_json(
        cache_key,
        ttl_seconds=MENU_TREE_OPTIONS_TTL_SECONDS,
        loader=_load_tree,
    )
    return SuccessResponse(data=tree)


@router.get("/routes", response_model=RouteListResponse)
async def get_async_routes(
    current_user: CurrentUser,
    db: DBSession,
) -> dict[str, Any]:
    """
    Get async routes for current user.
    Returns routes filtered by user permissions.

    Permission logic (itrainer design):
    - Superuser: has access to all menus
    - Regular user: only has access to menus assigned to their roles
    - Menu access is determined by role-menu associations, not by perms field

    菜单逐租户一份；先按租户过滤，再按角色授权过滤。
    """
    actor = snapshot_current_user(current_user)
    menu_version, tenant_ui_version, tenant_permissions_version = await get_menu_routes_cache_versions(actor.tenant_id)
    cache_key = build_menu_routes_cache_key(
        tenant_id=actor.tenant_id,
        user_id=actor.user_id,
        is_superuser=actor.is_superuser,
        menu_version=menu_version,
        tenant_ui_version=tenant_ui_version,
        tenant_permissions_version=tenant_permissions_version,
    )

    async def _load_routes() -> list[dict[str, Any]]:
        user_menu_ids: set[int] | None = None if actor.is_superuser else await _load_user_menu_ids(
            db=db,
            tenant_id=actor.tenant_id,
            user_id=actor.user_id,
        )

        # 菜单行是**逐租户**的（reconciler 按 tenant_id 读写，每租户一份副本），
        # 所以这里必须按租户过滤——**超管也一样**。
        # 不过滤的后果实测过：建第二个租户后，18 个 CMS 菜单标题各有 2 份，
        # 超管的菜单树里会重复出现。租户隔离是比菜单权限更外层的硬边界，
        # 不该由"超管不过滤"这条权限规则顺带绕过；超管要看别的租户请切租户。
        stmt = (
            select(Menu)
            .where(
                Menu.tenant_id == actor.tenant_id,
                Menu.deleted_at.is_(None),
                Menu.is_active.is_(True),
            )
            .order_by(Menu.sort_order)
        )
        result = await db.execute(stmt)
        menus = list(result.scalars().all())

        routes = build_route_tree(menus, user_menu_ids, actor.is_superuser)
        routes = _filter_routes_by_path(routes, _get_runtime_removed_paths())

        tenant_config = await db.scalar(
            select(Tenant.config).where(
                Tenant.id == actor.tenant_id,
                Tenant.deleted_at.is_(None),
            )
        )
        return _filter_routes_by_feature_switches(routes, tenant_config)

    routes = await remember_json(
        cache_key,
        ttl_seconds=MENU_ROUTES_TTL_SECONDS,
        loader=_load_routes,
    )
    return SuccessResponse(data=routes)


@router.get("/{menu_id}", response_model=ResponseBase[MenuItem])
async def get_menu(
    menu_id: int,
    current_user: CurrentSuperuser,
    db: DBSession,
) -> dict[str, Any]:
    """
    Get menu by ID.

    仅系统管理员可访问。菜单逐租户一份，只能操作当前租户的。
    """
    service = MenuService(db)
    menu = await service.get_by_id(menu_id, tenant_id=current_user.tenant_id)
    if not menu:
        raise NotFoundError(message="Menu not found")

    return SuccessResponse(data=MenuService.to_response(menu))


@router.post("/create", response_model=ResponseBase[MenuItem])
async def create_menu(
    data: MenuCreate,
    current_user: CurrentSuperuser,
    db: DBSession,
) -> dict[str, Any]:
    """
    Create new menu.

    仅系统管理员可访问。菜单逐租户一份，只能操作当前租户的。
    """
    service = MenuService(db)
    menu_data = data.model_dump(exclude_unset=True, by_alias=False)
    # 如果有父级菜单，则设置 always_show 为 False（与 itrainer 逻辑一致）
    # 只有顶级菜单才可能需要 always_show = True
    if menu_data.get("parent_id"):
        menu_data["always_show"] = False
    # 菜单逐租户，新建的菜单归当前租户；原来写死 tenant_id=1，
    # 导致超管在别的租户下建的菜单落进了 1 号租户。
    menu = await service.create_menu(menu_data, tenant_id=current_user.tenant_id)
    await invalidate_menu_runtime_cache()
    return SuccessResponse(data=MenuService.to_response(menu))


@router.put("/{menu_id}", response_model=ResponseBase[MenuItem])
async def update_menu(
    menu_id: int,
    data: MenuUpdate,
    current_user: CurrentSuperuser,
    db: DBSession,
) -> dict[str, Any]:
    """
    Update menu.

    仅系统管理员可访问。菜单逐租户一份，只能操作当前租户的。
    """
    service = MenuService(db)
    menu_data = data.model_dump(exclude_unset=True, by_alias=False)
    # 如果更新了 parent_id 且不为 None，则设置 always_show 为 False（与 itrainer 逻辑一致）
    if "parent_id" in menu_data and menu_data["parent_id"] is not None:
        menu_data["always_show"] = False
    menu = await service.update_menu(menu_id, menu_data, tenant_id=current_user.tenant_id)
    await invalidate_menu_runtime_cache()
    return SuccessResponse(data=MenuService.to_response(menu))


@router.delete("/{menu_id}")
async def delete_menu(
    menu_id: int,
    current_user: CurrentSuperuser,
    db: DBSession,
) -> dict[str, Any]:
    """
    Delete menu (soft delete).

    仅系统管理员可访问。菜单逐租户一份，只能操作当前租户的。
    """
    service = MenuService(db)
    await service.delete_menu(menu_id, tenant_id=current_user.tenant_id)
    await invalidate_menu_runtime_cache()
    return SuccessResponse(message="Menu deleted")
