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

- **分支 / PR**：`cursor/model-api-config-9973` → https://github.com/nancywrayg57-jpg/mihuanyuantu-v2/pull/43（工单 `MODEL-API-CONFIG-2026-11-11`）
- **M1–M4**：系统管理「模型 API」可配置四职责渠道（单 Key、不轮询）；`ensure()` 不覆盖管理员配置；运行时读启用合同；RBAC + FR-030 审计落点
- **跳过**：gpt-image-2 尺寸 / B2-X；S7；生产收费；Key 轮询
- 不得自评自合；`production_billing=false`；`polling_enabled=false`

## 4. 证据

- `/tmp/model-api-config-e2e.log`（含 `M1_MODEL_API_UI_PASS` `M2_CONTRACT_PERSIST_PASS` `M3_RUNTIME_SYNC_PASS` `M4_RBAC_AUDIT_PASS`）
- 约束台账：`docs/mihuanyuantu-v2/input/MODEL-API-CONFIG-constraint-ledger.md`
