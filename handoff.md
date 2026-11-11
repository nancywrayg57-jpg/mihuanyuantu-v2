# 蜜獾原图 v2 · 新会话移交

## 1. 一分钟接手

项目：蜜獾原图 v2（多租户图片资源 + 相机参数处理 + 积分）。

**开工入口**：`docs/mihuanyuantu-v2/DEV_INSTRUCTIONS.md`  
必读：`AGENTS.md`、`handoff.md`、`anchor.md`、`checkpoint.md`。  
过程权威：`docs/mihuanyuantu-v2/progress.yaml` 的 `next_action` / `vibe_coding.current_loop`。

## 2. 权威顺序

1. PRD → `docs/蜜獾原图-v2-PRD-v2.0.md`
2. 架构 → `docs/蜜獾原图-v2-项目架构-v1.0.md`
3. 阶段 → `docs/mihuanyuantu-v2/DEV_INSTRUCTIONS.md`

## 3. 下一步（摘要）

- **分支 / PR**：`cursor/product-gap-fix-9973` → https://github.com/nancywrayg57-jpg/mihuanyuantu-v2/pull/45（工单 `PRODUCT-GAP-FIX-2026-11-11`）
- **合入注意**：当前推送账号为 `@nancywrayg57-jpg`（Owner）；按 AGENTS §7 **不得自评自合**——须非作者账号审批/合并，或改由 Collaborator 重开作者身份。
- **范围**：开发 G1–G5；G6=FR-025 **仅回归**（MODULE-A A2 已交付，不重做）
- **端测**：`/tmp/product-gap-fix-e2e.log` → `PRODUCT_GAP_FIX_E2E_PASS=true`
- **合入**：仅非作者 Owner squash；Collaborator 不合并、不打 Tag、不部署
- **禁止**：开 S7；生产收费；改 `PASS_SCORE`；重做成本计量；AD-009 SDK

## 4. 证据

- `/tmp/product-gap-fix-e2e.log`（含 G1–G6 分项与 `S7_OUT_OF_SCOPE` / `G6_NO_REIMPLEMENT`）
- 工单：`docs/mihuanyuantu-v2/input/PRODUCT-GAP-FIX-2026-11-11.md`
- 约束台账：`docs/mihuanyuantu-v2/input/PRODUCT-GAP-FIX-constraint-ledger.md`
