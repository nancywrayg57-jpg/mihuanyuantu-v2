# 新功能模块开发链路（nextjs-base）

> 目标：给“从 0 到 1 新增一个功能模块”提供统一作业流（考虑项、顺序、技能选择、验收方式）。
>
> 新模块默认支持 PostgreSQL / SQLite 双方言；确需 PostgreSQL 专有能力时请显式声明。

## 0) 先做分类（决定后续路径）

### 0.1 落在哪一层（判据见 `reference/BASE_ARCHITECTURE.md`）

| 层 | 一句话判据 | 结果 |
|---|---|---|
| kernel | 删掉它就没法认证/解析租户/授权/隔离数据 | 必装，且**不许 import 任何业务域** |
| base capability | 产品要求所有基座发行版内置，或已被 ≥3 个互相独立的模块使用且协议稳定无业务词汇 | 默认装，可租户级关，也**可部署时不装 / 硬卸载**（须登记 `module_manifest`） |
| optional pack | 有专用业务表/业务状态机/垂直菜单，或只有一个业务分支消费 | 默认关，**部署时选择安装** |
| sample | 只用于教学与脚手架验收 | 不进生产 catalog，发布构建遇到即失败 |

命中 optional pack 任一条件的，就按 pack 做，除非有明确的"全基座内置"产品决策。
**判断自包含的硬标准：把这个目录整个拷进一个空基座，能不能直接跑。**

无论落在哪一层，"不装就不加载"都是硬要求：装配与卸载的完整流程见
`flows/DYNAMIC_MODULE_LOADING.md`，三种「未安装」的语义差别见
`reference/BASE_ARCHITECTURE.md` §5.1。

### 0.2 其余分类

1. **是否存在租户级配置（模块设置）？**
   - 有：租户级配置入口**目前没有声明式机制**：AI 与语音已折叠进 `/system/tenant-settings?tab=<code>`（legacy path 由 `menus.py` 的 `LEGACY_ROUTE_PATH_ALIASES` 映射），其余仍是独立页。
  新模块二选一即可，**不要照抄旧文档里“必须是 `/system/<module>-settings`”那条**。
2. **是否需要数据权限（DataScopeCtx）？**
   - 只有需要"按团队/范围过滤"的列表/查询才需要

参考：
- `docs/public/open-edition-base-hardening.md`
- `docs/dev/guide_docs/DATA_PERMISSION_GUIDE.md`

## 1) 需求与验收（必须先写出来）

最小输入（建议用模板）：
- 目标与边界（In/Out）
- 角色（普通用户/租户管理员/超级管理员）
- 页面入口（path）与权限码清单（`resource:action`）
- 数据模型字段（含：索引/唯一/默认值/是否 JSONB）
- 验收标准（至少 5 条：权限可见性/租户隔离/升级可用/新装可用/日志可定位）

模板：
- `docs/dev/templates/REQUIREMENTS_TEMPLATE.md`

建议 Skill：
- `docs/dev/skills/aojuai-development-workflow/SKILL.md`

## 2) DB 设计（多租户 + 软删除 + 索引）

关键考虑：
- `tenant_id`（绝大多数业务表必须）
- `deleted_at` 软删除默认过滤
- 列表查询常用索引（tenant_id + 常用过滤字段）
- JSONB 默认值与 asyncpg cast 规则

参考：
- `docs/dev/templates/DB_DESIGN_TEMPLATE.md`
- `docs/dev/guide_docs/ENUM_USAGE_GUIDE.md`

建议 Skill：
- `docs/dev/skills/aojuai-sqlalchemy-async/SKILL.md`

## 3) 权限与菜单（先设计再写代码）

### 3.1 权限模型事实（不要误用旧分支）

- 没有 `permissions` 表
- 权限码在 `menus.perms`
- 角色授权通过 `role_menus`

参考：
- `docs/dev/guide_docs/PERMISSION_CHECKER_GUIDE.md`
- `docs/dev/skills/aojuai-rbac-menu-perms/SKILL.md`

### 3.2 模块设置入口（如果有租户级配置）

- 形态见 0.2；不要硬编码 `/system/<module>-settings`
- 仅租户管理员（默认 `admin` 角色）可见/可配

### 3.3 菜单/权限必须三写（最容易漏）

必须**同时**覆盖三条链路，缺一条就会出现"只在某类环境缺菜单"的线上问题：

- 新装 / 全库对账：seed（`seed_data.py` / `seed_<module>.py`）
- 已有租户升级：Alembic 数据迁移（内嵌不可变快照、幂等、无租户时 no-op）
- 运行时新建租户：租户创建后调用同一个 reconciler

三条链路**共用同一个 reconciler**。seed 必须是对账语义（缺的补、变的改、
重复的合、授权补齐含父级闭包），不是"根节点在就跳过"。

参考：
- `docs/dev/flows/MENUS_PERMS_DUALWRITE.md`
- `docs/dev/guide_docs/MENU_SEED_MIGRATION_GUIDE.md`

建议 Skill：
- `docs/dev/skills/aojuai-menu-perms-dualwrite/SKILL.md`

## 4) API 契约（前后端对齐）

重点：
- 分页字段（`currentPage/pageSize/total/list`）
- 排序字段（`sortBy/sortOrder`）与白名单校验
- 错误响应结构（统一 response）

参考：
- `docs/dev/templates/API_CONTRACT_TEMPLATE.md`
- `docs/dev/guide_docs/API_ENDPOINT_GUIDE.md`
- `docs/dev/checklists/DEV_CHECKLIST.md`

建议 Skill：
- `docs/dev/skills/aojuai-backend-module/SKILL.md`

## 5) 后端实现（API 薄 + Service 承载 DB）

硬性规则：
- API 层只做参数校验/依赖注入/调用 Service（禁止直接 DB）
- 事务与提交策略遵循 guide_docs
- 禁止 lazy loading（关系预加载）

参考：
- `docs/dev/guide_docs/SERVICE_LAYER_GUIDE.md`
- `docs/dev/guide_docs/DATABASE_TRANSACTION_GUIDE.md`
- `docs/dev/guide_docs/RESPONSE_USAGE_GUIDE.md`

建议 Skills：
- `docs/dev/skills/aojuai-backend-module/SKILL.md`
- `docs/dev/skills/aojuai-backend-migrations/SKILL.md`

## 6) 迁移（结构）+ 种子/数据迁移（运行时数据）

### 6.1 结构迁移（表/字段/索引/约束）

参考：
- `docs/dev/skills/aojuai-backend-migrations/SKILL.md`

### 6.2 菜单/权限与默认数据（运行时数据）

参考：
- `docs/dev/skills/aojuai-backend-seed/SKILL.md`
- `docs/dev/guide_docs/MENU_SEED_MIGRATION_GUIDE.md`

## 7) 前端对接（Next.js App Router）

关键点：
- 路由以文件结构为准：`frontend/src/app/(app)/**/page.tsx`
- 菜单必须由后端输出并按权限过滤：`GET /api/v1/menus/routes`
- 页面按钮权限与后端 perms 一致（React 条件渲染，例如 `hasAnyPermission(session, [...])`）
- 任何 options / lookup / config 预加载，都必须先与后端 `PermissionChecker(...)` 对齐；缺权限时直接 skip request，不允许靠 `catch 403` 兜底
- superuser 场景注意 `X-Tenant-Id`（`useTenant()` → `apiFetch(..., { tenantId })`）

参考：
- `docs/dev/skills/aojuai-nextjs-shadcn-frontend/SKILL.md`
- `docs/dev/reference/frontend/FRONTEND_BASELINES.md`
- `docs/dev/guide_docs/FRONTEND_PERMISSION_OPTION_LOADING.md`

## 8) 机器验收清单

> 完成定义：以下检查必须由命令/CI 证明通过，**不接受"人工 grep 过"**。
> 不适用的条目也要在模块声明里显式置空，不能直接跳过。
> 标 ⏳ 的门禁本轮尚未实现（需要真实 PostgreSQL），先按人工执行并记录结果。

- [ ] 模块文件被 inventory **动态发现**；没有靠改硬编码白名单让测试变绿
- [ ] 未安装时**不 import、不挂路由**：`AOJ_ENABLED_MODULES` 不列它时，
      子进程里该模块的业务模块加载数为 0，访问其路径返回 404（不是 403）
- [ ] 内置能力另需在 `app/core/module_manifest.py` 登记 `code_paths` /
      `model_modules` / `table_prefixes`（GOV-18 检查），删掉代码目录后应用仍能启动
- [ ] 每条 API route 都声明了安全等级；权限路由的 dependency graph 里有匹配的 `PermissionChecker`
- [ ] owner 作用域资源通过"本人成功 / 同租户他人 404 / 跨租户 404"
- [ ] 请求模型不接收服务端计费价格；服务端价格由价格表解析
- [ ] 公开分享（如有）：缺密码 / 密码错 / 失效 / 不存在的状态矩阵通过；
      密码更新的未传（保留）/ 空串（清除）/ 非空（替换）三态通过；资源归属缺失 fail closed
- [ ] ⏳ seed 连跑两次数据库快照一致；删一个子菜单 + 一个按钮 + 一条授权并改一个 path 后，
      重跑 seed 恢复到声明终态
- [ ] fresh+seed、旧租户只 upgrade、新租户 bootstrap 三场景终态**相等**：
      `python -m scripts.check_scenario_parity`（自建临时库，跑完销毁；
      当前已知 bootstrap 掉队，见 `issues/PERMISSIONS_MENUS.md` §0.1）
- [ ] 所有页面菜单 path 都能解析到 `frontend/src/app/(app)/**/page.tsx`；
      新增后台页面要么被声明为菜单，要么显式标记 internal/hidden
- [ ] 三场景的 `role_menus` 都满足祖先闭包（同上脚本一并检查）
- [ ] 迁移图恰好一个 head；`updated_at` 为 nullable
- [ ] 软删除模型的业务唯一键用 `WHERE deleted_at IS NULL` 的 partial unique index；
      永久唯一键要显式写明理由
- [ ] 运行时配置全部在 Settings；源码里没有直接 `os.environ` / `os.getenv`
- [ ] ⏳ flush/commit 之后构造响应不读过期 ORM 属性（server-managed 字段先 refresh）
- [ ] ⏳ 新增缓存只走统一 cache adapter，Redis key 自动带实例 namespace
- [ ] 可选 PostgreSQL 扩展（如 `pg_trgm`）有可用性 guard，没装扩展也能 upgrade head
- [ ] 前端 `pnpm check` 通过（**标准 build，含 lint**，不许用 `--no-lint` 蒙混）
- [ ] 后端 `pytest -q` 无新增失败；`python -m scripts.check_governance` 返回 0
- [ ] **每个新增的扫描器都注入过一次真实违规并确认变红**，还原后变绿

关于最后一条：本仓已经出现过两次"测试写完全绿但一个 bug 也抓不到"。
规则是全仓的，测试的作用域就必须是全仓的；检查 ORM 模型挡不住迁移文件里写错。

参考：
- `docs/dev/checklists/DEV_CHECKLIST.md`
- `docs/dev/skills/aojuai-backend-testing/SKILL.md`

## 9) 遇到问题怎么沉淀（不是写一遍就丢）

当出现可复现问题：
1. 先加到 `docs/dev/issues/` 对应分类（见 `docs/dev/issues/README.md`）
2. 如果是“会反复踩坑”的：同步补到 `docs/dev/checklists/DEV_CHECKLIST.md`
