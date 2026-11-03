# nextjs-base 架构：四层分工与装配契约

> 状态：现行（2026-08-08 定稿）。本文是基座的准入判据与回流清单，取代
> 早期回流审计里过时的口径。
>
> 一句话原则：**base 只收「拷进一个空基座就能直接跑、且不认识任何业务概念」的东西；
> 其余一律做成可选装配或样例。**

## 0. 为什么要分层

下游分支（下游电商分支 / logistics / plugins / radio）各自长出了大量能力，其中一部分是
所有业务都要重写一遍的通用件（邮件、CMS、工单、通知分发、套餐配额），另一部分是纯业务。
过去的做法是「谁需要谁自己抄一份」，结果是同一个坑在每个分支各踩一次
（seed 漏双写、菜单路由不一致、迁移 NOT NULL、软删除撞唯一约束……）。

但把它们一股脑塞进 base 会让基座臃肿：新业务分支一开局就背着工单表、套餐表、汇率表。
所以要分层，并且**每一层的准入判据必须是可执行的检查，不是形容词**。

### 0.1 数据库方言中立

定位：**L0/L1 内核保持方言中立；PostgreSQL 是标准档，SQLite 是轻量档；所有方言差异只允许存在于
`app/infrastructure/database/`；L2 默认支持双方言，确需 PostgreSQL 专有能力时必须用
`requires_postgresql` / `PG_ONLY_FEATURES` 显式声明。**

数据库 schema 有三条生命周期路径：

1. 新 SQLite 库按当前 ORM metadata 执行 `create_all`，随后 stamp 到 core head。
2. 存量库执行 `alembic upgrade head`；基线后的每条迁移都必须同时支持 PostgreSQL 与 SQLite。
3. 能力包使用自己的迁移链和 version table，独立 upgrade、独立校验 head，不混入 core 链。

明确不做：不支持多进程 SQLite 部署；不在 SQLite 新库上重放 PostgreSQL 专有的历史迁移；
`:memory:` SQLite 只用于测试，不作为部署形态。

## 1. 四层定义与准入判据

### L0 内核 kernel

没有它系统起不来。

| 判据 | 检查方式 |
|---|---|
| 删掉它其它层编译不过或登录不了 | 人工；新增内核件需在评审说明 |
| 内核不得 import 任何能力域 | **GOV-14**（`backend/governance_tools/kernel_purity.py`）：扫 `app/core/**`、`app/infrastructure/**` 的 import，只允许 auth/users/roles/menus/teams/organizations/user_groups 这组「认证与租户根」，其余能力域与具体能力包一律禁止 |
| 内核不得出现业务字段/业务路径常量 | 同一扫描测试的黑名单（例：`teams.max_note_workspaces`、`security_headers` 里的 `/exam-prep-share` 都是反例） |

需要内核在某个时机回调模块时（例如调度器停止时要收掉长连接），
**由模块自己 `register_shutdown_hook` 注册进来**，不许内核反过来 import 模块。

装配机制（`core/capability_registry.py` 与 `core/capability_runtime.py`）属于内核；
`app/capabilities/` 目录下**只放能力包**。这条区分是有代价的教训：
机制一开始被放进 `app/capabilities/`，于是内核不得不 import 它，GOV-14 一上线就报警。

成员：auth / tenants / users / roles / menus / teams / user_groups / organizations /
data_permission / operation_logs / upload / db session / cache / scheduler /
feature_switches + modules + module_guards / response / schemas / security_headers /
public_share / provider_secrets。

### L1 底座能力 base capability（默认装）

| 判据 | 检查方式 |
|---|---|
| 至少两个下游分支已实际用过 | 回流时在本文件记录来源分支与 commit |
| 自包含：整个目录拷进空 base 能跑 | 依赖扫描：只允许 import L0 与其它 L1 |
| 关掉它不影响登录与菜单树完整性 | 开关组合测试 |
| 不认识任何业务概念 | 只存 `related_type` 这类字符串，业务含义由调用方定义 |

成员（现状 + 本轮回流）：assistant / speech / invitations / credits /
notifications（个人消息通道 + 网关 + **事件 dispatcher**）/ **邮件 SMTP（系统级 + 租户级）** /
**CMS + 公开站** / public_share。

### L2 可选能力包 optional pack（默认关，部署时选）

判据同 L1 的自包含要求，但**不是每个业务分支都需要**。硬要求是「关掉即零负担」：

| 关闭时 | 必须做到 |
|---|---|
| 后端路由 | 不挂载（OpenAPI 里也看不到） |
| 数据表 | 不建（见 §3 迁移分层） |
| 菜单/权限 | 不 seed，不出现在菜单树 |
| 前端 | 无入口；直接敲 URL 不 500，走 404/access-denied |
| 依赖 | 其它模块不得直接 import 它；跨模块联动只能走「非强制查询」`is_module_enabled_for_tenant` |

候选成员：support 工单 / media 媒体存储与图片转存 / devices 设备令牌 /
credentials 凭据保险库。

**已裁决（2026-08-08 调研）**：

| 能力 | 结论 | 依据 |
|---|---|---|
| support 工单核心 | 可选包（默认关）；框架就绪前先以**样例**形式进 base | 两套实现同源（下游电商分支 移植自 logistics），骨架通用；但当前不满足「整目录拷走即可跑」 |
| support × CMS 公开留言桥接 | **独立**的集成包，不并入 support 核心 | CMS 与 support 必须能各自独立安装；蜜罐/限流属于 CMS 公开路由，不属于 support |
| plans / quota 套餐配额 | **不回流**，只作设计与实现参考 | entitlement 闸门 P0 未做；指标 `collect_count/product_count/storage_bytes` 与 adapter 操作名全部 下游电商分支 硬编码；无购买/续费/对账闭环 |
| billing/price_list | 不回流 | 只是 下游电商分支 积分动作价（publish/monitor） |
| pricing 定价规则 | 不回流 | 商品售价规则（汇率/加价/运费/平台抽成），电商垂直 |

**support 作为可选包必须先修掉的耦合**（回流前的硬前提）：

1. 默认值当前是 `defaultEnabled=true`（前后端都是），测试甚至断言默认开 → 必须默认关。
2. `api/v1/__init__.py`、`backend/alembic/env.py`、前端 `(app)/layout.tsx` 都是**静态 import** → 必须改动态注册。
3. 业务词汇 `collect/export/publish/quota` 与 `create_public_contact_ticket()` 里写死的
   `related_type="public_contact"` → 移出核心，由调用方/桥接包传入。
4. `SupportService` 直接查 `Menu/Role/RoleMenu` 找客服接收人、直接依赖 `notifications.dispatcher`
   → 改为注入 notifier + audience resolver 端口。
5. 迁移把**建表 + seed 菜单 + 开模块开关**混在一个 upgrade 里 → 拆开；schema 迁移不许开开关。
6. 匿名建单用 `requester_user_id=0` 哨兵 → 需要正式 contract（或改 nullable + requester_type）。
7. 附件字段是任意 `list[dict]` → 数量/大小/MIME/URL scheme/归属校验。
8. 公开留言限流是 `get_json` 后 `set_json` 非原子、key 不含 tenant、Redis 挂了退化为进程内存。
9. **业务页面反向 import support 组件**（下游电商分支 的 sources/catalog/transform/publish 四个页面）
   → 真不安装就构建失败；必须改成「业务页声明失败上下文，support 包通过 extension slot 渲染入口」。

### L3 样例模块 sample（参考实现，不进生产）

一个最小但完整的模块，用来教「一个业务模块该怎么落地」：模型 / 迁移 / seed / 菜单 /
权限码 / 开关 / 后端路由 / 前端页 / 测试，一样不少，配套 `backend/scripts/new_module.py` 脚手架。

### 生命周期轴（与分层轴正交，取自 nextjs-plugins 的模块登记册）

分层回答「这东西属于哪一层」，生命周期回答「承诺什么、要不要继续投入」。两轴不能互推。

| 生命周期 | 含义 | 约束 |
|---|---|---|
| GA | 有生产用户，承诺维护 | 改动走完整验收 |
| Incubating | 孵化中，可用但不承诺 | 必须有活跃 backlog |
| Frozen | 代码保留、默认关、迁移保持可用 | 重启先补立项文档 |
| Retired | 有移除计划 | 移除迁移/菜单/权限码需单独方案 |

来源：`nextjs-plugins:devdocs/reference/MODULE_REGISTRY.md`（2026-07-17 已在 plugins 落地，
配套 `plugins_20260717_frozen_module_defaults` 迁移：新租户默认关、存量租户写显式 true 保持现状）。
基座采纳这套登记册格式，并与本文的四层合并成一张表。

## 2. 内核卫生回流清单（已证据核实，与分层无关）

下游分支各自修过、但从未回到 base 的**纯内核**改进：

| 项 | 来源 | 价值 |
|---|---|---|
| `TooManyRequestsError`（429） | 下游电商分支 `core/exceptions.py` | 限流场景内核缺这个异常 |
| `is_module_enabled_for_tenant()`（只查不抛） | 下游电商分支 `core/module_guards.py` | 可选包联动必需：对方关了要跳过而不是 403 |
| `send_notification(deliver_to_channels=False)` | 下游电商分支 `core/notification.py` | 只落站内不外发 |
| `PaginatedResponse` 泛型 | nextjs-plugins `core/schemas.py` | 分页响应统一 |
| `core/http_cache.py` | nextjs-plugins | 公开页/分享信息的缓存头收口 |
| DB 连接池参数化（pool_size/overflow/timeout/recycle 走 Settings） | nextjs-plugins `infrastructure/database/session.py` | 现在是硬编码 10/20 |
| `init_db()` 检测到 `alembic_version` 有记录就跳过 `create_all` | nextjs-plugins 同文件 | 防 AUTO_INIT_DB 覆盖已迁移库 |
| `CreditService._get_account_for_update` 行锁加 `populate_existing=True`（并发扣费丢失更新）+ 并发回归测试；`OpenAIClient._normalize_usage` 保留 cached/cache_write/reasoning 字段 | nextjs-plugins <commit> / <commit>（2026-08-26 真实并发预扣实测抓到）；回流分支 backflow/credits-kernel-20260827 | 纯内核 bug：同一会话已加载账户对象时 FOR UPDATE 返回锁前快照，三笔并发只扣一笔；计费细分的事实来源 |
| notifications 域整体同步：入站 HMAC 验签默认 fail-closed、渠道限定到绑定它的网关账号（跨租户冒充）、网关跨账号隔离三件套、企业微信渠道与会话续期提醒；迁移 `base_20260820_gateway_auth` / `base_20260821_channel_gateway_owner` / `base_20260827_wecom_channel_unique_index`；`core/task_queue.py` 随 `scheduler_job_lock` 一并回流（L0 其余能力在此文件内，worker 接入另记） | nextjs-plugins <commit> / <commit> / <commit> / <commit>（2026-08-20~22）；回流分支 backflow/kernel-20260827 | 安全缺陷；回流时做了双方言改写（`dialect_insert` / `json_merge_patch` / `json_array_contains` / 写锁升级），网关任务仍受 `MESSAGE_GATEWAY_TASKS_ENABLED` 门控（plugins 侧无条件注册的 hunk 未搬） |
| 模块安装判定三态：`module_code_is_present()` 缺一部分抛 `ModuleInstallationBroken`（部署残缺不再静默当成卸载）；前缀映射改用未过滤目录 `_PREFIX_CATALOG`，硬卸载后的子域路由仍解析到模块、门禁 fail-closed；GOV-23 `api_contract.py` API 契约比对；Redis 键实例命名空间；openai_client 完成事件/严格前缀缓存/搜索引用三项修复 | nextjs-plugins <commit> / <commit> / <commit> / <commit> / <commit> / <commit> / <commit>；回流分支 backflow/kernel-20260827 | 内核缺陷与门禁语义；GOV-22 真删探针与 15 模块清单强绑定未回流 |
| 统一积分策略内核：`credits/usage.py`（UsageEvent/收集器/恰好一次）、`pricing.py` + `price_service.py`（版本化 pricebook + 租户覆盖表 `credit_price_items`）、`settlement.py`（预留/完成/退款幂等）、`pricing_mode.py` + `billing.py`（legacy/shadow/unified 租户模式分流）、费率 API 与 `credits:pricing:update` 权限、assistant 共享客户端计量与 `@collects_usage`；迁移 `base_20260827_credit_price_items` / `credits_pricing_mode_perm` / `credit_price_cache_write`；文档 CREDITS_BILLING_GUIDE / PITFALLS / DEV_CHECKLIST §14 | nextjs-plugins <commit> … <commit>（2026-08-25~27，13 个提交）；回流分支 backflow/kernel-20260827 | 通用能力；base 保留 `CreditRule` 模型避免 autogenerate 判 drop；灰度对账 SQL 为 PG 专有（SQLite 档返回业务错误）；前端"计费模式与费率"面板依赖 plugins 的 i18n/组件结构，未随后端回流（API 已可用） |
| 第二批（B 项与前端）：X-API-Key 机器凭证 + 公开分享访客解析；内核组合层扩展点 `core/composition.py`（业务分支 `app/plugins/app_wiring` 接生命周期/路由/调度/异常翻译）；运行时权限审计脚本清单化；SQLite 轻量档统一禁用机制 `core/dialect_features.py`（功能级 `require_postgresql` + 模块级 `requires_postgresql` + catalog 下发 `databaseDialect`/`unavailableFeatures`）；前端"计费模式与费率"页签（SQLite 隐藏对账）与个人"消息 Channel"页（菜单 seed/system_menus/迁移三写） | nextjs-plugins <commit> / <commit> / <commit> / <commit> / <commit> / <commit> / <commit> / <commit>；回流分支 backflow/kernel-20260827 | B1（assistant 原生工具微循环）留待 plugins 灰度稳定；GOV-22 真删探针、L0 并发测试仍绑业务清单未回流 |
| 来自 下游日报分支（纯 SQLite 开发）：能力包编排器 `scripts/capability.py` 双方言（inspector 代替 to_regclass、按方言的迁移互斥锁 PG advisory / SQLite flock、SQLite 新库 create_all+stamp 引导）、脚手架与样例包迁移 SQLite 化、能力包可声明 `label_key/description_key`；用户 CSV 批量导入（预演→执行、逐行独立、可重复；`/system/user-import` 页 + 菜单三写）；LLM 出站脱敏引擎提升为内核 `app/core/redaction/`（allowlist、假名化、独立 L4 守卫、红队语料）+ 设计文档 | 下游日报分支 <commit> / <commit> / <commit> / <commit> / <commit>（2026-08-27） | PG 路径逐行不变（advisory lock + upgrade），SQLite 只走带方言判断的分支；daily_reports 能力包本体（L2 业务）不回流，其 `redaction_policy_store` 留在包内并改指向 `app.core.redaction` |
| 租户级 AI 出站脱敏策略：`app/domain/ai_redaction`（按 scope 版本化）、`RedactionPolicy.level` 四档预设 + custom、租户设置 AI 页签卡片与 `/tenant/profile/settings/ai-redaction` API；迁移 `base_20260828_tenant_redaction_policies` | 由 codex 在 base 上实现（2026-08-28），源于 下游日报分支 的模块级策略表 | 日报分支改为委托 base 存储；模块只留自身开关 |

**反面教材（明确不回流）**：`teams.max_note_workspaces/max_note_storage_bytes`（笔记配额列长在
内核 Team 模型上）、`security_headers.py` 里的业务分享路径、`scheduler.py` 里直接
`from app.domain.jobs...` 注册业务任务、`auth/config_security.py` 里硬编码 logistics
密钥字段名、`notifications/dispatcher.py` 的 `NotificationEventType` 写死
support/quota/monitor/publish/export 事件 —— 这五处都是「内核认识业务」，回流时一律改注册式。

## 3. 明确不回流

- 业务域：下游电商分支（采集/上架/监控/转换）、shopify 主题、radio/music、ppt_master/aippt、
  training/okr/crm/harness、logistics 运单。
- 业务专有的通用件变体：fx 汇率、pricing 定价规则（都绑定电商语义）。
- 内核里的业务泄漏：`teams` 上的 notes 配额列、`security_headers` 里的业务分享路径、
  `scheduler.py` 里直接 import 业务 runner 的注册块（改为注册钩子，见 §4）。

## 4. 迁移分层（已定稿）

矛盾点：本仓硬规则要求 **单 alembic head**、升级路径靠迁移补齐老租户；而可选包要求
**不装就不建表**。这两件事在字面上不可兼得，所以把硬规则**精确化**：

> core 必须恰好一个 head；每个**已安装**的 pack 也必须恰好一个 head；同一条迁移链禁止多 head。

四种方案的取舍：

| 方案 | 单 head | 未装不建表 | 结论 |
|---|---|---|---|
| 单链全建表（空表） | 是 | 否 | 只用于 kernel / base capability |
| alembic branch label + 多 head | 否 | 理论可行 | **否决**：`upgrade heads` 会把所有可见分支都升级，反而破坏可选性；而加 merge revision 要求所有父 revision 存在＝要求所有 pack 都装 |
| **包内独立迁移链 + 独立 version_table** | 每条链是 | 是 | **采纳** |
| install 命令自己建表 | 伪装的是 | 是 | 否决：手写 DDL 没有稳定 revision、审计、downgrade 与失败恢复 |

**绝对不要写"条件迁移"**（core revision 里按环境变量跳过 DDL）：Alembic 仍会把该 revision
标记为已执行，以后再安装 pack 时不会重跑，schema 与迁移永久错位。

编排命令（生产权威）：`python -m scripts.capability db upgrade`
—— advisory lock → core upgrade → 按依赖拓扑逐个 pack upgrade → 校验每条链单 head →
记录已安装版本与 manifest 摘要 → 跑 tenant provision/reconcile。
裸 `alembic upgrade head` 降级为"core-only 的开发命令"，文档里所有把它当完整部署的说法都要改。

**卸载语义**：取消选择只做"不挂路由 / 不加载 worker / 不生成前端入口 / 不再 seed"，
**默认保留表与数据**。真正删表要显式跑 `python scripts/capability.py db purge <code> --purge`。
部署配置变更绝不允许自动 drop table。

## 5. 装配契约（声明驱动）

一个模块只声明一次，其余全部由声明推导。声明分两处，各管一件事：

**目录声明**（`app/core/feature_switches.py` 的 `ModuleCatalogItem`，或能力包自己的
`CapabilityDefinition`）——这个模块**对外长什么样**：

```
ModuleCatalogItem(
    code=...,                 # 唯一标识
    layer="pack",             # kernel | capability | pack | sample
    route_prefixes=...,       # 前端路由 → 菜单/route_exclude 判定
    api_prefixes=...,         # 后端 API → deps.py 统一门禁
    permission_prefixes=...,  # 权限码前缀 → 权限归属判定
    default_enabled=False,
)
```

**物理边界声明**（`app/core/module_manifest.py` 的 `BuiltinModuleManifest`）——
这个模块的**代码、模型、表分别在哪**：

```
BuiltinModuleManifest(
    code="speech",
    code_paths=("app/domain/speech", "app/api/v1/endpoints/speech.py"),
    model_modules=("app.domain.speech.models", ...),
    table_prefixes=("speech_",),
)
```

物理边界只对**内置能力**需要手写。可选能力包（`app/capabilities/<code>/`）
天然满足：一个目录装着全部代码、模型和独立迁移链，删目录就整条消失。
内置能力散落在 `app/domain/` 与 `app/api/v1/endpoints/` 里，所以要显式登记。
漏登记由 **GOV-18** 拦（`governance_tools/module_manifest_check.py`）。

### 5.1 三种「未安装」——权威定义（2026-08-09）

这是本仓关于动态加载的**唯一权威表**。任何"不装就零占用"的说法都必须
指明是哪一级，否则会有人拿"租户关了怎么表还在"来返工。

| | 租户级停用 | 部署级不装 | 硬卸载 |
|---|---|---|---|
| **怎么做** | 租户 `feature_switches` 关掉 | `AOJ_ENABLED_MODULES` 不列它 | 删掉 `code_paths` 里的目录 |
| **代码是否 import** | 加载 | **不加载** | 不存在 |
| **路由是否挂载** | 挂载（API 403） | **不挂载（404）** | 不挂载（404） |
| **菜单** | 隐藏 | 不下发 | 不下发 |
| **模块目录里的开关项** | 显示（关闭态） | **不显示** | 不显示 |
| **数据表** | 在 | 在 | 能力包：随包消失；内置能力：**残留** |
| **前端产物** | 仍编译 | 仍编译 | 页面目录一并删则不编译 |
| **典型场景** | 多租户里 A 要 B 不要 | 这个部署根本不做这块业务 | 分支裁剪，从此不再维护 |

三级是**逐级加强**的：部署级不装隐含租户级不可用，硬卸载隐含部署级不装。

### 5.1.1 残留表：内置能力**明确不追求零残留**（2026-08-09 决策）

内置能力（assistant / speech / cms）的迁移在核心 alembic 链上，摘掉会撕裂链，
所以硬卸载后表会留下。**这是定下来的取舍，不是欠账**：

> 内置能力的目标只有一条——**不冗余加载代码**。表留着没关系。

理由：残留表是静态数据，不占进程内存、不影响启动时间、不参与请求路径；
而把内置能力拆成独立迁移链要动线上库，风险远大于收益。
所以**不要**把"内置能力转能力包"当技术债去推——除非某个模块本来就该是能力包
（判据见 §1），那是分层问题，不是残留表问题。

配套保护已经做了：`alembic/env.py` 的 `include_object` 把残留表和能力包的
`cap_*` 表排除出 autogenerate 比对，**否则卸载后第一次 autogenerate 就会生成
DROP TABLE，把数据删掉**。

真要清表：能力包走 `python -m scripts.capability db purge`（它有独立链，能干净摘除），
内置能力走人工 SQL，两者都**先备份**。

### 5.2 现状实测（2026-08-09 复测）

| 关掉模块时 | 现状 | 依据 |
|---|---|---|
| 后端 router 不注册 | ✅ `register_capability_router` / `register_builtin_capability_router` 条件挂载，未装不 import | `tests/test_api_router_assembly.py` |
| 已认证 API 拒绝 | ✅ `deps.py` 按 api_prefixes 统一拦截 | — |
| 公开 / optional-auth API 拒绝 | ✅ 未装即未挂载，路径根本不存在（404 而非 403） | 同上 |
| 表不创建 | 能力包 ✅（独立迁移链）；内置能力**按设计留表**（见 §5.1.1，不是缺口） | — |
| 菜单不写库 | ✅ 三写共用 `menus/reconciler.py`，按安装状态过滤 | `flows/MENUS_PERMS_DUALWRITE.md` |
| 前端页面不编译 | ❌ 页面在 App Router 下，Next 一律编译（只是产物变大，不是漏洞） | — |
| 前端手敲 URL 进不去 | ✅ `ModuleRouteGuard` 按声明目录解析路径，未装/未启用不渲染页面 | `frontend/tests/module-routing.test.mjs` |
| 未知模块 | ✅ **fail-closed**：`is_module_installed()` 对目录里没有的 code 返回 False | `tests/test_feature_switches.py` |
| 删掉模块代码后应用能否启动 | ✅ 模型按代码存在与否注册，`app/domain/__init__.py` 与 `alembic/env.py` 都不再写死 | `tests/test_hard_uninstall.py` |

改造前这张表几乎全是 ❌（顶层全量 import + 无条件挂载 + 未知模块 fail-open），
逐项的历史快照留档在 `reference/BASE_CHANGELOG_2026_08.md`。

### 5.3 自检命令

```bash
# 部署级不装：模块不加载、路由不挂载
AOJ_ENABLED_MODULES=none python -c "import app.api.v1 as v1; print(len(v1.api_router.routes))"

# 硬卸载：删目录后应用仍能启动、目录里不再有该模块
pytest tests/test_hard_uninstall.py -q

# 声明漂移（GOV-18 等 10 条门禁）
python scripts/check_governance.py
```

### 5.4 待补清单

**前端产物按已安装 pack 裁剪**：Next 的 App Router 会编译 `(app)` 下所有页面，
未安装模块的页面代码仍在产物里。要真正裁掉得把模块页面移出 `app/` 目录、
构建期按已装清单生成 route shim——那是对前端目录结构的改动，
影响面比收益大（多出来的只是产物体积，不是可访问性漏洞：
`ModuleRouteGuard` 已经挡住手敲 URL，后端未装的模块连路由都不挂载）。
**要动之前先确认这笔投入值得**，不要顺手改。

已清账：CMS 页面 i18n（2026-08-09）、模块路由守卫（2026-08-09）。

**已从待补清单移除**："内置能力转成独立迁移链的能力包" —— 见 §5.1.1，
内置能力只要求不冗余加载代码，残留表是接受的。

## 6. 2026-08 这一轮的交付范围

全套设计是个多轮工程。本轮只做能闭环验证的部分，其余明确列为延后，不做"半截壳层"。

**本轮做**：

1. 内核卫生回流（✅ 已提交 `<commit>`）
2. 装配机制：manifest 单一真源、未知模块 fail-closed、后端条件挂载、公开端点门禁、
   前端 catalog 由后端驱动
3. CMS 底座化第一步：`PUBLIC_SITE_ROUTING_MODE` 三态（off/domain/path）取代
   RESERVED_SEGMENTS 猜测法；host resolver 收紧（未知 Host 返 404，不再回落"第一个活跃租户"）
4. 治理自检第一批（静态门禁，不依赖数据库）：单 head、禁 os.environ、
   `updated_at` nullable、软删除 partial unique、菜单 path ↔ Next 页面、scanner 覆盖度元测试
5. seed 真 bug 修复：CMS seed 哨兵改 reconciler；新租户创建补 `role_menus`
6. 样例模块 `sample_items` + `backend/scripts/new_module.py` 脚手架
7. SMTP：typed config + inherit/override/disabled 三态 + 明文封堵（P0）

**本轮不做（已记录理由）**：

- 租户群通道 / 中立 dispatcher 回流（依赖 SMTP 先落地）
- support 真正 pack 化（先要装配框架跑通，且 support 本身有 13 项耦合待修）
- pack 的 wheel / npm 分发与前端 route shim 生成（部署用的是共享 BT python env、
  前端也没有 pnpm workspace；引入打包会把风险从基座代码扩散到部署管线，收益 90% 不需要它）
- 需要真实 PostgreSQL 的治理测试（seed 幂等对账、role_menus 祖先闭包、
  flush 后属性过期的运行时探针）
- plans/billing/pricing/fx —— 明确不回流
