# nextjs-base 变更说明（2026-08）

面向"要基于这个基座开新业务分支"的人。分层与判据见 `BASE_ARCHITECTURE.md`。

## 这一轮解决了什么

旧基座的问题不是缺功能，而是**同一个坑每个业务分支各踩一次**：seed 漏项、
菜单权限只写了一半、迁移把列建成 NOT NULL、软删除撞唯一约束、配置读 `os.environ`、
公开接口忘了加门禁。经验都散在各分支的文档里，回不到基座。

这一版做三件事：

1. **把经验变成机器门禁** —— 规则扫全仓、自动发现新模块、每条规则都验证过"能抓到 bug"。
2. **把模块开关从"可见性过滤"升级为"装配机制"** —— 部署时没选的能力，
   不挂路由、不建表、不 seed、不出现在前端。
3. **把基座该有的底座能力补齐**（SMTP、CMS 公开站路由与租户解析），
   同时**拒绝**把业务能力塞进来（套餐配额、定价、汇率一律不回流）。

## 关键行为变化（升级时注意）

| 变化 | 影响 |
|---|---|
| 未知模块从 fail-open 改为 **fail-closed** | 下游新增模块必须登记 catalog，否则一律视为未安装 |
| `init_db()` 在已迁移的库上不再 `create_all` | 迁移失败不能再靠 `AUTO_INIT_DB` 兜底，部署会真的失败——这是刻意的 |
| 公开接口（CMS/公开站）新增模块门禁 | 模块关闭时返回 **404**（不是 403，避免泄漏"这里有功能但关了"） |
| 公开站路由从"保留字白名单"改为 `PUBLIC_SITE_ROUTING_MODE` 三态 | 默认 `off`；开启公开站不会再抢走后台路由 |
| 公开站租户解析不再回落"第一个活跃租户" | 未知 Host 返回 404 |
| SMTP 支持租户级覆盖 | 三态 `inherit / override / disabled`；override 配置不全直接报错，**不回落系统 SMTP** |
| 软删除模型的业务唯一键改为 partial unique index | 删除后可以复用同名业务键 |
| 数据库连接池参数化 | `DB_POOL_SIZE / DB_MAX_OVERFLOW / DB_POOL_TIMEOUT / DB_POOL_RECYCLE` |

## 动态加载：改造前的现状快照（历史记录）

留档，免得以后有人以为"一直都是这样"。改造前逐项实测：

| 关掉模块时 | 改造前 |
|---|---|
| 后端 router 不注册 | ❌ `api/v1/__init__.py` 顶层全量 import 并无条件 `include_router` |
| 已认证 API 拒绝 | ⭕ 部分：`deps.py` 按 api_prefixes 拦截，只覆盖走 `get_current_user` 的接口 |
| 公开 / optional-auth API 拒绝 | ❌ `cms_public.py` 只有 `DBSession`，完全没有门禁 |
| 表不创建 | ❌ `alembic/env.py` 全量 import 模型 |
| 菜单不写库 | ❌ 无条件 seed，只在读取时过滤 |
| 未知模块 | ❌ fail-open：`is_module_installed()` 对未登记模块返回 True，且有测试在断言这个行为 |
| 删掉模块代码 | ❌ `app/domain/__init__.py` 写死模型 import，删目录 = 整个进程 ModuleNotFoundError |

量化：`AOJ_ENABLED_MODULES=none` 时进程里仍加载 7 个 CMS 模块、注册 173 条路由；
改造后同样配置下 CMS 模块 0 个、路由 146 条。

现状（三种「未安装」的权威定义）见 `reference/BASE_ARCHITECTURE.md` §5.1。

## 新增的开发者工具

- `backend/scripts/check_governance.py` —— 部署前跑一遍静态门禁，非零退出即违规
- `backend/scripts/check_seed_state.py` —— 只读对账：重复菜单 / 缺失授权 / 父级闭包断层
- `backend/tests/governance/` —— 全仓扫描测试（含"扫描器真的覆盖了全仓"的元测试）

## 开新模块从哪儿看

1. `docs/dev/flows/NEW_MODULE.md` —— 分层归属 + 机器验收清单
2. `docs/dev/flows/MENUS_PERMS_DUALWRITE.md` —— 菜单权限三条链路
3. `docs/dev/issues/` —— 已经踩过的坑，按类别分好了
