# nextjs-base 架构复盘（2026-08-08）

上一轮 33 个 commit 落地后的第一次整体复盘。只记**发现了什么、怎么判、怎么处置**，
不重复架构本身（见 `BASE_ARCHITECTURE.md`）。

## 复盘方法

不是重新读一遍代码，而是拿四层判据去**逐条对代码提问**，重点问三种东西：

1. 合并留下的重复实现（同一件事有两套）
2. 层次倒置（下层依赖上层）
3. 文档写了但没有机器验证的规矩（迟早会破，而且破了没人知道）

## 发现与处置

### 1. 两套公开站租户解析并存，用的还是不安全的那套（安全相关）

合并时两个批次各写了一套：

| 实现 | 语义 |
|---|---|
| `core/module_guards.resolve_public_tenant_id` | host → `code="default"` → **第一个活跃租户** |
| `core/public_site.resolve_public_tenant` | 精确匹配已配置域名；开发态回落需同时满足显式配置 + loopback；否则 404 |

`deps.py` 引用的是**前者**。今天没出事只因为唯一的可选认证端点在 `/auth` 下、
不属于任何模块，那段代码根本不会执行——是把上了膛的枪。

处置：删掉重复实现；匿名请求打到模块路径上改为 **fail closed**，不再猜租户；
顺带删掉从未被使用的 `PublicSiteTenantId` 依赖。
测试锁住两件事：匿名路径**不查库**（一旦有人加回猜租户就会出现 DB 调用）、
带回落的解析器不许再回到内核里。

### 2. 内核反过来依赖能力域（层次倒置）

四层判据里最硬的一条「内核不得认识业务/能力」，此前只是文字。实际已破四处：

| 位置 | 实质 | 处置 |
|---|---|---|
| `core/notification.py` | 其实是通知域的门面 | → `domain/notifications/send.py` |
| `core/operation_log.py` | 操作日志域的门面 | → `domain/operation_logs/recorder.py` |
| `core/middlewares/operation_log_middleware.py` | 同上 | → `domain/operation_logs/middleware.py` |
| `core/scheduler.py` | 直接 import 飞书长连接客户端做关停 | 改注册式：内核提供 `register_shutdown_hook`，通知域自己注册 |

调用方各只有 1 处，代价很小——**放着不管的成本远高于现在改**。

### 3. 装配机制的归属错了

`capability_registry` / `capability_runtime` 是**装配机制**，不是能力包，
却被放在 `app/capabilities/` 下，于是内核不得不 import 它。
搬进 `app/core/`，现在 `app/capabilities/` 下只有能力包，语义自解释。

### 4. 菜单内核持有 CMS 的声明

CMS 的菜单声明住在 `domain/menus/cms_declaration.py` —— 等于菜单内核认识 CMS。
移到 `domain/cms/access.py`。菜单域只提供对账机制与 spec 类型。
配套测试：`domain/menus/` 下只允许出现内核文件，且不许提到 cms / capabilities。

### 5. 文档说的生产命令与部署脚本不一致

架构文档写明生产权威命令是 `capability db upgrade`，但 `deploy.sh` 还在跑裸
`alembic upgrade heads` —— 装了能力包后它的独立迁移链**永远不会被升级**。
`deploy.sh` 改为能力探测（有 `capability.py` 就用它，没有就走原路径），
对其他分支逐字不变。

## 新增门禁 GOV-14（内核纯净度）

`backend/governance_tools/kernel_purity.py`：扫 `app/core/**` 与 `app/infrastructure/**` 的
import，只允许 auth/users/roles/menus/teams/organizations/user_groups 这组
「认证与租户根」，其余能力域与具体能力包一律禁止。唯一豁免是发现机制本身，
理由写在 allowlist 里。

注入验证：内核 import 能力域 → 变红；内核 import 具体能力包 → 变红；还原 → 全绿。

## 这次复盘暴露的方法问题

第一版 fail-closed 测试是**假绿**：注入违规后它照样通过，因为代码往下走到另一行
也会抛同样的异常。改成断言「匿名路径不查库 + 那个解析器不许存在」才真正锁住不变量。

教训与之前一致：**测试写完必须注入一次违规确认它变红**，
而且要想清楚自己锁的是"现象"还是"不变量"——锁现象很容易被别的路径顺带满足。

## 验收

后端 355 passed / 0 failed、前端 tsc 干净、`check_governance.py` 6 条全 PASS、
alembic 单 head。

---

# 整轮复盘（2026-08-09 收口，`4e78fbc4` → `016f5b7e`）

上面记的是中途的一次架构复盘；这一段是**整轮 50 个 commit 收口时的账**。

## 规模

| | |
|---|---|
| 变更 | 194 文件，+12489 / −1090 |
| 新增文件 | 83 |
| **删除文件** | **0**（核对过：只有 9 处移动，没有能力丢失） |
| 核心迁移 | 18 → 21（含 1 条 merge revision） |
| 测试 | 43 → 68 个文件，**237 → 368** 条 |
| 静态门禁 | **0 → 10 条**（GOV-06/08/09/10/13/14/15/16/17/18） |

## 这一轮真正的突破：模块从"可见性过滤"变成"装配机制"

改造前 `AOJ_ENABLED_MODULES=none` 只是把菜单藏了——7 个 CMS 模块照样加载、
173 条路由照样注册、未知模块还 fail-open。收口后三级语义定死（见
`BASE_ARCHITECTURE.md` §5.1），并且每一级都有测试锁住：

- 租户级停用 → 代码在、路由在、菜单隐藏、API 403
- 部署级不装 → 不 import、不挂载、404、开关项都不出现（CMS 模块 7→0，路由 173→146）
- 硬卸载（删代码目录）→ 声明一并消失，应用照常启动，表按设计留着

配套落地：能力包自注册 + 独立迁移链 + 独立 `version_table`、`scripts/new_module.py`
脚手架、`sample_items` 官方样例、`app/core/module_manifest.py` 物理边界清单、
alembic `include_object` 防误删残留表。

## 踩过的坑（按"下次怎么避免"记）

1. **codex 空转 30 分钟找 Python 环境**，一行代码没写。
   → 所有 codex 提示词写死解释器路径 `<deploy-root>/.venv/bin/python`。
2. **两次假绿测试**：全绿但抓不到任何 bug。
   → 断言不变量而不是源码文本；每条新检查都注入违规确认变红。本轮这条规矩
   抓住了自己写的三处漏洞。
3. **文档里编事实**：写过不存在的 `settings_surface`、不存在的
   `capability uninstall --purge`、把菜单租户语义写反。收口时写
   `DYNAMIC_MODULE_LOADING.md` 又冒了一次（不存在的 `capability install`）。
   → 文档里出现的每个命令/路径，落笔前跑一次 `--help` 或 `ls`。
4. **规范与代码冲突时先查事实**：审计说 `SERVICE_LAYER_GUIDE` 的 Repository 约束
   过时了；实测 14 个域里 12 个都遵守——是新写的代码偏了。**改代码，不改规范。**
5. **双 head**：两条迁移挂在同一个 `down_revision`。→ 用 merge revision，不改历史。
6. **纯 mock 测试抓不到的两个线上真 bug**：
   `(:tenant_id IS NULL OR id=:tenant_id)` 在 asyncpg 下推断不出 NULL 参数类型；
   `reconciler` 修完不 bump 菜单缓存版本，导致修复看起来无效。
   → 能被单元测试覆盖的路径，和用户真正走的路径不是同一条。
7. **三次测量都测错了**才拿到 CMS 的真实开销（共享依赖算进去了 / 模块已预加载测出 0ms /
   设错 settings 实例）。→ 下结论前先确认自己测的是什么。
8. **基座测试断言了精确的模块目录集合**：下游每装一个包就把基座测试打红——
   等于"加模块要改中央文件"搬进了测试里。→ 断言"内置项存在且取值正确"。

## 明确不做（写下来免得被当技术债推回）

- 业务能力不回流：套餐配额、定价、汇率
- 内置能力不转能力包、不追求零残留表——目标只有"不冗余加载代码"（见 §5.1.1）
- 不为优化另起分支，一律在 nextjs-base 上迭代

## 收口时仍欠的账

- CMS 六个页面约 155 处硬编码中文（GOV-16 白名单挂着，`issues/FRONTEND.md` 有清账计划）
- 前端 route shim 不按已装包生成，整棵 `(app)` 仍会编译
- "fresh+seed / 旧租户只 upgrade / 新租户 bootstrap 三场景终态相等"需要真 PostgreSQL，
  本轮手工验过，没做成 CI

## 收口验收

后端 368 passed / 0 failed、`check_governance.py` 10 条全 PASS、
`pnpm typecheck` 干净、alembic 单 head、线上 nextjs-base（57963/57964）已更新。
