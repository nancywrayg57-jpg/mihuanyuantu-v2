# Auth / Security Baseline

适用范围：

- `nextjs-base`
- 后续所有下游扩展

目标：

- 统一认证会话策略，避免下游扩展重新发明一套登录/刷新逻辑
- 把跨租户、跨域、反向代理、公开分享页面的安全边界前置说清楚
- 给下游扩展一个“能直接照着实现”的最小安全基线

## 1. 会话基线

### 1.1 后端签发方式

后端统一签发两类 `HttpOnly` Cookie：

- 访问令牌：`AUTH_ACCESS_COOKIE_NAME`
- 刷新令牌：`AUTH_REFRESH_COOKIE_NAME`

默认行为：

- `access cookie` 路径：`/`
- `refresh cookie` 路径：`/api/v1/auth`
- `SameSite` 默认：`lax`
- `Secure` 默认按请求协议自动判断；如果 `AUTH_COOKIE_SAMESITE=none`，则强制 `Secure=true`

### 1.2 前端存储策略

前端允许把“会话元数据”写入 `localStorage`，但**不允许**持久化真实 `accessToken` / `refreshToken`。

允许保留的数据：

- `username`
- `nickname`
- `roles`
- `permissions`
- `isSuperuser`
- `mustCompleteProfile`
- `expires`
- `authMode=cookie`

禁止重新引入：

- 把真实 JWT 长期放入 `localStorage`
- 每个业务模块自己复制一套 `refresh token` 逻辑
- AI 助手、SSE、上传、下载绕过通用会话层直接读裸 token

### 1.3 前端请求基线

所有浏览器侧请求默认：

- `credentials: 'include'`
- 优先使用共享的 `apiFetch` / `apiFetchBlob`
- Bearer 头只作为兼容回退，不作为首选

例外：

- 公开分享、公开 SEO、公开只读接口可以不带会话

## 2. 刷新与登出基线

### 2.1 刷新

统一刷新入口：

- `POST /api/v1/auth/refresh-token`

规则：

- Cookie 会话优先从 `refresh cookie` 取值
- 兼容 Bearer 老会话时，允许请求体传 `refreshToken`
- 刷新后必须同时更新新 cookie

### 2.2 会话探测

统一会话探测入口：

- `GET /api/v1/auth/session`

用途：

- 前端冷启动恢复登录态
- Cookie 会话校验
- SSR / hydration 前后保持同一套会话事实

### 2.3 登出

统一登出入口：

- `POST /api/v1/auth/logout`

规则：

- 不要求 access token 一定有效
- 只要请求到了后端，就应尽最大努力清理 auth cookies

## 3. CSRF 基线

Cookie 会话下，对所有非安全方法启用 CSRF 防护：

- 安全方法：`GET` / `HEAD` / `OPTIONS` / `TRACE`
- 非安全方法：其余请求

拦截条件：

- `Sec-Fetch-Site=cross-site`
- `Origin` / `Referer` 不在允许来源内
- `Origin=null`

放行条件：

- 明确使用 Bearer 头的请求
- 不使用 auth cookie 的请求

允许来源集合：

- `settings.CORS_ORIGINS`
- 当前请求实际解析出的站点 origin

## 4. 可信代理基线

对公网 Host 的后端请求，必须经过受信代理注入共享密钥：

- 请求头：`x-aoju-proxy-key`
- 服务端配置：`AOJ_PROXY_SHARED_SECRET`

适用场景：

- 正式 Nginx 部署中，浏览器 `/api/v1/*` -> Nginx -> FastAPI
- Next.js SSR 服务端到 FastAPI 的内部请求
- Next App Route proxy 兜底场景

运维要求：

1. 正式部署以 Nginx 为唯一受信边界，浏览器请求页面、`/_next/*`、前端资源走 Next.js，浏览器请求 `/api/v1/*` 走 FastAPI。
2. 外部用户传入的 `x-aoju-proxy-key` 必须在 Nginx / 网关层被覆盖，不允许透传原始值。
3. 只有受信代理或同机服务端进程可以重新注入正确密钥。
4. `NEXT_ENABLE_BACKEND_REWRITES=0`，不要用 Next rewrite 转发 `/api/:path*`。
5. Next App Route proxy 只作为端口直连、无 Nginx 或特殊服务端代理场景的兜底。
6. `AOJ_PROXY_SHARED_SECRET` 只能放服务端环境变量，不能暴露为 `NEXT_PUBLIC_*`。

Nginx 核心配置：

```nginx
location ^~ /api/v1/ {
    proxy_pass http://127.0.0.1:38000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header x-aoju-proxy-key "<AOJ_PROXY_SHARED_SECRET>";
}
```

## 5. 安全响应头基线

后端与 Next.js 前端都应统一补齐：

- `Referrer-Policy: strict-origin-when-cross-origin`
- `X-Content-Type-Options: nosniff`
- `X-DNS-Prefetch-Control: off`
- `Permissions-Policy`
- HTTPS 下的 `Strict-Transport-Security`

普通页面额外要求：

- `X-Frame-Options: SAMEORIGIN`
- CSP 限制 `frame-ancestors 'self'`

公开分享 / 嵌入页面例外：

- `/share`
- `/share-groups`
- `/conversation-share`
- `/forms/share`
- `/reports/share`
- `/s`

这些路径允许放宽嵌入保护，否则会直接打断对外分享和嵌入。

## 6. SSR 基线

Next.js 服务端发往 FastAPI 的内部请求，至少需要：

- `Accept: application/json`
- `x-forwarded-host`
- `x-aoju-proxy-key`（如果配置了 `AOJ_PROXY_SHARED_SECRET`）

当前已明确依赖这套行为的场景：

- 站点公共 SEO 配置
- 公开分享页的 SSR 元数据

## 7. 环境变量基线

后端必须关注：

- `JWT_SECRET_KEY`
- `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`
- `JWT_REFRESH_TOKEN_EXPIRE_DAYS`
- `AUTH_ACCESS_COOKIE_NAME`
- `AUTH_REFRESH_COOKIE_NAME`
- `AUTH_COOKIE_DOMAIN`
- `AUTH_COOKIE_SECURE`
- `AUTH_COOKIE_SAMESITE`
- `AOJ_PROXY_SHARED_SECRET`
- `CORS_ORIGINS`

前端服务端运行时必须关注：

- `NEXT_PUBLIC_API_BASE_URL`
- `API_BASE_URL`
- `AOJ_PROXY_SHARED_SECRET`
- `NEXT_ENABLE_BACKEND_REWRITES=0`
- `NEXT_PUBLIC_DEMO_MODE`
- `NEXT_PUBLIC_DEMO_MODE_MESSAGE`

## 8. 下游分支继承规则

所有下游分支都应遵守：

1. 不允许重新把 JWT 明文持久化到浏览器长期存储。
2. 不允许业务模块各自复制认证刷新逻辑。
3. AI 助手、SSE、下载、导入导出都应复用统一会话层。
4. 新增公开分享路径时，必须同步评估是否加入嵌入保护放宽名单。
5. 新增 SSR 到后端的服务端请求时，必须评估是否需要透传 `x-aoju-proxy-key`。

## 9. 最小验收清单

每个分支上线前至少验证：

1. 登录后浏览器 `localStorage` 中不存在真实 access/refresh token。
2. 清空页面并刷新，`/api/v1/auth/session` 能恢复会话。
3. 登录态过期后，刷新请求能自动续期。
4. 点击登出后，cookie 被清空，页面跳回登录页。
5. 公开分享页可正常打开，不被 `X-Frame-Options` / CSP 错误拦截。
6. SSR 公共页面不会因 trusted proxy 校验而返回 403/500。
7. 跨站伪造的 cookie 写请求会被 CSRF 拦截。
