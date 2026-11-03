# nextjs-base backend

FastAPI + SQLAlchemy Async + PostgreSQL 后端，提供多租户系统管理、RBAC、数据权限、AI 助手、语音配置、通知与消息通道等底座能力。

## Tech Stack

- Python `>= 3.11`
- FastAPI
- SQLAlchemy 2 async ORM
- PostgreSQL
- Redis optional runtime cache
- Alembic
- Pydantic v2

## Development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.production.template .env
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 38000
```

## Runtime Notes

- 配置默认读取 `backend/.env`；进程环境变量会覆盖 `.env`。
- 生产环境必须设置 `JWT_SECRET_KEY` 和数据库密码。
- Redis 不可用时 runtime cache 降级为未命中。
- `MESSAGE_GATEWAY_TASKS_ENABLED=false` 时保留消息通道配置能力，但不启动网关轮询任务。
- SSR/代理链路启用 trusted proxy 时，正式部署由 Nginx 为 `/api/v1/*`、`/health`、`/static/*` 注入 `x-aoju-proxy-key`；Next 服务端代理只作为兜底。
- 登录态以 `HttpOnly` Cookie 为主，前端不长期持久化真实 token。

## Tests

```bash
python -m compileall -q app tests
python -m pytest tests/test_feature_switches.py -q
```

## Structure

```text
app/
├── api/              # API routes and dependencies
├── core/             # config, feature switches, permissions, runtime helpers
├── domain/
│   ├── auth/         # tenants and authentication
│   ├── users/        # users and profile fields
│   ├── roles/        # roles and role-menu/team permissions
│   ├── menus/        # menu tree and route metadata
│   ├── teams/        # team tree and data scope
│   ├── assistant/    # assistant foundation
│   ├── speech/       # speech foundation
│   ├── notifications/# notifications and message channels
│   └── operation_logs/
└── infrastructure/   # database and cache adapters
```

API docs are available in development mode at `/api/v1/docs` and `/api/v1/redoc`.
