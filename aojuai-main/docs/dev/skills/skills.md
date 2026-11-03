# AOJUAI Skills（本仓库）

> 目标：把 AOJUAI 当前 Next.js 主线的“开发套路”封装成可复用的 Skills（工作流 + 参考 + 小脚本），让 AI 能更稳定地按项目约束产出代码。

## 如何使用（建议）

1. 在对话里**点名 Skill**，例如：`使用 aojuai-backend-module ...`
2. 提供“模块规格”（可直接粘贴下面模板并填写）。
3. 让 AI 先对照**3+个现有模块**（users/roles/menus 等）再落代码，并补齐迁移/菜单/种子/前端对接。

## 模块规格模板（推荐粘贴）

- 模块英文名（domain）：`projects`
- 资源前缀（api）：`/api/v1/projects`
- 表名：`projects`
- 字段：`name(str, required) ...`（含：是否可空/默认值/索引/唯一性/是否 JSONB）
- 列表查询：筛选项、排序规则、分页参数（`currentPage/pageSize`）
- 权限码：`project:read/list/create/update/delete`（以及按钮级扩展如 `project:export`）
- 菜单：`title/path/icon/perms`
  - 本分支前端为 Next.js：路由以文件结构为准（`frontend/src/app/(app)/**/page.tsx`）
  - 菜单必须由后端输出并按权限过滤：`GET /api/v1/menus/routes`
  - 不依赖 `menus.component` 做组件映射（但 `menus.path` 必须与 Next.js 路由一致）
- 演示模式：哪些“读语义 POST（分页查询）”需要可用（否则会被前端拦截）
- 数据权限：是否需要团队级过滤（DataScope）

## Skill 列表

### 现行主线（默认使用）

- `aojuai-devbase-scaffold`：脚手架扩展总览（决策树 + 端到端流程）
- `aojuai-development-workflow`：应用开发闭环（需求→DB/API→实现→部署→日志闭环）
- `aojuai-db-setup`：数据库与初始化（PostgreSQL/Alembic/seed）
- `aojuai-backend-module`：后端新模块（Domain + Service + Endpoint），对齐 `guide_docs`
- `aojuai-backend-migrations`：Alembic 迁移工作流（autogenerate→审阅→upgrade）
- `aojuai-backend-seed`：种子数据/菜单权限初始化与增量脚本（含模板与脚手架脚本）
- `aojuai-sqlalchemy-async`：SQLAlchemy 2.0 异步会话/事务/JSONB（asyncpg）实践
- `aojuai-rbac-menu-perms`：RBAC：Role⇄Menu + `menu.perms`（无 permissions 表）的权限设计与排错
- `aojuai-menu-perms-dualwrite`：菜单/权限新增（seed + Alembic 数据迁移双写闭环）
- `aojuai-nextjs-shadcn-frontend`：Next.js（App Router）前端开发剧本（路由/布局/权限/复用策略）
- `aojuai-demo-mode`：演示模式（只读）扩展与 allowlist 原则
- `aojuai-backend-testing`：后端测试（pytest/pytest-asyncio）脚手架与示例模板
## 目录结构约定

每个 Skill 目录形态：

```
docs/dev/skills/<skill-name>/
  SKILL.md            # 触发说明 + 工作流（主入口）
  references/         # 需要时加载的详细参考（按需打开）
  scripts/            # 可执行脚本（生成/校验/对比）
  templates/          # 代码/配置模板（可选）
```

## 后续可继续创造的 Skills（建议）

- `aojuai-module-fullstack`：一条指令生成“后端+迁移+种子+菜单+前端”
- `aojuai-api-contract`：前后端接口契约（分页/错误码/字段别名/演示模式）
- `aojuai-ci`：CI（lint/typecheck/test/build）与质量门禁
- `aojuai-ops`：生产部署（systemd、nginx、日志与备份策略；无 Docker）
