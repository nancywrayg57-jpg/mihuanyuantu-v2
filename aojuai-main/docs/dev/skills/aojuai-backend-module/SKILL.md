---
name: aojuai-backend-module
description: Create a new AOJUAI backend module (domain models/schemas/service + FastAPI endpoints) with multi-tenant isolation, RBAC permission codes, DataScope support, and standard SuccessResponse/ErrorResponse.
---

# AOJUAI 后端新模块（Domain + Service + Endpoint）

目标：为一个新资源快速建立**一致、可维护、可对接前端**的模块骨架。

## 模块规格模板（推荐先填）

- `docs/dev/skills/aojuai-backend-module/references/MODULE_SPEC_TEMPLATE.md`

## 开始前先问清（缺一不可）

1. 资源名（英文 `module` / `ModelName` / 表名）与业务含义
2. 字段清单：类型、是否可空、索引、唯一性、默认值、是否 JSONB
3. 列表查询：分页参数名（前端常用 `currentPage/pageSize`）、筛选字段、排序规则
4. 权限码：`resource:create/read/update/delete`（以及按钮级扩展如 `resource:export`）
5. 多租户策略：是否必须 `tenant_id`（绝大多数业务表都需要）
6. 是否需要团队数据权限（DataScope）：列表过滤 / 单条读写校验

## 先找 3 个以上“同类参考”

建议优先参考：
- Domain：`backend/app/domain/users`、`backend/app/domain/roles`、`backend/app/domain/user_groups`
- Endpoints：`backend/app/api/v1/endpoints/users.py`、`backend/app/api/v1/endpoints/roles.py`
- 规范：`guide_docs/API_ENDPOINT_GUIDE.md`、`guide_docs/SERVICE_LAYER_GUIDE.md`
- 对照清单：`docs/dev/skills/aojuai-backend-module/references/EXAMPLES.md`

## 先分流：你要做的是内置能力，还是可选能力包

判据见 `docs/dev/flows/NEW_MODULE.md` §0.1。**两条路径的代码规范完全一样
（Service/权限/响应/事务），差别只在注册与迁移方式**：

| | 内置底座能力 | 可选能力包 |
|---|---|---|
| 什么时候用 | 所有发行版都要内置（assistant / speech / cms 这类） | 部署时选装、只有部分分支需要 |
| 代码位置 | `app/domain/<module>/` | `app/capabilities/<code>/` |
| 路由注册 | `backend/app/api/v1/__init__.py` 中央挂载 | 包内 `CAPABILITY` 声明，**自动发现，禁止改中央文件** |
| 迁移 | core 链（`backend/alembic/`） | 包内独立链 + 独立 version table |
| seed | `scripts/seed_*.py` | 包内 `seed.py::provision/sync` |
| 怎么起步 | 照下面的标准步骤手写 | `python -m scripts.new_module <code> --layer pack ...` |

**下面的"标准落地步骤"讲的是内置能力那条路。** 做可选包就用脚手架生成骨架，
再回来照本手册写业务代码；可运行样例见 `backend/app/capabilities/sample_items/`。

## 标准落地步骤（内置能力）

### 1) 新建 Domain 包

目录：`backend/app/domain/<module>/`

最小文件集：
- `models.py`：模型（多租户用 `TenantBaseModel`，关联表用 `AssociationBaseModel`，系统表用 `BaseModel`）
- `schemas.py`：Pydantic v2 schemas（可选；部分模块也会把 schema 放在 endpoints 内）
- `service.py`：继承 `RepositoryBase[Model]`，只 `flush()` 不 `commit()`
- `__init__.py`：导出需要暴露的对象（可选）

### 2) 将模型注册到 Domain 汇总（必须）

为确保 SQLAlchemy 关系解析与 Alembic autogenerate 正常：
- 编辑 `backend/app/domain/__init__.py`，导入新模型并加入 `__all__`

### 3) Service 层（必须遵守）

- 继承 `RepositoryBase[Model]`（见 `guide_docs/SERVICE_LAYER_GUIDE.md`）
- 事务：一个请求 = 一个事务；**Service 层只 `flush()`**，由 `get_db()` 统一提交（见 `guide_docs/DATABASE_TRANSACTION_GUIDE.md`）
- 返回：返回 ORM 对象；由 API 层做响应转换

### 4) API Endpoint（薄控制器）

目录：`backend/app/api/v1/endpoints/<module>.py`

必须包含：
- 依赖注入：`DBSession`、`CurrentUser`、`TenantCtx`、（需要则）`DataScopeCtx`
- 权限检查：`Depends(PermissionChecker([...]))`
- 统一响应：`SuccessResponse()` / 抛出异常（见 `guide_docs/RESPONSE_USAGE_GUIDE.md`）
- 日志：`get_logger(__name__)`，事件名用 `snake_case`（见 `guide_docs/LOGGING_GUIDE.md`）

### 5) 注册路由

在 `backend/app/api/v1/__init__.py`：
- `from app.api.v1.endpoints import <module>`
- `api_router.include_router(<module>.router, prefix="/<resource>", tags=[...])`

### 6) 迁移与验证

- 生成迁移：按 `aojuai-backend-migrations`
- 最小验证：用 `curl` 走通列表/详情接口，确认分页字段与错误码

## 常见坑（直接规避）

- JSONB：raw SQL 时用 `cast(:param as jsonb)`，不要用 `:param::jsonb`（asyncpg 不支持）
- 时间：统一使用带时区的 `datetime`（`timezone.utc`）
- 多租户：查询/更新/删除必须加 `tenant_id` 条件（除非明确是系统级表）

## 参考文件（按需打开）

- `guide_docs/API_ENDPOINT_GUIDE.md`
- `guide_docs/SERVICE_LAYER_GUIDE.md`
- `guide_docs/DATABASE_TRANSACTION_GUIDE.md`
- `guide_docs/PERMISSION_CHECKER_GUIDE.md`
- `guide_docs/DATA_PERMISSION_GUIDE.md`

## 脚手架

**新业务模块优先用官方脚手架**（生成 capability 骨架、独立迁移链、access 声明、
seed、前端页面与一组契约测试，且不改任何中央文件）：

```bash
python -m scripts.new_module projects --layer pack \
    --route /projects --entity project --permissions read,create,update,delete
```

> `docs/dev/skills/aojuai-backend-module/scripts/scaffold_backend_module.py` 是旧脚手架，
> 它仍会提示你手改中央 router/`domain/__init__.py`——**只适用于内置能力**，
> 做可选包时别用它。
