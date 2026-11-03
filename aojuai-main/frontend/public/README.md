# AOJUAI nextjs-base frontend public assets

本目录只放 Next.js public 静态资源说明。`nextjs-base` 前端基于 Next.js App Router 与 shadcn/ui，作为公开底座管理后台实现：

- 动态菜单：从后端 `/api/v1/menus/routes` 拉取并渲染
- 多租户：系统管理员可切换目标租户（`X-Tenant-Id`）
- 登录鉴权：使用后端 `/api/v1/auth/login` 与 HttpOnly Cookie 会话
- 管理模块：个人设置、租户设置、系统设置、用户、角色、菜单、团队、通知、操作日志、积分等

## 环境变量

- `NEXT_PUBLIC_API_BASE_URL`：后端 API 基址，例如 `http://127.0.0.1:8000`；为空则使用同源。
- `NEXT_ENABLE_BACKEND_REWRITES=0`：正式 Nginx 部署保持关闭；`/api/v1/*` 由 Nginx 直转 FastAPI。

## 本地开发

```bash
pnpm -C frontend install
pnpm -C frontend dev
```

默认端口：`3000`

## 演示账号

登录页提供了演示账号快捷填充（以你的后端 seed/环境为准）。
