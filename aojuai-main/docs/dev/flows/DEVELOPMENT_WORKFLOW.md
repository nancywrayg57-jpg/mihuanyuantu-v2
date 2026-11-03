# AOJUAI 应用开发闭环流程（nextjs-base）

> 目标：把“需求 → 设计 → 开发 → 部署 → 验证 → 复盘”做成可重复、可审计、可回滚的闭环流程，适用于 `nextjs-base` 及其下游扩展。

维护者文档建议入口：
- 新模块端到端：`docs/dev/flows/NEW_MODULE.md`
- Skill 选择地图：`docs/dev/flows/SKILLS_MAP.md`
- 开发自检：`docs/dev/checklists/DEV_CHECKLIST.md`

## 0. 适用范围与基本原则

- 适用范围：本仓库 `backend/` + `frontend/` 的所有增量功能、修复、扩展模块（含外部平台接入）。
- 关键原则：
  - **先规格后代码**：先明确需求、数据模型、权限/菜单、接口契约，再进入编码。
  - **后端先行**：先跑通 API 再写前端页面。
  - **闭环交付**：交付必须包含“安装/升级步骤 + 验证用例 + 日志排错线索”。
  - **演示模式（可选）**：用于演示环境只读浏览；默认关闭，可通过前端环境变量开启。
  - **无 Docker**：文档与部署方案不以 Docker 为前提（按当前产品约束）。
  - **端口约束**：避免常见端口冲突，推荐后端 `38000`、前端 `38848`（按现有脚手架默认）。

## 1. 交付物（每个功能/模块最少要有）

1. **需求说明**：范围、角色、用例、验收标准、非目标（Out of scope）
2. **数据模型**：表结构（字段/索引/约束/tenant_id）、关系、迁移策略
3. **权限/菜单**：权限码清单（`resource:action`）、菜单结构（目录/页面/按钮）
4. **接口契约**：请求/响应字段、分页、错误码、权限要求
5. **安装/升级**：迁移命令、seed 命令、配置项、回滚策略
6. **验证闭环**：冒烟用例、关键链路用例、日志关键词与排错路径

> 模板与脚手架：见 `docs/dev/skills/aojuai-development-workflow/SKILL.md`。

## 2. 闭环流程（推荐顺序）

### Step A：需求澄清（从“做什么”开始）

必须输出：
- 用户故事（谁/在什么场景/要完成什么/为什么）
- 功能边界（本次不做什么）
- 验收标准（可操作、可测试）
- 角色与权限边界（系统管理员/租户管理员/普通用户/外部访客）

### Step B：模块形态决策（核心 or 下游扩展）

先判定：
- 是否属于“通用底座能力”（租户/用户/角色/菜单/权限体系）？
  - 是：进入 Core 改造（谨慎、少改）
  - 否：按“下游扩展”方式设计（推荐），不要把业务语义写入公开底座。

### Step C：数据模型设计（先表结构再写代码）

检查清单：
- 是否为租户数据？（绝大多数业务表需要 `tenant_id`）
- 是否需要软删除？（默认有 `deleted_at`，查询需过滤）
- 是否需要审计字段？（`created_by/updated_by` 或在 `extra` 中记录）
- JSONB 字段是否有 `server_default="{}"` / `server_default="[]"`（避免插入报错）
- 索引是否足够（tenant_id、外键、查询条件、唯一约束）

迁移策略：
- 结构变更与数据回填尽量拆分两次迁移
- 每次迁移都能升级/回滚（至少不报错）

### Step D：权限/菜单设计（避免后补导致返工）

本仓库权限事实：
- 默认采用 **Role⇄Menu** 赋权
- 权限码建议承载在 `menus.perms`
- **按钮权限**建议用 `menu_type="2"`（不参与动态路由，但会进入登录返回 `permissions`）

输出：
- 权限码清单（`resource:read/list/create/update/delete`）
- 菜单树（目录 `0` / 页面 `1` / 按钮 `2`），并给出 icon 与 component

补充规范（来自多分支反复修订的共识）：
- **模块设置入口统一放系统配置**：`/system/<module>-settings`，只授权给租户管理员（默认 `admin` 角色）
- **配置数据必须是租户级**：带 `tenant_id` 的配置表，或落到 `tenants.config.<namespace>`

### Step E：接口契约（前后端对齐）

建议固定的契约点：
- 统一响应：`success/data/message/code`
- 分页字段：`{ list, total, pageSize, currentPage }`
- 错误码：业务错误要能定位（例如 `KB_NOT_CONFIGURED`）

### Step F：后端实现（对齐 guide_docs）

实现顺序：
1. `backend/app/domain/<module>/`（models/service/schemas）
2. `backend/app/api/v1/endpoints/<module>.py`（薄控制器 + PermissionChecker + TenantCtx）
3. 注册路由 + 模型导入（避免 Alembic 漏生成）

必须做到：
- 查询/更新/删除均带 `tenant_id` 限定（除非系统表）
- 事务：Service 层只 `flush()`，不 `commit()`（由 `get_db()` 统一管理）
- 结构化日志：关键操作记录 `user_id/tenant_id/obj_id`

### Step G：迁移与种子（可重复执行）

- 迁移：`alembic revision --autogenerate` → 审阅 → `alembic upgrade head`
- 种子：
  - 全新库：`backend/scripts/seed_data.py`
  - 增量（推荐）：`backend/scripts/seed_<module>.py`（幂等）

菜单/权限变更的闭环（必须做）：
- **新租户/新装**：在 `seed_data.py`（或租户创建钩子）中创建菜单并写入 `role_menus`
- **已有租户升级**：用 Alembic 做“数据迁移”补齐新菜单/授权（迁移必须允许“无租户时安全 no-op”，并保持幂等）

参考：
- `docs/dev/checklists/DEV_CHECKLIST.md`（“菜单权限同步”章节）
- `docs/dev/issues/DEVBASE_PITFALLS.md`（“迁移 vs seed 时序”章节）

### Step H：前端实现（菜单后端输出 + Next.js App Router）

要点：
- **菜单路由必须由后端输出并按权限过滤**：`GET /api/v1/menus/routes`
- Next.js 路由以文件结构为准：`frontend/src/app/(app)/**/page.tsx`
  - 本分支不依赖 `menus.component` 做组件映射（但 `menus.path` 必须与 Next.js 路由一致）
- 演示模式下写接口会被前端拦截；若列表使用 POST（读语义），需要评估是否加入 allowlist

### Step I：验证（冒烟 → 关键链路 → 回归）

最小冒烟：
- `/health` 返回正常
- 登录正常、菜单加载正常、核心列表页可打开

关键链路：
- 本功能的“主路径”至少跑通 1 次（含权限边界）

### Step J：上线与日志闭环（必须做）

上线前：
- 确认已执行迁移、seed（如有）
- 确认 `.env` 配置齐全（不要提交敏感信息）
- 正式 Nginx 部署确认 `NEXT_ENABLE_BACKEND_REWRITES=0`
- 确认 `/api/v1/*`、`/health`、`/static/*` 由 Nginx 直达 FastAPI，并注入 `x-aoju-proxy-key`

上线后（闭环完成的判定标准）：
- 关键链路用例通过
- 登录 smoke test 结果符合预期：未知账号应返回 `401`，不是代理/CSRF 边界导致的 `403`
- 如果使用 BT 随机端口，`ss -ltnp` 真实 Next 端口与 Nginx `location /` 一致
- `logs/error.log` 无新增 500 峰值（或已解释）
- 能通过日志关键词定位异常（见下一节）

## 3. 日志闭环（从“可观测”到“可排错”）

### 3.1 日志记录要求（最低标准）

对外接口（API endpoint）建议至少记录：
- 事件名（snake_case）
- `user_id`、`tenant_id`、`path`、`method`
- 关键对象 `obj_id` 或 `resource_id`
- 跨租户操作标记（如 `is_cross_tenant`）

### 3.2 排错路径（建议 SOP）

1. 先看错误响应的 `code`（业务错误应有明确 code）
2. 查 `logs/error.log` / `logs/info.log` 相关时间窗口
3. 以 `path` + `user_id` + `tenant_id` 定位请求链路
4. 若涉及外部平台：同时检查外部平台日志与网络连通性

## 4. 附：复用模板与脚手架

- 开发流程 Skill：`docs/dev/skills/aojuai-development-workflow/SKILL.md`
- 公开版稳定基线：`docs/public/open-edition-base-hardening.md`
- 开发检查表：`docs/dev/checklists/DEV_CHECKLIST.md`
