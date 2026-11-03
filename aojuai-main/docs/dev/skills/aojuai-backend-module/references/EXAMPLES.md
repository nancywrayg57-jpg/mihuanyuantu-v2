# AOJUAI 后端模块参考（对照 3+ 个再动手）

> 目的：在生成/修改代码前，先对照现有实现，保持风格一致（Evidence-Based）。

## 参考模块（建议至少看 3 个）

### sample_items（唯一端到端的**可选能力包**样例，做可选包先看它）

- 声明：`backend/app/capabilities/sample_items/__init__.py`（`CAPABILITY`，自注册的唯一入口）
- 模型 / schemas / service：同目录，Service 继承 `RepositoryBase`，租户过滤显式写在每个查询
- 菜单权限声明：`access.py`（交给 `domain/menus/reconciler.py` 对账）
- seed：`seed.py`（`provision` 新租户 / `sync` 全库对账）
- 独立迁移链：`migrations/`（独立 version table，`down_revision=None`）
- 前端：`frontend/src/app/(app)/sample-items/page.tsx` + `frontend/src/lib/sample-items-api.ts`
- 抄它之前先读 `backend/app/capabilities/sample_items/README.md`：写明了哪些必须改、哪些不许改

### users（最完整的**内置能力**：domain schemas + service + endpoints）

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
