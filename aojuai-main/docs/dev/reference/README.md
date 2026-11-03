# reference

这里保存 `nextjs-base` 公开版的核心参考资料。内容必须描述底座事实，不记录业务分支路线图或垂直模块方案。

## 先读这两份（架构真源）

- `BASE_RELEASE_2026_08.md`：**本版基线**——回流了什么、共性教训对应哪条门禁、新分支起手式
- `WORKER_AND_AGENT_LOOP.md`：worker 三层设计与 PDCA/OODA 宏循环；与 pi 的对照、harness 的走向建议
- `BASE_ARCHITECTURE.md`：**唯一的架构真源**——kernel / base capability /
  optional pack / sample 四层的**可执行准入判据**、逐能力归类、迁移分层、装配契约。
- `NEXTJS_KERNEL_BOUNDARIES.md`：内核边界（认证/租户/语音基础层/public_share/菜单）。

## 推荐阅读

- `AUTH_SECURITY_BASELINE.md`：认证、会话、可信代理和分享页安全头基线。
- `DB_MIGRATION_BASELINE.md`：数据库新装、迁移和 seed 边界。
- `IMPORTANT_DEV_VIOLATIONS.md`：开发违规记录（历史，引用的是当时下游分支的文件）。
- `frontend/FRONTEND_BASELINES.md`：Next.js 前端基线。
- `assistant/ASSISTANT_MODULE_INTEGRATION_PLAYBOOK.md`：助手模块接入 playbook。
- `assistant/ASSISTANT_PUBLISHED_ROUTE_WORKFLOW.md`：助手公开路由工作流。
- `message-channel/MESSAGE_CHANNEL_BOUNDARY.md`：个人 Message Channel、系统网关和助手入口边界。

## 某一轮的记录（想知道"为什么是现在这样"时看）

- `BASE_REVIEW_2026_08.md`：2026-08 架构复盘——发现了什么、怎么判、怎么处置。
- `BASE_CHANGELOG_2026_08.md`：那一轮的行为变化与新增工具。
- `BASE_VERIFICATION_2026_08.md`：真机验收记录，**含明确列出的"没做的验证"**。

新增 reference 文档前先判断是否属于公开底座；如果依赖垂直业务语义，应留在私有文档或下游扩展仓库。
- `TASK_QUEUE_TOP_LEVEL_DESIGN.md`：任务队列 L0 顶层设计（交付语义、租约、所有权栅栏、公平认领；回流自 nextjs-plugins，代码在 `app/core/task_queue.py`，worker 通过 `WorkerDefinition.queue` 声明）
- `LLM_OUTBOUND_REDACTION.md`：把数据发给外部模型之前的去标识化设计——allowlist 姿态、四层结构、假名化与还原、出站守卫与红队语料（实现在 `app/core/redaction/`，回流自 下游日报分支）
