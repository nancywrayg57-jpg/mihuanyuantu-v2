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

- **分支**：`cursor/module-b-contract-9973`（工单 `MODULE-B-CONTRACT-2026-11-10`）
- **B1**：OpenAPI `contracts/realphotos_image_processing.openapi.json` + `docs/mihuanyuantu-v2/FR-033-image-processing-对接说明.md`；无会话端测 PASS
- **B2**：门闸 `SUPPORTS_SIZE_CONTROL=false`（探测尺寸不符 + 物料无书面合同）→ `B2_SIZE_UNSUPPORTED_RECORDED`；**未标 B2 完成**
- **管理员待办（可选）**：提供 gpt-image-2 / aoju 尺寸控制书面说明后，再考虑 B2-X
- 不得开 S7；不得自评自合；`production_billing=false`

## 4. 证据

- `/tmp/module-b-contract-e2e.log`
- 约束台账：`docs/mihuanyuantu-v2/input/MODULE-B-CONTRACT-constraint-ledger.md`
