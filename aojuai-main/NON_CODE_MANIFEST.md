# 非代码文件清单

本清单用于公开发行版维护，说明仓库内主要非运行时代码文件的用途。

## Public Docs

- `README.md`：公开版入口说明。
- `DOCS_MAP.md`：仓库文档地图和路径职责。
- `docs/README.md`：统一文档入口。
- `docs/DOCUMENTATION_ROUTING.md`：文档顶层设计和路径归属规则。
- `docs/deploy/README.md`：部署文档入口。
- `docs/deploy/*.md`：最小部署、BT 前后端重启、Nginx 缓存和事故 SOP。
- `docs/deploy/*.conf`：通用 Nginx 参考片段，使用占位域名、端口和密钥。
- `docs/public/open-edition-base-hardening.md`：公开版稳定基线与发布检查。
- `docs/public/assistant-foundation-boundary.md`：AI 助手底座边界。
- `backend/README.md`：后端开发与运行说明。
- `backend/API_ROUTES.md`：后端 API 路由索引。
- `frontend/README.md`：前端开发与运行说明。
- `frontend/public/README.md`：前端 public 资源说明。

## Maintainer Docs

- `.claude/CLAUDE.md`：AI/维护者启动入口，指向当前 `nextjs-base` 文档地图。
- `docs/dev/README.md`：维护者文档入口。
- `docs/dev/checklists/`：开发和发布检查表。
- `docs/dev/flows/`：开发流程。
- `docs/dev/guide_docs/`：后端、权限、菜单、日志、事务等代码级指南。
- `docs/dev/issues/`：公开底座问题和部署踩坑沉淀。
- `docs/dev/reference/`：认证、安全、迁移链、前端基线等核心参考。
- `docs/dev/reference/assistant/`：AI 助手底座接入、公开路由和能力治理规则。
- `docs/dev/reference/message-channel/`：个人消息通道、系统网关和助手入口边界。
- `docs/dev/skills/`：AI 开发技能包。
- `docs/dev/templates/`：需求、API、DB、测试、发布模板。

公开版不携带分支治理记录、业务研究资料、回收站归档、客户事故原文、真实部署路径或第三方 upstream 源码快照。

## Config And Templates

- `.gitignore`
- `backend/.env.production.template`
- `backend/alembic.ini`
- `backend/pyproject.toml`
- `backend/requirements.txt`
- `backend/requirements-dev.txt`
- `frontend/package.json`
- `frontend/pnpm-lock.yaml`
- `frontend/tsconfig.json`
- `frontend/.env.production`

本地私有文件如 `.env`、`backend/.env`、`frontend/.env.local` 不入库。
