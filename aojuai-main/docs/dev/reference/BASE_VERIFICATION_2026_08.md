# nextjs-base 验收记录（2026-08-08）

只记真机跑过的结果。没跑过的写在最后一节，不含糊。

## 静态验收

| 项 | 结果 |
|---|---|
| 后端 `pytest tests/ -q` | **322 passed / 0 failed**（基线 237） |
| 前端 `pnpm typecheck` | 干净 |
| 前端 `pnpm build`（标准生产构建） | 成功，40/40 静态页 |
| `python scripts/check_governance.py` | 5 条规则全 PASS（21 迁移 / 186 py 文件 / 29 模型 / 42 前端页面） |
| `alembic heads` | 单 head `base_20260808_merge_v2_heads` |

治理门禁的**注入验证**（规则必须能抓到真违规，否则等于没写）：

| 规则 | 注入内容 | 结果 |
|---|---|---|
| GOV-10 | 新增一个 `os.getenv("EXPORT_DIR")` 的业务文件 | 变红 → 还原变绿 |
| GOV-08 | 新增迁移把 `updated_at` 建成 `nullable=False` | 变红 → 还原变绿 |
| GOV-09 | 给软删模型加普通 `UniqueConstraint` | 变红 → 还原变绿 |

## 数据库验收（真实 PostgreSQL）

用 `aoju_base_v2` 及其克隆 `_fresh` / `_mig1` / `_mig2`。

### 三条链路终态一致

| 链路 | menus | role_menus | CMS 菜单集合 |
|---|---|---|---|
| 新装（migrate + seed） | 59 | 131 | 一致 |
| 升级（只跑 alembic） | 59 | 131 | 一致（diff 为空） |
| 运行时建租户 | 新租户拿到 **26 条授权** | — | 对账 0 问题 |

第三条是本轮修掉的真 bug：`create_tenant_with_admin()` 原来**一条 role_menus 都不写**。

### 残缺状态可恢复

打坏库（删授权）→ `check_seed_state.py` 报出 **缺失授权 9、父级闭包断层 29**
→ `repair_menu_state.py` 补齐 9 条 → 再对账**全部归零** → 再修一次 **0 变更**（幂等）。

原来做不到：CMS seed 拿根菜单当哨兵，子菜单/按钮/授权被删后重跑也修不回来。

### 软删除唯一约束

`ix_tenants_code` 迁移后变成 `CREATE UNIQUE INDEX ... WHERE (deleted_at IS NULL)`；
实测软删一条 `probe-code` 后可以再建同名的一条（原来被唯一约束顶回去）。

### init_db 不覆盖已迁移库

`AUTO_INIT_DB=true` 且库已有 `alembic_version` 记录时启动 → 日志无 `create_all`，
表数 35 全部来自迁移，登录 200。

## 运行时验收（后端 <backend-port> / 前端 <frontend-port>）

### 公开站关闭 = 路由不存在，不是"路由在、被拦住"

| 状态 | `/api/v1/site/cms/settings` 响应 | 含义 |
|---|---|---|
| `PUBLIC_SITE_ROUTING_MODE=off` | `{"detail":"Not Found"}` | FastAPI 自己的 404 → **路由未注册** |
| `path` 模式 + 未知 Host | `{"code":"NOT_FOUND","message":"Site not found"}` | 路由已注册并执行，租户解析拒绝、**不回落别租户** |

两个响应体签名不同，正好把"没注册"和"注册了被拦"区分开。
（注意：本应用关闭了 docs，`/openapi.json` 本身是 404，不能用它判断路由是否注册。）

### 公开站开启不再抢走后台路由

`path` 模式下逐个实测：

```
/login  200   /welcome 200   /cms/pages 200
/system/tenant-settings 200   /assistant 200
/site/anything 404（未命中的公开 slug 返回真 404，不做 soft-200）
```

这正是下游那次事故的场景 —— 开公开站后 `/catalog` `/sources` 等整个后台被当成 CMS slug 打成 404。

### SMTP 租户级配置

- PATCH 明文密码 → 库里只有 `passwordEncrypted`（密文），全库搜明文 **0 命中**
- GET 只回 `passwordSet: true`，不回显密文
- 通用 settings 接口写 `messaging.email.smtp.password` → **被拒绝**，
  报 `SMTP settings must be updated through /email-config`（P0 绕过路径已封死）

## 可选能力包装配（用样例模块 `sample_items` 实测）

```
capability db upgrade  → core 链与 sample 链各自独立升级
                         两张 version 表：alembic_version / alembic_version_cap_sample_items
                         只建了 cap_sample_items；迁移没有顺手 seed 菜单（seed 前菜单数 0）
capability sync        → 两个租户各补上菜单授权（seed 后 2 条）
```

装 ≠ 开，两级开关实测：

| 状态 | `/api/v1/sample-items` | 菜单 |
|---|---|---|
| 未安装 | 路由不存在 | 无 |
| 已安装、租户未开 | 403「模块已关闭」 | 不出现 |
| 已安装、租户已开 | 200，CRUD 正常（建了一条 tenant_id=1 的记录） | 出现 |

安装合同测试的注入验证（两道防线是分层的）：

- 拆掉发现层的 `continue` → **import 那条变红**（未安装的适配层被 import 了）
- 只拆 `register_capability_router` 内的检查 → 不红，第一道还在拦
- 两道都拆 → **路由注册那条也变红**

## 真机才暴露的两个缺陷（已修）

1. **对账脚本默认路径直接崩**：`(:tenant_id IS NULL OR id=:tenant_id)` 在 asyncpg 下
   无法推断 NULL 参数类型。纯 mock 测试抓不到，因为它们根本不连库。
2. **对账写完菜单不让缓存失效**：`/menus/routes` 按 `menu_version` 缓存，
   而 reconciler 从不 bump。表现是"菜单修好了、接口还是旧树"，
   用户会以为修复没生效然后去手改数据库。所有单测都直接调 reconciler，绕过了缓存层。

第二条尤其说明问题：**能被单元测试覆盖的路径，和用户真正走的路径，不是同一条。**

## 脚手架实测

```
python -m scripts.new_module demo_orders --layer pack --route /demo-orders \
    --entity order --permissions read,create,update,delete
→ created 18 files；**不改任何中央 router/catalog 文件**（靠自注册发现）
```

装上这个生成的包之后全量 356 passed；移除后回到 352 passed。

过程中抓到一个真摩擦：基座自己有 5 处测试断言了**精确的**模块目录集合，
于是下游每装一个包都会把基座测试打红 —— 等于"加模块还要改中央文件"，
只是搬到了测试里。已改成断言"内置项存在且取值正确"。

## 没做的验证（如实记录）

- 真实 SMTP 服务器发信（没有可用凭据，只验到配置解析与加密存储）
- 公开站 `domain` 模式（需要真实域名与 DNS，只验了 `off` 与 `path`）
- 需要真实 PostgreSQL 的治理门禁自动化（seed 幂等对账、祖先闭包、flush 后属性过期探针）
  —— 本轮是手工跑的，还没做成 CI 测试
- 浏览器端 E2E（只做了 HTTP 层状态码验证，没跑 Playwright）
- support / media / devices / credentials 这几个真正的可选包尚未拆出来 ——
  机制已经跑通（样例模块走的就是这条路），但把 support 从 下游电商分支 拆成自包含的包
  还有一串耦合要先解（见架构文档里列的 9 条前提）。
