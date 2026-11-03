# nextjs-base 公开版稳定基线

本文定义公开发行版必须保留的底座能力、合入准则和发布前检查项。

## 定位

`nextjs-base` 是多租户系统管理底座。它只内置跨模块、低业务耦合、可独立启动、可关闭、可测试的能力。

公开版保留：

- 个人设置、租户设置、系统设置。
- 租户、用户、角色、菜单、权限、团队和数据权限。
- AI 助手基础配置、通用会话、工具/技能治理和基础 UI 入口。
- 语音配置、provider catalog、试听和音色管理。
- 通知、站内消息、Message Channel、微信、飞书、Webhook。
- 注册、邀请、验证码、积分、操作日志、调度器、缓存降级、代理与安全头。

公开版不保留垂直业务页面、业务表、业务 prompt、业务 action executor、业务 adapter、分支治理记录或历史研究资料。

## 合入准则

可以合入 base：

- 身份、租户、RBAC、菜单、数据权限、设置页面的稳定性修复。
- 统一 API client、代理、错误处理、日志、缓存、调度器、安全头。
- 可被多个下游扩展复用的 assistant / speech / notification 基础协议。
- 不依赖业务表结构的测试、部署脚本和运行时硬化。

不应合入 base：

- 只服务单个垂直模块的页面、模型、路由、任务或文档。
- 业务 prompt、业务 tool、业务 action executor。
- 为某个实验分支临时放宽的权限、租户或数据边界。
- 未配置即会启动轮询、长连接或外部调用的默认任务。

## 经验规则

- 模块开关必须以后端 catalog 为真源头；前端菜单过滤只负责体验，后端守卫负责边界。
- 租户配置保存 canonical key；公开 API 需要兼容必要的 snake/camel 形态，但不能把历史扩展配置重新暴露出来。
- 菜单、权限和数据范围必须 tenant-aware；角色分配子菜单时应自动补齐父级菜单，避免前端树断层。
- 可选集成必须默认关闭或空配置降级；未配置第三方 provider 不得阻断启动、登录、菜单和租户设置。
- 调度任务必须显式开关控制；`MESSAGE_GATEWAY_TASKS_ENABLED` 默认关闭，但 Message Channel 配置能力完整保留。
- 正式部署以 Nginx 为唯一受信边界，`/api/v1/*` 直转 FastAPI 并注入 `x-aoju-proxy-key`；Next rewrite 不承接 API。
- BT / Nginx 部署中，随机端口同步、后端直连 extension、HTML 壳缓存和登录 `403` 排查应参考 `docs/deploy/README.md` 与 `docs/dev/issues/DEPLOYMENT_PROXY_PITFALLS.md`。
- 下游扩展应通过 adapter/plugin 接入底座，不能反向把业务语义写入 base。

## 发布检查

```bash
cd backend
python -m compileall -q app tests
python -m pytest tests/test_feature_switches.py tests/test_tenant_profile_config_safety.py tests/test_role_semantics.py -q

cd ../frontend
pnpm typecheck
pnpm build

cd ..
git diff --check
```

公开资料检查：

```bash
rg -n "<private-business-keywords>" README.md DOCS_MAP.md docs backend/README.md frontend/README.md NON_CODE_MANIFEST.md
```

预期结果是无公开文档命中；如命中，必须改写为通用“下游扩展/垂直模块”表述或移出公开版。
