# nextjs-base 常见问题与注意事项（复盘）

> 目的：沉淀在 nextjs-base 联调/修复中容易反复踩坑的点，作为后续开发的提醒与检查清单。

## 1. 多租户与权限边界（最容易混淆）

本系统是**多租户**系统：绝大多数业务数据都应该以 `tenant_id` 隔离。

### 1.1 角色层级（建议用“能力边界”理解，而不是 UI 菜单）

- **系统级管理员（System Admin）**：`User.is_superuser=True`（通常账号为 `admin`）
  - 能跨租户执行系统级操作
  - 跨租户时需要显式指定目标租户（见 `backend/app/api/deps.py` 的 `TenantContext`）
- **租户管理员（Tenant Admin）**：在**某个租户**内拥有管理员角色（例如 role code=`admin`），或系统管理员在“当前租户上下文”下执行租户内操作
  - 默认应限定在租户内进行写操作（见 `backend/app/api/deps.py` 的 `get_current_tenant_admin`）
- **普通用户（Tenant User）**：只能访问自己租户的资源（并受数据权限进一步约束）

### 1.2 “admin 既是系统管理员，也是默认租户管理员”带来的坑

系统存在**默认租户**，`admin` 往往同时具备：
- **全局能力**（superuser）
- **默认租户内的租户管理员能力**

这会导致前端/产品层面容易把“系统级能力”和“租户内能力”混在同一个入口里。建议在菜单与文案上强制区分：
- “全站/跨租户”能力：仅 System Admin 可见
- “当前租户”能力：Tenant Admin 可见（System Admin 在当前租户下也可用）

### 1.3 跨租户上下文的约定（后端）

- 超级管理员可通过 `X-Tenant-Id` 请求头（或 `tenant_id` query）指定目标租户（`TenantContext.tenant_id`）
- 非超级管理员始终使用自身 `tenant_id`

开发自检：
- API 里尽量统一注入 `tenant_ctx: TenantCtx`（`backend/app/api/deps.py`），并全程使用 `tenant_ctx.tenant_id` 作为实际过滤条件
- 所有跨租户写操作要明确标注（日志里打 `tenant_ctx.is_cross_tenant`），并限制在 superuser 路径下

## 2. 通知与积分：入口与权限必须“按边界设计”

这两个模块属于脚手架“公共底座能力”，但它们的**能力边界不同**：

### 2.1 通知（Notifications）

通知明确区分两条链路：
- **租户内批量通知**：`POST /api/v1/notifications/bulk`
  - Tenant Admin（或 superuser）+ 权限 `notifications:send`
  - 目标用户集：`user_ids` + `team_ids`（可选递归子团队）
- **全站广播通知**：`POST /api/v1/notifications/broadcast`
  - **仅 superuser**
  - 覆盖所有租户下的启用用户（见 `backend/app/api/v1/endpoints/notifications.py`）

前端设计建议：
- System Admin 在“用户管理”页提供 **全站通知**入口
- 租户管理员在“用户/团队”页提供 **批量通知**入口
- 不要把“全站通知”做成租户管理员可见的能力（避免误操作）

### 2.2 积分（Credits）

积分只提供**租户内**批量能力：
- **批量积分**：`POST /api/v1/credits/recharge/bulk`
  - 租户隔离 + 权限 `credits:recharge`
  - 目标用户集：`user_ids` + `team_ids`（可选递归子团队）

重要原则：
- System Admin **不需要**“全站批量积分”入口（跨租户发放积分通常会带来合规/计费/审计风险）
- System Admin 仅在“当前租户上下文”下（显式切换租户）进行租户内批量积分即可

### 2.3 操作日志（Operation Logs）

操作日志是脚手架的公共审计底座，但要注意“记录覆盖面”和“敏感信息”：

- 查询接口是**租户隔离**的：`GET /api/v1/operation-logs`（权限 `operation_logs:read`）
- 写入主要由中间件自动记录（见 `backend/app/domain/operation_logs/middleware.py`）：
  - 默认记录 `PUT/PATCH/DELETE`
  - `POST` 只有命中白名单/后缀规则才会记录（例如 `/bulk`、`/broadcast`、`/recharge` 等）
- 日志落库前会做敏感字段脱敏（见 `backend/app/domain/operation_logs/recorder.py`），但仍应避免把完整 token/密钥/大体积响应写入 extra

开发自检：
- 新增“关键写操作”接口后，确认它会被 `_should_log_request` 捕获；否则需要补规则或在业务处显式调用 `log_operation`
- 跨租户操作时（superuser），日志应落在“目标租户”下，便于租户内审计与排错

## 3. dept → team：不要再做兼容分支

历史上存在 `dept/deptIds` 的命名与接口字段。nextjs-base 已完成重构：
- 统一使用 **team**（团队）概念
- API 请求字段统一使用 `teamIds`（后端通常为 `team_ids`，由 schema alias 映射）

开发自检：
- 不要在前后端继续保留 `dept/deptIds` 的兼容逻辑（避免长期双栈拖累）
- 新增/修改接口时，检查：表字段、schema、前端参数、列表筛选条件是否都已使用 team

## 4. 默认团队：让“批量能力”覆盖全部用户

如果租户允许“不划分团队”，会出现“无团队用户无法被团队批量操作覆盖”的问题。为让批量通知/批量积分成为可靠底座：
- 每个租户应存在一个 **默认团队**（承载未分组用户）
- 用户创建/导入时，如未指定团队，应自动归入默认团队

后端已提供默认团队的兜底能力（幂等）：
- `TeamService.ensure_default_team`：`backend/app/domain/teams/service.py`

补充说明：
- 当前用户与团队是**多对多**关系（允许用户在多个团队中）
- 后续如支持“迁移团队/新增团队”，依然可通过维护用户-团队关联实现，不需要引入 dept 兼容层

## 5. 演示模式（DemoMode）会拦截写操作：默认应关闭

演示模式用于演示环境“只读浏览”，但会导致联调/配置无法进行。

- 开关：环境变量 `NEXT_PUBLIC_DEMO_MODE`（读取处 `frontend/src/lib/demo.ts`）
- 拦截逻辑：`frontend/src/lib/api.ts` 的 `apiFetch`（非白名单写请求抛 `DEMO_MODE_READONLY`）
- 注：旧文档写的 platform-config.json 与 utils/http 是 Vue 时代路径，本仓没有

建议约定：
- nextjs-base 默认 `DemoMode=false`（便于联调）
- 如需演示环境开启，只在部署环境配置中开启，不要反向改回“默认开启”

## 6. CORS 与多端口联调：优先用前端代理规避

后端默认 CORS 白名单较窄（见 `backend/app/core/config.py` 的 `CORS_ORIGINS`）。

建议：
- 前端 dev server 统一走同源 `/api` 代理到后端（避免频繁改后端 CORS）
- 多分支并行开发时，前后端端口统一使用 `30000+` 并登记（避免互相影响）

## 7. 分支切换后的迁移一致性：看到列缺失先查 Alembic

典型现象：
- 登录/鉴权阶段报 `UndefinedColumnError`（例如 `roles.created_by does not exist`）

排查顺序：
1. 确认当前分支与数据库迁移版本一致
2. 执行 Alembic 升级到 head（必要时重新初始化本地库）
3. 通过日志定位触发点，再决定补迁移还是修代码

## 8. 前后端接口对齐检查清单（提交流水线前做一次）

- 权限码是否一致：后端 `PermissionChecker([...])`、菜单 `menus.perms`、前端 `hasAnyPermission(session, [...])` 是否同一套
- 字段命名是否一致：`teamIds`/`userIds`/分页字段 `currentPage/pageSize`（有无 alias 漏配）
- TenantCtx 是否贯穿：所有查询与写入是否都以 `tenant_ctx.tenant_id` 限定
- 操作日志/审计信息：关键写操作是否记录 `user_id/tenant_id/obj_id`，便于排错与追溯

## 9. 菜单初始化时序：Alembic 数据迁移 vs seed_data.py

### 9.1 问题现象

- 新部署环境登录成功但**菜单为空**（`GET /api/v1/menus/routes` 返回空数组）
- 或新增模块后，旧租户看不到新菜单，新租户却能看到（或反之）

### 9.2 根本原因

菜单/权限是一类“部署后数据库数据”，它既涉及：

- **全新环境 / 新租户初始化**：依赖 `seed_data.py`（或租户创建钩子）生成菜单
- **已有环境升级**：依赖 Alembic 的**数据迁移**补齐已有租户的菜单/role_menus

如果只做其中一侧，就会出现“某类环境缺菜单”的不一致。

此外要特别注意执行时序：

```
新装常见顺序（示意）：
1) alembic upgrade head          # core 链的结构迁移 +（可能包含数据迁移）
2) python -m scripts.seed_data   # 创建租户/角色/菜单/赋权
```

> **裸 `alembic upgrade head` 只升 core 链**。装了可选能力包的部署要用
> `python scripts/capability.py db upgrade`：每个已安装的包有自己的迁移链和
> 独立 version table，core 命令碰不到它们，包的表会建不出来。
> 部署脚本已做能力探测（有 `backend/scripts/capability.py` 就用它）。

因此：**在新装环境里，迁移执行时可能还没有任何租户数据**，数据迁移脚本必须允许安全 no-op。

### 9.3 推荐做法（必须“三写”：seed / 迁移 / 建租户，共用同一个 reconciler）

1) **seed_data.py / 租户初始化钩子**：负责“新租户一定有菜单”
- 父菜单 → 子菜单 → 按钮 perms → role_menus 赋权，按依赖顺序创建
- 保证幂等：重复执行不报错、不重复插入

2) **Alembic 数据迁移**：负责“老租户升级补齐菜单”
- 遍历所有租户（不要只假设 `default` 存在）
- 插入菜单时使用 `ON CONFLICT DO NOTHING` 或先查后插（避免重复）
- 插入 `role_menus` 前确认 role 与 menu 属于同一租户

> 迁移职责仍然是“升级已有环境”；不要把“新装初始化”只押在迁移里。

### 9.4 开发自检

- [ ] 新增模块菜单/权限时，是否同时更新了：
  - [ ] `seed_data.py`（新装/新租户）
  - [ ] Alembic 数据迁移（已有租户）
- [ ] 菜单插入是否按“父→子→按钮→赋权”顺序？
- [ ] `role_menus` 插入是否幂等且 tenant 一致？

### 9.5 手动修复步骤（已部署环境）

如果已部署环境出现菜单缺失，优先按如下方式排查：

1. 查数据库：`SELECT COUNT(*) FROM menus;`
2. 查目标路径：`SELECT * FROM menus WHERE path LIKE '/<module>%' ORDER BY id;`
3. 若确实缺失：
   - 运行模块增量 seed（推荐提供 `seed_<module>.py` 幂等脚本）
   - 或补一个 Alembic 数据迁移，把新菜单补齐到所有租户

## 10. 模块菜单结构与“模块设置”入口规范

### 10.1 菜单层级（约定）

```
Level 1: 目录（menu_type=0）
  └── Level 2: 页面（menu_type=1）
        └── Level 3: 按钮/权限（menu_type=2, perms=resource:action）
```

### 10.2 模块设置入口（必须放系统配置）

当模块存在“租户级配置”（开关、扣费策略、AI BaseURL/APIKey/提示词等）时：

- 入口必须放在：`/system/<module>-settings`
- 权限只给租户管理员：默认 `admin` 角色
- 配置数据必须是租户级（带 `tenant_id` 或落 `tenants.config.<namespace>`）

> 该规范来自多次下游扩展修订经验：不要把“模块设置”混在业务菜单里，也不要做成全局配置。

### 10.3 示例（通用结构参考）

```
业务模块 (path=/module, icon=ep:menu) - 租户内业务模块
├── 工作台 (path=/module/dashboard, perms=module:read)
├── 列表页 (path=/module/items, perms=module:read)
│   ├── 查看 (perms=module:read)
│   ├── 新增 (perms=module:create)
│   ├── 编辑 (perms=module:update)
│   └── 删除 (perms=module:delete)
└── 报表页 (path=/module/reports, perms=module:read)

系统管理 (path=/system) - 仅租户管理员可见
└── 模块设置 (path=/system/module-settings, perms=module:settings)
    └── 租户级模块配置
```
