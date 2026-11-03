# BT Nginx Cache SOP

适用于宝塔 Nginx 托管 Next.js 前端和 FastAPI 后端的公开版部署。

## 缓存分层

推荐把缓存分成三层：

- `/_next/static/*`：Next 构建静态资源，hash 命名，可长缓存。
- 前端 `public` 中的稳定静态资源：如 `/favicon.ico`、`/logo.svg`、`/vendor/*`，可短缓存。
- HTML 壳：登录页、管理页、公开页，不做代理层强缓存，至少必须回源校验。

## 为什么不缓存 HTML 壳

Next.js HTML 会引用当前构建生成的 `/_next/static/chunks/*.js` 和 CSS。若代理层继续返回旧 HTML，但服务器已切到新构建，就会出现：

- 页面 HTML 返回 `200`。
- 浏览器请求旧 chunk。
- 旧 chunk 不存在，页面白屏或静态资源 `404`。

所以默认策略：

- `/_next/static/*` 强缓存。
- HTML 壳使用 `no-store` 或 `public, max-age=0, must-revalidate`。
- 只有具备自动 purge、多版本静态资源共存或原子发布能力时，才考虑缓存 HTML。

## 推荐片段

```nginx
location ^~ /_next/static/ {
    alias /srv/nextjs-base/frontend/.next/static/;
    add_header Cache-Control "public, max-age=31536000, immutable" always;
    access_log off;
}

location = /favicon.ico {
    root /srv/nextjs-base/frontend/public;
    add_header Cache-Control "public, max-age=86400, stale-while-revalidate=604800" always;
    access_log off;
}

location = /logo.svg {
    root /srv/nextjs-base/frontend/public;
    add_header Cache-Control "public, max-age=86400, stale-while-revalidate=604800" always;
    access_log off;
}

location ^~ /_next/ {
    proxy_pass http://127.0.0.1:<FRONTEND_PORT>;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
}

location / {
    proxy_pass http://127.0.0.1:<FRONTEND_PORT>;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_no_cache 1;
    proxy_cache_bypass 1;
    proxy_hide_header Cache-Control;
    add_header Cache-Control "no-store" always;
}
```

不要让 `public` 静态资源规则拦截后端 `/static/*`。`/static/*` 属于 FastAPI，应在后端直连 location 中处理。

## 验证

```bash
curl -I -k https://base.example.com/_next/static/chunks/<chunk>.js
curl -I -k https://base.example.com/favicon.ico
curl -I -k https://base.example.com/
```

预期：

- Next chunk：`Cache-Control: public, max-age=31536000, immutable`。
- public 稳定资源：短缓存。
- HTML：`no-store` 或 `max-age=0, must-revalidate`。

## 与 BT 随机端口共存

`nodejs-sync-proxy.py` 或 `set_config(...)` 通常只会更新 `location /` 的 upstream，不会恢复你手工添加的缓存 location，也不会恢复后端直连 location。

如果 BT 重写了主配置：

1. 先恢复后端直连片段，参考 `nginx.bt.backend-routes.extension.conf`。
2. 再恢复 `/_next/static/*` 和 public 静态资源直出。
3. 最后同步 `location /` 到真实前端端口。
