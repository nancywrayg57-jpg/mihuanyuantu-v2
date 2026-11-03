"""
AOJU Backend - CMS Models

All CMS tables are tenant-scoped (TenantBaseModel) and keep structured/flexible
content in PortableJSON to avoid over-normalizing the block model.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import BigInteger, Index, String, Text, text
from app.infrastructure.database.types import PortableJSON, PortableDateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import TenantBaseModel


class ContentStatus(str, Enum):
    """Draft / published lifecycle for pages and posts."""

    DRAFT = "draft"
    PUBLISHED = "published"


class NavLocation(str, Enum):
    """Where a navigation menu is rendered on the public site."""

    HEADER = "header"
    FOOTER = "footer"


class SubmissionStatus(str, Enum):
    """Contact / lead submission triage status."""

    NEW = "new"
    REVIEWED = "reviewed"
    SPAM = "spam"
    ARCHIVED = "archived"


class CmsPage(TenantBaseModel):
    """A public marketing page composed of an ordered list of blocks."""

    __tablename__ = "cms_pages"
    __table_args__ = (
        Index(
            "uq_cms_pages_tenant_slug_locale",
            "tenant_id",
            "slug",
            "locale",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
    )

    slug: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    locale: Mapped[str] = mapped_column(String(12), nullable=False, default="default", server_default="default", index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ContentStatus.DRAFT.value, server_default="draft"
    )
    # Puck document: {"content": [ {type, props}... ], "root": {props}, "zones": {}}.
    # Stored verbatim so the public site can render with Puck's <Render>.
    blocks: Mapped[dict[str, Any]] = mapped_column(
        PortableJSON, nullable=False, default=dict, server_default="{}"
    )
    # {"title": str, "description": str, "keywords": str}
    seo: Mapped[dict[str, Any]] = mapped_column(
        PortableJSON, nullable=False, default=dict, server_default="{}"
    )
    sort_order: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    # System pages (home, etc.) cannot be deleted from the admin UI.
    is_system: Mapped[bool] = mapped_column(nullable=False, default=False, server_default=text("false"))
    published_at: Mapped[datetime | None] = mapped_column(PortableDateTime(), nullable=True)
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    updated_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class CmsPost(TenantBaseModel):
    """A blog / news post rendered as markdown."""

    __tablename__ = "cms_posts"
    __table_args__ = (
        Index(
            "uq_cms_posts_tenant_slug_locale",
            "tenant_id",
            "slug",
            "locale",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
    )

    slug: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    locale: Mapped[str] = mapped_column(String(12), nullable=False, default="default", server_default="default", index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    excerpt: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cover_image: Mapped[str | None] = mapped_column(String(500), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ContentStatus.DRAFT.value, server_default="draft"
    )
    tags: Mapped[list[str]] = mapped_column(
        PortableJSON, nullable=False, default=list, server_default="[]"
    )
    seo: Mapped[dict[str, Any]] = mapped_column(
        PortableJSON, nullable=False, default=dict, server_default="{}"
    )
    published_at: Mapped[datetime | None] = mapped_column(PortableDateTime(), nullable=True)
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    updated_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class CmsNavigation(TenantBaseModel):
    """A navigation menu (header / footer) as a flat/nested list of items."""

    __tablename__ = "cms_navigations"
    __table_args__ = (
        Index(
            "uq_cms_nav_tenant_location",
            "tenant_id",
            "location",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
    )

    location: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    # [{"label": str, "href": str, "external": bool, "children": [...]}]
    items: Mapped[list[dict[str, Any]]] = mapped_column(
        PortableJSON, nullable=False, default=list, server_default="[]"
    )


class CmsSiteSettings(TenantBaseModel):
    """One row per tenant holding global public-site settings."""

    __tablename__ = "cms_site_settings"
    __table_args__ = (
        Index(
            "uq_cms_site_settings_tenant",
            "tenant_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
    )

    # {"brandName", "logo", "footerText", "contactEmail", "social": {...}, "hero": {...}}
    # NOTE: this blob is served publicly — never put secrets here.
    settings: Mapped[dict[str, Any]] = mapped_column(
        PortableJSON, nullable=False, default=dict, server_default="{}"
    )
    # CMS-scoped AI provider override (admin-only, never served publicly).
    # {"mode": "inherit"|"custom", "baseUrl", "model", "temperature", "maxTokens", "apiKey": <encrypted>}
    ai_config: Mapped[dict[str, Any]] = mapped_column(
        PortableJSON, nullable=False, default=dict, server_default="{}"
    )


class CmsLanguage(TenantBaseModel):
    """Per-tenant language registry (the language taxonomy). Exactly one default."""

    __tablename__ = "cms_languages"
    __table_args__ = (
        Index(
            "uq_cms_languages_tenant_code",
            "tenant_id",
            "code",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
    )

    code: Mapped[str] = mapped_column(String(12), nullable=False)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    is_default: Mapped[bool] = mapped_column(nullable=False, default=False, server_default=text("false"))
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True, server_default=text("true"))
    sort_order: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)


class CmsContactSubmission(TenantBaseModel):
    """A lead / contact-form submission captured from the public site."""

    __tablename__ = "cms_contact_submissions"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    company: Mapped[str | None] = mapped_column(String(160), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    source_page: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=SubmissionStatus.NEW.value, server_default="new"
    )
    meta: Mapped[dict[str, Any]] = mapped_column(
        PortableJSON, nullable=False, default=dict, server_default="{}"
    )
    handled_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
