# Message Channel Boundary

本文定义 `nextjs-base` 个人 Message Channel、系统网关账号和 AI 助手入口的底座边界。它不描述任何垂直业务消息流程。

## 能力定位

Message Channel 是个人设置里的底层消息通道，用于：

- 个人通知投递。
- 外部会话唤起 AI 助手。
- 计划任务或系统事件向用户个人通道推送结果。

它不是租户业务集成配置。租户设置可以管理系统级 gateway account、品牌和开关，但具体外部身份绑定属于当前用户。

## 三层边界

1. 个人 Channel：`user_message_channels`，记录当前用户的 channel type、外部用户 ID、conversation、绑定状态和最近入站 token。
2. 系统 Gateway：系统或租户级 bot/app 账号，保存加密 token、secret、默认账号和运行状态。
3. Assistant Runtime：入站消息统一路由到 `/message-channel`，再由 assistant planner 解析有效模块和工具。

不要把个人外部身份、系统 bot secret、业务模块配置混在同一张配置表或同一个页面里。

## 绑定流程规则

- 绑定从个人设置发起，先生成 pending channel 和短期 bind token / 关联码。
- 外部平台首次入站时携带关联码，后端在事务中把 pending channel 变为 active。
- 同一个外部身份重新绑定到另一个账号时，旧 active channel 必须失效或解除默认。
- 入站事件必须带 context token / message id 并做幂等去重。
- 有 conversation id 时必须按 conversation 精确匹配；无法唯一确定时不要随便选一个 channel。
- 绑定码过期后只能重新从个人设置获取。

## 入站助手规则

- Channel 会话不依赖浏览器 URL。
- 入站上下文必须包含 `source=message_channel`、channel type、channel id、bound user id、bound tenant id 和 external user id。
- 后续追问默认沿用上轮 active route / module；用户明显切换模块时才重新规划。
- 清空上下文、重试、pending inbound message 等控制动作应在 Channel 层处理，再交给 assistant runtime。
- AI 助手未启用或不可用时，应返回清晰状态，不把外部消息静默吞掉。

## Provider 扩展准则

微信、飞书、Webhook、企业微信或其他平台都应复用同一套 Message Channel 抽象：

- provider-specific SDK/runtime 可以留在适配层。
- base 只保留通用 channel model、gateway account、绑定、幂等、assistant relay 和错误状态。
- 新平台默认关闭，不能携带业务语义或真实客户配置。
- secret 必须加密保存，任何文档和日志都只能使用占位值或 mask。
- 如果平台需要外部长连接 runtime，base 文档只能说明出站 payload contract，不应内置客户环境进程。

