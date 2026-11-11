# Web 登录唯一合法入口（FR-001 / REMAIN-GAP R1）

| 入口 | 用途 |
| --- | --- |
| `POST /api/v1/realphotos/auth/challenges` → `POST /api/v1/realphotos/auth/login` | **蜜獾原图业务 Web 登录**（用户名 + 密码 + 图形验证码）；成功写 cookie，绝对会话 30 天 refresh |
| `POST /api/v1/auth/login` | 仅非 `rp_*` 岗位的平台账号；**禁止**作为商家/订单客服/蜜獾管理员/技术客服旁路 |

业务角色（`rp_merchant` / `rp_order_support` / `rp_admin` / `rp_tech_support`）调用底座无 captcha 登录时返回 **403**，`code=AUTH_CAPTCHA_REQUIRED`，`details.loginPath=/api/v1/realphotos/auth/login`。
