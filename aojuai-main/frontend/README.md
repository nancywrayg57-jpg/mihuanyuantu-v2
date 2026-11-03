# nextjs-base frontend

Next.js App Router + Tailwind + shadcn/ui 管理后台。

## 底座页面

- 个人设置：个人资料、通知与 Message Channel 绑定。
- 租户设置：基础信息、注册、邀请、插件开关、AI 配置、语音设置、SEO。
- 系统设置：用户、角色、菜单、字典、通知、操作日志、租户包等平台管理页面。
- AI 助手与语音能力：只保留通用入口和配置，不内置垂直业务页面。

## 本地开发

```bash
pnpm install --frozen-lockfile
pnpm dev --host 0.0.0.0 --port 3000
```

## 环境变量

- `NEXT_PUBLIC_API_BASE_URL`：浏览器访问后端 API 的地址；为空时使用同源。
- `API_BASE_URL`：Next.js 服务端访问后端时使用的地址。
- `AOJ_PROXY_SHARED_SECRET`：服务端代理请求透传给后端的共享密钥。
- `NEXT_ENABLE_BACKEND_REWRITES`：兼容直连场景的后端 rewrite 开关；生产保持 `0`，且不会 rewrite `/api/:path*`。
- `NEXT_PUBLIC_AOJ_ENABLED_MODULES`：前端模块可见性兜底值，通常由后端 catalog 接管。
- `NEXT_PUBLIC_DEMO_MODE`：演示模式。
- `NEXT_PUBLIC_DEMO_MODE_MESSAGE`：演示模式提示文案。

## 构建

```bash
pnpm typecheck
pnpm build
pnpm start
```

`pnpm start` 会优先使用外部注入的 `PORT`。生产反代应使用稳定端口；随机端口只适合本地调试。

## 部署文档

- `../docs/deploy/README.md`：部署文档入口。
- `../docs/deploy/nginx.bt.reference.conf`：BT / Nginx 参考配置。
- `../docs/deploy/BT_FRONTEND_DEPLOY_SOP.md`：前端构建、重启、随机端口同步和 502 排查。
- `../docs/deploy/BT_NGINX_CACHE_SOP.md`：Next 静态资源和 HTML 壳缓存策略。

## 代理说明

- 正式 Nginx 部署：页面与 `/_next/*` 走 Next.js；`/api/v1/*`、`/health`、`/static/*` 走 FastAPI。
- Nginx 转发 FastAPI 时必须覆盖注入 `x-aoju-proxy-key`，值与 `AOJ_PROXY_SHARED_SECRET` 一致。
- Next App Route proxy 保留为本地端口直连、无 Nginx 或特殊服务端代理场景的兜底。
- 不要使用 Next rewrite 转发 `/api/:path*`；语音音频流与 AI 助手 SSE 都属于 `/api/v1/*`，生产应由 Nginx 直达 FastAPI。
