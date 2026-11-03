# BT Backend Deploy SOP

适用于宝塔 Python 项目托管 `nextjs-base/backend`。

示例占位：

- 后端项目名：`<BT_PYTHON_PROJECT_NAME>`
- 后端目录：`/srv/nextjs-base/backend`
- Python 虚拟环境：`<BACKEND_VENV>`
- 后端端口：`38000`
- 启动命令：`uvicorn app.main:app --host 127.0.0.1 --port 38000`

## 标准迁移和 seed

```bash
cd /srv/nextjs-base/backend
source <BACKEND_VENV>/bin/activate
alembic upgrade head
python -m scripts.seed_data
```
> **装了可选能力包时用编排命令**：`python -m scripts.capability db upgrade`
> —— 它先把 core 升到 head，再逐个把已安装的能力包升到各自链的 head，并校验每条链单 head。
> 裸 `alembic upgrade head` **只升 core**，能力包的表建不出来。
> （`aojubuilder/scripts/deploy.sh` 已做能力探测：分支里有 `backend/scripts/capability.py` 就自动改用它。）


说明：

- 生产不要依赖 `AUTO_INIT_DB=true` 或 `AUTO_SEED_DATA=true`。
- `seed_data` 应保持幂等，用于补齐菜单、角色、租户初始化数据。
- 有新迁移或菜单/权限变化时，先迁移，再 seed，再重启。

## 标准重启

```bash
/www/server/panel/pyenv/bin/python /www/server/panel/script/restart_project.py python <BT_PYTHON_PROJECT_NAME>
ss -ltnp | grep 38000
tail -n 80 /www/wwwlogs/python/<BT_PYTHON_PROJECT_NAME>/error.log
curl -I http://127.0.0.1:38000/
```

完成标准：

- `127.0.0.1:38000` 真实监听。
- 日志没有停在 traceback。
- `curl` 能连接到后端，根路径返回 `404` 也说明进程已监听。

## 新接口线上 404 排查

如果代码中已经存在新路由，但线上仍返回 `404`，先判断 uvicorn 是否加载了新代码，不要先改 Nginx。

```bash
rg -n '<route-keyword>' /srv/nextjs-base/backend/app
curl -i http://127.0.0.1:38000/api/v1/<route>
curl -i https://base.example.com/api/v1/<route>
```

判断：

- 本机直连 `127.0.0.1:38000` 也是 `404`：通常是后端进程未重启或未加载新代码。
- 本机直连已变为 `401`、`403` 或参数错误：说明路由已加载，继续排查登录态、权限、参数或业务逻辑。
- 外网 `502` 且本机 `38000` 连不上：先恢复后端进程。

## 宝塔提示成功但进程未运行

不要只信“重启成功”，直接看真实运行态：

```bash
ss -ltnp | grep 38000
ps -ef | grep 'uvicorn app.main:app' | grep -v grep
sed -n '1,120p' /www/server/python_project/vhost/scripts/<BT_PYTHON_PROJECT_NAME>_cmd.sh
```

如果应用本身没有代码错误，可以执行宝塔生成脚本兜底：

```bash
su -s /bin/bash www -c 'bash /www/server/python_project/vhost/scripts/<BT_PYTHON_PROJECT_NAME>_cmd.sh'
```

然后立刻复核监听、日志和 public config。

## 环境变量核对

涉及鉴权、Cookie、Nginx 代理头、分享页或公开页路由的变更，部署前核对：

- `CORS_ORIGINS` 包含生产域名。
- `AOJ_PROXY_SHARED_SECRET` 与 Nginx 注入值一致。
- `AUTH_COOKIE_SECURE=true`。
- `AUTH_COOKIE_SAMESITE` 与站点跨域策略一致。
- 前端生产环境 `NEXT_ENABLE_BACKEND_REWRITES=0`。

## 验收

```bash
curl http://127.0.0.1:38000/api/v1/site/public-config
curl -k https://base.example.com/api/v1/site/public-config
curl -k https://base.example.com/api/v1/auth/mine
```

预期：

- `site/public-config` 返回 `200`。
- 未登录访问 `auth/mine` 返回 `401`。
