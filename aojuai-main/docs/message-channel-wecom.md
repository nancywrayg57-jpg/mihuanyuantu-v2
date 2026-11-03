# 企业微信个人 Channel 接入

## 定位

企业微信 Channel 是个人设置里的系统底层消息通道，和微信、飞书 Channel 一样用于个人通知、计划任务结果推送，以及从外部会话唤起 AI 助手。

租户设置里的企业微信业务模块页签（若下游扩展提供）只负责租户级业务配置；它不配置个人 Channel，也不展示企业微信个人 Channel 网关。

## 二维码来源

个人绑定使用企业微信官方二维码接口获取机器人 `botId` / `secret`。AOJU 只复用企业微信二维码协议，不在系统设置里要求管理员手工填写个人 Channel 机器人网关。

## 当前接口

- `POST /api/v1/message-channels/wecom/qrcode/start`：当前用户生成企业微信二维码和八位关联码。
- `GET /api/v1/message-channels/wecom/qrcode/status?scode=...`：当前用户轮询扫码状态；成功后把机器人凭据保存到自己的 `user_message_channels`。
- `POST /api/v1/message-gateways/wecom/events`：企业微信机器人消息回推入口，用于八位关联码绑定和后续 AI 助手会话；请求必须遵循[消息网关入站鉴权](message-gateway-inbound-auth.md)。
- `GET /api/v1/message-channels`：个人设置和计划任务读取已绑定 Channel。

## 用户绑定流程

1. 用户进入个人设置 / 消息 Channel。
2. 点击“获取企业微信二维码”。
3. 前端调用 `/api/v1/message-channels/wecom/qrcode/start`。
4. 后端创建或复用当前用户的 pending `wecom` Channel，并返回二维码、`scode` 和八位关联码。
5. 前端每 3 秒调用 `/api/v1/message-channels/wecom/qrcode/status`。
6. 扫码成功后，后端加密保存机器人 secret，并把 `botId` 等元数据写入 `extra.wecomBot`。
7. 用户在企业微信机器人会话发送八位关联码。
8. 外部企业微信机器人运行时把消息转发到 `/api/v1/message-gateways/wecom/events`。
9. 后端完成当前用户和企业微信会话的绑定，Channel 状态变为 `active`。

## 入站回调格式

AOJU 的 WeCom 入站解析兼容企业微信智能机器人 SDK 的 WebSocket 帧结构。官方 Bot 文本消息可按下面格式转发：

```json
{
  "cmd": "aibot_callback",
  "headers": { "req_id": "req-1" },
  "body": {
    "msgid": "msg-1",
    "aibotid": "bot-1",
    "chattype": "single",
    "from": { "userid": "zhangsan", "corpid": "corp-1" },
    "msgtype": "text",
    "text": { "content": "12345678" }
  }
}
```

绑定时：

- `body.text.content` 作为八位关联码。
- `body.from.userid` 作为 `externalUserId`。
- `body.chatid` 存在时作为 `conversationId`。
- 单聊没有 `chatid` 时使用 `userid` 作为 `conversationId`。
- `body.msgid` 用作 `contextToken` 和幂等去重 token。

非绑定文本会转交统一 AI 助手，复用微信和飞书 Channel 的入站助手会话能力。

## 出站边界

当前 Python 后端不内置企业微信长连接运行时。扫码成功会保存个人机器人凭据；实际长连接、消息接收和主动发送仍需要外部企业微信机器人运行时或个人 `gatewayUrl` 承担。

出站兼容 payload 会包含标准 Channel 字段，并附带 `wecomBot` 字段，外部运行时可据此调用企业微信机器人 SDK 的 `sendMessage(chatid, body)`。
