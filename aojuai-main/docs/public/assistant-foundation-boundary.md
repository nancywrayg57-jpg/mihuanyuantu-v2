# AI 助手底座边界

本文定义 `nextjs-base` 中 AI 助手基础层的所有权边界。

## Base 负责

- 租户级助手配置：模型、Base URL、密钥脱敏、扣费参数和提示词基线。
- 助手会话与消息持久化。
- 通用 API：
  - `/api/v1/assistant/config`
  - `/api/v1/assistant/sessions`
  - `/api/v1/assistant/chat`
  - `/api/v1/assistant/chat/reply`
  - `/api/v1/assistant/actions/execute`
- 通用能力运行时：
  - builtin skills
  - builtin tools
  - capability context rendering
  - module-skill governance merge rules
- 通用前端：
  - assistant API client
  - assistant dock
  - action event bus
  - stream buffer
  - action presentation contract

## Base 内置 skills/tools

Skills:

- `core.context_reader`
- `core.permission_boundary`
- `core.form_collection`
- `core.write_confirmation`

Tools:

- `time.now`
- `time.range.resolve`
- `session.scope.inspect`
- `page.context.refresh`

这些能力跨租户、跨模块复用，应留在底座。

## 下游扩展负责

- 垂直模块 adapter。
- 模块 prompt pack 和 skill pack。
- 业务动作的参数收集、确认文案和执行器。
- 依赖业务表结构的测试。
- 带具体业务语义的 action card 或页面文案。

## 硬规则

1. `nextjs-base` 不 import 下游扩展模型或 adapter。
2. 下游扩展可以依赖 base assistant contract，base 不反向依赖下游扩展。
3. 能力如果需要业务表、业务角色语言或业务流程，留在下游扩展。
4. 能力如果是租户级、身份级、跨模块、可独立测试，优先沉淀到底座。
