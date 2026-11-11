# 蜜獾原图 v2 · 检查点

时区：Asia/Shanghai。本文件只记录**当前可核实状态**；不是发布说明，也不等同生产验收。

## 0. 每次会话必填（最小集）

| 字段 | 当前值 |
| --- | --- |
| updated | 2026-11-11 CST（Asia/Shanghai） |
| branch | `cursor/module-b-contract-9973` |
| HEAD | 待推 PR（MODULE-B-CONTRACT） |
| 文档态 | PRD **2.10**；架构 **1.7**；S7 未开 |
| 代码态 | B1：OpenAPI 对接工件 + 无会话 Key 路径端测 PASS；B2：尺寸门闸 `SUPPORTS_SIZE_CONTROL=false`，已诚实登记，**未做 B2-X** |
| 验证态 | `/tmp/module-b-contract-e2e.log`：`B1_FR033_CONTRACT_PASS` + `B2_SIZE_UNSUPPORTED_RECORDED`；`production_billing=false`；`s7_started=false` |
| 当前阶段 | Module B 合同收口（B1 必达；B2 条件未达） |
| 下一步 | Owner 审 PR；可选补充生图尺寸书面合同后再开 B2-X；不得开 S7 |

## 1. 约束说明

- B2 探测：`1024x768→1448x1086`、`1024x1024→1254x1254`；物料无尺寸书面合同；无批准映射表 → 不得宣称尺寸合同已收口。
- 适配器仍按请求发送 `size`，不静默改写；UI 已展示请求/实际尺寸。

## 2. 阶段状态（摘要）

| 阶段 | 状态 |
| --- | --- |
| MODULE-B-CONTRACT | B1 PASS；B2 缺口登记 |
| MODULE-A-GAP | 已合入 #41 |
| S7 | **须管理员确认** |
