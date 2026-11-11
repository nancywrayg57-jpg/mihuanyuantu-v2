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

- **工单**：`REMAIN-GAP-PLAN-2026-11-11`（九项剩余缺口；本会话交付 **W1 = R1+R2**）
- **分支 / PR**：`cursor/remain-gap-w1-9973` → https://github.com/nancywrayg57-jpg/mihuanyuantu-v2/pull/47（基线 `main` 含 #46 `f86b6af`；提交作者 `xtzhou247`）
- **合入注意**：PR 由本机 `nancywrayg57-jpg` 创建；按 AGENTS §7 **不得自评自合**——仅非作者 Owner squash。
- **端测**：`/tmp/remain-gap-e2e.log` → `REMAIN_GAP_W1_PASS=true`
- **证据闸门**：`R9_S7_BLOCKED=true`；`production_billing=false`；`R4_NEEDS_ADMIN_CHOICE=true`
- **禁止**：开 S7；生产收费；改 `PASS_SCORE`；重做 FR-025；ZIP；Key 轮询；正式 ND-012；自选 R4 路径 A/B

## 4. 证据与文档

- `/tmp/remain-gap-e2e.log`（R1/R2/R9 标记）
- 工单：`docs/mihuanyuantu-v2/input/REMAIN-GAP-PLAN-2026-11-11.md`
- 约束台账：`docs/mihuanyuantu-v2/input/REMAIN-GAP-PLAN-constraint-ledger.md`
- Web 登录入口：`docs/mihuanyuantu-v2/WEB_LOGIN_ENTRY.md`
- 上一单 PRODUCT-GAP-FIX 已合入 #46；本单不重复 G1–G5

## 5. 未决冲突（不得掩盖）

| ID | 状态 | 说明 |
| --- | --- | --- |
| C2 / R4 | `[NEEDS CLARIFICATION]` | 复制门闩：路径 A 对齐架构 vs 路径 B 改合同；须管理员书面确认后才能开 W2/R4 |
| C1 / R9 | BLOCKED | 无「授权 S7」书面前仅登记；证据已写 `R9_S7_BLOCKED=true` |
