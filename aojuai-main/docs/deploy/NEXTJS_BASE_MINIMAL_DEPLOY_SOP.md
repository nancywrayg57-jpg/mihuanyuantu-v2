# nextjs-base 独立部署最小 SOP

适用范围：
- `nextjs-base` 作为基座分支的独立部署
- 后续下游扩展的部署基线

边界约束：
- `nextjs-base` 只承载基座能力
- 当前基座内置 `assistant` 与 `speech` 两层能力
- 其他业务模块不应混入 base 的默认部署

配套安全基线：

- 认证 / 会话 / trusted proxy / 分享页安全头，统一参考 `docs/dev/reference/AUTH_SECURITY_BASELINE.md`
- BT / Nginx 细化部署参考见 `docs/deploy/README.md`
- 部署代理事故复盘见 `docs/dev/issues/DEPLOYMENT_PROXY_PITFALLS.md`

以当前代码为准（2026-08-09 起）：`AOJ_ENABLED_MODULES=none` 之后**只有 `assistant` 常驻**——
它是 AI 基座，CMS AI、租户模型配置都建在它之上。`speech` 已改为可装卸，
要用就显式写进 `AOJ_ENABLED_MODULES`（例如 `assistant,speech`）。
`none` 的含义是“除常驻基座外不再安装任何可选模块”。
三种「未安装」的语义差别见 `docs/dev/reference/BASE_ARCHITECTURE.md` §5.1。

## 1. 最小依赖

- Linux 服务器
- Python `>= 3.11`
- Node.js `>= 20.19`
- `pnpm >= 9`
- PostgreSQL `>= 14`
- Redis 可选：当前不是启动硬依赖，但建议保留

## 2. 最小目录约定

以下目录名不是强制，但本文档统一用这组示例：

```text
/srv/nextjs-base/
  backend/
  frontend/
```

后端配置固定读取 `backend/.env`。现在不再依赖“必须从哪个工作目录启动”才能正确加载环境变量，但运维脚本仍建议从各自目录执行。

## 3. 数据库准备

示例：

```sql
CREATE ROLE "nextjs_base" LOGIN PASSWORD '<DB_PASSWORD>';
CREATE DATABASE "nextjs_base" OWNER "nextjs_base";
```

## 4. 后端最小配置

复制环境模板：

```bash
cd /srv/nextjs-base/backend
cp .env.production.template .env
```

最小推荐配置：

```env
APP_NAME=AOJUAI
APP_VERSION=0.1.0
DEBUG=false
ENV=production

API_V1_PREFIX=/api/v1

CORS_ORIGINS=["https://base.example.com"]

DB_HOST=127.0.0.1
DB_PORT=5432
DB_USER=nextjs_base
DB_PASSWORD=<DB_PASSWORD>
DB_NAME=nextjs_base
DB_ECHO=false

JWT_SECRET_KEY=<STRONG_SECRET>
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
AUTH_ACCESS_COOKIE_NAME=aoju_access_token
AUTH_REFRESH_COOKIE_NAME=aoju_refresh_token
AUTH_COOKIE_DOMAIN=
AUTH_COOKIE_SECURE=true
AUTH_COOKIE_SAMESITE=lax

# 必须与 Nginx / 前端服务端环境保持一致，用于受信代理透传
AOJ_PROXY_SHARED_SECRET=<SHARED_PROXY_SECRET>

AUTO_INIT_DB=false
AUTO_SEED_DATA=false

# 基座部署建议显式收口，不安装额外业务模块。
# assistant 常驻（AI 基座）；speech 已可装卸，需要语音就写成 AOJ_ENABLED_MODULES=speech。
AOJ_ENABLED_MODULES=none

REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
```

说明：
- 生产环境不要依赖 `AUTO_INIT_DB` / `AUTO_SEED_DATA`
- 首次正式部署统一走 Alembic + 手动 seed
- `AOJ_ENABLED_MODULES=none` 是为了阻止误挂载业务插件，不会影响 base 内置的 `assistant` / `speech`
- 如果前端与后端处于同一主域，`AUTH_COOKIE_DOMAIN` 可留空；只有需要跨子域共享 cookie 时才显式配置
- `AUTH_COOKIE_SAMESITE=none` 时必须同时启用 HTTPS 与 `AUTH_COOKIE_SECURE=true`

## 5. 后端安装与启动

安装依赖：

```bash
cd /srv/nextjs-base/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

执行迁移：

```bash
cd /srv/nextjs-base/backend
source .venv/bin/activate
alembic upgrade head
```
> **装了可选能力包时用编排命令**：`python -m scripts.capability db upgrade`
> —— 它先把 core 升到 head，再逐个把已安装的能力包升到各自链的 head，并校验每条链单 head。
> 裸 `alembic upgrade head` **只升 core**，能力包的表建不出来。
> （`aojubuilder/scripts/deploy.sh` 已做能力探测：分支里有 `backend/scripts/capability.py` 就自动改用它。）


首次初始化基础数据：

```bash
cd /srv/nextjs-base/backend
source .venv/bin/activate
python -m scripts.seed_data
```

启动后端：

```bash
cd /srv/nextjs-base/backend
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 38000
```

开发态可用：

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 38000
```

## 6. 前端最小配置

前端是 Next.js，不再是旧的 Vite 方案。

生产最小配置建议写入 `frontend/.env.production`：

```env
NEXT_PUBLIC_API_BASE_URL=https://base.example.com
API_BASE_URL=http://127.0.0.1:38000
AOJ_PROXY_SHARED_SECRET=<SHARED_PROXY_SECRET>
NEXT_ENABLE_BACKEND_REWRITES=0
NEXT_PUBLIC_DEMO_MODE=false
NEXT_PUBLIC_DEMO_MODE_MESSAGE=演示模式：仅可查看，禁止修改
```

如果前后端同域且由反向代理统一转发 `/api/v1`，也可以把 `NEXT_PUBLIC_API_BASE_URL` 留空。

说明：

- `API_BASE_URL` 给 Next.js 服务端渲染使用
- `AOJ_PROXY_SHARED_SECRET` 只允许服务端读取，不能改成 `NEXT_PUBLIC_*`
- `NEXT_ENABLE_BACKEND_REWRITES` 生产保持 `0`；Next App Route proxy 只作为端口直连、无 Nginx 或特殊服务端代理兜底
- 如果遗漏 `AOJ_PROXY_SHARED_SECRET`，Nginx/SSR 代理请求可能会被后端 trusted proxy 规则拦截

安装与构建：

```bash
cd /srv/nextjs-base/frontend
pnpm install --frozen-lockfile
pnpm build
```

启动：

```bash
cd /srv/nextjs-base/frontend
pnpm start
```

开发态可用：

```bash
cd /srv/nextjs-base/frontend
pnpm dev --host 0.0.0.0 --port 3000
```

## 7. Nginx 最小转发要求

正式部署以 Nginx 为唯一受信边界，至少保证三类路径：

- `/` -> 前端 Next.js
- `/api/v1/` -> 后端 FastAPI
- `/static/` -> 后端静态文件

Nginx 转发后端时必须覆盖注入 `x-aoju-proxy-key`，值与后端 `AOJ_PROXY_SHARED_SECRET` 一致：

```nginx
location ^~ /api/v1/ {
    proxy_pass http://127.0.0.1:38000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header x-aoju-proxy-key "<SHARED_PROXY_SECRET>";
}
```

如果不把 `/api/v1` 和 `/static` 交给后端，前端只会启动成功，但实际登录、上传、配置页都会异常。不要使用 Next rewrite 转发 `/api/:path*`；它不能可靠承担受信代理密钥注入，也容易抢在 App Route proxy 前面匹配。

宝塔环境建议把后端直连规则放到站点 extension include，避免 Node 项目同步端口时重写主配置后丢失 `/api/v1/`、`/static/` 和 `/health`。参考 `docs/deploy/nginx.bt.backend-routes.extension.conf`。

## 8. 首次验收清单

先验后端：

```bash
curl http://127.0.0.1:38000/health
```

再验页面与接口：

- 打开登录页
- 使用 `admin / Admin@123456` 登录
- 打开 `/system/tenant-settings?tab=ai`
- 打开 `/system/speech-settings`
- 确认菜单中没有未启用的下游扩展菜单

## 9. 生产部署的最小禁忌

- 不要在生产长期开启 `AUTO_INIT_DB=true`
- 不要在生产长期开启 `AUTO_SEED_DATA=true`
- 不要把 `NEXT_PUBLIC_DEMO_MODE=true` 带到正式环境
- 不要让浏览器长期保存真实 access/refresh token
- 不要把 `AOJ_PROXY_SHARED_SECRET` 暴露成前端公开变量
- 不要在正式 Nginx 部署中启用 Next backend rewrite
- 不要把 `AOJ_ENABLED_MODULES` 配成业务分支白名单
- 不要让 base 直接承载垂直业务逻辑

## 10. 作为下游扩展基线时的继承规则

下游扩展部署应先满足本 SOP 的全部基线，再额外增加扩展自己的内容：

- 额外模块白名单
- 额外迁移后的模块初始化或 demo seed
- 额外外部服务配置，例如扩展网关、业务模块 AI 配置、业务数据 seed

换句话说：

1. 先按 `nextjs-base` 把“能启动、能迁移、能登录、能进入租户 AI/语音设置”的基座跑通
2. 再叠加下游扩展模块
3. 不允许反过来拿下游扩展的业务依赖回灌 base
