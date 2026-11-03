---
name: aojuai-nextjs-shadcn-frontend
description: Build AOJUAI admin frontend pages in this branch using Next.js (App Router) + shadcn/ui, reusing existing UI/components and aligning auth/tenant/perms conventions.
---

# AOJUAI 前端（Next.js + shadcn/ui）开发剧本

适用范围：当前 `nextjs-base` 前端实现（`frontend/`），使用 **Next.js App Router + React + Tailwind + shadcn/ui**。

## 0) 先读“系统事实”

- 前端目录结构：`frontend/src/app/`
- 路由分组：
  - `frontend/src/app/(auth)/login/*`：登录
  - `frontend/src/app/(app)/*`：受保护页面（已统一包裹 `RequireAuth` + `AppLayout`）
- API 客户端：`frontend/src/lib/api.ts`（`apiFetch()`）
- Auth/session：`frontend/src/hooks/useAuth.tsx` + `frontend/src/lib/auth.ts`（localStorage）
- 租户上下文：`frontend/src/hooks/useTenant.tsx`（superuser 目标租户 + `X-Tenant-Id`）

## 1) 新增页面/模块（建议顺序）

1. **先确认后端 API 契约已稳定**（先 curl/pytest 再写前端）
2. **在 Next.js 中创建路由文件**
   - 业务/管理页面：`frontend/src/app/(app)/<path>/page.tsx`
   - 个人中心：`frontend/src/app/(app)/personal/<path>/page.tsx`
   - 系统管理（superuser）：`frontend/src/app/(app)/system/<path>/page.tsx`
3. **菜单入口由后端输出（框架要求）**
   - 菜单/路由树：`GET /api/v1/menus/routes`（后端按角色菜单授权过滤）
   - 新增页面要想“出现在侧边栏”：必须新增菜单并完成 `role_menus` 授权（seed + Alembic + 建租户 reconciler 三写闭环）
   - 前端侧边栏以该接口返回为准，不允许硬编码“可见菜单树”
4. **权限与按钮门禁**
   - 使用 `hasAnyPermission(session, [...])` 做 React 条件渲染
   - 不要“只做前端隐藏”而不做后端鉴权（后端仍需 `PermissionChecker`）
5. **API 调用规范**
   - 使用 `apiFetch<T>(path, { session, tenantId, ... })`
   - superuser 需要传 `tenantId = targetTenantId`（来自 `useTenant()`）
6. **收口验证**
   - `pnpm -C frontend typecheck`
   - `pnpm -C frontend build`

## 2) 复用优先（避免重复造轮子）

优先顺序：

1. `frontend/src/components/ui/**`（shadcn/ui 组件）
2. `frontend/src/components/**`（业务组件/布局）
3. 参考现有页面实现（复制结构再改）
   - `frontend/src/app/(app)/system/user/page.tsx`
   - `frontend/src/app/(app)/system/menu/page.tsx`

原则：

- **优先不加依赖**：能用现有 shadcn/ui/Radix 组件组合就不要引入新库
- 如果必须新增依赖：先在 MR/PR 里明确理由、替代方案与影响面（体积/维护/安全）

## 3) 环境变量

- `NEXT_PUBLIC_API_BASE_URL`
  - 为空：默认同源（适合前后端同域部署）
  - 非空：指向后端地址（适合前后端分离）

## 4) 常见坑（快速定位）

- “页面 404 / 路由找不到”：
  - 检查 `frontend/src/app/**/page.tsx` 是否存在，目录名是否与 URL 对应
- “菜单里有入口，但点进去 404”：
  - 检查 `menus.path` 是否与 Next.js 路由一致（`/xxx` ↔ `frontend/src/app/(app)/xxx/page.tsx`）
  - 检查后端 `/api/v1/menus/routes` 返回的 path 是否正确
- “访问后直接跳回登录”：
  - 检查 `useAuth()` 是否有 session；检查 `apiFetch()` 是否触发 401 自动登出
- “superuser 切换租户无效”：
  - 检查 `apiFetch(..., { tenantId: targetTenantId })` 是否传入
- “按钮显示/隐藏不符合预期”：
  - 检查 `session.permissions` 与 `hasAnyPermission()` 传参是否一致
