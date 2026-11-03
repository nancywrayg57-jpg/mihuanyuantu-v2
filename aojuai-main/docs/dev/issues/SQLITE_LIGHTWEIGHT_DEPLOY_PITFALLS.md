# SQLite 轻量部署踩坑（base 双方言基线，2026-08-27）

配置：`DB_DRIVER=sqlite`（缺省 `postgresql`）+ `SQLITE_PATH`（缺省 `./data/aoju.db`；`:memory:` 仅测试）。
`DATABASE_URL_OVERRIDE` 可整串覆盖。方案：`devdocs/plans/LIGHTWEIGHT_DEPLOY_SQLITE_DESIGN_20260827.md`（业务分支）。

## 1. aiosqlite ≥0.22 + SQLAlchemy：进程退出时卡死（不是我们的 bug，是上游兼容缺口）

- 现象：查询全部成功，`asyncio.run()` 返回后进程不退出；`faulthandler` 显示主线程停在 `threading._shutdown`，等的是 aiosqlite 的 `_connection_worker_thread`。
- 根因：aiosqlite 0.22 起 `Connection` 不再继承 `Thread`，工作线程也不再是 daemon；而 SQLAlchemy 的 aiosqlite 适配器从不 `await close()`，只靠原先的 `daemon=True` 让线程随进程消亡。上游：[sqlalchemy#13039](https://github.com/sqlalchemy/sqlalchemy/issues/13039)、[aiosqlite#369](https://github.com/omnilib/aiosqlite/issues/369)（截至 SQLAlchemy 2.0.45 未修）。
- 我们的兼容方案（保留最新稳定版 aiosqlite，不降级）：
  1. 文件库 `poolclass=NullPool`：连接用完即关，线程随之结束；WAL 模式下每次建连开销可忽略。
  2. 内存库必须 `StaticPool`（否则每个连接都是一个新的空库）。
  3. 应用关闭统一走 `close_db()` → `engine.dispose()`（lifespan 已接）；一次性脚本也要 `await close_db()`。
- 判别方法：`python -X faulthandler`，或 `timeout` 后看栈；若栈顶是 `threading._shutdown` 就是这个问题，与网络/驱动无关。

## 2. `create_all` 撞索引：`index ix_<table>_tenant_id already exists`

- `TenantBaseModel.tenant_id` 已 `index=True`（自动生成 `ix_<table>_tenant_id`），模型 `__table_args__` 里再显式声明同名 `Index(...)` 在 PG 上被迁移掩盖，SQLite 新库走 `create_all` 时才炸。已清理 assistant/speech 两处；新模型不要重复声明租户索引。

## 3. 类型与方言写法（回流/新增模型必须遵守）

- JSON 列用 `app.infrastructure.database.types.PortableJSON`（PG 落 JSONB，SQLite 落 JSON），主键用 `PortablePK`；不要直接 `from sqlalchemy.dialects.postgresql import JSONB`。
- 布尔缺省用 `server_default=text("true"/"false")`（SQLite 不认字符串 `"true"`）。
- 部分唯一索引同时写 `postgresql_where=` 与 `sqlite_where=`。
- JSON 取字符串用 `col["k"].as_string()`，`.astext` 是 PG 专有。
- 迁移在 SQLite 下需 `render_as_batch=True`（`alembic/env.py` 已按方言处理）；SQLite 新库由 `init_db` `create_all` 后直接 stamp 到 head，历史 PG 专有迁移不在 SQLite 上重放。
- `init_db` 探测 `alembic_version`：PG `to_regclass`，SQLite 查 `sqlite_master`；合同测试的假连接只拦 `execute`，不要改回 inspector。

## 4. raw SQL（seed / reconciler）在 SQLite 上的三处差异

- `INSERT … SELECT … ON CONFLICT`：SQLite 解析器分不清 `ON` 是 upsert 还是 join，SELECT 没有 WHERE 时报 `near "DO": syntax error`；写法固定为 SELECT 末尾加 `WHERE true`（PG 同样合法）。
- `cast(:x as jsonb)` / `now()`：seed 与菜单 reconciler 统一用 `app.infrastructure.database.portable_sql.ptext()`（SQLite 下去掉 cast、`now()`→`CURRENT_TIMESTAMP`）。
- raw SQL 读 JSON 列：PG 返回 dict，SQLite 返回字符串；用 `json_column_value()` 归一后再 `dict(...)`（否则 `dictionary update sequence element #0 has length 1`）。
- `= ANY(:ids)` 是 PG 专有，改为 `IN :ids` + `bindparam(..., expanding=True)`（`data_permission.py` 递归团队树、并发扣费测试）。
- seed 脚本里 `from app...` 导入必须放在 `sys.path.insert` 之后，否则在带 editable 安装的 venv 里会解析到另一份 `app`。

## 5. 已验证的轻量档链路（2026-08-27）

`DB_DRIVER=sqlite` + aiosqlite 0.22.1 + SQLAlchemy 2.0.45：`init_db`（34 表 + stamp head，WAL、外键开）→ `scripts/seed_data.py`（1 租户 / 2 用户 / 58 菜单 / 129 授权 / 4 CMS 页）→ uvicorn 启动（lifespan 二次 seed 幂等）→ `admin` 登录 → `/menus/routes` 3 个顶级菜单 → 租户 JSON config 写入；base 测试套件 PG / SQLite 各 417 通过。测试档由 `tests/conftest.py` 的会话夹具建表（仅 `IS_SQLITE` 时）。

## 6. codex 复审（2026-08-27）确认并修掉的 7 处 + 事务模式决策

| 问题 | 结论 |
|---|---|
| `JSON().with_variant(JSONB)` 让 PG 上 `.contains()` 从 `@>` 退化成 `LIKE`（**PG 回归**） | `PortableJSON` 改为 **JSONB 为基座 + SQLite 变体**，PG 比较器/DDL/autogenerate 与原来完全一致；数组成员判断统一用 `json_array_contains()`（PG `@>`，SQLite `json_each`） |
| SQLite `JSON_EXTRACT` 数字返回整数，退款统计 `as_string()==str(id)` 永远不命中 → 可重复超额退款 | 改 `.as_integer() == int(id)`（PG 编译为 `CAST(->> AS INTEGER)`）；真实 SQLite 验证二次退款被拒 |
| `DateTime(timezone=True)` 在 SQLite 读回 naive，与 aware 比较抛 TypeError（锁定/验证码/邀请过期） | 新增 `PortableDateTime`（PG `timestamptz` 原样；SQLite 存 UTC naive、读回补 UTC），全部 25 处替换；迁移文件保持 `sa.DateTime(timezone=True)` |
| 列 `comment=` 里的 "JSONB" 被批量替换成 "PortableJSON" → PG autogenerate 噪音 | 已恢复原文，`git diff 40c99069` 无任何 comment 变化 |
| 缺省 `./data/aoju.db` 父目录不存在；`script_location` 相对 cwd | 引擎构建时 `mkdir -p`；stamp 时把 `script_location` 锚定到 `alembic.ini` 所在目录 |
| `alembic upgrade` 在空 SQLite 上进入 PG 专有 `information_schema` 探测 | legacy bootstrap 限定 PG；SQLite 新库走 `init_db` |
| raw SQL 读 JSON 列 `"null"` → `dict(None)` 崩 | `json_column_value` 把 JSON null 归一为 default |

**事务模式**（codex 提出全局 `BEGIN IMMEDIATE` 会把整库串行）：新增 `SQLITE_BEGIN_MODE`，实测 deferred 下三并发扣费以 `database is locked` 失败（不是静默丢失，但会失败），immediate 下 417 全绿。轻量档以正确性优先，**缺省 immediate**；所有 `with_for_update` 点与 `CreditService.consume` 入口加了 `escalate_to_write_lock()`（SQLite 下先拿写锁，PG no-op），使 deferred 模式下关键写路径同样正确。长时间持有会话的流式请求在 immediate 下会让其他事务排队（busy_timeout 30s），需要高并发读的部署可切 deferred。

未采纳：`portable_sql` 的正则可能误伤字符串字面量中的 `now()`（仅 seed/reconciler 使用，无该形态），记录为已知限制；`:memory:` 仅供单进程测试，不支持并发会话。

## 7. 请求内开第二个会话 = SQLite 自锁 30 秒（immediate 模式）

- 现象：登录、切计费模式等**每个写请求都慢 30 秒**但返回 200；日志里 `BEGIN IMMEDIATE` → `database is locked`。
- 根因：`OperationLogMiddleware` 在 `call_next` 返回后立刻用 `get_db_context()` 开第二个会话写日志，而请求自己的会话（`get_db` yield 依赖）要等响应发出后才 commit/close；SQLite 单写者下第二个 `BEGIN IMMEDIATE` 等满 busy_timeout 才失败（日志被吞，请求照常返回）。PG 上只是"日志先于请求事务提交"的顺序问题。
- 修复：日志写入挂到 `response.background`（响应发出、请求事务提交之后再开会话）；异常路径没有 response 才同步写。实测 0 次锁等待、日志照常落库。
- 规则：**请求处理期间不要再开第二个会话做写入**（中间件、after-response 钩子、审计）；确实要写就走 background task 或复用请求会话。后台 worker 各自独立会话没问题（各自短事务）。

## 8. SQLite 下"不支持"的正确姿势：登记 → 统一拒绝 → 前端隐藏

- **功能级**：依赖 PG 专有能力（`jsonb_*`、`FILTER`、`interval`、advisory lock、全文检索…）的功能码登记到
  `app/core/dialect_features.PG_ONLY_FEATURES`，端点加 `dependencies=[Depends(require_postgresql("<code>"))]`；
  SQLite 下返回 `FEATURE_REQUIRES_POSTGRESQL`（400，details 带 feature/dialect）。首个用例：`credits.pricing_reconciliation`。
- **模块级**：`ModuleCatalogItem(requires_postgresql=True)` 的模块在 SQLite 下视为未安装——目录不出现、路由不挂、菜单筛掉，
  与硬卸载走同一条链路；前缀映射保留以 fail-closed。
- **前端**：`/tenants/current` 的 feature catalog 多带 `databaseDialect` 与 `unavailableFeatures`（不进 `catalogDigest`），
  用 `isFeatureAvailable(catalog, code)` 隐藏入口。
- **能双方言的就不要禁**：表/列存在性用 `portable_sql.table_exists/column_exists`，跨进程互斥用 `task_queue.scheduler_job_lock`
  （SQLite 单进程放行），upsert 用 `dialect_insert`，JSON 合并用 `json_merge_patch`。本轮据此把消息网关轮询、
  credits schema 兼容层从 PG 专有改成了双方言，而不是禁用。
- 未登记就直接写 PG 专有 SQL 是缺陷：`tests/test_dialect_features.py` 守住机制本身，PG 专有 SQL 的静态扫描待补。

## 9. 能力包（optional pack）在 SQLite 上的安装链路（回流自 下游日报分支）

- `python -m scripts.capability db upgrade`：核心链在 SQLite 新库上不重放 PG 专有历史迁移，而是 `create_all + stamp head`（与 `init_db()` 同一语义，只出现在带 `dialect.name == "sqlite"` 判断的引导里，`test_capability_orchestration` 守住"PG 仍走 upgrade"）；各能力包自己的迁移链（独立 version table）照常 `upgrade`，因此包迁移必须双方言：`render_as_batch`、`BigInteger().with_variant(Integer(), "sqlite")`、`sa.func.now()` 而不是 `text("now()")`、部分索引同时写 `sqlite_where`。
- 迁移互斥：PG 用 advisory lock；SQLite 用库文件旁的 `<db>.migrate.lock` flock；内存库放行。
- 实测：`AOJ_ENABLED_MODULES=sample_items` 在空 SQLite 上 `db upgrade` → 核心 stamp 到 head、`sample_items_0001` 升级、`alembic_version_cap_sample_items` 独立版本表；`sync` 幂等。

## 10. 存量 SQLite 库的升级：新迁移必须双方言（2026-08-28 日报实例实测）

- 现象：日报实例（SQLite，在旧 base 上 `create_all + stamp` 建库）合并新 base 后个人设置页 500：`no such column: user_message_channels.gateway_account_id`、`no such table: api_keys`、`no such function: greatest`。
- 根因：**新库靠 create_all，存量库只能靠迁移**。基线之后的 5 条 base 迁移写了 `postgresql.JSONB(`、`'{}'::jsonb`、`now()`、`= ANY(:x)`、无 WHERE 的 `INSERT…SELECT…ON CONFLICT`，`alembic upgrade head` 在 SQLite 上直接炸；ORM 侧 `func.greatest` 同理。
- 修复：五条迁移改双方言（`sa.JSON().with_variant(postgresql.JSONB(...), "postgresql")`、`sa.func.now()`、`IN :x` + expanding、按 `dialect.name` 分支的 jsonb 回填 / `CAST(:meta AS jsonb)`）；PG 侧 DDL 与语义逐字不变。`types.greatest_of()` 替代 `func.greatest`。
- 门禁：`tests/test_sqlite_migration_portability.py` 静态扫描基线之后的所有 `base_*` 迁移。
- 运维流程：升级存量 SQLite 实例 = 备份 `data/aoju.db` → `python -m alembic upgrade head`（或 `scripts.capability db upgrade`）→ 重启后端（无 `--reload` 的进程不会自动加载新代码）。

## 11. 方言判断收口到 registry（2026-08-28）

- 现象：`settings.IS_SQLITE` / `connection.dialect.name` 曾散落在 core、domain、脚本与数据库助手中；新增一条
  双方言路径时，需要逐文件寻找分支，容易让 SQL 改写、锁语义和能力声明失配。
- 收口：`app/infrastructure/database/dialect.py` 统一登记能力位、事务起始、JSON 表达式、upsert、schema
  探测、写锁升级、scheduler advisory lock 与 portable SQL；旧的 `types.py` / `portable_sql.py` API 保持为薄包装。
- 边界：应用业务代码不得读取 `IS_SQLITE`、`DB_DRIVER` 或 `dialect.name`；只有数据库 infrastructure、配置计算字段、
  `core/dialect_features.py` 与 Alembic migration env 可以直接接触方言。静态门禁扫描 `app/` 持续守住该约束。
- 结果：L0/L1 默认方言中立，L2 默认双方言；PG-only 功能仍通过 `requires_postgresql` /
  `PG_ONLY_FEATURES` 显式拒绝，不用散落的运行时分支隐藏能力缺口。
