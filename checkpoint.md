# 蜜獾原图 v2 · 检查点

时区：Asia/Shanghai。本文件只记录**当前可核实状态**；不是发布说明，也不等同生产验收。

## 0. 每次会话必填（最小集）

| 字段 | 当前值 |
| --- | --- |
| updated | 2026-11-11 CST（Asia/Shanghai） |
| branch | `cursor/model-api-config-9973` |
| HEAD | （推送前本地未提交/待 PR；以 `git rev-parse HEAD` 为准） |
| 文档态 | PRD **2.10**；架构 **1.7**；S7 未开 |
| 代码态 | MODEL-API-CONFIG：管理员可配置四职责渠道；运行时读合同；`ensure()` 仅补缺行；单 Key 不轮询 |
| 验证态 | `/tmp/model-api-config-e2e.log`：`M1_MODEL_API_UI_PASS` `M2_CONTRACT_PERSIST_PASS` `M3_RUNTIME_SYNC_PASS` `M4_RBAC_AUDIT_PASS`；`SKIP_GPT_IMAGE_SIZE=true`；`production_billing=false`；`s7_started=false`；`polling_enabled=false` |
| 当前阶段 | MODEL-API-CONFIG-2026-11-11（M1–M4 端测 PASS，待非作者 Owner squash） |
| 下一步 | 开/更新 PR；Owner 审合；不得开 S7；不得借机做 B2-X |

## 1. 约束说明

- 原型多 Key 轮询 vs PRD FR-012：听 PRD，第一版不轮询。
- FR-030：模型配置**不进**用户操作日志；审计=合同 `updated_at` + `realphotos.supplier_config` 应用日志（脱敏）。
- 密钥明文仅写 gitignore 的 `生产物料/realphotos-duty-secrets.json` 或 `.secrets/`；响应只回掩码。

## 2. 阶段状态（摘要）

| 阶段 | 状态 |
| --- | --- |
| MODEL-API-CONFIG | M1–M4 端测 PASS；待 PR |
| MODULE-B-CONTRACT | 已合入 #42（B1 PASS；B2 缺口登记） |
| MODULE-A-GAP | 已合入 #41 |
| S7 | **须管理员确认** |
