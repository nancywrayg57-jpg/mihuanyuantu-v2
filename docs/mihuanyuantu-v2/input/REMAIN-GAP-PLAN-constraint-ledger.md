# REMAIN-GAP-PLAN-2026-11-11 · 约束台账

依据：工单原文、PRD 2.10、架构 1.7、AGENTS.md §7、PRODUCT-GAP-FIX（#46）。

## 冲突 / 歧义 / 前置 / 闸门

| ID | 类型 | 原文依据 | 处理 |
| --- | --- | --- | --- |
| C1 | 硬闸门 | R9「默认 BLOCKED」；「未经管理员确认不开真 S7」 | 证据强制 `R9_S7_BLOCKED=true`、`production_billing=false`；禁止部署/改 Secrets/生产 Tag |
| C2 | 需管理员裁决 | R4：路径 A（对齐架构 `guard_epoch`/`ACCOUNT_SPEND_BUSY`）或路径 B（书面改合同承认 `copy_latch_*`）；「禁止长期双轨」；DoD「R4 路径 A/B 有管理员确认记录」 | **本会话不私自选 A/B**；W2/R4 标 `[NEEDS CLARIFICATION]` 直至书面确认 |
| C3 | 前置 | 「PR #46 已合入」；开干前 pull main 含缺口修复 | 校验 merge 后再切 `cursor/remain-gap-9973` |
| C4 | 推送纪律 | 「推送前必须本地对齐 CI 门禁」；配置读法变更须同改测试 | W1 PR 推送前跑 ruff+pytest(sqlite)+前端 typecheck/test（若触达） |
| C5 | 范围 | 不重复 PRODUCT-GAP-FIX（captcha/锁图/batch20/outbox/OpenAPI 可达） | W1 只做旁路关闭 + 服务端分页 |
| C6 | 波次 | 「W1 可同一 PR」；R3 宜在 R4 前或同 PR | 本会话优先交付 **W1（R1+R2）**；W2+ 待 R4 裁决后再开 |

## 声明假设

- `[DECLARED]` W1/R1：对商家/业务角色调用底座 `POST /api/v1/auth/login` 返回 403 + 引导 realphotos；平台超管/非 realphotos 角色策略以实现时核验代码为准并在证据写明（工单：「业务租户/商家入口禁止」）。
- `[DECLARED]` W1/R2：`GET /api/v1/realphotos/assets?page=&pageSize=` 默认 pageSize=20；最大 pageSize 钳制为 100（工单允许「钳制或 422」——选钳制并写证据）。
- `[DECLARED]` 本会话不实施 R3–R8 代码（除可选 R8 文档若同 PR 成本低）；R9 仅登记。

## W1 交付核对（2026-11-11）

| 项 | 状态 | 证据 |
| --- | --- | --- |
| R1 | PASS | `/tmp/remain-gap-e2e.log` `R1_AUTH_BYPASS_CLOSED_PASS=true`；文档 `WEB_LOGIN_ENTRY.md` |
| R2 | PASS | 同日志 `R2_ASSET_SERVER_PAGE_PASS=true`（page1/2 各 20；pageSize=10000→钳制 100） |
| R4 | `[NEEDS CLARIFICATION]` | 同日志 `R4_NEEDS_ADMIN_CHOICE=true`；**未**选 A/B |
| R9 | BLOCKED | 同日志 `R9_S7_BLOCKED=true`；`production_billing=false` |
| 本地 CI | 部分 | 后端 ruff(改动范围)+pytest sqlite 相关用例 PASS；前端 `tsc` PASS；本机 Node 对 `tests/*.test.mjs` 直 import `.ts` 报 `ERR_UNKNOWN_FILE_EXTENSION`/`ERR_NO_TYPESCRIPT`（**未改**测试/脚本；记入 PR 为存量本机基线风险，不以本地假绿掩盖） |
