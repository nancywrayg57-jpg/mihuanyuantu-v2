# nextjs-base CMS 模块设计（独立内置模块）

> 状态：MVP 设计与实施基线。结论经 3 路代码库调研 + codex 框架调研收敛。

## 1. 决策：自建内置模块，不嵌入第三方 CMS

调研对象：Strapi、Payload、Directus、KeystoneJS、Builder.io OSS、Plate/Editor.js、Wagtail。

结论（codex + 本仓库实情一致）：**在仓库内自建一个轻量 `cms` 模块**。

理由：
- Strapi / Payload / Directus / Keystone 均为独立 Node 服务，自带 **独立数据库 schema、独立鉴权、独立 RBAC、独立部署单元**。嵌入即引入“第二运行时 + 第二套权限”，与底座“复用 FastAPI RBAC / 多租户 / 单一部署”的目标冲突，也违背“不要过度复杂”。
- 底座已具备小型 CMS 所需的全部原语：`TenantBaseModel`（多租户、软删除、时间戳）、菜单/权限 RBAC、公开免鉴权端点范式（`backend/app/api/v1/endpoints/site.py` 的 `/site/public-config`）、shadcn/ui 后台 CRUD 模板（如 `system/role`）、`react-markdown`、i18n、租户主题。
- SaaS 营销站需求面很窄：Home / Features / Pricing / About / Blog / Contact。块化页面 + 文章 + 导航 + 站点设置 + 留言 ≈ 5 张表即可。
- Payload 作为唯一“备选外部方案”保留；仅当业务明确需要完整可视化 CMS 产品时才考虑。

## 2. 顶层架构

### 2.1 公开层（新增，免登录）
- 新增 Next.js 路由组 `frontend/src/app/(site)/`，**不包裹 `RequireAuth`**，拥有 `/`、`/pricing`、`/features`、`/about`、`/blog`、`/blog/[slug]`、`/contact`。
- 现有受登录保护的仪表盘从 `(app)/page.tsx` 迁移到 `(app)/dashboard/page.tsx`；登录成功后跳 `/dashboard`。`/` 改为 CMS 渲染的公开首页。
- 公开页通过免鉴权读端点取数（`apiFetch(..., { anonymous: true })`），仅返回 `published` 内容，`remember_json` 缓存。
- 公开站 layout（营销 header/footer）由 CMS 的 `navigation` + `site_settings` 驱动，复用租户主题与 i18n。

### 2.2 后端 `app/domain/cms/`
全部继承 `TenantBaseModel`（→ `tenant_id`、软删除、时间戳）。块/结构化数据用 **JSONB**，避免过度规范化。

| 表 | 关键列 |
|---|---|
| `cms_pages` | `slug`, `title`, `status(draft/published)`, `blocks(JSONB[])`, `seo(JSONB)`, `sort_order`, `is_system`, `published_at` |
| `cms_posts` | `slug`, `title`, `excerpt`, `cover_image`, `body(markdown)`, `status`, `published_at`, `tags(JSONB)` |
| `cms_navigations` | `location(header/footer)`, `items(JSONB tree: {label,href,external})` |
| `cms_site_settings` | 每租户一行：`settings(JSONB)`（brand、logo、footer、social、contact_email、hero 默认值） |
| `cms_contact_submissions` | `name`, `email`, `company`, `message`, `source_page`, `status(new/reviewed/spam/archived)`, `handled_by` |

延后（非 MVP）：`cms_media`（MVP 复用现有 `/upload` + URL 字符串）、`cms_*_revisions`（用 `updated_at` + draft/published 顶替）。

### 2.3 块模型（约束式，非自由可视化搭建）
页面 = 有序块数组，每块 `{ "type": string, "data": object, "enabled": bool }`。MVP 块类型：
- `hero`（heading, subheading, primaryCta, secondaryCta, image）
- `feature_grid`（heading, items[{icon,title,desc}]）
- `pricing`（plans[{name,price,period,features[],cta,highlighted}]）
- `rich_text`（markdown）
- `cta`（heading, text, button）
- `faq`（items[{q,a}]）
- `logos` / `stats`（可选）

渲染端按 `type` 映射 React 组件；编辑端用 **Puck** 拖拽搭建。

### 2.3.1 编辑器选型：内置第三方库 Puck（已定）
> 用户决策：CMS 页面编辑器采用第三方库 **`@measured/puck`**（MIT，支持 React 19，0.20.2，peer `react ^18||^19`），作为 `/cms` 模块内置的可视化拖拽编辑器——“内置模块可以是第三方模块”的轻量最小 MVP 路径。

- 我们只定义 **少量 Puck 组件**，每个映射到一个 shadcn 实现的块组件（Hero / FeatureGrid / Pricing / RichText / CTA / FAQ）。
- 这套 **Puck config（组件定义）在前端代码中，编辑器与公开渲染共用**。
- 编辑器 `<Puck config data onPublish>` 输出 JSON（`{content, root, zones}`），直接存入 `cms_pages.blocks`（JSONB 对象）。
- 公开站用 `<Render config data>` 渲染同一份 JSON；只渲染 `published`。
- 不引入独立运行时/独立 DB/独立鉴权——数据在我们 Postgres，权限走我们 RBAC。
- 博客文章正文用现有 `react-markdown` + 文本域，不再加富文本依赖。

### 2.4 API 面
公开读（免鉴权，挂在 `/site/cms/*`）：
- `GET /site/cms/settings`、`GET /site/cms/navigation`
- `GET /site/cms/pages/{slug}`、`GET /site/cms/posts`、`GET /site/cms/posts/{slug}`
- `POST /site/cms/contact`（留言提交，含频率限制/蜜罐）

后台（`CurrentUser` + `PermissionChecker`）：pages / posts / navigation / settings 的 CRUD + publish/unpublish；contact 列表与状态更新。响应统一 `SuccessResponse` / `PageResponse`。

## 3. 权限层级（不同管理员能力）
复用菜单/权限 RBAC，新增权限码：
- `cms:page:read|create|update|delete|publish`
- `cms:post:read|create|update|delete|publish`
- `cms:nav:read|update`、`cms:settings:read|update`
- `cms:contact:read|update`

管理员档位（codex 五档，落地按需精简）：
- **cms:admin**（= tenant_admin/超管）：全部 CMS + 设置/导航 + 发布。
- **cms:publisher（site_manager 角色）**：页面/文章 CRUD + 发布，可改导航/设置，不碰用户/角色后台。
- **cms:editor（content_editor 角色）**：建/改草稿、传图，**不能发布**、不能改设置/导航。
- **cms:leads（lead_viewer 角色）**：仅 `cms:contact:read|update`。

MVP 至少落地 **tenant_admin（全权）+ content_editor（无发布/设置）** 两档，发布权 `*:publish` 为关键分水岭。

## 4. 菜单与种子（三写：seed / 迁移 / 建租户）
按 `docs/dev/flows/MENUS_PERMS_DUALWRITE.md`：
- 新增 `/cms` 目录菜单（menu_type=0）+ 子菜单（type=1：内容页 `/cms/pages`、文章 `/cms/posts`、导航 `/cms/navigation`、站点设置 `/cms/settings`、留言箱 `/cms/messages`）+ 按钮权限（type=2，`cms:*`）。
- 新装：`backend/scripts/seed_data.py` 调 `seed_cms_for_tenant()`；存量：幂等 Alembic 数据迁移遍历现有租户回填。
- 默认内容种子：home/pricing/features/about 页 + 一篇示例文章 + header/footer 导航 + 站点设置，保证全新安装首页即是可用落地页。

## 5. MVP 验收
1. 免登录访问 `/` 渲染 CMS 首页；`/pricing /features /about /blog /blog/[slug] /contact` 可用；联系表单落库。
2. 后台 `/cms/*` 自有编辑页：页面（块编辑 + 发布）、文章、导航、站点设置、留言箱。
3. 权限：tenant_admin 全权；content_editor 无发布/设置。403 在 API 层强制（不止 UI）。
4. `/` 公开化、仪表盘迁 `/dashboard`、登录跳转更新。
5. 全新安装含默认内容；存量租户经迁移回填。
6. `pnpm typecheck && pnpm build`、`python -m compileall app` 通过。

## 6. 主要陷阱（codex）
通用可视化搭建器、放任任意 HTML、忘记 draft/published、只在 UI 做租户隔离、pricing/features 过度自由导致布局崩、无草稿预览、联系表单无限流/反垃圾、把每个块过度建表（应 JSONB）。
