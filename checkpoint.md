# 蜜獾原图 v2 · 检查点

时区：Asia/Shanghai。本文件只记录**当前可核实状态**；不是发布说明，也不等同生产验收。

## 0. 每次会话必填（最小集）

| 字段 | 当前值 |
| --- | --- |
| updated | 2026-11-08 CST（Asia/Shanghai） |
| branch | `cursor/fix-failure-rate-remain-9973` |
| HEAD | 待推送 PR（非合入就绪） |
| 文档态 | PRD **2.10**；架构 **1.7**；S7 未开 |
| 代码态 | FIX-FAILURE-RATE-TECH：R1 prompt≥75 对齐+软日志；R2 EXIF 预检；R3 MakerNote 映射/重试；R4 gpsSubmitGuard；R5 detectionBrief；R6 本地 five_layer/pytest 绿，**缺开发机 `/tmp/r6-devhost-task.json`**。未改 PASS_SCORE；未伪造 GPS |
| 验证态 | `/tmp/fix-failure-rate-remain-e2e.log`：R1–R5_E2E_PASS；**R6_E2E_FAIL**；`MERGE_READY=False`；`production_billing=false` |
| 当前阶段 | 剩余项部分完成；R6 被 LAN/开发机证据阻塞（约束台账 X1） |
| 下一步 | 开发机补 R6 证据后重跑 e2e；全绿前禁止 squash；不得开 S7 |

## 1. 约束冲突（必须保留）

见 `docs/mihuanyuantu-v2/fix-failure-rate-remain-constraints.md`：X1 开发机不可达不得写 R6_PASS；X2 PR 可开但非合入就绪；不得降 75 分门槛。

## 2. 阶段状态（摘要）

| 阶段 | 状态 |
| --- | --- |
| FIX-TASK-FAILURE-UX F1–F6 | 已合入 #36 |
| FIX-FAILURE-RATE-TECH R1–R5 | 本地端测 PASS |
| FIX-FAILURE-RATE-TECH R6 | **FAIL / 阻塞**（无开发机任务证据） |
| S7 | **须管理员确认** |
