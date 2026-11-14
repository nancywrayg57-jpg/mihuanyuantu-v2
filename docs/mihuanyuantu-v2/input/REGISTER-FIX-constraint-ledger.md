# REGISTER-FIX · 约束账本（2026-11-14）

## 工单

查明并修复「注册功能不能使用」。

## 根因（分类型）

| 类型 | 事实 |
| --- | --- |
| 代码事实 | 登录页链到 `/register`，但注册页调用底座 `/api/v1/auth/registration-config`；无租户编码时解析 `DEFAULT_TENANT_CODE=default` |
| DB 事实 | 开发库仅有 `rp-tenant-1` / `rp-platform` / `rp-tenant-2`，**无** `default` 租户 → API 返回 `enabled:false` → 文案「当前租户未开放注册」 |
| 代码事实 | 架构 §9.2 要求 `POST /api/v1/realphotos/auth/register`（验证码 + User/Tenant 绑定）；修复前该路由 **404** |
| 待验证推断（已用端测证伪） | 并非「合同内刻意关闭公共注册」：`rp-tenant-1` 的 `registration` 键为 null，属性默认 `enabled=True`；页面无租户编码时却落到不存在的 default 租户 |

## 修复边界

- 实现 `POST /api/v1/realphotos/auth/register`：验证码 → 新建商家租户 `m-{username}` + `rp_merchant` + 商家档案 + 积分户；`requireAudit=false`，可立即登录。
- 前端注册页改为与登录一致的图形验证码流，不再依赖底座租户编码 / 邀请码配置页。
- 不改五层默认、`PASS_SCORE`、CA/Layer0；不开 S7；不清空业务数据。

## 证据

- 单元：`tests/capabilities/realphotos/test_auth_register.py`（3 passed）
- 端测：`docs/mihuanyuantu-v2/input/REGISTER-FIX-e2e-2026-11-14.txt`（`REGISTER_FIX_E2E_PASS=true`）
