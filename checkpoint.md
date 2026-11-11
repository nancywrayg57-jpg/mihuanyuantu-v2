# 蜜獾原图 v2 · 检查点

时区：Asia/Shanghai。本文件只记录**当前可核实状态**；不是发布说明，也不等同生产验收。

## 0. 每次会话必填（最小集）

| 字段 | 当前值 |
| --- | --- |
| updated | 2026-11-11 CST（Asia/Shanghai） |
| branch | `cursor/five-layer-phys-tune-9973` |
| HEAD | （推送后以 `git rev-parse HEAD` / PR 为准） |
| 文档态 | PRD **2.10**；架构 **1.7**；S7 未开 |
| 代码态 | `s2-five-layer-2`：L1 ISO 弱相关阻尼噪声 + L2 小幅加强；未移植暗角/色差/饱和度 |
| 验证态 | `/tmp/five-layer-phys-tune-e2e.log`：`P0_BASELINE_FROZEN` `P1_PIPELINE_BUMP_PASS` `P2_FIDELITY_PASS` `P3_GEMINI_COMPARE_PASS` `FIVE_LAYER_PHYS_TUNE_E2E_PASS`；结论 `PHYS_TUNE_NEUTRAL`；`pass_score=75`；`production_billing=false`；`s7_started=false` |
| 当前阶段 | FIVE-LAYER-PHYS-TUNE（技术完成，待 Owner 决定是否合入） |
| 下一步 | 开 PR；非作者 Owner squash；不得宣称已解决低分；不得开 S7 |

## 1. 约束说明

- ND-020：肉眼无可见主体/颜色/文字变化；本地对照 MAD≈1.0–1.6（asset 159 等）。
- 旧版 `imagePhysicalizer` 仅借鉴 ISO–噪声定性；禁止色差/暗角/饱和度。
- 分数：v1 中位数 69 → v2 中位数 68（Δ=-1）；≥75 仍为 0 → `PHYS_TUNE_NEUTRAL`。

## 2. 阶段状态（摘要）

| 阶段 | 状态 |
| --- | --- |
| FIVE-LAYER-PHYS-TUNE | 端测 PASS；结论 NEUTRAL |
| MODEL-API-CONFIG | 已合入 #43 |
| MODULE-B-CONTRACT | 已合入 #42 |
| S7 | **须管理员确认** |
