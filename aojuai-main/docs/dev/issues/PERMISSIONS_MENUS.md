# 权限与菜单问题（RBAC / Menus）

> 累计权限码、菜单结构、动态路由、按钮权限相关问题。

## 0. 事实基线（不要照抄旧分支的说法）

- **没有 `permissions` 表**。权限码存在 `menus.perms`，角色授权走 `role_menus`。
- `role_menus` **有** `tenant_id` 列（`0001_initial_schema` 建表处 + `ix_role_menus_tenant_id`）。
- **菜单行是逐租户的**（reconciler 按 `WHERE tenant_id=:tenant_id` 读写，每租户一份副本）；
  `role_menus.tenant_id` 跟随 role 的 tenant。
- `/menus/routes` 的查询**不按 `menus.tenant_id` 过滤**：普通用户靠 `role_menus`（租户内）过滤，
  超管不过滤。
- ✅ **已实测并已修（2026-08-09）**：`/menus/routes` 与 `/menus/tree/options` 原来
  都没有租户过滤，超管拿到全库菜单（建第二个租户后实测 18 个 CMS 标题各 2 份）。
  现已补上租户过滤（**超管同样过滤**），菜单 CRUD 的 list/get/update/delete 也
  一并按租户限定。**租户隔离是比菜单权限更外层的硬边界**，不该由"超管不过滤"
  这条权限规则顺带绕过；超管要看别的租户请切租户。
- 旧文档"菜单是系统级单副本、存 `tenant_id=1`"的说法**是错的**，不要照抄。
- 前端按钮权限用 `hasAnyPermission(session, [...])` / `RequirePermission`，
  **不是** `v-perms`（那是 Vue 时代的写法）。

## 0.1 菜单模型定案：逐租户一份（2026-08-09 定 + 已修）

这个仓库里菜单归属长期是矛盾的：`reconciler` 按 `WHERE tenant_id=:tenant_id` 逐租户
读写，而 `MenuService` 的注释和实现却当它是"系统级单副本"（读不过滤、写死 `tenant_id=1`）。
**已定案：逐租户一份**，理由是 `role_menus` 本来就带 `tenant_id`、能力包按租户 provision，
且多租户差异化（A 租户装物流、B 租户没有）在菜单层面自然可表达。

三处按这个模型改齐了：

| 位置 | 改前 | 改后 |
|---|---|---|
| `/menus/routes`、`/menus/tree/options` | 无租户过滤，超管拿全库 | 按租户过滤（超管同样） |
| `MenuService` list/get/update/delete/create | 全局；create 写死 `tenant_id=1` | 一律要求显式 `tenant_id` |
| `create_tenant_with_admin` | 只 reconcile CMS | 先 reconcile 系统菜单再 CMS |

**顺带修掉的三个真问题**（都是改这轮时才暴露的）：

1. **提权（最重要）**：建租户时手写 `Role(...)` 没填 `data_range` / `data_permissions`，
   吃了模型默认 `DataRangeEnum.ALL`——新租户的普通 `user` 拿到「全部数据」可见范围，
   而 seed 里 user 是 0（仅本人）。这是**数据权限**那一套，和菜单权限是两套独立机制，
   一个都不能靠默认值。角色字段已收口到 `app/core/system_menus.py` 的
   `SYSTEM_ROLE_DEFAULTS` 单一真源。
2. **越权写入**：`assign_menus_to_role` 原注释写着"菜单是系统级、不按租户"并**刻意**
   不过滤，于是 A 租户的角色可以被授予 B 租户的菜单 id。已加 `Menu.tenant_id` 过滤。
3. **升级倒退**：只改运行时不加数据迁移的话，旧租户（当初只拿到 CMS 菜单）在 routes
   补上租户过滤后会直接少一块菜单。已补 `base_20260809_system_menu_backfill`。

**为什么值得记**：这三个里有两个是**注释写反了**导致的——注释说"系统级、不区分租户"，
代码却按租户建行。错误的注释比没有注释更贵，因为它会让下一个人照着错的模型改。
现在语义用**函数签名**钉死（`tenant_id` 关键字参数、无默认值），
`tests/test_system_menu_declaration.py` 看着。

验收：`python -m scripts.check_scenario_parity` 四场景终态一致
（fresh / legacy / bootstrap / oldtenant）。

## 1. 角色授权子菜单但父菜单没授权 → 前端菜单树断层

**现象**：用户有子页面权限，但侧栏里那一整组都不显示。

**根因**：`role_menus` 只授权了子菜单，父目录没授权，前端拼树时断链。

**正确做法**：授权必须**祖先闭包** —— 授权任意子菜单时补齐它到根的所有父级。
这条要由 reconciler 保证，并用递归查询做检查，不能靠人写 seed 时记得。

## 2. `menus.path` 与实际前端路由不一致

**现象**：菜单点进去 404。

**根因**：后端 seed 里写的 path 和 `frontend/src/app/(app)/**/page.tsx` 的实际路径对不上
（复数/单数、少一层目录、route group 没处理）。

**正确做法**：用扫描 `(app)` 目录得到的真实路由集合去校验所有菜单 path；
反向也要扫 —— 新增的后台页面要么被声明为菜单，要么显式标记 internal/hidden。
**这条检查必须自动发现新页面，不能靠维护名单。**

## 3. 权限码声明了但接口没挂 checker

**现象**：菜单按钮受控，接口却裸奔。

**正确做法**：遍历真实的 FastAPI route 及其递归依赖图，
声明的权限码与实际 `PermissionChecker` 必须**双向一致**（声明了必须挂，挂了必须声明）。

## 4. 前端先打接口再吞 403

**现象**：无权限用户打开页面，控制台一片 403。

**正确做法**：options / lookup / config 预加载前先与后端 `PermissionChecker` 对齐，
缺权限直接 skip request，不允许靠 `catch 403` 兜底。

## 5. owner 作用域资源没做归属过滤

**正确做法**：owner 私有资源必须过"本人成功 / 同租户他人 404 / 跨租户 404"三态测试。
非属主返回 **404 而不是 403** —— 403 会泄漏"这个 id 存在"。

## 6. 公开接口没有模块门禁

**现象**：模块开关关掉了，公开接口照样吐内容。

**根因**：模块门禁挂在 `get_current_user` 上，只覆盖已认证请求；
公开路由只依赖 `DBSession`，`get_optional_current_user()` 也没走门禁。

**正确做法**：公开路由要有显式的"解析租户 + 校验模块开关"依赖，
模块关闭时返回 **404**（不是 403 —— 公开接口不该泄漏"这里有个功能但关了"）。
