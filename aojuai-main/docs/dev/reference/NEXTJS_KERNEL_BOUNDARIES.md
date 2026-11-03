# Next.js 主线内核边界

> 本文档是 `nextjs-base` / `nextjs-plugins` 的内核边界约定。
>
> 早期版本这里写着「项目级总规范以 `<repo-root>/spec/constitution.md` 为准」——
> **那个文件不存在**：全盘、git 全历史、所有分支都查过，从未存在。别再去找它。
>
> 现行规范来源就是本仓的三层文档：
> `docs/dev/guide_docs/`（代码级落地手册，最初建立 nextjs-base 的规范）、
> 本文与 `BASE_ARCHITECTURE.md`（架构与分层判据）、`docs/dev/flows/`（作业流）。

## 1. 分支角色

- `nextjs-base`
  - 当前内核规范基线。
  - 负责认证、租户、RBAC、菜单、路由契约、共享 hooks / components、共享后端 helper。
- `nextjs-plugins`
  - 当前插件整合主分支。
  - 负责模块接入、模板验证、整合回归、发布口径。
- `nextjs-<module>`
  - 独立插件源分支。
  - 负责模块快速演进，成熟后再并回 `nextjs-plugins`。
- `dev-base`
  - 历史来源，仅用于复盘与继承来源，不再作为现行主线事实来源。

## 2. 必须复用的共享内核

### 2.1 认证与租户

- `auth`、`users`、`roles`、`menus`、`teams` 等核心能力优先沉淀在 `nextjs-base`
- 模块不应绕过当前租户上下文、自建第二套角色菜单体系，或在前端维护独立菜单事实

### 2.2 语音基础层（speech）

- `speech` 是租户基础语音层，不是独立业务模块
- 规范入口：`/system/speech-settings`
- 兼容入口：`/speech` 系列路径仅保留历史兼容，不再承担独立导航职责
- 规范接口：
  - `/api/v1/speech/*`
  - `POST /api/v1/tenant/profile/settings/speech/preview-tts`
- 模块约束：
  - `audio` / `radio` / `chat` 等模块如需语音能力，只能在该基础层之上叠加模块默认值或交互体验
  - 不允许重新定义 Provider 层、重复维护租户级语音表单、或再造一套预览接口

### 2.3 分享公共内核（public_share）

- 位置：`backend/app/core/public_share.py`
- 目标：统一跨模块分享能力的最小公共语义
- 规范字段：
  - 优先使用 `token`
  - 优先使用 `expires_at`
  - 优先使用 `password_hash`
- 兼容别名：
  - `share_code` / `shareCode`
  - `publicToken`
  - `publicExpiry`
  - `expire_time`
- 模块约束：
  - 不同模块可以保留自己的业务表
  - 但公开访问、过期校验、密码校验、字段别名兼容应优先复用内核 helper，而不是复制一套实现

## 3. 设置页与菜单边界

- 租户级配置入口**目前没有声明式机制**：AI 与语音已折叠进 `/system/tenant-settings?tab=<code>`（legacy path 由 `menus.py` 的 `LEGACY_ROUTE_PATH_ALIASES` 映射），其余仍是独立页。
  新模块二选一即可，**不要照抄旧文档里“必须是 `/system/<module>-settings`”那条**。
- `menus.path` 必须与 Next.js App Router 实际页面路径一致
- 新菜单与权限必须**三写**（缺一条就会出现"只在某类环境缺菜单"）：
  - 全新部署 / 全库对账：seed
  - 已有租户升级：Alembic 数据迁移（内嵌不可变快照）
  - 运行时新建租户：建租户后调用同一个 reconciler
  三条链路共用 `backend/app/domain/menus/reconciler.py`，详见 `flows/MENUS_PERMS_DUALWRITE.md`

## 4. nextjs-plugins 的集成边界

- `nextjs-plugins` 可以接入尚未完全迁回的模块，但必须显式记录缺口
- 不允许用临时壳层文案掩盖真实能力缺失
- 不允许在 `nextjs-plugins` 中长期堆叠没有来源分支的大型功能
- 若模块能力应回落为基础能力，应先收口到 `nextjs-base`，再由插件分支复用

## 5. 最小验证闭环

每次治理至少检查：

- 菜单是否正确出现 / 隐藏
- 租户管理员与普通用户可见性是否正确
- 路由与 `menus.path` 是否一致
- 新装路径是否能通过 seed 获得完整菜单
- 升级路径是否能通过迁移补齐已有租户
- 共享能力是否被模块复用，而不是重复造轮子
