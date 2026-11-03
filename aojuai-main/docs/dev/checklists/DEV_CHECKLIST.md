# 开发检查清单

> 新开发或复盘时需要重点检查的点

---

## 开发优先级顺序

```
1. 安全性 (Security)     ← 最高优先级
2. 数据完整性 (Data Integrity)
3. 功能正确性 (Functionality)
4. 用户体验 (UX)
5. 性能优化 (Performance)
```

---

## 必读规范文档

| 优先级 | 文档 | 核心内容 |
|:------:|------|---------|
| **P0** | [DATA_PERMISSION_GUIDE.md](../guide_docs/DATA_PERMISSION_GUIDE.md) | DataScopeCtx 使用、数据范围过滤 |
| **P0** | [PERMISSION_CHECKER_GUIDE.md](../guide_docs/PERMISSION_CHECKER_GUIDE.md) | PermissionChecker 使用、功能权限控制 |
| **P1** | [SERVICE_LAYER_GUIDE.md](../guide_docs/SERVICE_LAYER_GUIDE.md) | RepositoryBase 继承、禁止 API 层直接操作数据库 |
| **P1** | [API_ENDPOINT_GUIDE.md](../guide_docs/API_ENDPOINT_GUIDE.md) | API端点规范 |
| **P2** | [DATABASE_TRANSACTION_GUIDE.md](../guide_docs/DATABASE_TRANSACTION_GUIDE.md) | 事务处理 |
| **P0** | [DEPLOYMENT_PROXY_PITFALLS.md](../issues/DEPLOYMENT_PROXY_PITFALLS.md) | Nginx、BT、rewrite、缓存事故规避 |

---

## 检查清单

### 1. 数据权限 (DataScopeCtx)

- [ ] 是否需要按团队过滤数据？
- [ ] 列表接口是否注入了 `DataScopeCtx`？
- [ ] 是否使用 `data_scope.read_team_ids` 过滤查询？
- [ ] 详情/编辑/删除接口是否调用了 `data_scope.check_xxx_permission()`？

**判断标准**: 如果数据属于用户/团队级别（非租户级），需要数据权限控制。

### 2. Service 层规范

- [ ] API 层是否有直接的 `db.execute(select(...))` 调用？
- [ ] 所有数据库操作是否都通过 Service 方法？
- [ ] Service 是否继承 `RepositoryBase[ModelType]`？
- [ ] 是否使用 `flush()` 而非 `commit()`？

**判断标准**: API 层只负责参数校验和调用 Service，不直接操作数据库。

### 3. 功能权限 (PermissionChecker)

- [ ] 需要权限控制的接口是否添加了 `PermissionChecker`？
- [ ] 权限码命名是否符合 `资源:操作` 格式？
- [ ] 是否在 docstring 中说明了所需权限？

### 3.1 前端受保护选项接口

- [ ] 页面初始化是否无条件请求了 `/api/v1/users`、`/api/v1/teams/options`、`/api/v1/agents/app-groups/options` 之类的受保护接口？
- [ ] 前端是否先用 `hasAnyPermission(session, [...])` 对齐后端 `PermissionChecker(...)` 再决定是否加载？
- [ ] 无权限时是否直接跳过请求、清空 options、禁用对应选择器，而不是先打 `403` 再吞异常？
- [ ] 普通用户 smoke test 是否验证了“页面可进入且不会触发越权 options/config 请求”？

### 3.2 生产代理与 rewrite

- [ ] 生产环境是否保持 `NEXT_ENABLE_BACKEND_REWRITES=0`？
- [ ] Nginx 是否将 `/api/v1/*`、`/health`、`/static/*` 直转 FastAPI？
- [ ] 后端直连 location 是否覆盖注入 `x-aoju-proxy-key`，且值与 `AOJ_PROXY_SHARED_SECRET` 一致？
- [ ] 助手 SSE、语音音频、上传下载是否没有经 Next rewrite 转发？
- [ ] BT 随机端口部署后，`ss -ltnp` 真实 Next 端口是否与 Nginx `location /` 一致？
- [ ] 部署后登录 smoke test 是否返回预期 `401` 而不是代理边界导致的 `403`？

### 4. 列表排序（sortBy / sortOrder）

- [ ] 列表接口是否支持 `sortBy`、`sortOrder` 参数？
- [ ] Service 层是否对 `sort_by` 做了白名单校验？
- [ ] 是否有稳定的默认排序（未传排序时默认 `id asc`）？

### 5. 前端响应式布局

> 当前前端是 Next.js App Router + shadcn，**不是** Vue + responsive.scss。
> 下面几条是现行约定，旧文档里的 `class="main"` / `class="search-form"` 已作废。

- [ ] 列表页使用统一的 PageHeader / 列表容器组件（见 `reference/frontend/FRONTEND_BASELINES.md`）？
- [ ] 表格外层有 `overflow-x-auto`（手机端兜底）？
- [ ] 页内跳转用 `next/link`，没有裸 `<a href>`（会被 lint 阻断生产构建）？
- [ ] `pnpm check`（typecheck + **标准 build，含 lint**）通过？
- [ ] 移动端布局正常，没有横向溢出？

### 6. 权限可见性（菜单/按钮）

> 前端权限判定用 `hasAnyPermission(session, [...])` / `RequirePermission`，
> **不是** `v-perms`（Vue 时代写法，已作废）。

- [ ] 侧边栏菜单只展示有权限的页面？
- [ ] 页面按钮统一走 `hasAnyPermission` / `RequirePermission`？
- [ ] 接口权限码与菜单 `perms`、前端判定三处一致？
- [ ] 无权限时**不发请求**（不是发了再 catch 403）？

### 7. 表单编辑回显

- [ ] 编辑弹窗所需字段是否在列表接口返回？
- [ ] 多选组件回显值类型是否一致（id 统一为 number）？

### 8. 密码规则一致性

- [ ] 前端密码规则是否统一复用同一份常量？
- [ ] 后端是否对设置密码类接口做同等校验？

### 9. 危险操作确认

- [ ] 删除/清空等高风险操作是否明确提示"不可恢复"？
- [ ] 自由文本字段是否设置最大长度？

### 10. FastAPI 路由顺序（重要）

- [ ] 固定路径路由（如 `/my`）是否在参数路由（如 `/{id}`）之前？

**常见错误**: `/my` 定义在 `/{log_id}` 之后，导致 `/my` 被当作参数匹配。

### 11. 菜单结构与角色分配

- [ ] seed_data.py 中是否有重复的顶级菜单？
- [ ] 新增菜单后是否同步更新 role_menus 分配？
- [ ] 菜单是否按 IA 分类归位（业务 / 个人 / 租户设置 / 平台）？
  - 个人中心：`/personal/*`（默认 `user` 可见）
  - 租户设置：`/system/<module>-settings`（默认仅 `admin`）
  - 业务模块：`/<module>`（按业务授权）
  - 平台级：仅 `CurrentSuperuser`（避免非 superuser 出现空目录或点进 403）

### 12. 菜单权限同步（Alembic ↔ seed_data.py）

**重要**: 菜单权限要在**三个**地方同步维护（旧版本这里只写了两个，
于是"运行时新建租户"这条链路长期是空的）：

| 场景 | 维护位置 | 说明 |
|------|---------|------|
| **全新部署 / 全库对账** | `seed_data.py` / `seed_<module>.py` | 对账到声明终态，不是"有就跳过" |
| **已有租户升级** | alembic 数据迁移 | 内嵌不可变快照，遍历所有租户幂等补齐 |
| **运行时新建租户** | 建租户后调用同一个 reconciler | `create_tenant_with_admin()` 本身**不写任何菜单授权** |

三条链路共用同一个 reconciler，三者终态必须相等。详见 `flows/MENUS_PERMS_DUALWRITE.md`。

#### 12.1 识别租户级应用

租户级应用的特征：
- 配置存储在 `tenants.config.<namespace>` 或独立的租户配置表
- 存在“模块设置入口”（租户管理员配置）：`/system/<module>-settings`
- 菜单仅对租户管理员可见（`admin` 角色）
- 数据表包含 `tenant_id` 字段

**示例（结构参考）**：
- 模块设置：`/system/<module>-settings`，权限码 `<module>:settings`，仅 `admin`
- AI 设置：`/system/ai-settings`，权限码 `assistant:config`，仅 `admin`

> 说明：本节沉淀的是“如何识别租户级应用 + 如何补齐菜单”的方法论；主分支未必已经包含上述示例页面。

#### 12.2 添加菜单的标准流程

**Step 1: 在 seed_data.py 添加菜单定义**

```python
# backend/scripts/seed_data.py

# 在 system_menus 列表中添加
system_menus = [
    # ... 已有菜单
    ("<module>-settings", "<模块>设置", "/system/<module>-settings",
     "views/system/<module>-settings/index", "ep:setting", 9, "1", "<module>:settings"),
]

# 在 admin_menu_assignments 中添加角色分配
admin_menu_assignments = [
    # ... 已有分配
    "/system/<module>-settings",
]
```

**Step 2: 在 alembic 迁移中为已有租户添加菜单**

```python
# backend/alembic/versions/xxx_add_ai_settings_menu.py

def upgrade() -> None:
    conn = op.get_bind()

    # 获取所有租户
    tenants = conn.execute(
        text("SELECT id FROM tenants WHERE deleted_at IS NULL")
    ).fetchall()

    # 新装环境可能还没有任何租户：允许安全 no-op
    if not tenants:
        return

    for (tenant_id,) in tenants:
        # 1. 获取父菜单
        parent = conn.execute(
            text("SELECT id FROM menus WHERE tenant_id = :tid AND path = '/system'"),
            {"tid": tenant_id}
        ).fetchone()

        if not parent:
            continue

        # 2. 插入菜单
        result = conn.execute(
            text("""
                INSERT INTO menus (tenant_id, title, path, component, parent_id, ...)
                VALUES (:tenant_id, :title, :path, :component, :parent_id, ...)
                RETURNING id
            """),
            {"tenant_id": tenant_id, "title": "AI 配置", ...}
        )
        menu_id = result.scalar()

        # 3. 分配给 admin 角色
        admin_role = conn.execute(
            text("SELECT id FROM roles WHERE tenant_id = :tid AND code = 'admin'"),
            {"tid": tenant_id}
        ).fetchone()

        if admin_role:
            conn.execute(
                text("INSERT INTO role_menus (role_id, menu_id) VALUES (:rid, :mid) ON CONFLICT DO NOTHING"),
                {"rid": admin_role[0], "mid": menu_id}
            )
```

#### 12.3 role_menus 表的 tenant_id 一致性

**更正（已核实）**：`role_menus` **有** `tenant_id` 列 ——
见 `backend/alembic/versions/0001_initial_schema.py` 的建表处与 `ix_role_menus_tenant_id` 索引。
旧文档说"没有"是错的。

正确规则：

- `role_menus.tenant_id` 跟随 **role 的 tenant**
- **菜单行是逐租户的**（reconciler 按 `tenant_id` 读写，每租户一份副本）；
  `/menus/routes` 的查询**不按 `menus.tenant_id` 过滤**，普通用户靠 `role_menus` 过滤、超管不过滤
- ⚠️ 超管在多租户库里是否会看到其它租户的菜单副本**尚未实测**，改这块前先验；
  旧文档"菜单是系统级单副本、存 tenant_id=1"的说法是错的，不要照抄
  也不要再照抄"为每个租户复制一套菜单"的示例

插入 role_menus 时的检查清单：
- [ ] `role_id` 对应的角色属于目标租户
- [ ] `menu_id` 对应的菜单属于同一租户
- [ ] 使用 `ON CONFLICT DO NOTHING` 避免重复插入

#### 12.4 执行顺序与幂等性（避免“新装没菜单/升级没菜单”）

常见执行顺序（示意）：

```
1) alembic upgrade head      # 结构迁移 +（可能包含数据迁移）
2) python -m scripts.seed_data  # 创建租户/角色/菜单/赋权
```

因此：
- Alembic 的数据迁移要能在“无租户”时安全 no-op
- `seed_data.py` 必须保证新装/新租户一定能得到菜单与 role_menus 授权

---

### 13. 静态守门（回流自 nextjs-plugins）

- [ ] pyflakes 未定义名为 0（运行到才炸的 NameError；一条 pyflakes 未定义名扫描测试（plugins 侧为 `tests/test_ppt_master_insert_slide_imports.py`）
- [ ] 真实测试跑批量/长任务时不改后端文件（dev `--reload` 会杀任务）

### 14. 积分计费接入（统一积分策略）

- [ ] 业务入口 `@collects_usage`；直连供应商客户端在解析 usage 处 `record_llm_usage(usage=<原始 dict>)`，不压成两个数
- [ ] 扣费走 `charge_usage_with_pricing_mode`（对话类）或 `reserve/complete/refund_all`（任务类）；幂等键用业务 id
- [ ] 付费人由调用方解析；长任务 worker 自建根收集器；有僵尸回收
- [ ] `with_for_update()` 必配 `populate_existing=True`（并发扣费丢失更新）
- [ ] 新模型/新图片档位在 `default_price_items.json` 有价（流水 `fallbackRate=true` 即漏价）
- 详见 [CREDITS_BILLING_GUIDE](../guide_docs/CREDITS_BILLING_GUIDE.md)、[CREDITS_BILLING_PITFALLS](../issues/CREDITS_BILLING_PITFALLS.md)

### 15. 双方言（PostgreSQL / SQLite 轻量档）

- [ ] 新模型：`PortableJSON` / `PortablePK` / `PortableDateTime`，布尔缺省 `text("true")`，部分索引同时写 `postgresql_where` + `sqlite_where`；不重复声明 `tenant_id` 索引。
- [ ] 查询：不用 `.astext` / `= ANY()` / `::jsonb` / `||`；用 `.as_string()` / `IN` expanding / `json_array_contains` / `json_merge_patch`；`with_for_update` 前 `escalate_to_write_lock()`。
- [ ] raw SQL：seed 与运维脚本走 `ptext()`；表/列存在性用 `table_exists/column_exists`。
- [ ] 确实 PG 专有的功能：登记 `PG_ONLY_FEATURES` + `require_postgresql()`；整模块 PG 专有用 `requires_postgresql=True`。
- [ ] 请求处理期间不开第二个写会话（中间件/审计走 `response.background`）。
- [ ] 验收：`DB_DRIVER=sqlite` 跑一遍套件（conftest 自动建表 + seed）。

## 两套权限系统对照

| 权限类型 | 作用 | 依赖注入 | 检查位置 |
|---------|------|---------|---------|
| **菜单权限** | 能不能用这个功能 | `PermissionChecker` | API层 |
| **数据权限** | 能操作哪些数据 | `DataScopeCtx` | API层+Service层 |

### API 端点示例

```python
@router.get("/items")
async def list_items(
    db: DBSession,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    data_scope: DataScopeCtx,  # ← 必须注入
    _: None = Depends(PermissionChecker(["items:read"])),
):
    team_ids = None if data_scope.has_all_read_access else data_scope.read_team_ids
    items = await service.list_items(tenant_id=tenant_ctx.tenant_id, team_ids=team_ids)
```

---

## 权限体系速查

```
功能权限 (PermissionChecker)
├── 控制: 用户能否访问某个接口
├── 位置: API 层 dependencies
└── 例: user:create, notification:list

数据权限 (DataScopeCtx)
├── 控制: 用户能看到/操作哪些数据
├── 位置: API 层参数注入
├── DataRange: SELF_ONLY, OWN_TEAM, TEAM_AND_BELOW, CUSTOM_TEAMS, ALL
└── 过滤: 通过 read_team_ids/edit_team_ids/delete_team_ids
```

---

## 参考实现

正确实现的模块：
- `backend/app/api/v1/endpoints/users.py`
- `backend/app/api/v1/endpoints/teams.py`
- `backend/app/api/v1/endpoints/roles.py`

开发新模块前，**必须先阅读这些文件的权限实现模式**。

---

**最后更新**: 2026-01-27

---

## 审计增补检查项（2026-06 跨分支回流）

### 安全
- [ ] 模块所有种了 perms 的端点都挂了 `PermissionChecker`（grep 双向核对）
- [ ] 公开分享端点对客户端传入的资源 id 做归属校验，空值不 fail-open
- [ ] "代他人提交"字段只有审核/管理权限可指定

### 定时任务
- [ ] 新增 scheduler job 的间隔经过论证（秒级间隔需要专门理由）
- [ ] 扫描型任务的查询窗口覆盖业务允许的全部取值范围

### 轮询与热路径
- [ ] 前端轮询 effect 的依赖里没有"会被轮询自己更新的 state"
- [ ] 搜索输入触发的请求加防抖（300-500ms）
- [ ] 被轮询的后端读路径没有：每次写库、同步 bcrypt、同步文件 IO（用变化检测/缓存/to_thread）

### 批量端点
- [ ] 循环内 rollback 后不会把已成功项也回滚（逐项 commit 或明确整批原子）
- [ ] 异常分支不访问可能已过期的 ORM 对象（先快照标量值）

### 迁移
- [ ] trgm/扩展类索引有 `pg_available_extensions` 守卫
- [ ] push 前 `alembic heads` 确认单 head（多 head 加 merge revision）
