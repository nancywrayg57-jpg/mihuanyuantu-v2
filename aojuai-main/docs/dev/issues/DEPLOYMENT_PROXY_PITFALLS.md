# Deployment / Proxy Pitfalls

本文件沉淀 `nextjs-base` 和下游分支部署过程中可复用的代理、rewrite、BT、Nginx、缓存事故经验。

## Next rewrite 抢占 API 导致登录 403

### 症状

- 页面能打开，但登录 `POST /api/v1/auth/login` 返回 `403`。
- 后端日志出现来源校验或 CSRF 拦截。
- 账号密码本身没有进入正常校验流程。

### 触发条件

- 正式部署使用 Nginx + Next.js + FastAPI。
- `/api/v1/*` 没有由 Nginx 直达 FastAPI，而是落入 Next rewrite 或前端代理链路。
- Nginx 没有覆盖注入 `x-aoju-proxy-key`，或 `X-Forwarded-Proto` / `CORS_ORIGINS` 漂移。

### 根因

Next rewrite 只是路径转发，不能可靠承担生产受信代理边界，也容易抢在 App Route proxy 之前匹配。可信代理密钥应由 Nginx 作为唯一公网边界注入。

### 解决方案

- 生产 `NEXT_ENABLE_BACKEND_REWRITES=0`。
- Nginx 将 `/api/v1/*`、`/health`、`/static/*` 直转 FastAPI。
- Nginx 后端 location 覆盖注入 `x-aoju-proxy-key`，值与 `AOJ_PROXY_SHARED_SECRET` 一致。
- 外部传入的同名 header 不允许透传。

### 如何预防

- `frontend/.env.production` 默认关闭 rewrites。
- 部署后跑登录 smoke test，未知账号应返回 `401`，不是 `403`。
- 参考 `docs/deploy/BT_FRONTEND_DEPLOY_SOP.md` 和 `docs/dev/reference/AUTH_SECURITY_BASELINE.md`。

## BT 随机端口未同步导致 502

### 症状

- 宝塔显示 Node 项目重启成功。
- 域名返回 `502`。
- `ss -ltnp` 能看到 Next.js 监听在新端口，但 Nginx `location /` 仍指向旧端口。

### 根因

BT Node 项目可能使用随机端口。项目重启和 Nginx upstream 同步不是一个动作，面板状态也不总是等于真实监听端口。

### 解决方案

```bash
ss -ltnp | grep next-server
rg -n "location / \\{|proxy_pass http://127.0.0.1:" <BT_NGINX_FRONTEND_CONF>
/www/server/panel/pyenv/bin/python /www/server/panel/script/nodejs-sync-proxy.py <BT_NODE_PROJECT_NAME> 120
nginx -t && nginx -s reload
```

如果同步脚本未生效，再调用宝塔 `set_config(...)` 刷新 upstream。

### 如何预防

- 生产优先使用稳定 `PORT`。
- 如果保留随机端口，部署完成必须以 `ss` 真实监听端口为准。
- 不要用手工 `pnpm start` 替代宝塔托管项目。

## BT 重写主 Nginx 配置导致后端直连规则丢失

### 症状

- 前端页面正常。
- 登录、上传、语音试听、助手 SSE 或静态上传资源异常。
- 主 Nginx 文件只剩 `location /`，缺少 `/api/v1/`、`/static/`、`/health`。

### 根因

BT 同步 Node 项目端口时可能重写站点主配置。手工写在主文件里的后端直连 location 和缓存 location 会丢失。

### 解决方案

- 将后端直连规则放入 BT extension include。
- 仓库参考：`docs/deploy/nginx.bt.backend-routes.extension.conf`。
- 每次部署后检查实际 Nginx 配置，而不是只看仓库参考文件。

## 新接口代码存在但线上仍 404

### 症状

- 仓库代码中能搜到新 API 路由。
- 线上访问仍返回 `404`。

### 判断方法

```bash
rg -n '<route-keyword>' /srv/nextjs-base/backend/app
curl -i http://127.0.0.1:38000/api/v1/<route>
curl -i https://base.example.com/api/v1/<route>
```

### 结论规则

- 本机 `127.0.0.1:38000` 也是 `404`：优先重启后端，进程可能仍是旧代码。
- 本机返回 `401`、`403` 或参数错误：路由已加载，继续排查权限、登录态或参数。
- 外网 `502` 且本机端口连不上：先恢复 FastAPI 进程。

## HTML 壳缓存导致旧 chunk 404

### 症状

- 页面 HTML 返回 `200`。
- 浏览器继续请求旧 `/_next/static/chunks/*.js`。
- 部署后出现白屏或 chunk `404`。

### 根因

Nginx/CDN/浏览器缓存了旧 HTML 壳，但服务端已切到新 Next 构建产物。旧 HTML 引用的 hash chunk 已不存在。

### 解决方案

- `/_next/static/*` 可强缓存。
- HTML 壳使用 `no-store` 或 `public, max-age=0, must-revalidate`。
- 不要对 HTML 壳使用代理层强缓存，除非具备自动 purge 或多版本静态资源共存。

## 长请求、SSE、音频流不要经 Next rewrite

### 症状

- 助手流式输出中断。
- TTS/STT 音频请求超时。
- 浏览器 Range 请求退化成完整下载或播放拖动异常。

### 根因

长请求和音频流经 Next.js 中间代理会增加超时、buffering、连接重置和 Range 头丢失风险。

### 解决方案

- `/api/v1/*` 直达 FastAPI。
- 对 SSE endpoint 关闭 `proxy_buffering`。
- 对音频/静态流透传 `Range` / `If-Range`。
- 设置足够的 `proxy_read_timeout`。

参考：`docs/deploy/nginx.bt.reference.conf`。

## HTTP（裸 IP/端口）演示部署下登录失败（2026-06）

部署到 `http://<IP>:<port>`（无 HTTPS）时登录会以两种方式失败，且都被 `127.0.0.1` 回环访问掩盖：

### A. Secure cookie 被浏览器丢弃 → refresh-token 401
- 根因：`AUTH_COOKIE_SECURE=true` 时会话 cookie 带 `Secure`，浏览器只在 HTTPS 下接受；HTTP 访问 cookie 被静默丢弃 → refresh 无凭据 → 401 → 踢回登录。
- 修复（仅 HTTP 演示）：`.env` 设 `AUTH_COOKIE_SECURE=false` 重启；**上 HTTPS 必须改回 true**。

### B. 受信代理密钥缺失 → "请求来源未通过受信代理校验"
- 根因：`trusted_proxy` 要求非回环来源带 `AOJ_PROXY_SHARED_SECRET` 头（前置代理注入）；前端服务未配该环境变量，`127.0.0.1` 自测命中回环白名单掩盖了缺口。
- 修复：把后端 `.env` 的同值密钥注入前端服务（systemd Environment），正式 nginx 形态由 nginx 注入同一头。

### 预防
演示部署不要只用 127.0.0.1 验证——回环白名单 + 同机 cookie 会掩盖这两类问题；必须用对外 IP 带 Origin 头复测登录全链路。
