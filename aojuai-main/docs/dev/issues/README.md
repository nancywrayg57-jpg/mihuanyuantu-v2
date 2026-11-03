# issues（问题/踩坑库）

> 目标：把开发过程中遇到的问题沉淀为团队可复用知识，而不是散落在聊天记录里。
>
> 使用原则：**按类别累计**，每条问题必须可检索、可复现、可修复、可预防。

## 1) 什么时候应该写入 issues

- 遇到“第一次就解决了但未来会再遇到”的问题
- 遇到“环境/依赖/迁移/seed/权限/路由”导致的系统性问题
- 遇到“只有某类租户/某类环境才出问题”的不一致

不建议写：
- 一次性的业务需求讨论
- 无法复现/没有结论的猜测

## 2) 如何写一条问题（模板）

建议每条问题按以下结构追加：

```
## <标题：症状 + 关键关键词>

### 症状
- ...

### 触发条件
- 环境/租户/角色/接口/页面

### 根因
- ...

### 解决方案
- ...

### 如何预防（应该补到哪里）
- checklist / guide_docs / skills（选一个或多个）
```

## 3) 分类文件（按优先级）

- `DEVBASE_PITFALLS.md`：跨模块通用坑（高频）
- `ENVIRONMENT.md`：本地环境/依赖/端口/工具链
- `DEPLOYMENT_PROXY_PITFALLS.md`：生产部署、BT、Nginx、rewrite、缓存、代理链路
- `SPEECH_PROVIDER_PITFALLS.md`：语音 provider 切换、握手错误、租户配置和运行态问题
- `MIGRATIONS_SEED.md`：迁移/seed/数据迁移
- `PERMISSIONS_MENUS.md`：RBAC、菜单、动态路由、perms
- `BACKEND.md`：后端运行时/ORM/事务/性能
- `FRONTEND.md`：前端构建/路由/组件问题
- `FRONTEND_I18N_PITFALLS.md`：多语言外置/SSR/分支合并漏译/代理批量改造的坑
- `TESTING.md`：测试相关（pytest/异步/fixture）

## 4) “问题 → 规范化”的闭环（推荐）

当一个问题具有普遍性：

1. 先写入对应 `issues/*.md`
2. 若能形成可验收的规则：
   - 同步补到 `checklists/DEV_CHECKLIST.md`
3. 若需要形成可复用写法：
   - 同步补到 `guide_docs/*`
4. 若可以形成可执行套路：
   - 同步补到 `docs/dev/skills/*`

> 这就是“开发链路治理”，不是为了复盘而复盘，而是为了减少下次成本。
- `MODEL_GATEWAY_BEHAVIOR.md`：模型网关实测行为（非流式 ~125s 断开窗、流式 strip bug、responses 参数拒绝、缓存最小前缀与并发路由不粘、temperature 策略、探针方法）
- `SQLITE_LIGHTWEIGHT_DEPLOY_PITFALLS.md`：SQLite 轻量部署（aiosqlite ≥0.22 退出卡死的上游根因与 NullPool/dispose 方案、create_all 撞重复租户索引、PortableJSON/PortablePK 与双方言写法）
- `HARD_UNINSTALL_GAPS.md`：硬卸载三态（缺一部分 = 部署残缺必须炸）、前缀映射保留已卸载模块以 fail-closed、真删探针与 API 契约比对方法（回流自 nextjs-plugins，模块名为那边实测）
- `QUEUE_L0_ROLLOUT_RETROSPECTIVE_20260822.md`：队列 L0 落地与两日集中审查复盘（失败类与护栏；回流自 nextjs-plugins）
- `CREDITS_BILLING_PITFALLS.md`：积分计费稳定坑（并发旧快照、嵌套双计、预留只退不追、僵尸回收；回流自 nextjs-plugins）
- `SERVICE_DECOMPOSITION_PIPELINE.md`：巨型 Service 安全拆分管线（分片 / late-binding / 逐片零回归 / 进程真的加载了新代码；回流自 nextjs-plugins，实例为 ppt-master）
