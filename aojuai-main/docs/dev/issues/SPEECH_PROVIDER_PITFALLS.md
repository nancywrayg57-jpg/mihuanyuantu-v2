# Speech Provider Pitfalls

本文沉淀语音 provider、租户配置、试听和运行态的通用问题。它只描述 `speech` 底座经验，不记录任何垂直音频产品流程。

## Provider 切换后旧 settings 残留

### 症状

- 租户从一个 TTS provider 切到另一个 provider 后，试听或合成请求返回 `400`。
- 页面显示已选择新 provider，但后端实际 payload 仍带旧 provider 的 `model`、`baseUrl`、`voice` 或自定义 headers。
- 只有历史租户、旧 payload 或非主设置入口容易复现。

### 根因

provider 发生变化时，如果后端只是浅合并 `providerSettings`，旧 provider 的字段会被保留下来。HTTP provider 与 realtime/WebSocket provider 尤其容易冲突，例如把 REST URL 留给 WebSocket SDK。

### 解决方案

- 判断 `providerId` 变化时，先取目标 provider descriptor 的默认 settings，再合并本次提交的显式字段。
- secrets 按 provider 分组保存和读取，不能把旧 provider secret 当作新 provider secret 使用。
- 前端切 provider 时也应按 descriptor 重建表单默认值，但后端仍必须兜底。
- provider category 必须校验：TTS provider 不能写入 STT section，反之亦然。

### 测试基线

- 从 HTTP TTS provider 切到 realtime provider，只提交部分 settings，不应继承旧 HTTP `baseUrl` / `model`。
- 从 provider A 切到 provider B 后，旧 provider 专属字段不应出现在最终运行态 payload。
- secrets view 只能暴露布尔状态，不回传明文 secret。

## 握手级 400/401 被包装成笼统超时

### 症状

- provider 实际返回 `400` / `401`，但业务层只显示“连接失败”或“timeout”。
- 排障时无法判断是 API key、endpoint、model、region 还是 SDK 参数问题。

### 根因

WebSocket / realtime SDK 的握手失败经常被底层库包装为连接异常。如果上层不解析状态码和官方 body，就会丢失真正原因。

### 解决方案

- provider runtime 捕获异常时，提取 status code、provider error code、request id 和 body 摘要。
- 用户可见错误要说明 provider、状态码和摘要；日志可以记录更多上下文，但必须 mask secret。
- 不要把所有连接异常都归类为 timeout。
- 对 SDK 缺失、证书缺失、URL scheme 错误分别给出明确错误。

### 测试基线

- realtime 握手 `401 InvalidApiKey` 时，错误详情包含 `401` 和 provider body 摘要。
- realtime endpoint 使用 HTTP URL 时，应该在本地校验阶段失败，而不是打到上游后返回难以理解的 `400`。

## Speech 与下游模块边界

- provider registry、provider descriptor、tenant speech storage、试听和 provider prompt context 属于 `speech` 底座。
- 下游模块只能消费 speech 的规范化 provider settings，不应 fork 第二套 provider catalog。
- 新 provider 进入 base 前，需要同时补 descriptor、runtime、secret key 列表、默认 settings、prompt context 和测试。
- 语音音频流、试听和上传下载属于 `/api/v1/*`，生产必须由 Nginx 直达 FastAPI，不经 Next rewrite。

