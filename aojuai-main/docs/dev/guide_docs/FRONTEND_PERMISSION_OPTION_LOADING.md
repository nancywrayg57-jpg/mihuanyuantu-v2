# 前端受保护选项接口加载指南

> 适用场景：`/api/v1/users`、`/api/v1/teams/options`、`/api/v1/user-groups` 这类“给下拉框/选择器/搜索框提供数据”的接口。

## 核心结论

这些接口不是“免费元数据接口”，而是**受权限保护的真实业务接口**。

如果后端对接口加了 `PermissionChecker(...)`，前端就不能在页面初始化时无条件预加载；否则普通用户会出现：

- 页面首屏直接打出 `401/403`
- 某些全局 API 层把失败误判成“会话失效”，触发登出/跳登录
- 页面功能本身可用，但因为某个次要选项接口失败而白屏或报错

## 必须遵守的规则

### 1. 先看后端权限契约，再写前端预加载

示例：

- `/api/v1/users` 对应 `PermissionChecker(["user:read", "user:list"])`
- `/api/v1/teams/options` 对应 `PermissionChecker(["team:read"])`
- `/api/v1/users`（POST 列表）对应 `PermissionChecker(["user:read", "user:list"])`（OR 语义）
- `/api/v1/teams/options` 对应 `PermissionChecker(["team:read"])`
- ⚠️ **不是所有受保护接口都用权限码**：`/api/v1/speech/config` 用的是
  **角色门禁** `CurrentTenantAdmin`（见 `backend/app/api/v1/endpoints/speech.py`），
  没有 `speech:config` 这个权限码。前端按一个不存在的权限码判断会判错——
  这种接口要按"是不是租户管理员"来决定发不发请求。

前端必须用同一组权限做 `hasAnyPermission(session, [...])` 判断，再决定是否请求。

### 2. 无权限时要“跳过请求”，不是“请求后再兜底”

错误写法：

```ts
try {
  const users = await apiFetch('/api/v1/users', { session })
} catch {
  setUsers([])
}
```

这会让普通用户每次打开页面都先打一发 `403`。

正确写法：

```ts
const canReadUsers = hasAnyPermission(session, ['user:read', 'user:list'])

if (!session || !canReadUsers) {
  setUsers([])
  return
}

const users = await apiFetch('/api/v1/users', { session })
setUsers(users.list || [])
```

### 3. 受保护选项要有“无权限 UI 状态”

不要只把请求跳过；还要让界面处于可理解状态：

- 清空 options
- 禁用对应搜索框/下拉框
- 占位文案明确写“当前无读取权限”
- 保留手动输入 ID 的路径时，不要再强依赖 options 预加载

### 4. 页面权限和选项权限不是一回事

一个用户可能：

- 能访问页面
- 能执行主流程
- 但**不能读取某些辅助选项**

典型例子：

- 普通用户可进入只需自身权限的页面（如“我的消息”“我的积分”）
- 但没有 `user:list` / `team:read`
- 页面仍应可用，只是不能加载“用户/团队候选项”

### 5. 分享页 / 公共页不能复用后台假设

分享页或公开访问页：

- 默认没有登录态
- 不能假设存在 `session`
- 不能默认发后台管理员侧的 options/config 请求

## 推荐实现模式

```ts
const canReadUsers = hasAnyPermission(session, ['user:read', 'user:list'])

const loadUsers = useCallback(async (keyword = '') => {
  if (!session || !canReadUsers) {
    setUserOptions([])
    return
  }

  try {
    const result = await apiFetch<UserPageResponse>('/api/v1/users', {
      method: 'POST',
      body: JSON.stringify({
        currentPage: 1,
        pageSize: 20,
        username: keyword || undefined,
        nickname: keyword || undefined,
      }),
      session,
      tenantId: targetTenantId,
    })
    setUserOptions(result.list || [])
  } catch {
    setUserOptions([])
  }
}, [canReadUsers, session, targetTenantId])

useEffect(() => {
  if (!open) return
  if (!canReadUsers) {
    setUserOptions([])
    return
  }
  void loadUsers('')
}, [canReadUsers, loadUsers, open])
```

## 回归测试最低要求

至少补一条“普通用户真实登录”的页面回归，验证：

1. 页面能正常进入
2. 没有被重定向回 `/login`
3. 没有主动请求自己无权限的 options/config 接口

如果有 Playwright，优先做页面级 smoke test，而不是只做接口单测。
