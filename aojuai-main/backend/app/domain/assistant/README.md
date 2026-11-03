# Assistant Module Onboarding

维护者版接入 playbook：`docs/dev/reference/assistant/ASSISTANT_MODULE_INTEGRATION_PLAYBOOK.md`。

## Scope

`assistant` 是 AOJU 的内部 AI 助手底层，不是一个直接暴露后端接口的公共集成层。

底层只负责两件事：

- 给各业务模块提供统一的助手接入边界
- 给模块提供“自发现候选接口 -> 人工发布 -> 进入能力目录”的合规路径

默认拒绝。后端存在的 API、service、schema 不等于自动暴露给 AI。

## Stable Boundary

`base` 层负责：

- 会话、消息、权限、租户、用户上下文
- 统一的模块适配器入口
- 全局文本入口的模块 / 路由 / 工具规划
- 页面聊天与 Channel 聊天共享同一套执行路径
- 提示上下文瘦身 `prompt_context.py`
- 连续追问的上一轮动作 / 上一轮执行摘要注入
- 助手能力描述结构 `tool_schema.py`
- API 候选扫描与 publish 编译 `route_compiler.py`
- publish-based 治理约束

业务模块负责：

- 当前页面 / 当前对象上下文加载
- 模块提示词与角色语义
- 模块级提示上下文裁剪
- 哪些路由允许被发布给 AI
- 对发布后工具的字段语义修正
- 服务端动作执行

## Global Execution Runtime

AI 助手现在按全局执行框架处理每一轮对话，网页聊天和个人 Channel 不再分成两套业务逻辑：

1. 从入口路由、会话记忆和本轮用户消息解析有效执行范围。
2. 优先使用模块发布的 `get_execution_manifest()` 匹配可执行意图。
3. 找不到明确工具意图时，再退回路由目录做模块 / 页面定位。
4. 按有效路由加载对应 adapter 的 `get_context()` 与 `get_capability_source()`。
5. 只允许 `toolCatalog` 中可用的工具进入 `assistantAction`。
6. 对 `autoExecute=true` 的只读 query 工具自动执行，并把真实结果作为回复。
7. 写入、确认、缺字段或不可用工具只返回待确认 / 澄清动作，不自动执行。

这意味着 Channel 会话不依赖浏览器 URL。它会保留入口路由为 `/message-channel`，但每轮会在内部解析 `activeRoutePath` 和 `activeModuleCode`，后续追问默认沿用该执行范围；当用户明显切换模块时，本轮重新规划并覆盖执行范围。

模块不要在 `AssistantService` 里增加 `if 用户说 X 就调 Y` 的硬编码。正确做法是把能力注册到模块 adapter：

- `get_execution_manifest()`: 轻量声明模块意图、示例、目标路由和默认 tool。
- `get_capability_source()`: 声明当前账号在当前路由可用的 `toolCatalog`、角色和治理策略。
- `execute_action()`: 在真实 tenant / user / permission / data scope 内执行服务端动作。

只有同时满足 `get_execution_manifest()` 规划到工具、`toolCatalog` 当前可用、且治理未拦截时，助手才会执行工具。这样“查询我的积分”“统计当前用户数”这类纯文本请求可以在网页和微信 / 飞书 Channel 中得到同一套结果。

## Self-Discovery Path

新增一个业务模块后，不再手工散落维护 prompt 和接口说明，而是走固定链路：

1. 模块先接入 `ModuleAdapterBase`
2. 用 `scan_api_route_drafts(...)` 扫描该模块相关 FastAPI 路由
3. 产出候选路由草案，人工筛选后写入模块自己的 `route_manifest.py`
4. 用 `build_published_route_tools(...)` 编译成 assistant tool schema
5. 用 `lint_published_route_manifest(...)` 检查字段描述、示例、权限依赖是否合格
6. 只有 publish 过的工具，才允许进入模块的 `toolCatalog`

这条路径解决的是“自发现”，不是“自动暴露”。

## Prompt Contract Rule

`base` 已把助手提示词收口为两层：

- runtime context
  - 完整服务端上下文，供页面和动作执行使用
- prompt context
  - 传给模型的瘦身契约，只保留当前对象摘要、角色语义、工具字段语义和必要治理规则

新模块默认应复用 `ModuleAdapterBase.build_prompt_context(...)`。
只有当模块有明显更好的压缩方式时，才覆盖这个方法。

默认 prompt context 优先保留：

- `scope`
- `query`
- `currentRoleProfile`
- `currentProject/currentApp/currentDocument/...` 这类当前对象摘要
- `toolCatalog`
- `blockedIntentCatalog`
- `operationPolicy`
- `capabilitySummary`

默认不应该直接塞进模型提示词：

- 大列表数据
- 冗余统计
- 原始 API 响应全文
- 长权限数组
- 前端展示态 JSON
- 一整页表格内容

连续追问时，`base` 会自动注入：

- `priorAction`
- `priorExecution`

模块不要自己再重复拼接“上一轮动作历史”，否则 prompt 会重新膨胀。

## Recommended Module Layout

当一个模块准备接入 AI 助手时，建议至少形成这些文件：

- `<module>/assistant/adapter.py`
- `<module>/assistant/catalog.py`
- `<module>/assistant/route_manifest.py`

职责边界：

- `adapter.py`: 负责模块上下文、预设、能力源、动作执行
- `catalog.py`: 负责模块对外暴露的 tool catalog 组织
- `route_manifest.py`: 负责 publish 过的 API 路由清单

如果模块还没有准备好上线写操作，可以只发布 query / preview 工具。

## Adapter Contract

最小接入只需要实现：

- `get_context`
- `get_presets`
- `execute_action`

建议同时补齐：

- `get_capability_source`
- `canonicalize_action`
- `build_prompt_context`

推荐理解如下：

- `get_context`
  - 服务端当前页面真实上下文
- `get_capability_source`
  - 当前页面允许 AI 使用的工具面和角色语义
- `build_prompt_context`
  - 把前两者压缩成模型能稳定理解的轻量契约
- `canonicalize_action`
  - 只做安全规范化，不做业务意图猜测
- `execute_action`
  - 严格在 tenant / user / permission / data scope 内执行

`canonicalize_action` 允许做：

- route 绑定 ID 回填
- 危险字段剔除
- tool 可用性校验
- 参数规范化

`canonicalize_action` 不应该做：

- 把“继续”硬编码成“下一页”
- 把模糊问题偷偷放宽成“全部查询”
- 把用户想法改写成另一个业务动作
- 用后端规则替代模型澄清

## Registry-Based Discovery

业务分支接入时，优先把已发布接口编译成 `AssistantModuleToolsetSpec`，再用 `AssistantCapabilityProviderSpec` 发布到能力目录：

- `toolset_registry.py` 只保存模块发布过的工具 schema 和可选执行 binding。
- `capability_registry.py` 负责按路由 scope、权限和工具状态生成当前可见 `toolCatalog`。
- `execution_manifest.py` 会从 capability provider / toolset 自动生成 planner 可用的 intents。
- `execution_planner.py` 统一处理网页入口、`/assistant` 文本入口和 `/message-channel` Channel 入口。

因此新增业务能力的默认路径不是改通用 prompt，也不是在 `AssistantService` 写关键词规则，而是：

1. 用 `route_compiler.py` 扫描 FastAPI 路由生成候选草案。
2. 人工筛选后发布 manifest，编译为 `AssistantToolSchema`。
3. 注册 `AssistantModuleToolsetSpec` 和 `AssistantCapabilityProviderSpec`。
4. 模块 adapter 只实现上下文、权限语义和实际执行。

底座只负责发现、治理、规划、执行调度；业务含义和接口可用性仍由业务模块声明。

## Backend Field Design Rule

如果希望后续模块能快速接入 assistant，数据库字段和 schema 设计阶段就要配合：

- Pydantic 字段尽量写 `description`
- 用户可直接填写的字段尽量写 `examples`
- 枚举类字段要表达真实业务语义
- 条件必填要通过 `requiredWhen`
- 高影响但非阻塞字段优先用：
  - `importance`
  - `downstreamEffects`
  - `followUpHint`

目标不是为了“生成 Swagger”，而是为了让 assistant tool contract 能直接复用真实后端字段语义，而不是再手写一套提示词解释。

## Recommended Test Baseline

一个模块接入 assistant 后，至少补这些测试：

1. context endpoint 能返回正确的模块上下文和 capability source
2. presets endpoint 正常返回模块预设
3. chat / stream 能带入模块 capability block
4. assistant 提示词使用的是瘦身后的 prompt context，而不是整页大 JSON
5. 上一轮动作 / 上一轮执行摘要能进入 follow-up 提示词
6. action execution 的回写摘要不会把大列表原样塞回历史

## Compliance Rules

必须遵守这些规则：

- 不允许直接扫描 OpenAPI 后全量暴露
- delete / internal / public / auth 路由默认不进入 manifest
- 每个用户可填写字段都要有 `description`
- 必填字段尽量提供 `examples`
- 条件必填通过 `requiredWhen` 表达
- 高影响字段通过 `importance / downstreamEffects / followUpHint` 表达
- 权限依赖必须来自真实后端 dependency，而不是只写在 prompt 中

## Base-Level Deliverables

当前 `base` 已提供这几个底层件：

- `app.domain.assistant.tool_schema`
- `app.domain.assistant.toolset_registry`
- `app.domain.assistant.capability_registry`
- `app.domain.assistant.execution_manifest`
- `app.domain.assistant.execution_planner`
- `app.domain.assistant.route_compiler`
- `app.domain.assistant.prompt_context`
- `docs/dev/reference/assistant/ASSISTANT_PUBLISHED_ROUTE_WORKFLOW.md`
- `docs/dev/reference/assistant/ASSISTANT_MODULE_INTEGRATION_PLAYBOOK.md`

它们的目的不是替代业务模块实现，而是给所有模块提供统一接入规范，避免再次回到逐个手写 prompt / tool / 接口说明的状态。
