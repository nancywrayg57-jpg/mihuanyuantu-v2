"""
AOJU Backend - Menu Models

Menu model for dynamic routing.
Compatible with vue-pure-admin frontend and itrainer design.
"""
from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, Text
from app.infrastructure.database.types import PortableJSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import TenantBaseModel

if TYPE_CHECKING:
    from app.domain.roles.models import Role


class Menu(TenantBaseModel):
    """
    Menu Model - 菜单

    Dynamic menu/routing system compatible with vue-pure-admin.
    Follows itrainer design: menu includes permission identifier.
    Tree structure using parent_id.
    
    Menu Types:
    - "0" (directory): Directory/folder, groups other menus
    - "1" (menu): Actual menu item with a page
    - "2" (button): Button/action permission within a page
    """

    __tablename__ = "menus"

    # Basic Info (itrainer design: only title, no name field)
    title: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Display title (菜单名称)",
    )

    # Routing
    path: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="Route path (e.g., '/system/user')",
    )
    component: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="Component path (e.g., 'views/system/user/index')",
    )
    redirect: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="Redirect path",
    )

    # Tree Structure
    parent_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("menus.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Parent menu ID",
    )
    level: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
        comment="Menu level (1 = top level)",
    )

    # Display
    icon: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Icon name",
    )
    sort_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Sort order (order/rank)",
    )

    # Menu Type (itrainer design)
    menu_type: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
        default="1",
        comment="Menu type: 0=directory, 1=menu, 2=button",
    )

    # Permission Identifier (itrainer design - core field)
    perms: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Permission identifier (e.g., 'user:create', 'auth.menu.list')",
    )

    # Visibility & Behavior
    is_visible: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Show in menu (showLink, opposite of hidden)",
    )
    is_cache: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Enable keep-alive (keepAlive, opposite of noCache)",
    )
    is_frame: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Is iframe/external link",
    )
    frame_src: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Iframe source URL",
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Is menu active (opposite of disabled)",
    )

    # Extended attributes (itrainer design)
    no_cache: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="If true, will not be cached by <keep-alive>",
    )
    breadcrumb: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="If false, will not show in breadcrumb",
    )
    affix: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="If true, will always be fixed in tag",
    )
    no_tags_view: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="If true, will not appear in tag",
    )
    can_to: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="If true, can navigate even if hidden",
    )
    always_show: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Always show root route regardless of children count",
    )

    # Meta (vue-pure-admin compatible)
    meta: Mapped[dict[str, Any]] = mapped_column(
        PortableJSON,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Route meta info (additional attributes)",
    )

    # Relationships
    parent: Mapped["Menu | None"] = relationship(
        "Menu",
        remote_side="Menu.id",
        back_populates="children",
        lazy="joined",
    )
    children: Mapped[list["Menu"]] = relationship(
        "Menu",
        back_populates="parent",
        lazy="selectin",
    )
    roles: Mapped[list["Role"]] = relationship(
        "Role",
        secondary="role_menus",
        back_populates="menus",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Menu(id={self.id}, title={self.title}, menu_type={self.menu_type})>"

    def to_route_dict(self, parent_name: str = "") -> dict[str, Any]:
        """
        Convert to vue-pure-admin route format.
        
        Following itrainer design:
        - name is generated from path segments (PascalCase)
        - meta.title is the display name (菜单名称)
        
        Args:
            parent_name: Reserved for compatibility (not used)
        """
        # path is required in itrainer design
        path = self.path or "/"

        # Generate route name from path (itrainer design)
        # e.g., "/system/user" -> "SystemUser"
        # e.g., "/speech/providers/:providerId" -> "SpeechProvidersProviderId"
        import re

        def normalize_part(part: str) -> str:
            p = part.lstrip(":")
            p = re.sub(r"[^A-Za-z0-9]", "", p)
            if not p:
                return ""
            return p[:1].upper() + p[1:]

        path_parts = [p for p in path.split("/") if p]
        generated_name = "".join(normalize_part(part) for part in path_parts) or "Root"

        meta: dict[str, Any] = {
            **(self.meta or {}),
            # Persisted columns are authoritative over meta JSON overrides.
            "title": self.title,
            "icon": self.icon,
            "rank": self.sort_order,
            "showLink": self.is_visible,
            "hidden": not self.is_visible,
            "keepAlive": not self.no_cache,
            "noCache": self.no_cache,
            "breadcrumb": self.breadcrumb,
            "affix": self.affix,
            "noTagsView": self.no_tags_view,
            "canTo": self.can_to,
            "alwaysShow": self.always_show,
        }

        # Legacy route: speech demo has been merged into speech config.
        if path == "/system/speech/demo":
            meta["showLink"] = False
            meta["hidden"] = True
            meta["canTo"] = True
        
        result: dict[str, Any] = {
            "path": path,
            "name": generated_name,
            "meta": meta,
        }

        if self.component:
            result["component"] = self.component

        if self.redirect:
            result["redirect"] = self.redirect

        if self.is_frame and self.frame_src:
            result["meta"]["frameSrc"] = self.frame_src

        return result
