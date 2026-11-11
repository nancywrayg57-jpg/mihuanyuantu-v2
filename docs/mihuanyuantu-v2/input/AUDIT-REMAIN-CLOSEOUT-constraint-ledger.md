# AUDIT-REMAIN-CLOSEOUT-2026-11-11 · Constraint Ledger

记录时间：2026-11-11（开干基线 `main` = `c92fbfd` = #49 squash）

## 硬性排除（不得放宽）

| ID | 原文依据 | 执行 |
| --- | --- | --- |
| OUT-ND012 | 工单 §3：FR-028 正式 URL/JSON 外呼 + ND-012 正式供应商 **本单跳过** | 证据强制 `OUT_ND012_SKIPPED=true`；不冒充正式闭合 |
| OUT-S7 | 工单 §0.4 / §3 / DoD：真 S7 / 生产收费未授权禁止 | `R9_S7_BLOCKED=true`；`production_billing=false` |
| OUT-OSS-LIVE | 工单 §3：OSS 真桶仅已有 stub | 禁止接真桶 |
| OUT-ZIP | 工单 §3 / FR-031：禁止 ZIP | 继续拒绝 |
| OUT-POLL | 工单 §3：Key 轮询第一版关闭 | 不启用 |
| OUT-PHYS | 工单 §3：PASS_SCORE / 五层抬分另单 | 不改 `PASS_SCORE` |
| SELF-MERGE | 工单 §6.4 / AGENTS §7：Collaborator 不合并、不打 Tag、不部署 | 仅非作者 Owner squash |
| SECRETS | 工单 §0.2 / AGENTS：密钥只读同级 `生产物料/` | 禁止入库 |
| CI-LOCAL | 工单 §0.6：推送前本地对齐 CI | ruff/pytest·sqlite / pnpm typecheck+test |
| CFG-TEST | 工单 §0.7：改 Settings/getenv 读法须同改测试 | 配置与测试同 PR |

## 已识别矛盾 / 歧义 / 前置（不私自调和）

| ID | 类型 | 说明 | 处置 |
| --- | --- | --- | --- |
| PRE-49 | 前置（已闭合） | 工单要求 #49 合入或基于 tip；开干时 #49 已 MERGED → `origin/main`=`c92fbfd` | 已 `checkout main && pull`，分支 `cursor/audit-remain-closeout-9973` |
| B2-LEASE | 已裁决（书面降级） | 工单 B2 二选一 | **选②**：`LEASE_TTL_DEFERRED=true`；架构 §6.2 已注明；`lease_until=NULL`；仅 batch 终态释放；忙码 `ACCOUNT_SPEND_BUSY`；禁 `copy_latch_*` 业务读写 |
| A1-GEN-UI | 边界 | FR-002 含「资源获取」；工单 A1 前端写明禁用「上传/导入」；生图已有服务端 `assert_can_create_task` | W1：后端三入口 + 库页上传/导入禁用；生图入口保持服务端硬拦；库页生成链接可附加禁用提示以对齐 FR-002（标注为与工单上传/导入同冻结态 UX） |
| NFR008 | 范围 | 工单 §1：NFR-008/AD-001 进程拓扑不重复，仅回归不抢错队列 | W1 不改 worker 拓扑 |
| FR028-SKIP | 裁决 | A 中 FR-028+ND-012 跳过；staging 现状保持 | 不改正式导入供应商 |

## 波次完成闸门

```text
AUDIT_REMAIN_W1_PASS / W2 / W3
R9_S7_BLOCKED=true
production_billing=false
OUT_ND012_SKIPPED=true
```

## 假设（仅当必要时标注）

- `[ASSUMPTION]` 端测仍走开发机 `hbs@192.168.19.128` FE`3000`/API`38000`+PostgreSQL（工单「验证环境」原文）；若本机会话即该主机则同机执行，不另发明环境。
