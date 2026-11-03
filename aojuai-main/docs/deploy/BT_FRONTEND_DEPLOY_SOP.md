# BT Frontend Deploy SOP

适用于宝塔 Node 项目托管 `nextjs-base/frontend`。

示例占位：

- 前端项目名：`<BT_NODE_PROJECT_NAME>`
- 前端目录：`/srv/nextjs-base/frontend`
- Node bin：`/www/server/nodejs/<NODE_VERSION>/bin`
- Nginx 站点配置：`<BT_NGINX_FRONTEND_CONF>`
- 域名：`base.example.com`

## 核心结论

前端部署完成的标准不是“宝塔显示重启成功”，而是同时满足：

- `ss -ltnp` 能看到真实 `next-server` 监听端口。
- Nginx `location /` 的 `proxy_pass` 指向同一个端口。
- `https://base.example.com/` 和 `/login` 返回 `200`。
- `/api/v1/*`、`/health`、`/static/*` 仍由 Nginx 直达 FastAPI。

生产建议给 Next.js 配置稳定 `PORT`。如果继续使用 BT 随机端口，每次重启后必须同步 Nginx upstream。

## 标准流程

```bash
cd /srv/nextjs-base/frontend
/www/server/nodejs/<NODE_VERSION>/bin/pnpm build
/www/server/panel/pyenv/bin/python /www/server/panel/script/nodejs-service.py <BT_NODE_PROJECT_NAME> restart
/www/server/panel/pyenv/bin/python /www/server/panel/script/nodejs-sync-proxy.py <BT_NODE_PROJECT_NAME> 120
```

然后核对真实端口：

```bash
ss -ltnp | grep next-server
rg -n "location / \\{|proxy_pass http://127.0.0.1:" <BT_NGINX_FRONTEND_CONF>
nginx -t && nginx -s reload
```

## 随机端口 502 排查

典型故障：

- Next.js 实际监听在新端口。
- Nginx `location /` 仍指向旧端口。
- 域名返回 `502`。

处理顺序：

1. 用 `ss -ltnp | grep next-server` 找真实端口。
2. 检查 `<BT_NGINX_FRONTEND_CONF>` 的 `location /`。
3. 不一致时同步 Nginx upstream，不要继续盲目重启。
4. reload 后再验证域名。

如果 `nodejs-sync-proxy.py` 未同步，可使用宝塔内部配置刷新兜底：

```bash
/www/server/panel/pyenv/bin/python - <<'PY'
import os, sys, json
sys.path.insert(0, '/www/server/panel/class')
sys.path.insert(0, '/www/server/panel')
os.chdir('/www/server/panel')
from projectModel.nodejsModel import main
print(json.dumps(main().set_config('<BT_NODE_PROJECT_NAME>'), ensure_ascii=False, default=str))
PY
```

`set_config(...)` 只刷新前端 upstream，不会补回你手工维护的 `/api/v1/`、`/static/` 或缓存 location。

## 403 登录排查

如果部署后登录返回 `403`，优先检查 Nginx 后端直连规则是否被 BT 重写丢失：

```bash
rg -n "location \\^~ /api/v1/|location = /health|location \\^~ /static/|x-aoju-proxy-key|X-Forwarded-Proto" <BT_NGINX_FRONTEND_CONF>
```

正确结果：

- `/api/v1/` 直达 `127.0.0.1:<BACKEND_PORT>`。
- 后端 location 覆盖注入 `x-aoju-proxy-key`。
- 保留 `X-Forwarded-Proto $scheme`。
- 生产 `NEXT_ENABLE_BACKEND_REWRITES=0`。

登录 smoke test：

```bash
curl -sk -D - -o /tmp/login_probe.txt \
  -H 'Content-Type: application/json' \
  -H 'Origin: https://base.example.com' \
  -X POST https://base.example.com/api/v1/auth/login \
  --data '{"username":"_probe_","password":"_probe_"}'
cat /tmp/login_probe.txt
```

预期不存在测试账号时返回 `401`。如果返回 `403`，说明请求在账号校验前被代理/来源/CSRF 边界拦截。

## 验证

```bash
curl -I -k https://base.example.com/
curl -I -k https://base.example.com/login
curl -k https://base.example.com/api/v1/site/public-config
```

预期：

- 页面返回 `200`。
- public config 返回 `200`。
- Nginx 日志无持续 `502`。
