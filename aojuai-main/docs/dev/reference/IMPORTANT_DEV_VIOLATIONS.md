# nextjs-base 模块开发违规记录

> 记录时间: 2026-01-14
> 涉及模块: Notifications (通知消息), Operation Logs (操作日志), Agents (应用管理/分配), Menu Structure (菜单结构)
> 状态: **已修复** ✅

---

## 违规概述

| 违规类型 | 涉及模块 | 关联规范文档 | 状态 |
|---------|---------|-------------|------|
| 未使用数据权限检查 (DataScopeCtx) | Operation Logs | [DATA_PERMISSION_GUIDE.md](../guide_docs/DATA_PERMISSION_GUIDE.md) | ✅ 已修复 |
| API 层直接操作数据库 | Notifications | [SERVICE_LAYER_GUIDE.md](../guide_docs/SERVICE_LAYER_GUIDE.md) | ✅ 已修复 |
| 数据权限判断放在 Service 层 | Agents | [API_ENDPOINT_GUIDE.md](../guide_docs/API_ENDPOINT_GUIDE.md) | ✅ 已修复 |
| 模型字段硬编码/双源参数 | Agents | [SERVICE_LAYER_GUIDE.md](../guide_docs/SERVICE_LAYER_GUIDE.md) | ✅ 已修复 |
| FastAPI 路由顺序错误 | Operation Logs | [DEV_CHECKLIST.md](./DEV_CHECKLIST.md#10-fastapi-路由顺序重要) | ✅ 已修复 |
| 前端静态路由与后端动态路由冲突 | Menu Structure | [DEV_CHECKLIST.md](./DEV_CHECKLIST.md#11-菜单结构与角色分配) | ✅ 已修复 |
| User 角色菜单分配过多 | Menu Structure | [DEV_CHECKLIST.md](./DEV_CHECKLIST.md#11-菜单结构与角色分配) | ✅ 已修复 |

**注**: Credits 模块为租户级资源，不需要数据权限检查。

---

## 修复记录

### 1. Operation Logs - 添加 DataScopeCtx

**修复文件**:
- `backend/app/api/v1/endpoints/operation_logs.py:72` - 添加 `data_scope: DataScopeCtx` 参数
- `backend/app/domain/operation_logs/service.py:51` - 添加 `team_ids` 参数

**修复内容**:
```python
# API 层 - 根据数据权限获取 team_ids
team_ids = None if data_scope.has_all_read_access else data_scope.read_team_ids

# Service 层 - 通过 user_teams 关联过滤
if team_ids is not None:
    user_ids_subquery = (
        select(UserTeam.user_id)
        .where(UserTeam.team_id.in_(team_ids))
        .distinct()
    )
    where.append(OperationLog.user_id.in_(user_ids_subquery))
```

### 2. Notifications - 移除 API 层直接数据库操作

**修复文件**:
- `backend/app/domain/teams/service.py:61` - 新增 `get_team_ids_by_tenant()`
- `backend/app/domain/users/service.py:182` - 新增 `get_user_ids_by_tenant()`
- `backend/app/domain/users/service.py:218` - 新增 `get_all_enabled_users()`
- `backend/app/api/v1/endpoints/notifications.py:265,348` - 改用 Service 方法

### 3. Agents - 数据权限移到 View + JSONB-first

**修复文件**:
- `backend/app/api/v1/endpoints/agents.py` - View 层注入 `DataScopeCtx`，组装 `team_ids`/对象权限检查后再调用 Service
- `backend/app/domain/agents/service.py` - 移除 `DataScope` 依赖，Service 仅接收过滤参数并执行查询/CRUD
- `backend/app/domain/agents/models.py` - `AgentApp` 去掉硬编码配置列，统一通过 `app_config`（JSONB）
- `backend/app/domain/agents/schemas.py` - 删除 `parameters/store_chat_history/...` 等字段，统一输出 `parameters_raw/app_config`
- `backend/alembic/versions/*` - 迁移：保持 JSONB-first schema；老库升级需数据迁移回填并删除旧列（模板见 `docs/dev/templates/ALEMBIC_MIGRATION_TEMPLATE.md`）
- `frontend/src/views/agents/apps/index.vue`、`frontend/src/views/agents/apps/components/Write.vue` - 前端从 `app_config` 读写配置开关

**修复内容**:
- 列表数据权限：View 通过 `data_scope.read_team_ids` 计算 `team_ids`，Service 用 `user_teams` 子查询过滤
- 详情/编辑/删除：View 调用 `data_scope.check_read/edit/delete_permission()` 做对象级权限校验
- 扩展性：应用开关项统一收敛到 `app_config`（JSONB），参数统一使用 `parameters_raw`（单一数据源）

---

**文档维护者**: Dev-base Docs
**最后更新**: 2026-01-28
