# 蜜獾原图 v2 · 检查点

时区：Asia/Shanghai。本文件只记录**当前可核实状态**；不是发布说明，也不等同生产验收。

## 0. 每次会话必填（最小集）

| 字段 | 当前值 |
| --- | --- |
| updated | 2026-11-11 CST（Asia/Shanghai） |
| branch | `cursor/audit-remain-closeout-9973` |
| HEAD | tip · 基线 `main`=`c92fbfd`（#49） |
| 文档态 | PRD **2.10**；架构 **1.7** front-matter=`s0_s6_coded_partial`；§14.1 已去 NOT_IMPLEMENTED；`LEASE_TTL_DEFERRED` |
| 代码态 | A1 冻结禁获取；A2 下载扩展名；B1 `realphotos_0004`；B2 lease 书面降级 |
| 验证态 | `/tmp/audit-remain-closeout-e2e.log`：`AUDIT_REMAIN_W1/W2/W3_PASS`；闸门三联 |
| 当前阶段 | AUDIT-REMAIN-CLOSEOUT 端测绿，待统一 PR |
| 下一步 | 推 PR；非作者 Owner squash；**不得开 S7**；**不得宣称 ND-012 正式闭合** |

## 1. 约束说明

- OUT-ND012 / OUT-S7 / OUT-OSS-LIVE / OUT-ZIP / OUT-PHYS 本单均跳过或阻塞
- B2 选书面降级：`LEASE_TTL_DEFERRED=true`；忙码 `ACCOUNT_SPEND_BUSY`
- 推送前本地 ruff/pytest·sqlite + FE typecheck + download 单测

## 2. 阶段状态

| 波次 | 状态 |
| --- | --- |
| W1 A1/A2 | PASS |
| W2 B1/B2 | PASS |
| W3 C1 | PASS |
| S7 | BLOCKED |
