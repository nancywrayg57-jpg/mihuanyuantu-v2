# AOJUAI nextjs-base

`nextjs-base` 是 AOJUAI 的公开底座版本，目标是提供可复用的多租户管理后台与后端基础能力，而不是业务模块合集。

启动后，前端 `/welcome` 会渲染本文件作为默认欢迎页。

## 底座范围

- 多租户、用户、角色、菜单、权限、团队与数据权限。
- 个人设置、租户设置、系统设置等管理面。
- AI 助手基础配置、会话、工具/技能治理与通用交互入口。
- 语音配置、TTS/STT provider catalog、试听与音色能力。
- 通知、站内消息、Message Channel、微信、飞书与 Webhook 网关。
- 注册、邀请、验证码、积分、操作日志、运行时缓存、调度器与安全头。

公开版不内置垂直业务页面、业务数据模型、业务 prompt、业务 action executor 或业务分支历史资料。需要垂直能力时，应作为插件或下游扩展接入底座契约。

## 文档入口

- 文档地图：`DOCS_MAP.md`
- 统一文档索引：`docs/README.md`
- 文档路由设计：`docs/DOCUMENTATION_ROUTING.md`
- 部署文档入口：`docs/deploy/README.md`
- 最小部署 SOP：`docs/deploy/NEXTJS_BASE_MINIMAL_DEPLOY_SOP.md`
- 开放版稳定基线：`docs/public/open-edition-base-hardening.md`
- AI 助手边界：`docs/public/assistant-foundation-boundary.md`
- 后端说明：`backend/README.md`
- 前端说明：`frontend/README.md`
- 维护者文档中心：`docs/dev/README.md`

## 仓库结构

- `backend/`: FastAPI + SQLAlchemy Async + PostgreSQL 后端。
- `frontend/`: Next.js App Router + Tailwind + shadcn/ui 管理后台。
- `docs/`: 统一文档根目录。
- `docs/public/`: 面向公开版的底座说明。
- `docs/dev/`: 面向维护者的开发流程、检查表、模板和核心参考。

## 环境依赖

- Python `>= 3.11`
- Node.js `>= 20.19` 或 `>= 22.13`
- pnpm `>= 9`
- PostgreSQL
- Redis 可选；不可用时运行时缓存降级为未命中。

默认本地端口：

- 后端：`38000`
- 前端：`3000`

## 本地启动

后端：

```bash
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.production.template .env
alembic upgrade head          # 本地开发：只升 core 链
uvicorn app.main:app --reload --host 0.0.0.0 --port 38000
```

前端：

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm dev --host 0.0.0.0 --port 3000
```

前端最小联调变量：

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:38000
API_BASE_URL=http://127.0.0.1:38000
AOJ_PROXY_SHARED_SECRET=<SHARED_PROXY_SECRET>
NEXT_ENABLE_BACKEND_REWRITES=0
```

## 生产代理边界

正式部署以 Nginx 为唯一受信边界：

- 页面、`/_next/*`、前端资源：Nginx -> Next.js。
- `/api/v1/*`、`/health`、`/static/*`：Nginx -> FastAPI。
- Nginx 转发 FastAPI 时覆盖注入 `x-aoju-proxy-key`，值与后端 `AOJ_PROXY_SHARED_SECRET` 一致。
- `NEXT_ENABLE_BACKEND_REWRITES=0`。Next App Route proxy 只作为端口直连、无 Nginx 或特殊服务端代理的兜底。

不要使用 Next rewrite 转发 `/api/:path*`。rewrite 不能可靠承担受信代理边界，也容易抢在 App Route proxy 之前匹配。

## 默认账号

开启 `AUTO_SEED_DATA=true` 时会创建：

- 管理员：`admin / Admin@123456`
- 测试用户：`test / Test@123456`

## 验证

```bash
cd backend
python -m compileall -q app tests
python -m pytest tests/test_feature_switches.py tests/test_tenant_profile_config_safety.py -q

cd ../frontend
pnpm typecheck
pnpm build
```
