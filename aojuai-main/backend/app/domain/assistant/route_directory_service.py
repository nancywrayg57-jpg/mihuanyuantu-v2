"""AOJU Backend - Assistant Route Directory Service"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.core.feature_switches import is_module_enabled, label_for_module, resolve_module_from_route_path
from app.domain.auth.models import Tenant
from app.domain.menus.models import Menu
from app.domain.roles.models import Role, RoleMenu
from app.domain.users.models import User, UserRole
from app.infrastructure.cache.base_runtime_keys import (
    MENU_ROUTES_TTL_SECONDS,
    build_assistant_scope_directory_cache_key,
)
from app.infrastructure.cache.runtime_cache import remember_json


class AssistantScopeDirectoryService:
    """Build a lightweight navigation directory from the current user's menus."""

    def __init__(self, db) -> None:
        self.db = db

    @staticmethod
    def _normalize_route_path(value: Any) -> str:
        path = str(value or "").strip()
        if not path:
            return "/"
        if not path.startswith("/"):
            path = f"/{path.lstrip('/')}"
        return path.rstrip("/") or "/"

    @staticmethod
    def _trim_hint_values(values: list[Any], *, limit: int = 5) -> list[str]:
        seen: set[str] = set()
        items: list[str] = []
        for raw in values:
            value = str(raw or "").strip()
            if not value or value in seen:
                continue
            seen.add(value)
            items.append(value)
            if len(items) >= limit:
                break
        return items

    @staticmethod
    def _module_enabled(tenant_config: dict[str, Any] | None, route_path: str) -> bool:
        module_code = resolve_module_from_route_path(route_path)
        if not module_code:
            return True
        return is_module_enabled(tenant_config, module_code)

    async def _load_user(self, *, tenant_id: int, user_id: int) -> User | None:
        result = await self.db.execute(
            select(User).where(
                User.id == user_id,
                User.tenant_id == tenant_id,
                User.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def _load_tenant_config(self, *, tenant_id: int) -> dict[str, Any]:
        result = await self.db.execute(select(Tenant.config).where(Tenant.id == tenant_id, Tenant.deleted_at.is_(None)))
        config = result.scalar_one_or_none()
        return dict(config) if isinstance(config, dict) else {}

    async def _load_user_menu_ids(self, *, tenant_id: int, user_id: int) -> set[int]:
        result = await self.db.execute(
            select(RoleMenu.menu_id)
            .join(Role, Role.id == RoleMenu.role_id)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(
                UserRole.tenant_id == tenant_id,
                UserRole.user_id == user_id,
                Role.tenant_id == tenant_id,
                Role.is_active.is_(True),
                Role.deleted_at.is_(None),
            )
        )
        return {int(menu_id) for menu_id in result.scalars().all() if menu_id is not None}

    async def _load_navigation_snapshot(self, *, tenant_id: int, user_id: int) -> dict[str, Any]:
        user = await self._load_user(tenant_id=tenant_id, user_id=user_id)
        tenant_config = await self._load_tenant_config(tenant_id=tenant_id)
        user_menu_ids = None if bool(getattr(user, "is_superuser", False)) else await self._load_user_menu_ids(
            tenant_id=tenant_id,
            user_id=user_id,
        )

        result = await self.db.execute(
            select(Menu).where(
                Menu.tenant_id == tenant_id,
                Menu.is_active.is_(True),
                Menu.deleted_at.is_(None),
                Menu.menu_type != "2",
            )
        )
        menus = list(result.scalars().all())
        accessible_routes: list[dict[str, Any]] = []
        for menu in sorted(menus, key=lambda item: (int(item.sort_order or 0), int(item.id or 0))):
            route_path = self._normalize_route_path(menu.path)
            if route_path == "/":
                continue
            if not bool(getattr(user, "is_superuser", False)):
                if user_menu_ids is not None and int(menu.id) not in user_menu_ids:
                    continue
                if isinstance(menu.meta, dict) and menu.meta.get("requireSuperuser") is True:
                    continue
            if not self._module_enabled(tenant_config, route_path):
                continue
            accessible_routes.append(
                {
                    "routePath": route_path,
                    "path": route_path,
                    "title": str(menu.title or route_path).strip() or route_path,
                    "isVisible": bool(menu.is_visible),
                    "canNavigate": bool(menu.is_visible or menu.can_to),
                    "sortOrder": int(menu.sort_order or 0),
                    "meta": dict(menu.meta or {}),
                }
            )
        return {
            "accessibleRoutes": accessible_routes,
            "visibleMenuCount": sum(1 for item in accessible_routes if item.get("isVisible") is True),
        }

    async def _load_cached_navigation_snapshot(self, *, tenant_id: int, user_id: int) -> dict[str, Any]:
        cache_key = build_assistant_scope_directory_cache_key(tenant_id=tenant_id, user_id=user_id)
        return await remember_json(
            cache_key,
            ttl_seconds=MENU_ROUTES_TTL_SECONDS,
            loader=lambda: self._load_navigation_snapshot(tenant_id=tenant_id, user_id=user_id),
        )

    def _build_route_entry(self, item: dict[str, Any], *, current_route_path: str, index: int) -> dict[str, Any] | None:
        route_path = self._normalize_route_path(item.get("routePath") or item.get("path"))
        if not route_path or route_path == "/":
            return None
        title = str(item.get("title") or item.get("label") or route_path).strip() or route_path
        module_code = resolve_module_from_route_path(route_path) or ""
        module_name = label_for_module(module_code) if module_code else ""
        query_hints = self._trim_hint_values(
            [
                title,
                module_name,
                module_code,
                route_path,
                str((item.get("meta") or {}).get("title") or "") if isinstance(item.get("meta"), dict) else "",
            ]
        )
        return {
            "routePath": route_path,
            "title": title,
            "moduleCode": module_code or None,
            "moduleName": module_name or None,
            "pageSummary": f"{title}，属于「{module_name}」模块。" if module_name else title,
            "queryHints": query_hints,
            "canNavigate": bool(item.get("canNavigate", True)),
            "isVisible": bool(item.get("isVisible")),
            "isCurrent": route_path == current_route_path,
            "sortOrderIndex": index,
        }

    def _build_scope_directory_from_snapshot(
        self,
        *,
        current_route_path: str,
        current_module_code: str | None,
        current_module_name: str | None,
        navigation_snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        route_entries = [
            entry
            for index, item in enumerate(navigation_snapshot.get("accessibleRoutes") or [])
            if isinstance(item, dict)
            for entry in [self._build_route_entry(item, current_route_path=current_route_path, index=index)]
            if isinstance(entry, dict)
        ]
        current_entry = next((item for item in route_entries if item.get("routePath") == current_route_path), None)
        adapter_module_code = str(current_module_code or "").strip()
        if adapter_module_code == "default":
            adapter_module_code = ""
        resolved_module_code = adapter_module_code or (
            str(current_entry.get("moduleCode") or "").strip() if isinstance(current_entry, dict) else ""
        ) or resolve_module_from_route_path(current_route_path) or ""
        resolved_module_name = (
            (str(current_module_name or "").strip() if adapter_module_code else "")
            or (str(current_entry.get("moduleName") or "").strip() if isinstance(current_entry, dict) else "")
            or (label_for_module(resolved_module_code) if resolved_module_code else "")
            or str(current_module_name or "").strip()
        )
        if current_entry is None:
            current_entry = {
                "routePath": current_route_path,
                "title": current_route_path,
                "moduleCode": resolved_module_code or None,
                "moduleName": resolved_module_name or None,
                "pageSummary": current_route_path,
                "queryHints": self._trim_hint_values([current_route_path, resolved_module_name, resolved_module_code]),
                "canNavigate": True,
                "isVisible": False,
                "isCurrent": True,
                "sortOrderIndex": -1,
            }

        module_scope_items = [
            item for item in route_entries if str(item.get("moduleCode") or "").strip() == str(resolved_module_code or "").strip()
        ]
        module_scope_items.sort(
            key=lambda item: (
                0 if item.get("isCurrent") is True else 1,
                0 if item.get("isVisible") is True else 1,
                int(item.get("sortOrderIndex") or 0),
                str(item.get("routePath") or ""),
            )
        )

        global_scope_items = list(route_entries)
        global_scope_items.sort(
            key=lambda item: (
                0 if item.get("isCurrent") is True else 1,
                0 if item.get("isVisible") is True else 1,
                str(item.get("moduleName") or ""),
                int(item.get("sortOrderIndex") or 0),
                str(item.get("title") or ""),
            )
        )

        return {
            "currentScope": {
                "moduleCode": resolved_module_code or None,
                "moduleName": resolved_module_name or None,
                "item": current_entry,
            },
            "moduleScope": {
                "moduleCode": resolved_module_code or None,
                "moduleName": resolved_module_name or None,
                "count": len(module_scope_items),
                "items": module_scope_items[:12],
            },
            "globalScope": {
                "count": len(global_scope_items),
                "items": global_scope_items[:32],
            },
        }

    async def build_scope_directory(
        self,
        *,
        tenant_id: int,
        user_id: int,
        current_route_path: str,
        current_module_code: str | None = None,
        current_module_name: str | None = None,
        navigation_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        current_route = self._normalize_route_path(current_route_path)
        snapshot = (
            dict(navigation_snapshot)
            if isinstance(navigation_snapshot, dict)
            else await self._load_cached_navigation_snapshot(tenant_id=tenant_id, user_id=user_id)
        )
        return self._build_scope_directory_from_snapshot(
            current_route_path=current_route,
            current_module_code=current_module_code,
            current_module_name=current_module_name,
            navigation_snapshot=snapshot,
        )
