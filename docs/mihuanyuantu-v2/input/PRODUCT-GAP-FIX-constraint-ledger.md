# PRODUCT-GAP-FIX-2026-11-11 · 约束台账

依据：工单原文、PRD 2.10、架构 1.7、MODULE-A A2、AGENTS.md。

## 冲突 / 歧义 / 前置

| ID | 类型 | 原文 | 处理 |
| --- | --- | --- | --- |
| C1 | 硬排除 | S7 本工单不纳入 | 日志 `S7_OUT_OF_SCOPE=true`；禁止部署清单 |
| C2 | 硬排除 | FR-025 不重做 | G6 仅回归；`G6_NO_REIMPLEMENT=true`；禁止改 `provider_usage` 口径 |
| C3 | 歧义已裁 | 单张非法上传：整批拒 vs 逐张 | 工单：超 20 整批拒；单张非法与现单文件一致并写证据 |
| C4 | 会话 | realphotos login 现返 JSON token，平台 login 写 cookie | G1 须使 Web 会话与现 FE 一致（cookie 或统一 token 存储）；不得省略 captcha |
| C5 | outbox | AD-001 最小独立消费，非完整多机 | 提供可单独启动的 notify worker；heartbeat 可不唯一兼任 |
| C6 | OpenAPI | 不做 AD-009 SDK；制品对齐实现路径 | 商家页可下载仓内 JSON；Key 最短路径回归 |

## 声明假设

- `[DECLARED]` G1：realphotos login 成功后调用与平台 login 相同的 cookie 写入（或 FE 改存 accessToken 且 `apiFetch` 带 Bearer）；优先 cookie 以少动全局。
- `[DECLARED]` G2：锁校验用 `pixel_identity(asset bytes)`，与 `s6_ops._lock_on_second` 一致。
- `[DECLARED]` G3：新增 `POST /assets/batch`（multipart files[]）；保留单文件 `POST /assets`。
- `[DECLARED]` G4：outbox 增 `attempt_count`/`next_attempt_at`/`recipient_user_id`；`_notify` 只写 outbox；worker 投递写 inbox。
