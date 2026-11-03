# Responses 工具能力与三模式扩展调研（2026-08-10，只调研未开发）

网关 gateway-a.example.com 实测（gpt-5.5 / deepseek-v4-flash，responses 流式）。

## 一、内置工具实测矩阵

| 能力 | gpt-5.5 | deepseek-v4-flash | 证据 |
|---|---|---|---|
| `web_search`（联网搜索） | ✅ 完整可用 | ✅ 完整可用 | 事件流含 `web_search_call.searching/completed`；回答带真实时效新闻（2026-08-07/10 Axios 报道）与来源 URL；deepseek 单次任务触发 9 次搜索调用 |
| `function`（自定义工具） | ✅ 完整可用 | 未测（同协议，预期可用） | `function_call_arguments.delta/done` 事件、正确产出工具名与参数 |
| `web_search_preview` | ❌ 400 | — | 网关不支持该旧别名，用 `web_search` |
| `code_interpreter` | ❌ 400 | — | 上游不支持 |

**含义**：AI 助手接入 responses 流式后可直接获得联网搜索（带引用）与既有
function-calling 工具体系的迁移通道——不需要自建搜索代理。

## 二、三模式扩展到 harness 与系统默认 API 的评估

现状：三模式（chat 非流式 / chat 流式 / responses 流式）目前只有 ppt-master
（走租户 AIPPT 配置的 OpenAIClient）完整支持；client 层机制（api_mode 路由、
流式聚合、responses 非流式自动聚合、reasoning/缓存键注入）已全部就绪且回流 base。

| 调用域 | 现状 | 扩展改动量 | 收益 |
|---|---|---|---|
| harness（runtime_service） | OpenAIClient 但不传 api_mode（恒 chat） | 小：provider 配置加 api_mode/stream 字段并透传 | 绕 125s 网关窗、web_search 可用 |
| assistant（AI 助手） | OpenAIClient，provider 配置有 api_mode | 小：对话链路接 responses 流式 + tools 注入 | **最大收益**：联网搜索、工具事件流 |
| ai_practice / aippt service | OpenAIClient 恒 chat | 小 | 中（长输出场景少） |
| okr coaching / agents | 独立 AiClient 体系 | 中：需在 AiClient 加同款机制或换 OpenAIClient | 中 |

## 三、落地计划（分三期，待批准后开发）

**P1（1 天）配置与客户端就绪**
- OpenAIClient 增加 `tools` 参数透传（responses 的 tools 数组 + function_call
  事件解析进流式聚合；web_search_call 事件透出为进度信号）。
- harness / assistant 的 provider 配置补 `api_mode`（三选一，同 AIPPT 校验：
  responses 仅流式）。

**P2（1-2 天）AI 助手接入搜索**
- 助手对话链路切 responses 流式；租户级开关"允许联网搜索"（默认关）；
  搜索调用与来源 URL 展示进对话 UI；工具事件（searching/completed）作为
  打字机中间态。
- 现有助手 function 工具迁移到 responses tools 协议（探针已证协议兼容）。

**P3（1 天）harness 与其余域切换 + 回归**
- harness runtime 按 provider 配置走三模式；全量测试 + 各域 E2E；
  文档与 MODEL_GATEWAY_BEHAVIOR 更新。

风险与边界：code_interpreter 不可用（勿规划依赖它的功能）；web_search 计费
未知（上线前向网关方确认单次搜索计价）；deepseek 搜索次数偏多（单任务 9 次），
接入时应设 max 搜索次数约束（responses 支持 `tool_choice`/提示词约束）。
