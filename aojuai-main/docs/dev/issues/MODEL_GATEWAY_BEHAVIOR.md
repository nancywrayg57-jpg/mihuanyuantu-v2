# 模型网关行为知识库（回流自 nextjs-plugins 生成链路实测）

更新：2026-08-09。以下全部为对 gateway-a.example.com / gateway-b.example.com 的实测结论，
换网关后需按同样方法重新标定（探针脚本模式见文末）。

## 1. 非流式长响应会被 CDN 层在 ~125s 强制断开（524）

- 症状：蓝图编译等大输出请求"600 秒都不返回，最终报错或无产出"。
- 实测：非流式强制长生成 127s 被断（body `error code: 524`）；同场景流式 141s 完整返回。
- 结论：**输出生成时长可能超过 ~120s 的请求必须走流式**。蓝图编译默认流式聚合
  （`AOJU_PPT_MASTER_BLUEPRINT_STREAM=0` 可回退），单页直出跟随租户 codeStream。
- 客户端超时怎么调都救不了非流式：断开发生在网关侧。

## 2. 流式历史 bug：逐 chunk strip 吃掉空格

- `_content_text` → `.strip()` 对每个 SSE 增量执行，聚合文本空格全丢，SVG/JSON 必坏。
  这是"流式一开就出乱码"的历史根因。修复：`_incremental_content_text`（严禁 strip），
  回归测试 `test_stream_collect_preserves_whitespace_across_chunks` 锁定。

## 3. responses 端点差异

- 2apitest 网关：responses 请求带 `temperature` 或 `max_output_tokens` 即 400
  （历史上 responses 模式必败的根因）；且无论 stream 参数为何都只回 SSE。
- gateway-a.example.com：responses 流式正常；responses 非流式对 gpt 系 500（上游只回 SSE）。
- 因此**请求模式只允许三种组合**：chat_completions（流式/非流式）、responses（仅流式）。
  后台保存时强制校验，`auto` 不再接受新写入。
- responses 流式事件格式（两网关一致）：正文在 `response.output_text.delta` 的 `delta`
  字段，usage 在 `response.completed` 事件的 `response.usage`。

## 4. 提示词缓存：真实开启，但有两个隐藏条件

- **最小前缀阈值高于官方 1024**：~1.8k token 前缀不写不读（`cache_write_tokens=0`），
  ~5k+ 前缀正常命中。短请求（设计规范确认等）不命中属正常。
- **并发请求路由不粘**：同一 `prompt_cache_key` 的并发请求仍被负载均衡分散到不同
  上游节点，实测 5 并发仅 2 命中。串行请求（如 codex）100% 命中。
- 客户端已注入 `user`+`prompt_cache_key`（`OpenAIClient.prompt_cache_scope`，
  ppt-master 按租户 `aoju-ppt-tenant-{id}`）；并发命中率的根治需网关按
  cache key 做一致性哈希路由（网关侧配置）。
- 观测：任务结果 `result.tokenUsage`（requests/promptTokens/completionTokens/
  cachedTokens）与每次调用的 `modelRequest.usage`。

## 5. temperature

- GPT-5 系 reasoning 模型拒绝自定义 temperature（只接受默认）；DeepSeek 默认 1.0
  且 V3 系有 API 映射（1.0→0.3）。租户配置留空=不下发（跟随模型默认，推荐）。

## 6. 模型可用性（按网关而异）

- 2apitest：仅 gpt-5.x + 图像模型（13 个），无 deepseek。
- gateway-a.example.com：81 个模型含 deepseek 全系。deepseek-v4-flash：蓝图快且缓存命中好；
  写复杂单页 SVG 的一次成功率低于 gpt 系（p92 实测 6 页 1 页语法坏，补全可兜底）。

## 探针方法备忘

- 缓存：同 `prompt_cache_key` 大前缀（≥5k token）两连发，看第二次
  `input_tokens_details.cached_tokens`（responses）或 deepseek 的
  `prompt_cache_hit_tokens`（chat）。
- 网关窗：强制长生成（"写 12000 字禁止提前收尾"）非流式计时到断开。
- 凭据取自租户运行时配置（`AipptService._code_runtime_config`），探针文件用完即删，
  不得落入 git 或长期文件。

<!-- 以下 §7 / §12 / §13.4 回流自 nextjs-plugins（2026-08-10~12 实测），与 base 的 openai_client 修复 <commit> 对应 -->

## 7. max_tokens 与 reasoning 的实测结论（2026-08-10 修订）

- **max_tokens 不是单页时延的主因**（此前"96000 必然顶格生成"判断有误）：
  A/B 同一单页请求，非流式不下发 72s / 64000 100s / 96000 168s（有相关性，
  疑为上游按预算预留调度配额），流式下各档差异在噪声内。
- **固定上限有截断风险**：185 个真实单页 completion_tokens 分布 p50=2994、
  p99=18458、max=20486——16000 会截断复杂页，且截断在流式聚合下是不可重试失败。
- **终态策略**：单页请求默认**不下发 max_tokens**（跟随模型默认；
  `AOJU_PPT_MASTER_HARNESS_DIRECT_PAGE_TOKEN_CEILING` 显式设值才限制）；
  失败重试仍经 gateway-safe 档（16000）收紧。单页请求超时被 direct-page 档
  （默认 240s）封顶，租户全局大超时只留给蓝图。
- **reasoning=none 是真正的大杠杆**：10 组合矩阵实测全线提速 16-45%
  （chat 流式 99.6→55.0s），输出 token 少 20-30%。两端点均支持
  （chat: `reasoning_effort:"none"`；responses: `reasoning:{"effort":"none"}`；
  `minimal` 被网关拒 400）。ppt-master 默认注入 none
  （`AOJU_PPT_MASTER_REASONING_EFFORT`，设 "default" 恢复模型默认）。
- **responses 模式下非流式调用自动走流式聚合**：多网关 responses 转发只支持
  SSE，非流式端点 400/500——chat_with_usage(stream=False) 在 responses 模式下
  改为内部聚合，harness loop（aiOptimize=off）路径由此修复。
- 蓝图开关 A/B（2 页，reasoning=none）：开=83.9s，关（harness loop 串行）=118s
  ——蓝图路径反而更快，保持默认开启。


## 12. responses function-calling 实测协议事实（2026-08-11，deepseek-v4-flash）

AI 助手原生工具微循环(assistant/tool_loop.py)接入时逐条实测确认：

1. **事件序列**：函数调用以 `response.output_item.added`(item.type=function_call,
   含 call_id/id/name) 开始，参数经 `response.function_call_arguments.delta` 增量、
   `response.function_call_arguments.done`(带完整 arguments,权威值) 收束；
   deepseek 会先发 reasoning item(`reasoning_text.delta/done`)再发函数项。
   个别网关可能不发 arguments.done——解析器须以 `output_item.done` 兜底且去重。
2. **纯函数调用轮没有任何 `output_text.delta`**：把"无正文"当空流错误会误伤，
   须以"无正文且无函数调用"才判空(openai_client.responses_stream_events)。
3. **工具结果回灌 = 全量 input 重放**：下一跳 input 为原始消息 + assistant 正文项 +
   整批 function_call 项(保持模型产出顺序) + 对应 function_call_output 项；
   **无需 previous_response_id**，网关直接接受。结构化 input 的 system/assistant
   role 消息均被接受(拍平字符串非必需)。
4. **写入语义靠提示词硬约束**：模型倾向用文字描述写入草案而不调用写入工具；
   提示词必须写明"必须调用写入工具提出草案,不要只用文字描述,否则确认流程
   无法进行"，实测措辞加强后折叠稳定触发。
5. **重试边界**：流式下"未向下游产出任何事件"的截断/空流可安全重试；
   一旦有 delta/函数调用产出就不得重试(下游已消费,重放必重复)。工具执行
   与重试交叠用 call_id 缓存 output 去重。

微循环预算默认值(tool_loop.NativeToolLoopBudget)：工具 6 次/LLM 8 跳/120s/
搜索 6 次/token 20 万/单跳 HTTP 重试 2 次，任一耗尽即停。


## 13. 提示词缓存深度复盘（节选，回流自 nextjs-plugins；§13.1–13.3 为 ppt-master 专属，留在业务分支）

### 13.4 GPT-5.6 隐式断点语义与严格前缀引导修复(2026-08-12 深度复盘)

13.3 的“共享 88% 前缀仍为 0、严格增量链可命中”并非请求体哈希分片的充分
证据。OpenAI GPT-5.6 官方语义是:默认只在最新 user/tool message 末尾放隐式
cache breakpoint,且不再回退到该断点之前的最长未标记公共前缀。因此两个请求
即使共享数千 token,只要最新 message 的尾部不同,断点对应的完整 prefix 就不同,
`cached_tokens` 可以稳定为 0；而多轮对话/严格增量链恰好保留了前一轮完整断点。

真实 p139 对照（共同稳定区 17,412 字符）:
- 单字符串共享前缀+异尾:0；结构化 items 同一 message 内拆 content blocks:0；
- 普通 `developer(system)+user(stable)+user(dynamic)` 结构只命中 system 小段
  1,792 tokens；把 system+stable 合并为单个 developer item 后可命中 7,936，
  而拍平字符串两轮均为 0（合并方案会提升用户资料权限，未用于生产）；
- 先发稳定区,再以完全相同稳定区追加页面尾部:命中 6,912；加入短响应条件
  协议后命中 7,936；字符串严格增量链同样命中 6,912；
- `prompt_cache_breakpoint`、`prompt_cache_options`（分别或同时）均被当前网关
  HTTP 400 `Upstream request failed`，说明现网尚未透传 GPT-5.6 显式断点协议。

客户端兼容修复:公共 Responses client 接受 `stable_prefix_messages`，按
`developer(system) + user(stable) [+ user(dynamic)]` 结构化且保留 user 角色；
公共 `prime_prompt_cache()` 先发稳定 items，完整请求形成严格增量链。PPT 单页和
分步蓝图只声明稳定消息边界，不自行拼 HTTP payload。最终公共函数完整真实请求
（非短尾探针）:p138 prime 后首个蓝图 batch 命中 17,152/17,749；p139 prime 后
首个完整单页 SVG 命中 7,936/13,144。role-preserving fresh 重复为 2 hit/1 miss，
与已知网关概率 miss 一致。p139
蓝图稳定区仅 1,192 tokens，在本网关连续三读仍为 0（短文档/单来源块本来也不进
split 蓝图）；生产代码对不足 4,096 字符的细化稳定区跳过额外 prime。另一次
fresh key p138 曾首读 0、第二读 9,984，证明概率 miss 依旧存在，但已不再是
架构性零命中。

网关开票项更新为两项:①透传 `prompt_cache_breakpoint` 与
`prompt_cache_options.mode=explicit`，客户端届时可直接标记稳定 content block；②继续按
`prompt_cache_key` 做缓存亲和，降低已观测到的同 payload/同断点随机 miss。
