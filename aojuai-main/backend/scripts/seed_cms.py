"""
AOJU Backend - CMS seeding (idempotent, tenant-scoped)

Shared by scripts/seed_data.py (fresh installs) and the companion Alembic data
migration (existing tenants). Seeds:
  - the /cms admin menu tree + cms:* button permissions
  - grants for admin / tenant_admin, plus a `content_editor` role (no publish/settings)
  - design-rich default published content so a fresh site renders immediately

All inserts guard on existence so re-running is safe.
"""

from __future__ import annotations

import json
from typing import Any

from app.infrastructure.database.portable_sql import ptext
from app.domain.cms.access import CMS_MENU_DECLARATION
from app.domain.menus.reconciler import reconcile_menu_declaration

# --------------------------------------------------------------------------- #
# Default public content (Puck document shape: {root, content, zones})
# Component names here MUST match the frontend Puck config in
# frontend/src/components/cms/puck-config.tsx
# --------------------------------------------------------------------------- #

def _page(content: list[dict[str, Any]]) -> dict[str, Any]:
    return {"root": {"props": {}}, "content": content, "zones": {}}


HOME_BLOCKS = _page([
    {"type": "Hero", "props": {
        "id": "hero-1",
        "eyebrow": "AOJUAI · SaaS 平台底座",
        "title": "更快地把你的 SaaS 产品推向市场",
        "subtitle": "多租户、权限、计费与 AI 能力开箱即用。你只需要专注业务，剩下的交给底座。",
        "primaryText": "免费开始",
        "primaryHref": "/register",
        "secondaryText": "查看定价",
        "secondaryHref": "/pricing",
        "image": "",
    }},
    {"type": "Stats", "props": {
        "id": "stats-1",
        "items": [
            {"value": "99.9%", "label": "服务可用性"},
            {"value": "5 分钟", "label": "完成接入"},
            {"value": "30+", "label": "内置能力模块"},
            {"value": "24/7", "label": "技术支持"},
        ],
    }},
    {"type": "Features", "props": {
        "id": "features-1",
        "title": "为增长而生的能力",
        "subtitle": "从认证到 AI，一站式具备一个现代 SaaS 所需的全部基础设施。",
        "columns": "3",
        "items": [
            {"icon": "shield", "title": "多租户与权限", "description": "租户隔离、RBAC 角色菜单、数据权限，企业级安全开箱即用。"},
            {"icon": "zap", "title": "AI 助手", "description": "内置助手框架、工具治理与对话入口，快速嵌入智能能力。"},
            {"icon": "layout", "title": "可视化 CMS", "description": "拖拽搭建营销站点，无需开发即可发布落地页与博客。"},
            {"icon": "credit-card", "title": "计费与积分", "description": "积分账户、充值与流水，灵活支撑各种商业化模式。"},
            {"icon": "bell", "title": "通知与消息", "description": "站内信、邮件、微信、飞书与 Webhook 统一网关。"},
            {"icon": "mic", "title": "语音能力", "description": "TTS / STT provider catalog、试听与音色管理。"},
        ],
    }},
    {"type": "Pricing", "props": {
        "id": "pricing-1",
        "title": "简单透明的定价",
        "subtitle": "从个人到企业，按需选择。随时升级。",
        "plans": [
            {"name": "入门版", "price": "¥0", "period": "/月", "description": "适合个人和早期验证",
             "features": ["1 个租户", "最多 5 名成员", "社区支持", "核心模块"], "ctaText": "免费开始", "ctaHref": "/register", "highlighted": False},
            {"name": "团队版", "price": "¥299", "period": "/月", "description": "适合成长中的团队",
             "features": ["无限租户", "最多 50 名成员", "优先支持", "AI 助手", "CMS 营销站"], "ctaText": "选择团队版", "ctaHref": "/contact", "highlighted": True},
            {"name": "企业版", "price": "定制", "period": "", "description": "适合大规模与合规需求",
             "features": ["私有化部署", "SSO / 审计", "SLA 保障", "专属客户成功"], "ctaText": "联系我们", "ctaHref": "/contact", "highlighted": False},
        ],
    }},
    {"type": "FAQ", "props": {
        "id": "faq-1",
        "title": "常见问题",
        "items": [
            {"question": "可以私有化部署吗？", "answer": "可以。企业版支持私有化部署与定制集成。"},
            {"question": "支持哪些登录方式？", "answer": "支持账号密码、邀请注册，企业版支持 SSO。"},
            {"question": "是否需要信用卡？", "answer": "入门版完全免费，无需信用卡即可开始。"},
        ],
    }},
    {"type": "CTA", "props": {
        "id": "cta-1",
        "title": "准备好开始了吗？",
        "subtitle": "几分钟即可拥有属于你的 SaaS 平台。",
        "buttonText": "免费创建账户",
        "buttonHref": "/register",
    }},
])

FEATURES_BLOCKS = _page([
    {"type": "Hero", "props": {"id": "f-hero", "eyebrow": "产品能力", "title": "一个底座，满足所有",
        "subtitle": "深入了解 AOJUAI 提供的核心能力模块。", "primaryText": "免费开始", "primaryHref": "/register",
        "secondaryText": "", "secondaryHref": "", "image": ""}},
    {"type": "Features", "props": {"id": "f-grid", "title": "核心模块", "subtitle": "", "columns": "3", "items": HOME_BLOCKS["content"][2]["props"]["items"]}},
    {"type": "CTA", "props": {"id": "f-cta", "title": "想看实际效果？", "subtitle": "立即注册体验完整能力。", "buttonText": "免费开始", "buttonHref": "/register"}},
])

PRICING_BLOCKS = _page([
    {"type": "Hero", "props": {"id": "p-hero", "eyebrow": "定价", "title": "选择适合你的方案",
        "subtitle": "透明定价，随时升级或取消。", "primaryText": "", "primaryHref": "", "secondaryText": "", "secondaryHref": "", "image": ""}},
    HOME_BLOCKS["content"][3],
    HOME_BLOCKS["content"][4],
])

ABOUT_BLOCKS = _page([
    {"type": "Hero", "props": {"id": "a-hero", "eyebrow": "关于我们", "title": "让每个团队都能快速构建 SaaS",
        "subtitle": "我们相信优秀的基础设施应该是开箱即用的。", "primaryText": "", "primaryHref": "", "secondaryText": "", "secondaryHref": "", "image": ""}},
    {"type": "RichText", "props": {"id": "a-rt", "content": "## 我们的使命\n\nAOJUAI 致力于为开发者和企业提供可复用、可扩展的 SaaS 底座，让团队把精力放在真正创造价值的业务上。\n\n## 我们的方法\n\n- 多租户与权限是第一公民\n- AI 能力原生内置\n- 开放、可插拔的模块化架构\n"}},
    {"type": "CTA", "props": {"id": "a-cta", "title": "加入我们的旅程", "subtitle": "一起构建下一代 SaaS。", "buttonText": "联系我们", "buttonHref": "/contact"}},
])

DEFAULT_PAGES = [
    {"slug": "home", "title": "首页", "blocks": HOME_BLOCKS, "is_system": True, "sort_order": 0,
     "seo": {"title": "AOJUAI — 更快地把 SaaS 推向市场", "description": "多租户、权限、计费与 AI 能力开箱即用的 SaaS 平台底座。"}},
    {"slug": "features", "title": "产品能力", "blocks": FEATURES_BLOCKS, "is_system": True, "sort_order": 1,
     "seo": {"title": "产品能力 — AOJUAI", "description": "了解 AOJUAI 的核心能力模块。"}},
    {"slug": "pricing", "title": "定价", "blocks": PRICING_BLOCKS, "is_system": True, "sort_order": 2,
     "seo": {"title": "定价 — AOJUAI", "description": "简单透明的 SaaS 定价。"}},
    {"slug": "about", "title": "关于我们", "blocks": ABOUT_BLOCKS, "is_system": True, "sort_order": 3,
     "seo": {"title": "关于我们 — AOJUAI", "description": "AOJUAI 的使命与方法。"}},
]

DEFAULT_POST = {
    "slug": "welcome-to-aojuai",
    "title": "欢迎使用 AOJUAI 平台底座",
    "excerpt": "从今天起，用更少的时间构建你的 SaaS 产品。",
    "cover_image": "",
    "tags": ["公告", "产品"],
    "body": "## 欢迎\n\n这是一篇示例博客文章，展示 CMS 的文章能力。你可以在后台 `/cms/posts` 中编辑或新建文章，使用 Markdown 书写正文。\n\n### 你可以做什么\n\n- 用拖拽编辑器搭建营销页面\n- 用 Markdown 发布博客\n- 管理导航、站点设置与客户留言\n",
}

DEFAULT_HEADER_NAV = [
    {"label": "首页", "href": "/", "external": False},
    {"label": "产品能力", "href": "/features", "external": False},
    {"label": "定价", "href": "/pricing", "external": False},
    {"label": "博客", "href": "/blog", "external": False},
    {"label": "关于我们", "href": "/about", "external": False},
]

DEFAULT_FOOTER_NAV = [
    {"label": "产品能力", "href": "/features", "external": False},
    {"label": "定价", "href": "/pricing", "external": False},
    {"label": "博客", "href": "/blog", "external": False},
    {"label": "联系我们", "href": "/contact", "external": False},
    {"label": "登录", "href": "/login", "external": False},
]

DEFAULT_SETTINGS = {
    "brandName": "AOJUAI",
    "logo": "",
    "tagline": "SaaS 平台底座",
    "footerText": "© 2026 AOJUAI. 保留所有权利。",
    "contactEmail": "hello@aoju.ai",
    "social": {"github": "", "x": "", "linkedin": ""},
}


async def seed_cms_for_tenant(db, *, tenant_id: int, role_ids: dict[str, int | None]) -> bool:
    """Idempotently seed CMS menus, permissions, roles and default content.

    Returns whether menu, role, or grant reconciliation changed database state.
    Default CMS content remains additive and is intentionally handled below.
    """
    reconcile_result = await reconcile_menu_declaration(
        db,
        tenant_id=tenant_id,
        declaration=CMS_MENU_DECLARATION,
        role_id_overrides=role_ids,
    )

    # ---- language taxonomy (idempotent) ----
    for code, name, is_default, sort_order in (("zh-CN", "简体中文", True, 0), ("en-US", "English", False, 1)):
        lang_exists = await db.execute(
            ptext("SELECT 1 FROM cms_languages WHERE tenant_id=:t AND code=:c"),
            {"t": tenant_id, "c": code},
        )
        if not lang_exists.scalar():
            await db.execute(
                ptext(
                    "INSERT INTO cms_languages (tenant_id, code, name, is_default, is_active, sort_order) "
                    "VALUES (:t, :c, :n, :d, true, :s)"
                ),
                {"t": tenant_id, "c": code, "n": name, "d": is_default, "s": sort_order},
            )

    # ---- default content under the real default language (zh-CN) ----
    for page in DEFAULT_PAGES:
        exists = await db.execute(
            ptext("SELECT 1 FROM cms_pages WHERE tenant_id=:t AND slug=:s"),
            {"t": tenant_id, "s": page["slug"]},
        )
        if exists.scalar():
            continue
        await db.execute(
            ptext(
                "INSERT INTO cms_pages (tenant_id, slug, locale, title, status, blocks, seo, sort_order, "
                "is_system, published_at) VALUES (:t, :slug, 'zh-CN', :title, 'published', cast(:blocks as jsonb), "
                "cast(:seo as jsonb), :sort, :is_system, now())"
            ),
            {"t": tenant_id, "slug": page["slug"], "title": page["title"],
             "blocks": json.dumps(page["blocks"]), "seo": json.dumps(page["seo"]),
             "sort": page["sort_order"], "is_system": page["is_system"]},
        )

    post_exists = await db.execute(
        ptext("SELECT 1 FROM cms_posts WHERE tenant_id=:t AND slug=:s"),
        {"t": tenant_id, "s": DEFAULT_POST["slug"]},
    )
    if not post_exists.scalar():
        await db.execute(
            ptext(
                "INSERT INTO cms_posts (tenant_id, slug, locale, title, excerpt, cover_image, body, status, "
                "tags, seo, published_at) VALUES (:t, :slug, 'zh-CN', :title, :excerpt, :cover, :body, 'published', "
                "cast(:tags as jsonb), cast('{}' as jsonb), now())"
            ),
            {"t": tenant_id, "slug": DEFAULT_POST["slug"], "title": DEFAULT_POST["title"],
             "excerpt": DEFAULT_POST["excerpt"], "cover": DEFAULT_POST["cover_image"],
             "body": DEFAULT_POST["body"], "tags": json.dumps(DEFAULT_POST["tags"])},
        )

    for location, items in (("header", DEFAULT_HEADER_NAV), ("footer", DEFAULT_FOOTER_NAV)):
        nav_exists = await db.execute(
            ptext("SELECT 1 FROM cms_navigations WHERE tenant_id=:t AND location=:l"),
            {"t": tenant_id, "l": location},
        )
        if not nav_exists.scalar():
            await db.execute(
                ptext(
                    "INSERT INTO cms_navigations (tenant_id, location, items) "
                    "VALUES (:t, :l, cast(:items as jsonb))"
                ),
                {"t": tenant_id, "l": location, "items": json.dumps(items)},
            )

    settings_exists = await db.execute(
        ptext("SELECT 1 FROM cms_site_settings WHERE tenant_id=:t"), {"t": tenant_id}
    )
    if not settings_exists.scalar():
        await db.execute(
            ptext(
                "INSERT INTO cms_site_settings (tenant_id, settings) VALUES (:t, cast(:s as jsonb))"
            ),
            {"t": tenant_id, "s": json.dumps(DEFAULT_SETTINGS)},
        )

    return reconcile_result.changed
