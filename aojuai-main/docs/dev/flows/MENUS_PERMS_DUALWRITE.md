# 菜单/权限新增：三条链路（seed + 迁移 + 建租户）

> 目标：**新装、老租户升级、运行时新建租户**三种环境拿到的是同一套菜单与权限。
>
> 这是本仓最易漏项的工作。以前这份文档只写了两条链路（seed + 迁移），
> 于是第三条一直是空的：`create_tenant_with_admin()` **不写任何 role_menus**，
> 新建的租户开箱就没有菜单授权，只能靠事后补跑全库 seed 才有。

## 1) 你要新增的类型

- 新页面菜单（`menu_type=1`）
- 新按钮权限（`menu_type=2`，承载 `perms`）
- 新模块设置入口（租户级配置）

关于设置入口：租户级配置入口**目前没有声明式机制**：AI 与语音已折叠进 `/system/tenant-settings?tab=<code>`（legacy path 由 `menus.py` 的 `LEGACY_ROUTE_PATH_ALIASES` 映射），其余仍是独立页。
  新模块二选一即可，**不要照抄旧文档里“必须是 `/system/<module>-settings`”那条**。

## 2) 三条必须同时成立的链路

| 链路 | 场景 | 实现 |
|---|---|---|
| A. seed | 全新部署 / 全库对账 | `scripts/seed_*.py` → 调用菜单 reconciler |
| B. Alembic 数据迁移 | 已存在的租户升级 | 迁移内嵌**不可变快照**，遍历所有租户幂等补齐 |
| C. 运行时建租户 | 新建租户 | 租户创建成功后调用同一个 reconciler |

**三条链路必须共用同一个 reconciler**，不许出现三套写入实现 —— 一旦分叉，
就会出现"新装有、升级没有"或"新租户少一个按钮"这类只在某类环境复现的问题。

### 迁移里绝对不许 import 那份会变的声明

迁移必须内嵌当时的快照。若迁移 import 当前声明，以后声明一改，
历史迁移的行为就跟着变，"某个版本升级上来应该得到什么"就不再可复现。

## 3) seed 必须是对账语义，不是"有就跳过"

踩过的坑：CMS seed 拿**根菜单**当哨兵 —— 根菜单在就整段跳过。
于是子菜单、按钮权限、角色授权被删掉或从来没写进去时，重跑 seed 也修不回来。

正确语义：

- 缺的补齐
- `path` / `meta` 变了就更新
- 重复行合并
- 授权缺失就补
- **父级闭包**：授权了子菜单必须同时保证父菜单被授权，否则前端菜单树断层

判定标准：任意残缺状态（删子菜单 / 删按钮 / 删授权 / 改名 / 造重复）跑一次 seed
之后，都必须收敛到同一个终态；连跑两次第二次不产生任何变更。

## 4) 顺序原则（三条链路都适用）

1. 确保父菜单存在（如 `/system`）
2. 插入页面菜单（`menu_type=1`）
3. 插入按钮 perms（`menu_type=2`）
4. 写 `role_menus`

关于 tenant 语义（**旧文档在这里是错的，以下为核实后的事实**）：

- `role_menus` **有** `tenant_id` 列（见 `backend/alembic/versions/0001_initial_schema.py`
  建表处与 `ix_role_menus_tenant_id` 索引）。
- `role_menus.tenant_id` 跟随 **role 的 tenant**。
- **菜单行是逐租户的**：reconciler 按 `WHERE tenant_id=:tenant_id` 读写，
  每个租户各有一份副本（实测：同一个 `/cms` 在两个租户下是两行）。
- `/menus/routes` 的查询**不按 `menus.tenant_id` 过滤**：普通用户靠
  `role_menus`（租户内）过滤，超管则不过滤。
- ⚠️ 这两条组合起来有个**未核实的边界**：多租户库里超管取 routes 时，
  是否会看到其它租户的同名菜单副本。改这块前先实测，别照着旧文档
  "菜单是系统级单副本、存 tenant_id=1" 的说法动手——那句是错的。

## 5) 验收（机器验证，不接受"人工看过"）

- 新装：`alembic upgrade head` → `python -m scripts.seed_data` → 登录 → 菜单完整
- 升级：**只跑** `alembic upgrade head`（不跑 seed）→ 老租户也出现新菜单
- 新租户：调用建租户接口 → 新租户开箱菜单与授权完整
- 三者的菜单/权限快照必须**相等**
- `python -m scripts.check_seed_state --all-tenants --strict` 返回 0

## 6) 参考

- 新模块完整清单：`flows/NEW_MODULE.md`
- 迁移模板：`docs/dev/templates/ALEMBIC_MIGRATION_TEMPLATE.md`
- 排错：`docs/dev/issues/DEVBASE_PITFALLS.md`
- 分层与装配：`docs/dev/reference/BASE_ARCHITECTURE.md`
