# Dev-Base 核心开发指南

> 统一的开发流程、规范和注意事项 - 基于历史开发记录整理

---

## 1. 开发优先级

```
1. 安全性 (Security)        ← 最高优先级
2. 数据完整性 (Data Integrity)
3. 功能正确性 (Functionality)
4. 用户体验 (UX)
5. 性能优化 (Performance)
```

**开发顺序**: 后端 API → curl 验证 → 前端页面

---

## 2. 核心规则速查

### 2.1 多租户隔离 (必须)

```python
# 所有业务表继承 TenantBaseModel
from app.infrastructure.database.base import TenantBaseModel

class MyModel(TenantBaseModel):
    __tablename__ = "my_models"
    # tenant_id 自动包含

# 所有查询必须过滤
result = await db.execute(
    select(MyModel).where(
        MyModel.tenant_id == current_user.tenant_id,
        MyModel.deleted_at.is_(None)
    )
)
```

### 2.2 权限系统 (双轨制)

| 权限类型 | 作用 | 依赖注入 | 检查位置 |
|---------|------|---------|---------|
| **菜单权限** | 能不能用这个功能 | `PermissionChecker` | API层 |
| **数据权限** | 能操作哪些数据 | `DataScopeCtx` | API层+Service层 |

```python
@router.get("/items")
async def list_items(
    db: DBSession,
    current_user: CurrentUser,
    tenant_ctx: TenantCtx,
    data_scope: DataScopeCtx,  # ← 必须注入
    _: None = Depends(PermissionChecker(["module:item:read"])),
):
    team_ids = None if data_scope.has_all_read_access else data_scope.read_team_ids
    items = await service.list_items(tenant_id=tenant_ctx.tenant_id, team_ids=team_ids)
```

### 2.3 异步关系加载

```python
# ❌ 错误: 会触发 MissingGreenlet 错误
for menu in menus.scalars():
    for child in menu.children:  # FAILS!

# ✅ 正确: 使用 selectinload 预加载
from sqlalchemy.orm import selectinload

result = await db.execute(
    select(Menu).options(selectinload(Menu.children))
)
```

### 2.4 Service 层规范

- API 层禁止直接 `db.execute(select(...))`
- 所有数据库操作通过 Service 方法
- Service 继承 `RepositoryBase[ModelType]`
- 使用 `flush()` 而非 `commit()`

### 2.5 其他规则

- **异常处理**: 严禁 `except Exception`，使用 `NotFoundError`/`BusinessError`
- **API响应**: 使用 `ResponseBase[T]`，保持前后端响应契约一致
- **密码处理**: 直接用 `bcrypt`，不用 passlib
- **路由顺序**: 固定路径 (`/my`) 必须在参数路由 (`/{id}`) 之前

---

## 3. 菜单权限同步 (重要)

**核心原则**: 菜单权限需要在两个地方同步维护

| 场景 | 维护位置 | 说明 |
|------|---------|------|
| **新租户初始化** | `seed_data.py` | 创建租户时自动生成菜单 |
| **已有租户升级** | `alembic 迁移` | 为已存在的租户添加新菜单 |

### 3.1 添加菜单标准流程

**Step 1: seed_data.py 添加菜单定义**

```python
# backend/scripts/seed_data.py
system_menus = [
    # (name, title, path, component, icon, sort, menu_type, perms)
    ("<module>-settings", "<模块>设置", "/system/<module>-settings",
     "views/system/<module>-settings/index", "ep:setting", 9, "1", "<module>:settings"),
]

admin_menu_assignments = [
    "/system/<module>-settings",
]
```

**Step 2: alembic 迁移为已有租户添加菜单**

```python
# backend/alembic/versions/xxx_add_module_menu.py
def upgrade() -> None:
    conn = op.get_bind()
    tenants = conn.execute(
        text("SELECT id FROM tenants WHERE deleted_at IS NULL")
    ).fetchall()

    if not tenants:
        return  # 新装环境安全 no-op

    for (tenant_id,) in tenants:
        # 1. 获取父菜单 2. 插入菜单 3. 分配给 admin 角色
        # ... (详见 checklists/DEV_CHECKLIST.md)
```

---

## 4. 模块开发流程

### 4.1 后端模块结构

```
backend/app/domain/<module>/
├── __init__.py
├── models.py      # SQLAlchemy 模型
├── schemas.py     # Pydantic Schema
├── service.py     # 业务逻辑
└── repository.py  # 数据访问 (可选)

backend/app/api/v1/endpoints/<module>.py  # API 端点
```

### 4.2 开发步骤

1. **定义模型** - 继承 `TenantBaseModel`
2. **注册模型** - 更新 `backend/app/domain/__init__.py`
3. **生成迁移** - `alembic revision --autogenerate -m "desc"`
4. **执行迁移** - `alembic upgrade head`
5. **创建 Schema** - 设置 `from_attributes = True`
6. **实现 Service** - 继承 `RepositoryBase`
7. **创建 API** - 注入权限依赖
8. **注册路由** - 更新 `api/v1/__init__.py`
9. **添加菜单** - seed_data.py + alembic 迁移

---

## 5. 常用命令

| 任务 | 命令 |
|------|------|
| 启动后端 | `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` |
| 启动前端 | `pnpm dev` |
| 生成迁移 | `alembic revision --autogenerate -m "desc"` |
| 执行迁移 | `alembic upgrade head` |
| 种子数据 | `python -m scripts.seed_data` |
| 运行测试 | `pytest` |

---

## 6. 开发检查清单

### 权限相关
- [ ] 列表接口注入 `DataScopeCtx`
- [ ] 使用 `data_scope.read_team_ids` 过滤
- [ ] 需要权限的接口添加 `PermissionChecker`
- [ ] 权限码格式: `资源:操作`

### 数据库相关
- [ ] 模型继承 `TenantBaseModel`
- [ ] 查询过滤 `tenant_id` 和 `deleted_at`
- [ ] 模型注册到 `domain/__init__.py`
- [ ] 迁移已生成并执行

### API 相关
- [ ] 使用 `ResponseBase` 包装响应
- [ ] 固定路径在参数路由之前
- [ ] 列表支持 `sortBy`/`sortOrder`

### 菜单相关
- [ ] seed_data.py 添加菜单定义
- [ ] alembic 迁移为已有租户添加
- [ ] role_menus 分配正确

---

## 7. 参考实现

正确实现的模块 (开发前必读):
- `backend/app/api/v1/endpoints/users.py`
- `backend/app/api/v1/endpoints/teams.py`
- `backend/app/api/v1/endpoints/roles.py`

---

## 8. 详细文档索引

| 文档 | 内容 |
|------|------|
| [DATA_PERMISSION_GUIDE.md](../guide_docs/DATA_PERMISSION_GUIDE.md) | 数据权限详解 |
| [PERMISSION_CHECKER_GUIDE.md](../guide_docs/PERMISSION_CHECKER_GUIDE.md) | 功能权限控制 |
| [SERVICE_LAYER_GUIDE.md](../guide_docs/SERVICE_LAYER_GUIDE.md) | Service 层规范 |
| [API_ENDPOINT_GUIDE.md](../guide_docs/API_ENDPOINT_GUIDE.md) | API 端点规范 |
| [open-edition-base-hardening.md](../../public/open-edition-base-hardening.md) | 公开版稳定基线 |

---

*最后更新: 2026-01-27*
