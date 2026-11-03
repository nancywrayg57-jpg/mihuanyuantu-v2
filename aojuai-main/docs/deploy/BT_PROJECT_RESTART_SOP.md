# BT Project Restart SOP

本文是宝塔 / Nginx 部署下的前后端重启总入口。它只保留顺序、路由和验收点，具体命令以细分 SOP 为准，避免多个文件重复维护同一段部署逻辑。

## 适用范围

- `nextjs-base` 独立部署。
- 下游扩展继承 `nextjs-base` 部署基线。
- BT 托管 Next.js 前端、FastAPI 后端，并由 Nginx 作为唯一公网受信边界。

## 文档路由

- 前端构建、BT Node 重启、随机端口和 `502` 排查：`docs/deploy/BT_FRONTEND_DEPLOY_SOP.md`
- 后端迁移、seed、BT Python 重启和新路由 `404` 排查：`docs/deploy/BT_BACKEND_DEPLOY_SOP.md`
- Nginx 后端直连、可信代理密钥、Range/SSE、缓存策略：`docs/deploy/nginx.bt.reference.conf`
- BT extension 后端直连片段：`docs/deploy/nginx.bt.backend-routes.extension.conf`
- Next 静态资源、public 资源和 HTML 壳缓存：`docs/deploy/BT_NGINX_CACHE_SOP.md`
- 代理/rewrite 事故根因库：`docs/dev/issues/DEPLOYMENT_PROXY_PITFALLS.md`

## 重启顺序

1. 后端有迁移或 seed 变化时，先执行 `BT_BACKEND_DEPLOY_SOP.md` 的迁移与 seed。
2. 重启后端，确认 `127.0.0.1:<BACKEND_PORT>` 已监听。
3. 构建并重启前端，确认 Next.js 真实监听端口。
4. 同步或确认 Nginx `location /` 指向真实前端端口。
5. 确认 `/api/v1/*`、`/health`、`/static/*` 仍由 Nginx 直达 FastAPI。
6. reload Nginx 前先执行 `nginx -t`。
7. 跑页面、public config、未登录 auth smoke test。

## 生产代理红线

- 正式部署以 Nginx 为唯一受信边界。
- 浏览器页面、`/_next/*`、前端 public 资源走 Next.js 或 Nginx 本地静态直出。
- 浏览器 `/api/v1/*`、`/health`、`/static/*` 直达 FastAPI。
- Nginx 转发 FastAPI 时覆盖注入 `x-aoju-proxy-key`，值与后端 `AOJ_PROXY_SHARED_SECRET` 一致。
- `NEXT_ENABLE_BACKEND_REWRITES=0`。
- 不要使用 Next rewrite 转发 `/api/:path*`。

## 最小验收

```bash
curl http://127.0.0.1:<BACKEND_PORT>/health
curl -I -k https://base.example.com/
curl -k https://base.example.com/api/v1/site/public-config
curl -k https://base.example.com/api/v1/auth/mine
```

预期：

- 后端 health 返回 `200`。
- 页面返回 `200`。
- public config 返回 `200`。
- 未登录 `auth/mine` 返回 `401`，不是 `403`。

如果登录接口返回 `403`，优先检查 Nginx 后端直连规则和 `x-aoju-proxy-key`，不要先改 Next rewrite。
