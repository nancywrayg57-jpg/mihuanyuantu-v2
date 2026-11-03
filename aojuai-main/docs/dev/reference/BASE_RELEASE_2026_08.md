# nextjs-base 2026-08 版：合并后的基座基线

这一版是把散在各业务分支里的**共性能力与共性教训**回流合并之后的 nextjs-base。
新开业务分支从这一版起步，不必再重复踩下面这些坑。

- 范围：`<commit>` → 本版，56 个提交
- 验收：后端 374 tests、12 条静态门禁、四场景终态对账、前端 13 tests + typecheck 全绿
- 起手式看 `docs/dev/flows/NEW_MODULE.md`；架构判据看 `reference/BASE_ARCHITECTURE.md`

## 1. 从哪些分支回流了什么

| 来源 | 回流内容 | 落点 |
|---|---|---|
| nextjs-plugins | 模块注册层、内核边界文档、内核卫生件 | `app/core/capability_registry.py`、`reference/NEXTJS_KERNEL_BOUNDARIES.md` |
| 物流 / clocart | CMS 公开站与内容管理（做成默认关闭的可选能力） | `app/domain/cms/`、`app/api/v1/endpoints/cms*.py` |
| 多分支共用 | SMTP 收口为 typed 配置 + 租户三态 | `app/infrastructure/messaging/smtp_config.py` |
| 多分支共用 | 消息通道 / 网关模型 | `app/domain/notifications/gateway_models.py` |

**明确不回流**：套餐配额、定价、汇率这类业务能力。基座只收底座能力与共性机制。

## 2. 共性教训 → 机器门禁的对应表

回流的重点不是代码，是**把各分支反复踩的坑变成跑得起来的检查**。
下表左边是分支上真实发生过的故障，右边是基座里现在拦它的东西。

| 分支上反复出现的故障 | 基座里现在怎么拦 |
|---|---|
| 菜单 path 指向不存在的页面 | GOV-06 菜单路由可解析 |
| `updated_at` 非空导致迁移失败 | GOV-08 |
| 软删除后业务唯一键冲突、删了不能重建同名 | GOV-09 partial unique index |
| 运行时到处 `os.getenv`，配置行为不一致 | GOV-10 运行时配置必须走 Settings |
| 迁移图分叉出双 head | GOV-13 |
| 内核反过来 import 业务域（层次倒置） | GOV-14 内核纯度 |
| 文档里的路径/命令是编的 | GOV-15 文档引用必须真实存在 |
| 页面用原生弹窗、硬编码中文 | GOV-16（含裸 `confirm(` ） |
| 加模块要改中央 i18n 文件，多分支必冲突 | GOV-17 语言包索引构建期生成 |
| 内置能力删了代码却还在开关列表里 | GOV-18 硬安装边界必须登记 |
| **菜单标题漏翻译/多个空格 → 界面静默显示中文** | **GOV-19（本版新增，见下）** |
| 页面加了但模块没登记路由前缀 → 守卫拦不住 | **GOV-20**（本版新增） |
| seed 重复菜单 / 缺授权 / 父级闭包断层 | `scripts/check_seed_state.py`（只读对账） |
| 三条链路终态不一致（最贵、只在生产暴露） | `scripts/check_scenario_parity.py` 四场景对账 |

**每条检查都注入过真实违规确认能变红**，这是本仓的硬规矩——
之前出现过两次"测试写完全绿但一个 bug 也抓不到"。

### GOV-19 是怎么来的：一个典型样本

物流与 clocart 两条分支各自提交过同一句话：

    fix(i18n): menu key must match DB title verbatim — 'Shopify 接入' has a space

根因在 `translateMenuTitle`：菜单标题来自数据库，翻译键是 `menu.` + 标题**原文**，
查不到就**静默返回中文**。漏一个键、或标题里多一个空格，切到 en/es 就是中文，
没有任何报错，只能靠人点页面发现。

回流做法不是"在基座里也修一次这个标题"，而是把它变成门禁。
加上之后立刻发现**基座自己也有同样的病**：63 个声明标题里 50 个没有翻译键。
这说明这条坑不是某个分支的疏忽，是机制缺陷——正是该回流的那类。

## 3. 本版的架构性变化

### 3.1 模块动态加载：三种「未安装」

`AOJ_ENABLED_MODULES` 从"可见性过滤"升级为真正的**装配机制**。
完整定义见 `reference/BASE_ARCHITECTURE.md` §5.1，开发流程见
`flows/DYNAMIC_MODULE_LOADING.md`（这份是推到 plugins 等分支的流程底本）。

要点：**未安装 = 不 import、不挂路由、不出菜单、开关项都不显示**，
访问返回 404 而不是 403。改造前 `AOJ_ENABLED_MODULES=none` 只是把菜单藏了，
进程里 7 个 CMS 模块照样加载、173 条路由照样注册。

### 3.2 菜单模型定案：逐租户一份

长期矛盾（reconciler 按租户建行，MenuService 却当系统级）已定案为**逐租户**，
并把三处不一致改齐。详见 `issues/PERMISSIONS_MENUS.md` §0.1。

这轮顺带修掉三个真问题，其中一个是**提权**：建租户时手写 `Role(...)` 没填
`data_range` / `data_permissions`，吃了模型默认 `DataRangeEnum.ALL`，
新租户的普通 `user` 拿到「全部数据」可见范围。

> 基座有**两套**权限机制，不要混：
> **菜单/功能权限**（`role_menus` + `menus.perms`）决定"能不能看到、能不能点"；
> **数据权限**（`DataScopeCtx` / `data_range` / `data_permissions`）决定"同一个功能里能看到哪些行"。
> 两者正交。**租户隔离不属于这两套里的任何一套**，它是更外层的硬边界。
> 本版把 routes 查询漏掉的租户过滤补上，就是因为它被误当成了菜单权限的一部分。

### 3.3 前端

模块路由守卫（未安装/未启用手敲 URL 也进不去）、语言包目录自动发现、
Dialog 统一交互规范、CMS 六个页面 i18n 清账。

## 4. 新开业务分支的起手式

```bash
# 1. 从本版拉分支，先跑一遍验收，确认基线是绿的
cd backend
pytest -q
python scripts/check_governance.py
python -m scripts.check_scenario_parity        # 需要本机 PostgreSQL

# 2. 生成模块骨架（自注册、独立迁移链、语言包、前端页面，不改任何中央文件）
python -m scripts.new_module my_module --layer pack \
    --route /my-module --entity MyThing --permissions my_module

# 3. 照 flows/NEW_MODULE.md 往下走，完工前跑机器验收清单
```

## 5. 欠账清账结果（2026-08-09 复核）

上一版列的三项欠账，逐条实测后结论如下。

### 5.1 「前端产物不按已安装模块裁剪」——**实测后判定不做**

先前写的是"多出来的只是产物体积"。实测之后这句话还说轻了：**用户根本不会下载它**。

构建产物的证据（`pnpm build` 输出）：

```
+ First Load JS shared by all             103 kB
├ ƒ /cms/pages                             96 kB         351 kB
├ ƒ /sample-items                        4.63 kB         211 kB
```

Next 按路由做代码分割：96 kB 是 `/cms/pages` **这一条路由自己的** chunk，
不在 103 kB 的共享基线里。没装 CMS 的部署，用户不会访问该路由，
那份 JS 也就永远不会下载。**"不安装就不加载"在前端其实已经成立**，
剩下的只是构建时间和 `.next` 的磁盘占用，都不到用户面前。

评审时考虑过两种改法（生成 route shim / 按安装清单条件化 `pageExtensions`），
两者都要动前端目录结构，且都引入同一个新的失败模式：**清单算错就会静默少一条路由**。
拿"用户零收益"去换"可能静默丢页面"，不划算。**结论：不做，并把理由写死在这里**，
免得以后又被当成技术债推一遍。

真正的风险不在体积，而在**守卫覆盖率**：页面加了但模块没登记路由前缀，
`ModuleRouteGuard` 就拦不住它。这一条已经变成 **GOV-20**（新增）。

### 5.2 「菜单管理页不传 targetTenantId」——**已修**

菜单管理页的列表/新建/编辑/删除四个请求，以及角色页的菜单树请求，
现在都带 `tenantId: targetTenantId`，切租户会重新拉取。
不带的后果是超管切到 B 租户却在用 A 租户的菜单树授权，勾出来的 `menu_id` 根本不属于 B。

### 5.3 「内置能力硬卸载后表残留」——**不是欠账**

这是定下来的取舍，见 `BASE_ARCHITECTURE.md` §5.1.1：
内置能力的目标只有"不冗余加载代码"，表留着不占进程内存、不影响启动、不参与请求路径。

## 6. 相关文档

- `reference/BASE_ARCHITECTURE.md` —— 四层分工、装配契约、三种「未安装」
- `reference/BASE_REVIEW_2026_08.md` —— 整轮复盘（规模、踩坑、明确不做）
- `reference/BASE_CHANGELOG_2026_08.md` —— 行为变化与升级注意
- `flows/DYNAMIC_MODULE_LOADING.md` —— 模块动态加载开发流程
- `flows/MENUS_PERMS_DUALWRITE.md` —— 菜单权限三写
- `issues/` —— 各类别已经踩过的坑
