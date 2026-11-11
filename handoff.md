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

- **工单**：`REMAIN-GAP-PLAN-2026-11-11` · **W1+W2**（R1/R2/R3/R4A）
- **分支**：`cursor/remain-gap-w1-9973`（基线 `main` #46 `f86b6af`）
- **PR**：https://github.com/nancywrayg57-jpg/mihuanyuantu-v2/pull/48（统一 W1+W2；**#47 已关**）
- **R4 裁决**：管理员选 **路径 A**（`guard_epoch` / `ACCOUNT_SPEND_BUSY`）
- **端测**：`/tmp/remain-gap-e2e.log` → `REMAIN_GAP_W1_PASS` + `REMAIN_GAP_W2_PASS`
- **禁止**：开 S7；自评自合；改 `PASS_SCORE`；重做 FR-025

## 4. 证据与文档

- `/tmp/remain-gap-e2e.log`
- 工单 / 约束台账：`docs/mihuanyuantu-v2/input/REMAIN-GAP-PLAN-*.md`
- Web 登录入口：`docs/mihuanyuantu-v2/WEB_LOGIN_ENTRY.md`
- S7 草稿（未授权）：`docs/mihuanyuantu-v2/S7-开工检查清单-草稿.md`
