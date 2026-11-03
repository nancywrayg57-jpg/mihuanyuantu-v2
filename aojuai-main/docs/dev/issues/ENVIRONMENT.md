# 环境与部署配置问题

> 累计"环境变量 / 配置读取 / 多实例共享中间件"类问题。

## 1. 配置一律走 Settings，不许读 `os.environ`

**踩过的坑**：环境变量明明写进了 `.env`，服务里读出来是空。

**根因**：部署脚本 `manage.sh` 只 `source .env`（设 shell 变量，**不 export**），
子进程的 `os.environ` 里根本没有这些值；而 pydantic settings 是直接读 `.env` 文件的。

**做法**：所有运行时配置加到 `backend/app/core/config.py` 的 `Settings`，
业务代码只读 `settings.X`。这条规则要有扫全仓的 AST 检查
（识别 `os.environ`、`os.getenv` 以及 `from os import getenv` 这类 alias），
只允许 `config.py` 内部与显式 allowlist。

**已经复发过一次**：规则在 media 模块踩坑后定下并加了测试，
但测试硬编码了模块名单，于是 `transform` 的导出目录又原样犯了一次。

## 2. 同机多实例共享 Redis，key 没有命名空间

**现象**：两个分支的部署实例互相串缓存，改 A 的数据 B 也变了。

**做法**：所有 Redis key 由统一的 cache adapter 自动加实例 namespace；
禁止在 adapter 之外直接调 Redis client；测试不许连部署配置里的真实 Redis。

### 2.1 实例：无命名空间缓存键跨实例投毒（回流自 nextjs-plugins <commit>，2026-07-18）

### 症状
- dev 实例（<db-name>）管理员登录后仅见 4 个顶级菜单，且出现本库根本不存在的
  "Shopify 管理"菜单；模块开关、menus 表、role_menus 检查全部正常。

### 触发条件
- 本机 8+ 个 AOJU 实例（autubuild 各分支 + dev）全部 REDIS_DB=0 共享同一 Redis；
- 运行时缓存键形只含业务 id（如 `menu_routes:tenant:1:user:1:super:1:scope:<权限摘要>`），
  各实例都有 tenant 1/user 1/超管，权限摘要相同（*:*:*）时键完全相同。

### 根因
- `runtime_cache.py` 与 `cache/redis.py` 两个缓存收口点写入的键无实例命名空间——
  先写者投毒，后读者（TTL 内）拿到其他产品实例的菜单/开关/租户配置缓存。

### 修复/预防
- 已修（2026-07-18）：两个收口点统一加 `ns:<CACHE_NAMESPACE>:` 前缀；
  `CACHE_NAMESPACE` 默认取 `DB_NAME`（每实例唯一），可用 `AOJU_CACHE_NAMESPACE` 显式覆盖。
  见 `tests/test_cache_namespace.py`。
- 注意：本修复只随本分支代码生效；其他分支实例互相之间仍会碰撞，需各分支回流同类修复
  （或部署时为每实例设不同 REDIS_DB）。
- 残留未命名空间的 Redis 使用（键含哈希/随机成分，碰撞概率低但存在）：openai_client 的
  sticky_session、message gateway advisory lock——后续随模块迭代收口。
- 排查口诀：接口返回了"本库不存在的数据"→ 先查共享 Redis 缓存键，再查数据库。

## 3. 连接池参数硬编码

原来 `pool_size=10 / max_overflow=20` 写死在 `session.py`，高并发部署没法调。
现已参数化为 `DB_POOL_SIZE / DB_MAX_OVERFLOW / DB_POOL_TIMEOUT / DB_POOL_RECYCLE`
（走 Settings，带上下限）。

## 4. 生产不能隐式降级成 mock

无可用 SMTP 时不要静默用 MockSender 返回"成功"——用户以为发出去了。
production 必须 fail closed，开发态才允许 mock。

同理，SMTP 的"租户配置 → 系统配置"回落**只发生在配置解析阶段**：
一旦开始投递，失败了不许现场换另一套 SMTP 重试，否则可能重复发送、发件身份还变了。

## 5. 密钥轮换

`PROVIDER_SECRET_KEY` 若缺省回退到 JWT secret，轮换 JWT 会导致所有加密的租户凭据
解不开。生产必须配置独立且稳定的 key。

## 6. 部署与运维实例（回流自 nextjs-plugins，2026-06～08 实测；实例名为那边的模块）

### 6.1 宝塔 restart_project 报"重启成功"但进程未重启（前端/后端均会发生）

### 症状
- 执行 `/www/server/panel/script/restart_project.py python backend`（或 nodejs 项目）输出"重启项目成功"
- 但 `ss -tlnp` 显示监听端口的进程 PID 不变、`ps -o lstart` 启动时间是数周前
- 新部署的代码（新路由/新模块）404 或行为是旧版本

### 触发条件
- 宝塔面板 Debian 环境，python/nodejs 项目长期运行后

### 根因
- 宝塔 restart 脚本对已脱管的旧进程不生效，但仍返回成功；旧进程继续持有端口

### 修复
1. `kill <旧PID>`（nodejs 项目宝塔守护会自动拉起；python 项目不会）
2. python 项目 kill 后必须再执行一次 restart_project.py 才会真正启动新进程
3. 重启后必须验证：`ps -o lstart -p <新PID>` 启动时间是刚才，且 `curl` 新路由可达

### 预防
- 部署 SOP 中"重启"步骤后强制加 PID/启动时间校验，不要信任脚本输出


### 6.2 HTTP（裸 IP/端口）部署下登录失败的两个新坑（2026-06）

部署到 `http://<IP>:<port>`（无 HTTPS、无 nginx）做演示时，登录会以两种方式失败，且都被 `127.0.0.1` 回环访问掩盖：

### A. refresh-token 401 / 登录后被踢回
- 根因：`AUTH_COOKIE_SECURE=true` 时会话 cookie 带 `Secure` 标记，浏览器只在 HTTPS 下接受；HTTP 访问时 cookie 被静默丢弃 → 后续 refresh 无凭据 → 401。
- 修复（仅 HTTP 演示环境）：后端 `.env` 设 `AUTH_COOKIE_SECURE=false` 重启。**上 HTTPS 正式形态后必须改回 true**（refresh cookie 是 7 天凭据，不该跑明文）。

### B. "请求来源未通过受信代理校验"（ForbiddenError）
- 根因：后端 `trusted_proxy` 要求非回环来源的 `/api/v1` 请求带共享密钥头（`AOJ_PROXY_SHARED_SECRET`，由前置代理注入）。Next 的 App Route 代理支持注入，但前端服务没配该环境变量；用 `127.0.0.1` 自测时命中 loopback 白名单，掩盖了缺口，浏览器从公网 IP 访问才暴露。
- 修复：把后端 `.env` 的同值密钥注入前端服务（systemd `Environment=AOJ_PROXY_SHARED_SECRET=...`）并重启。正式 nginx 形态由 nginx 注入同一密钥头（这才是该机制的设计用法）。

### 通用预防
- **演示部署不要只用 127.0.0.1 验证**：回环白名单 + 同机 cookie 会掩盖 Secure-cookie 和受信代理两类问题；必须用对外 IP（带 `Origin` 头）复测登录全链路。


### 6.3 独立 worker 进程（harness/ppt_master 等），不随 uvicorn --reload 热更新

### 症状
- 改了 harness 域代码后行为不变（如推断修复"无效"、或租户未配模型时任务 0.09 秒"完成"却是旧逻辑）。

### 根因
- 异步任务由 `python -m app.tasks.harness_worker` 独立进程执行，代码在其启动时加载；
  uvicorn --reload 只热更新 API 进程。

### 修复/预防
- 改动 harness/assistant 域代码后必须重启 worker（dev：kill 后
  `nohup python -m app.tasks.harness_worker --concurrency 2 > run/harness_worker_dev.log &`）。
- 评测/验收前先确认 worker 启动时间晚于最后一次代码改动。


### 6.4 同机多实例：pkill -f 宽模式会误杀其他实例的同名进程

### 症状
- dev 上 `pkill -f "app.tasks.harness_worker"` 连带杀掉了 autubuild 生产实例的 worker
  （所有实例进程命令行完全相同）。

### 修复/预防
- 重启某实例的 worker 一律先 `pgrep -af` 列出并核对 `/proc/<pid>/cwd`，用**精确 PID** kill；
  禁止对共享命名的进程用 pkill -f 宽模式。
- worker 是队列制（claim_pending），误杀后重启即恢复，任务只延迟不丢；
  恢复时务必 cd 到该实例自己的 backend 目录再拉起（读对 .env）。


### 6.5 next start 重启时端口被旧进程占用导致新旧混跑（页面随机报"页面出错"）

### 症状
- 前端页面（如 /system/tenant-settings）客户端报"发生了一个未处理的错误"，SSR 却 200
- run_frontend.log 里有一条被忽略的 `Error: listen EADDRINUSE: address already in use`

### 触发条件
- rebuild 后重启：kill 旧进程未生效（PID 抓错/进程名不匹配），新进程启动失败退出，
  旧进程继续服务——**旧 server 代码 + 新 .next 客户端 chunk 混跑**

### 根因
- next start 的 server 模块启动时加载，客户端 chunk 按新构建下发，两者 manifest 不一致

### 修复
- 重启后必须验证：`ss -tlnp` 取监听 <port> 的真实 PID，`ps -o lstart` 确认启动时间
  **晚于** `.next/BUILD_ID` 的 mtime；只 curl 一个 200 不构成重启成功的证据

### 预防
- 重启脚本先 kill 监听端口的 PID（从 ss 取），确认端口释放后再启动


### 6.6 「改了代码不生效」的三种形态（2026-08-17 连踩三次）

### 症状
三次都表现为**代码改了、测试全绿，但实际行为还是旧的**，且都不报错：

1. 前端跑的是旧 build——改了 .tsx 没重新 build，页面上完全看不到新功能。
2. `uvicorn --reload` 监视了产物目录。启动命令是裸 `--reload`，
   而 ppt-master 把生成产物写在 `backend/run/` 下：每写一个 SVG 就触发一次重载，
   **把正在跑的进程内生成任务当场杀掉**。症状极具迷惑性——任务会"成功"，
   只是页数莫名变少（6 页请求最后只出 1 页），日志随进程重启丢光，
   看起来像模型接口不稳定。
3. 一个工具看不见的 worker 用旧代码跑了 3 天。
   `app/tasks/{ppt_master,harness,agent}_worker.py` 各有自己的入口模块和轮询循环，
   没法用 `WorkerDefinition(task_source_factory=...)` 表达，所以不在
   `deploy/workers.json`——于是 `dev_services.sh` 完全不认识它们，
   doctor 显示一切正常，任务却全被旧进程接走。

### 根因
"进程持有的代码版本"没有单一权威来源：前端看 build 产物、后端看 reload watcher、
worker 看进程启动时间，三套机制互不知情，任何一处漏掉都表现为静默用旧代码。

### 修复/预防
- **验证任何东西之前先跑 `scripts/dev_services.sh doctor`。** 三次里有两次
  工具其实已经标了"旧代码"，是人没看。
- 后端用 `scripts/dev_services.sh backend-restart` 拉起，带 `--reload-exclude`
  排除 `run/` 等产物目录。
- `EXTRA_WORKERS` 登记了三个清单外的独立 worker，status/doctor/restart 都覆盖。
- 前端新鲜度改为查两件事：`.next/BUILD_ID` 是否新于源码（改了没 build）、
  进程是否新于 BUILD_ID（build 了没重启）。只比进程时间会假绿。

### 另外两个坑
- **`worker-restart` 曾可能杀掉同机其它实例。** `worker_pids` 原来只按命令行
  匹配，而同机多实例命令行完全相同（本文档上一节记的就是这个事故）。
  现已按 `/proc/<pid>/cwd` 过滤到本 checkout，且改为先 TERM 等 10 秒再 KILL。
- **别在 `next build` 的同时跑后端测试。** `test_gov_00_scanner_coverage` 会在
  `frontend/src/app/(app)/` 下临时创建 `_mutation_probe/page.tsx` 再删掉，
  构建正好扫到就会失败在一个"文件不存在"的诡异报错上。串行跑。
