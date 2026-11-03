---
name: aojuai-devbase-scaffold
description: Extend AOJUAI nextjs-base scaffold (FastAPI + PostgreSQL + Next.js). Use for adding base modules/APIs, menus/permissions, migrations, and seed data.
---

# AOJUAI nextjs-base 脚手架扩展（总览）

用于在本仓库中**系统化扩展功能**：后端新模块/新接口、前端新页面/新接口、菜单权限、迁移与种子数据。

> Skills 总入口：`docs/dev/skills/skills.md`
> 开发闭环流程：`docs/dev/flows/DEVELOPMENT_WORKFLOW.md`

## 关键约束（不要踩坑）

- **端口**：后端 `38000`，前端 `39948`（本分支 Next.js dev）
- **无 Docker 部署**：公开版不携带 Docker 运行方案，默认使用本机进程或外部进程管理器部署
- **演示模式**：如你要启用 DemoMode（只读）能力，需明确前端实现策略并更新对应文档/Skill（见 `aojuai-demo-mode`）

## 目录定位（你该改哪里）

- 后端业务代码：`backend/app/domain/<module>/`、`backend/app/api/v1/endpoints/<module>.py`
- 迁移：`backend/alembic/versions/`
- 种子数据：`backend/scripts/seed_data.py`（一次性初始化）或新增 `backend/scripts/seed_<module>.py`（增量）
- 后端规范：`docs/dev/guide_docs/*.md`
- 前端业务代码（本分支 Next.js）：`frontend/src/app/**`、`frontend/src/components/**`、`frontend/src/lib/**`
- 菜单/权限：后端以 `menus`/`role_menus` 为准，并通过 `GET /api/v1/menus/routes` 输出“可见菜单树”（按权限过滤）
  - 本分支不依赖 `menus.component` 做组件映射（但 `menus.path` 必须与 Next.js 路由一致）

## 决策树（先选路径再动手）

```
要做什么？
  ├─ 需要闭环交付（需求/设计/测试/日志） → 用 `aojuai-development-workflow`
  ├─ 只改后端（新增资源/接口/表） → 用 `aojuai-backend-module` + `aojuai-backend-migrations`
  ├─ 只改前端（新页面/对接接口） → 用 `aojuai-nextjs-shadcn-frontend`
  ├─ 新模块要挂菜单/权限/按钮 → 加 `aojuai-backend-seed`（或用菜单管理页手动加）
  ├─ 默认演示模式下也要可浏览列表 → 加 `aojuai-demo-mode`
  └─ 要维护公开底座边界 → 先读 `docs/public/open-edition-base-hardening.md`
```

## 黄金流程（端到端新增一个模块）

1. **明确资源规格**：数据字段、列表筛选项、权限码（`resource:action`）、是否多租户、是否需要数据权限(DataScope)
2. **后端先行**：按 `docs/dev/guide_docs/` 规范实现 Domain + Service + Endpoint
3. **迁移**：生成并审阅 Alembic revision，执行 `alembic upgrade head`
4. **接口验证**：用 `curl` 验证返回结构（`SuccessResponse/ErrorResponse`）与分页字段（`currentPage/pageSize/total/list`）
5. **前端对接**：新增 `frontend/src/app/(app)/.../page.tsx`（先列表再表单），并补齐菜单（seed + Alembic + 建租户 reconciler 三写）确保 `/api/v1/menus/routes` 返回可见入口
6. **菜单/权限**：通过菜单管理页创建菜单（推荐），或用种子/增量脚本补齐
7. **演示模式自检**：列表是否可访问（POST 列表需 allowlist），写操作是否被阻断
8. **回归构建**：`python3 -m compileall backend/app`、`pnpm -C frontend build`

## 必读参考（按需打开）

- 后端端点规范：`docs/dev/guide_docs/API_ENDPOINT_GUIDE.md`
- Service 层规范：`docs/dev/guide_docs/SERVICE_LAYER_GUIDE.md`
- 事务规范：`docs/dev/guide_docs/DATABASE_TRANSACTION_GUIDE.md`
- 响应封装：`docs/dev/guide_docs/RESPONSE_USAGE_GUIDE.md`
- 权限检查：`docs/dev/guide_docs/PERMISSION_CHECKER_GUIDE.md`
- 数据权限：`docs/dev/guide_docs/DATA_PERMISSION_GUIDE.md`
- 公开版稳定基线：`docs/public/open-edition-base-hardening.md`
- 端到端清单：`docs/dev/skills/aojuai-devbase-scaffold/references/END_TO_END_CHECKLIST.md`
