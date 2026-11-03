# 迁移与 Seed 问题

> 本文件累计"迁移写错 / seed 漏项"类问题。每条都要写清楚：现象、根因、正确做法。
> 规则一旦定下，配套的检查必须能扫全仓（见 `flows/NEW_MODULE.md` 机器验收清单）。

## 1. seed 用"哨兵"判断已完成，导致残缺状态修不回来

**现象**：菜单少了一个按钮或一条角色授权，重跑 seed 也补不回来。

**根因**：seed 拿根菜单当哨兵 —— 根节点存在就整段跳过。CMS seed 就是这样写的。

**正确做法**：seed 是**对账（reconcile）**语义，不是"有就跳过"：
缺的补、path/meta 变了就改、重复行合并、授权缺失补齐（含父级闭包）。
判定标准：任意残缺状态跑一次 seed 都收敛到同一终态；连跑两次第二次零变更。

## 2. 只写了 seed 和迁移两条链路，漏了"运行时新建租户"

**现象**：新建的租户开箱没有菜单授权，只能事后补跑全库 seed。

**根因**：`create_tenant_with_admin()` 不写任何 `role_menus`；
而文档一直宣称"新装/新租户走 seed"，把两件事混成一件。

**正确做法**：三条链路（seed / Alembic 数据迁移 / 建租户）**共用同一个 reconciler**，
三者终态必须相等。详见 `flows/MENUS_PERMS_DUALWRITE.md`。

## 3. 迁移 import 了会变的声明

**现象**：改了菜单声明之后，历史版本升级上来的结果跟着变了，不可复现。

**正确做法**：迁移里内嵌**不可变快照**。当前终态用于 seed 与建租户，
历史快照用于迁移，两者由 CI 检查"声明变了但没生成新快照"。

## 4. `updated_at` 被建成 NOT NULL

**现象**：插入时不带 `updated_at` 直接报错。

**根因**：写迁移时顺手加了 `nullable=False`。**踩过两次**，第二次是因为
上一次的测试查的是 ORM 模型 —— 而模型是对的，错在迁移文件里。

**正确做法**：检查必须扫**迁移文件本身**的 `upgrade()`，不是扫 ORM。

## 5. 软删除与唯一约束打架

**现象**：删掉一条记录后，同名的建不回来。

**正确做法**：业务唯一键配 partial unique index
`postgresql_where=(deleted_at IS NULL)`；确实要永久唯一的，显式声明并写明理由。

## 6. 可选 PostgreSQL 扩展没有 guard

**现象**：目标库没装 `pg_trgm`，`alembic upgrade head` 直接失败。

**正确做法**：用到扩展的迁移要先探测可用性，不可用时降级建普通索引；
并有一条"在没装可选扩展的 PostgreSQL 上也能 upgrade head"的测试。

## 7. 迁移失败后回落 `AUTO_INIT_DB=true`

**现象**：schema 与迁移链长期对不上，后面每次迁移都要人工修。

**根因**：部署脚本在 `alembic upgrade` 失败后继续，依赖 `AUTO_INIT_DB` 的
`create_all()` 兜底 —— 它会按 ORM 现状补出迁移链里根本不存在的表和列。

**正确做法**（已在基座实现）：`init_db()` 检测到库里已有 `alembic_version`
且有版本记录时直接返回，不再 `create_all`。迁移是 schema 的唯一真源；
迁移失败就应该让部署失败，而不是用另一条路径把库"补"起来。

## 8. 单 head

`alembic heads` 必须恰好返回一个。可选能力包用**独立迁移链 + 独立 version_table**，
不要往 core 链上挂 branch label —— `upgrade heads` 会把所有可见分支都升级，
而 merge revision 要求所有父 revision 存在，等于要求所有包都安装。

## 9. 实例（回流自 nextjs-plugins）

### 9.1 迁移使用 gin_trgm_ops 但目标库无 pg_trgm 扩展导致 upgrade head 硬失败

### 症状
- `alembic upgrade head` 在 `plugins_20260608_project_management_core` 失败：
  `psycopg2.errors.UndefinedObject: operator class "gin_trgm_ops" does not exist`

### 触发条件
- 宝塔编译的 PostgreSQL（如 18.0）默认不带 contrib 扩展，`CREATE EXTENSION pg_trgm` 报 "extension is not available"

### 根因
- 该迁移无条件创建 trgm 索引；而先例 `plugins_20260405_training_search_trgm_indexes` 会先查 `pg_available_extensions`，不可用则跳过

### 修复（服务器侧，已在演示实例执行）
1. 宝塔保留了源码包 `/usr/local/src/postgresql-18.0.tar.gz`，解压 `contrib/pg_trgm`
2. `make USE_PGXS=1 PG_CONFIG=/www/server/pgsql/bin/pg_config && make install ...`
3. `CREATE EXTENSION pg_trgm;` 后重跑 `alembic upgrade head`

### 预防
- 所有 trgm/gin 表达式索引迁移必须按 `plugins_20260405` 的写法做扩展可用性守卫（不可用时安全跳过）
