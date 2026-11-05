"""
AOJU Backend - CMS Schemas (Pydantic DTOs)

camelCase aliases keep the contract consistent with the vue-pure-admin / Next
frontend (populate_by_name=True so both snake_case and camelCase parse).
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

from app.domain.cms.models import (
    ContentStatus,
    SubmissionStatus,
)


class _Base(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


# --------------------------------------------------------------------------- #
# Pages
# --------------------------------------------------------------------------- #
class PageBase(_Base):
    slug: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=200)
    locale: str = Field(default="", max_length=12)
    status: ContentStatus = ContentStatus.DRAFT
    blocks: dict[str, Any] = Field(default_factory=dict)
    seo: dict[str, Any] = Field(default_factory=dict)
    sort_order: int = Field(default=0, alias="sortOrder")

    @field_validator("slug")
    @classmethod
    def _slug_ok(cls, v: str) -> str:
        v = (v or "").strip().lower()
        if not v:
            raise ValueError("slug is required")
        if not all(c.isalnum() or c in "-_/" for c in v):
            raise ValueError("slug may only contain letters, numbers, -, _ and /")
        return v


class PageCreate(PageBase):
    pass


class PageUpdate(_Base):
    title: str | None = Field(default=None, max_length=200)
    status: ContentStatus | None = None
    blocks: dict[str, Any] | None = None
    seo: dict[str, Any] | None = None
    sort_order: int | None = Field(default=None, alias="sortOrder")


class PageListItem(_Base):
    id: int
    slug: str
    title: str
    locale: str = "default"
    status: str
    sort_order: int = Field(alias="sortOrder")
    is_system: bool = Field(alias="isSystem")
    published_at: datetime | None = Field(default=None, alias="publishedAt")
    updated_at: datetime | None = Field(default=None, alias="updatedAt")


class PageDetail(PageListItem):
    blocks: dict[str, Any] = Field(default_factory=dict)
    seo: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = Field(default=None, alias="createdAt")


# --------------------------------------------------------------------------- #
# Posts
# --------------------------------------------------------------------------- #
class PostBase(_Base):
    slug: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=200)
    locale: str = Field(default="", max_length=12)
    excerpt: str | None = Field(default=None, max_length=500)
    cover_image: str | None = Field(default=None, max_length=500, alias="coverImage")
    body: str = ""
    status: ContentStatus = ContentStatus.DRAFT
    tags: list[str] = Field(default_factory=list)
    seo: dict[str, Any] = Field(default_factory=dict)

    @field_validator("slug")
    @classmethod
    def _slug_ok(cls, v: str) -> str:
        v = (v or "").strip().lower()
        if not v:
            raise ValueError("slug is required")
        if not all(c.isalnum() or c in "-_" for c in v):
            raise ValueError("slug may only contain letters, numbers, - and _")
        return v


class PostCreate(PostBase):
    pass


class PostUpdate(_Base):
    title: str | None = Field(default=None, max_length=200)
    excerpt: str | None = Field(default=None, max_length=500)
    cover_image: str | None = Field(default=None, max_length=500, alias="coverImage")
    body: str | None = None
    status: ContentStatus | None = None
    tags: list[str] | None = None
    seo: dict[str, Any] | None = None


class PostListItem(_Base):
    id: int
    slug: str
    title: str
    locale: str = "default"
    excerpt: str | None = None
    cover_image: str | None = Field(default=None, alias="coverImage")
    status: str
    tags: list[str] = Field(default_factory=list)
    published_at: datetime | None = Field(default=None, alias="publishedAt")
    updated_at: datetime | None = Field(default=None, alias="updatedAt")


class PostDetail(PostListItem):
    body: str = ""
    seo: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = Field(default=None, alias="createdAt")


# --------------------------------------------------------------------------- #
# Navigation
# --------------------------------------------------------------------------- #
class NavigationUpdate(_Base):
    items: list[dict[str, Any]] = Field(default_factory=list)


class NavigationDetail(_Base):
    location: str
    items: list[dict[str, Any]] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Site settings
# --------------------------------------------------------------------------- #
class SiteSettingsUpdate(_Base):
    settings: dict[str, Any] = Field(default_factory=dict)


class SiteSettingsDetail(_Base):
    settings: dict[str, Any] = Field(default_factory=dict)


class LanguageItem(_Base):
    id: int
    code: str
    name: str
    is_default: bool = Field(alias="isDefault")
    is_active: bool = Field(alias="isActive")
    sort_order: int = Field(alias="sortOrder")


class LanguageCreate(_Base):
    code: str = Field(min_length=2, max_length=12)
    name: str = Field(min_length=1, max_length=60)
    is_default: bool = Field(default=False, alias="isDefault")
    is_active: bool = Field(default=True, alias="isActive")
    sort_order: int = Field(default=0, alias="sortOrder")


class LanguageUpdate(_Base):
    name: str | None = Field(default=None, max_length=60)
    is_default: bool | None = Field(default=None, alias="isDefault")
    is_active: bool | None = Field(default=None, alias="isActive")
    sort_order: int | None = Field(default=None, alias="sortOrder")


class CmsAiConfigUpdate(_Base):
    mode: str = Field(default="inherit")  # "inherit" | "custom"
    base_url: str | None = Field(default=None, alias="baseUrl", max_length=300)
    model: str | None = Field(default=None, max_length=120)
    temperature: float | None = None
    max_tokens: int | None = Field(default=None, alias="maxTokens")
    api_key: str | None = Field(default=None, alias="apiKey")
    clear_api_key: bool = Field(default=False, alias="clearApiKey")


class CmsAiConfigDetail(_Base):
    mode: str = "inherit"
    base_url: str | None = Field(default=None, alias="baseUrl")
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = Field(default=None, alias="maxTokens")
    has_api_key: bool = Field(default=False, alias="hasApiKey")
    system_configured: bool = Field(default=False, alias="systemConfigured")


# --------------------------------------------------------------------------- #
# Contact submissions
# --------------------------------------------------------------------------- #
class ContactCreate(_Base):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=160)
    company: str | None = Field(default=None, max_length=160)

    @field_validator("email")
    @classmethod
    def _email_ok(cls, v: str) -> str:
        v = (v or "").strip()
        if not _EMAIL_RE.match(v):
            raise ValueError("invalid email")
        return v
    message: str = Field(min_length=1, max_length=5000)
    source_page: str | None = Field(default=None, max_length=200, alias="sourcePage")
    # Honeypot: must stay empty; bots tend to fill every field.
    website: str | None = Field(default=None, max_length=200)


class SubmissionUpdate(_Base):
    status: SubmissionStatus


class SubmissionItem(_Base):
    id: int
    name: str
    email: str
    company: str | None = None
    message: str
    source_page: str | None = Field(default=None, alias="sourcePage")
    status: str
    created_at: datetime | None = Field(default=None, alias="createdAt")


# --------------------------------------------------------------------------- #
# Public (no-auth) read shapes
# --------------------------------------------------------------------------- #
class PublicPage(_Base):
    slug: str
    title: str
    blocks: dict[str, Any] = Field(default_factory=dict)
    seo: dict[str, Any] = Field(default_factory=dict)


class PublicPost(_Base):
    slug: str
    title: str
    excerpt: str | None = None
    cover_image: str | None = Field(default=None, alias="coverImage")
    body: str = ""
    tags: list[str] = Field(default_factory=list)
    seo: dict[str, Any] = Field(default_factory=dict)
    published_at: datetime | None = Field(default=None, alias="publishedAt")
