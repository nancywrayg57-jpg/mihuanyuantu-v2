# 演示模式 allowlist 规则（前端请求层）

> 目标：演示模式只能“看”，但部分列表接口可能用 POST（分页查询），需要有限放行。

## 允许放行的唯一场景

- **读语义**的 POST（分页/条件查询），例如：
  - `POST /api/v1/roles`（列表）
  - `POST /api/v1/users`（列表）

## 永远不要放行

- create/update/delete/assign 等任何写接口：
  - `POST /api/v1/users/create`
  - `PUT /api/v1/users/{id}`
  - `DELETE /api/v1/users/{id}`

## 代码位置

- 拦截点：`frontend/src/lib/api.ts`（`apiFetch` 内的 `allowPostExact` 白名单；开关见 `frontend/src/lib/demo.ts`）
- 允许列表：`allowPostExact`（只加“完整 path”，不带 query）

