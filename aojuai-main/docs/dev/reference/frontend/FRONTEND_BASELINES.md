# Frontend 基线与治理（Next.js + shadcn/ui）

> 目的：避免前端开发“随手写一套”，导致风格不一致、重复造轮子，以及后续难以维护/演进。

## 1) 单一事实源（Single Source of Truth）

在 `nextjs-base` 中：

- **运行时事实源**：`frontend/`（最终交付、最终行为以此为准）
- **UI 组件基线**：shadcn/ui（Radix + Tailwind；代码位于 `frontend/src/components/ui/**`）
- **路由基线**：Next.js App Router（代码位于 `frontend/src/app/**`）

> 说明：公开版以 Next.js App Router 为前端事实源，不携带历史前端栈对照资料。

## 2) 路由与布局约定（必须一致）

- 登录：`frontend/src/app/(auth)/login/*` → `/login`
- 受保护页面：`frontend/src/app/(app)/*`
  - `frontend/src/app/(app)/layout.tsx` 已统一包裹：
    - `RequireAuth`（未登录跳转）
    - `AppLayout`（侧边栏 + 顶栏）

新增页面时：

1. 创建 `frontend/src/app/(app)/<path>/page.tsx`
2. 菜单入口由后端输出（权限过滤），需同步新增菜单（seed + Alembic + 建租户 reconciler 三写）：
   - 后端菜单路由：`GET /api/v1/menus/routes`
   - 要求：`menus.path` 与 Next.js 路由路径一致（否则点击菜单会 404）

## 3) 复用优先策略（最重要）

当你要新增 UI（页面/组件）时，先按顺序查找：

1. 本仓库现有实现（优先）
   - `frontend/src/components/ui/**`
   - `frontend/src/components/**`
   - `frontend/src/app/**`（先复制同类型页面再改）
2. 仍然不存在才自研（保持 shadcn/ui 的交互与样式一致）

默认原则：

- **优先不加依赖**：能组合现有 shadcn/ui/Radix 组件完成就不要引入新库
- 如果必须新增依赖：先写清楚原因、替代方案、影响面（体积/维护/安全）

## 4) API / Auth / Tenant 约定（对接必看）

- API client：`frontend/src/lib/api.ts`（`apiFetch()`）
- session：`frontend/src/lib/auth.ts`（localStorage `aojuai.session`）
- superuser 目标租户：`frontend/src/hooks/useTenant.tsx`
  - 需要传 `tenantId` → `apiFetch(..., { tenantId: targetTenantId })`
  - 请求头：`X-Tenant-Id`

环境变量：

- `NEXT_PUBLIC_API_BASE_URL`（为空则同源）

## 5) 菜单（必须后端输出）

硬性要求：

- 菜单树/可见性必须由后端输出并按权限过滤：`GET /api/v1/menus/routes`
- 前端不允许硬编码“可见菜单树”（否则权限边界会漂移）

实现位置（本分支）：

- 拉取与缓存：`frontend/src/hooks/useMenuRoutes.ts`
- 渲染侧边栏：`frontend/src/components/layout/app-layout.tsx`

## 6) 推荐 Skill

- `docs/dev/skills/aojuai-nextjs-shadcn-frontend/SKILL.md`
