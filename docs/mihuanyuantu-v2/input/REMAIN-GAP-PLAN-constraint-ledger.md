# REMAIN-GAP-PLAN-2026-11-11 · 约束台账

依据：工单原文、PRD 2.10、架构 1.7、AGENTS.md §7、PRODUCT-GAP-FIX（#46）。

## 冲突 / 歧义 / 前置 / 闸门

| ID | 类型 | 原文依据 | 处理 |
| --- | --- | --- | --- |
| C1 | 硬闸门 | R9「默认 BLOCKED」；「未经管理员确认不开真 S7」 | 证据强制 `R9_S7_BLOCKED=true`、`production_billing=false`；禁止部署/改 Secrets/生产 Tag |
| C2 | 需管理员裁决 | R4：路径 A（对齐架构 `guard_epoch`/`ACCOUNT_SPEND_BUSY`）或路径 B（书面改合同承认 `copy_latch_*`）；「禁止长期双轨」；DoD「R4 路径 A/B 有管理员确认记录」 | **已裁决路径 A**（管理员 2026-11-11「A」）；实现 `cap_realphotos_copy_execution_guards` + `ACCOUNT_SPEND_BUSY`；业务路径不再读写 `COPY_LATCH_ACTIVE` |
| C3 | 前置 | 「PR #46 已合入」；开干前 pull main 含缺口修复 | 校验 merge 后再切 `cursor/remain-gap-9973` |
| C4 | 推送纪律 | 「推送前必须本地对齐 CI 门禁」；配置读法变更须同改测试 | W1 PR 推送前跑 ruff+pytest(sqlite)+前端 typecheck/test（若触达） |
| C5 | 范围 | 不重复 PRODUCT-GAP-FIX（captcha/锁图/batch20/outbox/OpenAPI 可达） | W1 只做旁路关闭 + 服务端分页 |
| C6 | 波次 | 「W1 可同一 PR」；R3 宜在 R4 前或同 PR；W3/W4 可拆 PR | W1+W2 已合入 #48；本波交付 **W3+W4（R5–R8）**；R9 仍 BLOCKED |
| C7 | 声明 | R6 合同 OpenAPI 缺 `components.schemas`（7 个 $ref） | 生成脚本注入最小 stub；正式补齐合同后去掉 stub；已写入 GENERATED.md |

## 声明假设

- `[DECLARED]` W1/R1：对商家/业务角色调用底座 `POST /api/v1/auth/login` 返回 403 + 引导 realphotos；平台超管/非 realphotos 角色策略以实现时核验代码为准并在证据写明（工单：「业务租户/商家入口禁止」）。
- `[DECLARED]` W1/R2：`GET /api/v1/realphotos/assets?page=&pageSize=` 默认 pageSize=20；最大 pageSize 钳制为 100（工单允许「钳制或 422」——选钳制并写证据）。
- `[DECLARED]` 本会话不实施 R3–R8 代码（除可选 R8 文档若同 PR 成本低）；R9 仅登记。

## W1 交付核对（2026-11-11）

| 项 | 状态 | 证据 |
| --- | --- | --- |
| R1 | PASS | `/tmp/remain-gap-e2e.log` `R1_AUTH_BYPASS_CLOSED_PASS=true`；文档 `WEB_LOGIN_ENTRY.md` |
| R2 | PASS | 同日志 `R2_ASSET_SERVER_PAGE_PASS=true`（page1/2 各 20；pageSize=10000→钳制 100） |
| R4 | 曾待裁决 | 已由管理员选 **A**；见 W2 |
| R9 | BLOCKED | 同日志 `R9_S7_BLOCKED=true`；`production_billing=false` |
| PR #47 | **已关闭** | 管理员要求取消；W1+W2 统一再开 PR |

## W2 交付核对（2026-11-11）

| 项 | 状态 | 证据 |
| --- | --- | --- |
| R3 | PASS | `realphotos_0003`；`/tmp/remain-gap-e2e.log` `R3_ALEMBIC_SCHEMA_PASS=true`（upgrade 0002→0003；outbox 四列 + guard 表） |
| R4 路径 A | PASS | 同日志 `R4_COPY_GUARD_CONTRACT_PASS=true`；二次复制/冻结 → `ACCOUNT_SPEND_BUSY`；`guard_epoch` |
| R9 | BLOCKED | `R9_S7_BLOCKED=true`；`production_billing=false` |
| 汇总 | PASS | `REMAIN_GAP_W2_PASS=true`；已合入 #48 |

## W3/W4 交付核对（2026-11-11）

| 项 | 状态 | 证据 |
| --- | --- | --- |
| R5 | PASS | `/tmp/remain-gap-e2e.log` `R5_WORKER_TOPOLOGY_PASS`；process/cleanup/notify CLI + systemd 示例 |
| R6 | PASS | `frontend/src/generated/realphotos/` + `openapi-typescript@7.4.4`；`R6_FE_SDK_GENERATED_PASS` |
| R7 | PASS | `OssStorageAdapter` 预留；默认 LocalDisk；`R7_OSS_ADAPTER_STUB_PASS` |
| R8 | PASS | 架构 front-matter `s0_s6_coded_partial`；`R8_ARCH_STATUS_DOC_PASS` |
| R9 | BLOCKED | `R9_S7_BLOCKED=true`；`production_billing=false` |
| 汇总 | PASS | `REMAIN_GAP_W3_PASS` + `REMAIN_GAP_W4_PASS` |
