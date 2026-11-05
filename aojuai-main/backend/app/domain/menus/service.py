"""
AOJU Backend - Menu Service

Menu management service with CRUD operations.
Menus are system-level configuration, not tenant-scoped.
Supports vue-pure-admin compatible route format.
"""
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BusinessError, NotFoundError
from app.domain.menus.models import Menu
from app.infrastructure.cache import bump_menu_structure_cache_version
from app.infrastructure.repository.base import RepositoryBase


async def expand_menu_ids_with_ancestors(
    db: AsyncSession,
    menu_ids: list[int] | set[int] | tuple[int, ...],
) -> list[int]:
    """Expand menu ids so role assignments include active ancestor containers."""
    normalized_ids = {int(menu_id) for menu_id in menu_ids if menu_id is not None}
    if not normalized_ids:
        return []

    known_ids = set(normalized_ids)
    pending_ids = set(normalized_ids)

    while pending_ids:
        result = await db.execute(
            select(Menu.id, Menu.parent_id).where(
                Menu.id.in_(pending_ids),
                Menu.deleted_at.is_(None),
                Menu.is_active.is_(True),
            )
        )
        rows = list(result.all())
        next_pending: set[int] = set()
        for _menu_id, parent_id in rows:
            if parent_id is None:
                continue
            parent_menu_id = int(parent_id)
            if parent_menu_id in known_ids:
                continue
            known_ids.add(parent_menu_id)
            next_pending.add(parent_menu_id)
        pending_ids = next_pending

    result = await db.execute(
        select(Menu.id, Menu.level, Menu.sort_order).where(
            Menu.id.in_(known_ids),
            Menu.deleted_at.is_(None),
            Menu.is_active.is_(True),
        )
    )
    rows = list(result.all())
    rows.sort(key=lambda row: (int(row.level or 0), int(row.sort_order or 0), int(row.id)))
    return [int(row.id) for row in rows]


class MenuService(RepositoryBase[Menu]):
    """Menu business logic - System level (not tenant scoped)"""

    def __init__(self, db: AsyncSession):
        super().__init__(db, Menu)
        self._default_options = [selectinload(Menu.children)]

    async def get_by_id(self, menu_id: int, *, tenant_id: int | None = None) -> Menu | None:
        """按 id 取菜单；给了 tenant_id 就限定在该租户内。

        菜单行逐租户一份，跨租户按 id 直取等于允许改别人家的菜单。
        `tenant_id=None` 只保留给内部按 id 回溯父级这类已经确定同租户的场景。
        """
        where = [Menu.id == menu_id]
        if tenant_id is not None:
            where.append(Menu.tenant_id == tenant_id)
        return await self.get_one(
            where=where,
            options=self._default_options,
        )

    async def get_by_title(self, title: str) -> Menu | None:
        """Get menu by title (system level)"""
        return await self.get_one(
            where=[Menu.title == title],
        )

    async def list_menus_paginated(
        self,
        page: int = 1,
        page_size: int = 10,
        title: str | None = None,
        is_active: bool | None = None,
        *,
        tenant_id: int,
    ) -> tuple[list[Menu], int]:
        """List menus (flat) with pagination，限定在指定租户内。

        Following itrainer design: no name field, only title for display

        原来不带租户条件，菜单管理页会把所有租户的菜单混在一起列出来。
        """
        where = [Menu.tenant_id == tenant_id]

        if title:
            where.append(Menu.title.ilike(f"%{title}%"))
        if is_active is not None:
            where.append(Menu.is_active == is_active)

        return await self.get_list(
            page=page,
            page_size=page_size,
            where=where if where else None,
            order_by="sort_order",
            return_total=True,
        )

    async def create_menu(self, data: dict[str, Any], *, tenant_id: int) -> Menu:
        """Create menu under the given tenant.

        Following itrainer design: no name field, only title for display

        菜单行是逐租户的（reconciler 按 tenant_id 读写，每租户一份副本），
        调用方必须显式传入租户；原来这里写死 tenant_id=1。
        """
        parent_id = data.get("parent_id")
        level = 1
        if parent_id:
            parent = await self.get_by_id(parent_id)
            if not parent:
                raise NotFoundError(message="Parent menu not found")
            level = parent.level + 1

        meta = data.get("meta", {}) or {}
        if "title" not in meta:
            meta["title"] = data.get("title", "")
        if "icon" not in meta and data.get("icon"):
            meta["icon"] = data["icon"]
        if "showLink" not in meta:
            meta["showLink"] = data.get("is_visible", True)
        if "keepAlive" not in meta:
            meta["keepAlive"] = data.get("is_cache", False)
        if "rank" not in meta:
            meta["rank"] = data.get("sort_order", 0)

        menu_data = {
            "tenant_id": tenant_id,
            "title": data.get("title", ""),
            "path": data.get("path"),
            "component": data.get("component"),
            "redirect": data.get("redirect"),
            "parent_id": parent_id,
            "level": level,
            "icon": data.get("icon"),
            "sort_order": data.get("sort_order", 0),
            "menu_type": data.get("menu_type", "1"),  # Default to menu type
            "perms": data.get("perms"),
            "is_visible": data.get("is_visible", True),
            "is_cache": data.get("is_cache", False),
            "is_frame": data.get("is_frame", False),
            "frame_src": data.get("frame_src"),
            "is_active": data.get("is_active", True),
            "no_cache": data.get("no_cache", False),
            "breadcrumb": data.get("breadcrumb", True),
            "affix": data.get("affix", False),
            "no_tags_view": data.get("no_tags_view", False),
            "can_to": data.get("can_to", False),
            "always_show": data.get("always_show", True),
            "meta": meta,
        }
        menu = await self.create(menu_data)
        await bump_menu_structure_cache_version()
        return menu

    async def update_menu(self, menu_id: int, data: dict[str, Any], *, tenant_id: int) -> Menu:
        """Update menu within the given tenant."""
        menu = await self.get_by_id(menu_id, tenant_id=tenant_id)
        if not menu:
            raise NotFoundError(message="Menu not found")

        new_parent_id = data.get("parent_id")
        if new_parent_id is not None and new_parent_id != menu.parent_id:
            if new_parent_id:
                if new_parent_id == menu.id:
                    raise BusinessError(
                        message="Menu cannot be its own parent",
                        code="CIRCULAR_REFERENCE",
                    )
                parent = await self.get_by_id(new_parent_id)
                if not parent:
                    raise NotFoundError(message="Parent menu not found")
                data["level"] = parent.level + 1
            else:
                data["level"] = 1
            data["parent_id"] = new_parent_id

        # Handle meta update
        if "meta" in data:
            current_meta = menu.meta or {}
            current_meta.update(data["meta"] or {})
            data["meta"] = current_meta
        else:
            meta = menu.meta or {}
            if "title" in data:
                meta["title"] = data["title"]
            if "icon" in data:
                meta["icon"] = data["icon"]
            if "is_visible" in data:
                meta["showLink"] = data["is_visible"]
            if "is_cache" in data:
                meta["keepAlive"] = data["is_cache"]
            if "sort_order" in data:
                meta["rank"] = data["sort_order"]
            data["meta"] = meta

        updated_menu = await self.update(menu, data, exclude_unset=False)
        await bump_menu_structure_cache_version()
        return updated_menu

    async def delete_menu(self, menu_id: int, *, tenant_id: int) -> None:
        """Soft delete menu within the given tenant."""
        menu = await self.get_by_id(menu_id, tenant_id=tenant_id)
        if not menu:
            raise NotFoundError(message="Menu not found")

        if menu.children:
            active_children = [c for c in menu.children if c.deleted_at is None]
            if active_children:
                raise BusinessError(
                    message="Cannot delete menu with active children",
                    code="HAS_CHILDREN",
                )

        await self.delete(menu)
        await bump_menu_structure_cache_version()

    @staticmethod
    def to_response(menu: Menu) -> dict[str, Any]:
        """Convert menu to response dict
        
        Following itrainer design: no name field, only title for display
        """
        return {
            "id": menu.id,
            "title": menu.title,
            "path": menu.path,
            "component": menu.component,
            "redirect": menu.redirect,
            "parentId": menu.parent_id,
            "level": menu.level,
            "icon": menu.icon,
            "sortOrder": menu.sort_order,
            "menuType": menu.menu_type,
            "perms": menu.perms,
            "isVisible": menu.is_visible,
            "isCache": menu.is_cache,
            "isFrame": menu.is_frame,
            "frameSrc": menu.frame_src,
            "isActive": menu.is_active,
            "noCache": menu.no_cache,
            "breadcrumb": menu.breadcrumb,
            "affix": menu.affix,
            "noTagsView": menu.no_tags_view,
            "canTo": menu.can_to,
            "alwaysShow": menu.always_show,
            "meta": menu.meta,
            "createdAt": menu.created_at.isoformat() if menu.created_at else None,
            "updatedAt": menu.updated_at.isoformat() if menu.updated_at else None,
        }

    @staticmethod
    def to_list_item(menu: Menu) -> dict[str, Any]:
        """Convert menu to list item dict"""
        return MenuService.to_response(menu)
