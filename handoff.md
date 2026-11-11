# 蜜獾原图 v2 · 新会话移交

## 1. 一分钟接手

项目：蜜獾原图 v2（多租户图片资源 + 相机参数处理 + 积分）。

**开工入口**：`docs/mihuanyuantu-v2/DEV_INSTRUCTIONS.md`  
必读：`AGENTS.md`、`handoff.md`、`anchor.md`、`checkpoint.md`。  
过程权威：`docs/mihuanyuantu-v2/progress.yaml` 的 `next_action`。

## 2. 权威顺序

1. PRD → `docs/蜜獾原图-v2-PRD-v2.0.md`
2. 架构 → `docs/蜜獾原图-v2-项目架构-v1.0.md`
3. 阶段 → `docs/mihuanyuantu-v2/DEV_INSTRUCTIONS.md`

## 3. 下一步（摘要）

- **分支 / PR**：`cursor/five-layer-phys-tune-9973` → https://github.com/nancywrayg57-jpg/mihuanyuantu-v2/pull/44（工单 `FIVE-LAYER-PHYS-TUNE-2026-11-11`）
- **实现**：`PIPELINE_VERSION=s2-five-layer-2`；L1 ISO 弱相关噪声（阻尼封顶）；L2 σ 0.02→0.028
- **端测结论**：`PHYS_TUNE_NEUTRAL`（保真通过；分数中位数无显著增益）——**不得宣称已解决低分**
- `PASS_SCORE=75` 未改；未开 S7；`production_billing=false`

## 4. 证据

- `/tmp/five-layer-phys-tune-e2e.log`（含 `FIVE_LAYER_PHYS_TUNE_E2E_PASS` 与 P0–P3 子标记）
- 约束台账：`docs/mihuanyuantu-v2/input/FIVE-LAYER-PHYS-TUNE-constraint-ledger.md`
