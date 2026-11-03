# Assistant Module Integration Playbook

本文定义下游扩展接入 `nextjs-base` AI 助手 foundation 的最小路径。它只描述通用 assistant contract，不描述任何业务模块语义。

## 目标

- 新模块通过 adapter 接入助手，而不是 fork dock、prompt 和执行链。
- base 负责通用 runtime、配置、权限边界、capability、tool 和 action protocol。
- 下游扩展只负责自己的 adapter、业务 skill、业务 prompt、业务 action executor。

## 分层

1. 路由发布层：从真实 API/schema 中人工挑选可暴露能力，默认拒绝，不自动公开。
2. 模块适配层：模块实现 context、presets、capability source、action canonicalize、execute action。
3. 全局规划层：base 从入口路由、会话记忆和本轮用户消息解析有效执行范围。
4. Prompt contract 层：base 将大上下文压缩成模型可理解的最小结构。
5. 执行回写层：base 统一管理 tenant/user/data scope、prior action、prior execution 和结果摘要。

## 最小接入顺序

1. 新增模块 adapter。
2. 先实现只读 `get_context` 和 `get_presets`。
3. 用 `scan_api_route_drafts(...)` 扫描候选 API。
4. 人工筛选后写入模块自己的 publish manifest。
5. 用 `assistant_tool(...)` 和 `assistant_tool_execution_binding(...)` 形成已发布工具和执行绑定。
6. 注册 `AssistantModuleToolsetSpec` 和 `AssistantCapabilityProviderSpec`。
7. 接入 `get_capability_source`。
8. 需要写操作时，再实现 `canonicalize_action` 和 `execute_action`。

如果模块暂时没有真实写入执行器，只发布 query / preview 工具，不要把 mutation 暴露成可执行动作。

## Adapter 规则

`get_context` 应返回：

- 当前页面 scope。
- 当前对象摘要。
- 当前筛选条件。
- 当前 route 绑定信息。

不应返回：

- 全页大表格。
- 无上限列表。
- 原始接口响应全文。
- 与当前用户权限无关的数据。

`execute_action` 必须：

- 在服务端执行。
- 走真实 permission、tenant、data scope。
- 不信任前端传来的越权 route 或对象 ID。
- 不在纯对话阶段假执行写操作。

## 全局执行规则

网页助手、`/assistant` 文本入口和个人 Message Channel 应共用同一条执行路径：

1. 从入口路由、会话记忆和用户消息解析 `activeRoutePath` / `activeModuleCode`。
2. 优先使用模块发布的 execution manifest 匹配可执行意图。
3. 找不到明确工具意图时，再退回 route directory 做页面定位。
4. 按有效路由加载 adapter context 和 capability source。
5. 只允许当前 `toolCatalog` 中 `available=true` 的工具进入 `assistantAction`。
6. 只读 query 工具可在治理允许时自动执行；mutation、缺字段或高风险动作必须确认或澄清。

不要在 `AssistantService` 中新增“用户说某个词就调用某个工具”的业务关键词规则。业务能力应通过 adapter、tool schema、capability provider、operation policy 和真实 executor 表达。

## Prompt contract

默认 prompt context 保留：

- 当前 scope。
- 当前用户 query。
- 当前对象摘要。
- 当前角色 profile。
- 可用工具目录窗口。
- blocked intent catalog。
- operation policy。
- capability summary。
- 必要治理规则。

默认不放入：

- 长权限数组。
- 原始大 JSON。
- 全量表格数据。
- 展示态冗余字段。

## Follow-up 规则

连续对话依赖两类摘要：

- `priorAction`：上一轮结构化动作意图。
- `priorExecution`：上一轮真实执行事实。

如果上一轮执行事实足够支撑当前追问，可以沿用；如果当前追问仍有多个合理解释，应要求澄清。不要在后端硬编码业务短语来替代模型澄清。

## Shared Context 方向

下游分支已经验证出一条通用方向：模块上下文不能只是一段自然语言摘要，应尽量收敛到稳定结构。base 当前不强制同名文件，但新模块 adapter 建议优先提供这些公共字段：

- `currentActor`：当前登录用户、租户、团队可读范围、角色画像和模块身份。
- `moduleState`：当前模块、scope、能力统计、资源分组和生命周期摘要。
- `relationshipState`：当前业务对象、对象关系、操作者引用和继承规则。
- `toolGraph`：当前模块工具按资源、读写模式和依赖关系形成的执行图。

如果后续把下游的 `context_contract.py` 回迁到 base，应先补测试，确保网页助手、全局文本入口和 Message Channel 三种入口拿到同一套结构化上下文。

## Capability Index 方向

当前 base 已有 `capabilityManifest`、`capabilitySummary` 和瘦身后的 `toolCatalog`。如果继续回迁下游的 indexed capability discovery，规则应保持：

- `apiIndex` 只用于发现候选后端路由，不作为执行入口。
- `toolIndex` 是轻量全量工具索引，用于语义检索和规划。
- `toolCatalog` 是当前轮高相关工具的详细契约窗口，不能无限膨胀。
- `executionStatus=discoverable_only` 的路由不能输出为 `assistantAction.toolId`。
- 只有注册到 `AssistantModuleToolsetSpec` 且通过权限、scope、skill governance 的工具才能执行。

这类能力可以作为底座开发方向，但不能只靠文档声明。回迁时必须同步代码、单元测试和 prompt context 体积回归。

## Base 与下游边界

适合留在 base：

- prompt context 压缩。
- follow-up 状态摘要。
- 通用 action protocol。
- capability / governance 公共层。
- route compiler / published route workflow。
- toolset registry / capability provider registry。
- 全局文本入口和 Message Channel 共用的 planner。
- 默认 adapter 和默认 tools。
- 测试基线。

留在下游扩展：

- 业务模块页面词汇。
- 业务角色映射。
- 业务 prompt pack。
- 业务 tool catalog。
- 业务 action executor。
- 依赖业务表结构的测试。

## 验收基线

每个接入模块至少验证：

1. context 接口返回正确 scope。
2. presets 接口返回模块预设。
3. chat / stream 注入 capability block。
4. prompt 使用瘦身后的 context。
5. prior action / prior execution 进入 follow-up。
6. 写操作只在显式执行后发生。
7. 服务端权限和数据范围能拦截越权动作。
