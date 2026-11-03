# AOJUAI 后端模块参考（对照 3+ 个再动手）

> 目的：在生成/修改代码前，先对照现有实现，保持风格一致（Evidence-Based）。

## 参考模块（建议至少看 3 个）

### users（最完整：domain schemas + service + endpoints）

- Domain 模型：`backend/app/domain/users/models.py`
- Domain schemas：`backend/app/domain/users/schemas.py`
- Service：`backend/app/domain/users/service.py`
- Endpoints：`backend/app/api/v1/endpoints/users.py`

### roles（endpoints 内部 schema 较多，数据权限场景更完整）

- 模型：`backend/app/domain/roles/models.py`
- Service：`backend/app/domain/roles/service.py`
- Endpoints：`backend/app/api/v1/endpoints/roles.py`

### menus（动态路由的关键模块）

- 模型：`backend/app/domain/menus/models.py`
- Service：`backend/app/domain/menus/service.py`
- Endpoints：`backend/app/api/v1/endpoints/menus.py`

### teams / user_groups（树结构与关联示例）

- `backend/app/domain/teams/*`
- `backend/app/domain/user_groups/*`

## 必查规范（按需打开）

- API 层：`guide_docs/API_ENDPOINT_GUIDE.md`
- Service 层：`guide_docs/SERVICE_LAYER_GUIDE.md`
- 事务：`guide_docs/DATABASE_TRANSACTION_GUIDE.md`
- 响应：`guide_docs/RESPONSE_USAGE_GUIDE.md`
- 权限：`guide_docs/PERMISSION_CHECKER_GUIDE.md`
- 数据权限：`guide_docs/DATA_PERMISSION_GUIDE.md`
