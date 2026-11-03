# AOJU Backend - API 路由文档

> Swagger UI: http://localhost:38000/api/v1/docs
> ReDoc: http://localhost:38000/api/v1/redoc

---

## 认证模块 `/api/v1/auth`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | `/login` | 用户登录 | 公开 |
| POST | `/refresh-token` | 刷新访问令牌 | 公开 |
| GET | `/mine` | 获取当前用户信息 | 登录用户 |
| POST | `/logout` | 用户登出 | 登录用户 |
| POST | `/register` | 用户自主注册 | 公开 |
| GET | `/registration-config` | 获取租户注册配置 | 公开 |
| GET | `/parse-invite` | 解析邀请码（返回租户信息） | 公开 |
| GET | `/resolve-domain` | 通过域名识别租户 | 公开 |

---

## 用户管理 `/api/v1/users`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | `/` | 获取用户列表（分页） | 登录用户 |
| POST | `/pending` | 获取待审核用户列表 | 管理员 |
| GET | `/{user_id}` | 获取用户详情 | 登录用户 |
| POST | `/create` | 创建用户 | 管理员 |
| PUT | `/{user_id}` | 更新用户 | 管理员 |
| DELETE | `/{user_id}` | 删除用户（软删除） | 管理员 |
| POST | `/{user_id}/audit` | 审核用户注册（批准/拒绝） | 管理员 |
| POST | `/{user_id}/reset-password` | 重置用户密码 | 管理员 |
| POST | `/change-password` | 修改当前用户密码 | 登录用户 |

---

## 角色管理 `/api/v1/roles`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | `/` | 获取角色列表（分页） | 登录用户 |
| GET | `/all` | 获取所有角色（下拉框用） | 登录用户 |
| GET | `/{role_id}` | 获取角色详情 | 登录用户 |
| POST | `/create` | 创建角色 | 管理员 |
| PUT | `/{role_id}` | 更新角色 | 管理员 |
| DELETE | `/{role_id}` | 删除角色 | 管理员 |
| GET | `/{role_id}/menus` | 获取角色菜单ID列表 | 管理员 |
| POST | `/{role_id}/menus` | 设置角色菜单（权限分配） | 管理员 |

---

## 菜单管理 `/api/v1/menus`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | `/` | 获取菜单列表（管理端） | 登录用户 |
| GET | `/routes` | 获取异步路由（前端动态路由） | 登录用户 |
| GET | `/{menu_id}` | 获取菜单详情 | 登录用户 |
| POST | `/create` | 创建菜单 | 管理员 |
| PUT | `/{menu_id}` | 更新菜单 | 管理员 |
| DELETE | `/{menu_id}` | 删除菜单 | 管理员 |

---

## 团队管理 `/api/v1/teams`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | `/` | 获取团队列表（分页） | 登录用户 |
| GET | `/tree` | 获取团队树 | 登录用户 |
| GET | `/{team_id}` | 获取团队详情 | 登录用户 |
| POST | `/create` | 创建团队 | 管理员 |
| PUT | `/{team_id}` | 更新团队 | 管理员 |
| DELETE | `/{team_id}` | 删除团队 | 管理员 |

---

## 租户管理 `/api/v1/tenants`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | `/` | 获取租户列表（分页） | 管理员 |
| GET | `/current` | 获取当前用户所属租户 | 管理员 |
| GET | `/{tenant_id}` | 获取租户详情 | 管理员 |
| POST | `/create` | 创建租户 | 管理员 |
| PUT | `/{tenant_id}` | 更新租户 | 管理员 |
| PUT | `/{tenant_id}/registration` | 更新租户注册配置 | 管理员 |
| DELETE | `/{tenant_id}` | 删除租户（软删除） | 管理员 |

### 租户注册配置字段

```json
{
  "enabled": true,        // 是否允许自主注册
  "requireAudit": true,   // 是否需要审核
  "defaultRole": "user"   // 默认角色代码
}
```

---

## 租户自管理（租户管理员）`/api/v1/tenant/profile`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/` | 获取当前租户信息 | 租户管理员 |
| PUT | `/` | 更新当前租户信息（基本信息） | 租户管理员 |
| GET | `/settings` | 获取当前租户设置（config/quota） | 租户管理员 |
| PUT | `/settings` | 更新当前租户设置（registration/verification/seo） | 租户管理员 |
| POST | `/invite-link` | 生成租户邀请链接 | 租户管理员 |

---

## 站点公开配置（无需登录）`/api/v1/site`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/public-config` | 获取站点公开配置（SEO） | 公开 |

---

## 用户分组 `/api/v1/user-groups`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | `/` | 获取分组列表（分页） | 登录用户 |
| GET | `/all` | 获取所有分组（下拉框用） | 登录用户 |
| GET | `/tree` | 获取分组树形结构 | 登录用户 |
| GET | `/{group_id}` | 获取分组详情 | 登录用户 |
| POST | `/create` | 创建分组 | 管理员 |
| PUT | `/{group_id}` | 更新分组 | 管理员 |
| DELETE | `/{group_id}` | 删除分组 | 管理员 |
| GET | `/{group_id}/members` | 获取分组成员 | 登录用户 |
| POST | `/{group_id}/members` | 添加分组成员 | 管理员 |
| DELETE | `/{group_id}/members` | 移除分组成员 | 管理员 |

### 用户分组支持无限层级

使用物化路径模式，支持类似：集团 → 分公司 → 团队 → 小组 的无限层级结构。

---

## 积分 `/api/v1/credits`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | `/` | 获取积分记录（分页） | 登录用户 |

---

## 消息通知 `/api/v1/notifications`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | `/` | 获取通知列表（分页） | 登录用户 |
| POST | `/mine` | 获取我的通知（分页） | 登录用户 |

---

## 操作日志 `/api/v1/operation-logs`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | `/` | 获取操作日志（分页） | 登录用户 |
| POST | `/mine` | 获取我的操作日志（分页） | 登录用户 |

---

## 健康检查

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/health` | 健康检查 | 公开 |

---

## 用户状态说明

| 状态值 | 说明 |
|--------|------|
| 0 | 禁用 |
| 1 | 正常 |
| 2 | 待审核（注册待审核） |
| 3 | 审核拒绝 |

---

## 响应格式

### 标准响应
```json
{
  "success": true,
  "data": { ... },
  "message": "操作成功",
  "code": "SUCCESS"
}
```

### 分页响应
```json
{
  "success": true,
  "data": {
    "list": [...],
    "total": 100,
    "pageSize": 10,
    "currentPage": 1
  }
}
```

### 错误响应
```json
{
  "success": false,
  "code": "NOT_FOUND",
  "message": "资源不存在",
  "details": null
}
```

---

## 权限说明

- **公开**: 无需登录即可访问
- **登录用户**: 需要有效的 JWT Token
- **管理员**: 需要 `is_superuser = true` 的用户

---

*最后更新: 2026-01-28*
