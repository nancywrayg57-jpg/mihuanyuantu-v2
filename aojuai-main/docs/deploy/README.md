# Deploy Docs

本目录保存 `nextjs-base` 公开版的部署文档。跨前端、后端、Nginx、BT 的部署规范统一放这里，不再放在根目录或前端子目录。

所有示例都使用占位项目名、路径、域名、端口和密钥，不能写入真实客户环境信息。

## 路由

- `NEXTJS_BASE_MINIMAL_DEPLOY_SOP.md`：独立部署最小基线。
- `BT_PROJECT_RESTART_SOP.md`：宝塔 / Nginx 前后端重启总入口。
- `BT_FRONTEND_DEPLOY_SOP.md`：前端构建、重启、随机端口同步和 502 排查。
- `BT_BACKEND_DEPLOY_SOP.md`：后端重启、迁移、seed、新接口 404 排查。
- `BT_NGINX_CACHE_SOP.md`：Next 静态资源、public 资源和 HTML 壳缓存策略。
- `nginx.bt.reference.conf`：完整 Nginx 反向代理参考。
- `nginx.bt.backend-routes.extension.conf`：适合宝塔 extension 目录的后端直连 location 片段。

## 固定原则

- 正式部署以 Nginx 为唯一受信边界。
- 页面、`/_next/*`、前端 public 资源走 Next.js 或 Nginx 本地静态直出。
- `/api/v1/*`、`/health`、`/static/*` 直达 FastAPI，并由 Nginx 覆盖注入 `x-aoju-proxy-key`。
- `NEXT_ENABLE_BACKEND_REWRITES=0`。Next rewrite 不能作为生产 API 代理。
- BT 若使用随机前端端口，必须以 `ss -ltnp` 查到的真实 Next 监听端口为准，不能只看面板记录。
