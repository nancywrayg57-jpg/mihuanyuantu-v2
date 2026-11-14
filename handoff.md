# 蜜獾原图 v2 · 新会话移交

## 1. 一分钟接手

**工单** `DET-SCORE-OPTIMIZE`（承接 ALIGN）  
**分支** `cursor/det-score-hemostasis-9973`（自 `main` 仅止血提交）  
**PR** https://github.com/nancywrayg57-jpg/mihuanyuantu-v2/pull/55  
**代码** OPEN_PARTIAL（CA=0、Layer0 默认关、async 它线程）；R4 **仅 env 覆写**可测；**未把 R4 写成默认**  
**推送** 已 push；Q1 仍 SHORTFALL，不宣称 W5 PASS  
**消融 W** 8mm mean_v3=**62.17**（史≈49 回升）；gain_vs_v2=**−4.08**；色差 reason **0/12**  
**R4** mean_r4=**63.0**（Δ vs W +0.83）→ **P-V3-OVERDRIVE NOT_CONFIRMED**  
**协议 C** mean_v3=**66.92** gain=**+1.17** → **`ALIGN_W5_E2E_SHORTFALL`**；Q1 仍 **UNPROVEN**  
**PASS_SCORE=75** 不放宽；**停止加码**待管理员  
**禁止** 开 S7；改 PASS_SCORE；白名单外改像素；自评自合

## 2. 权威顺序

`AGENTS.md` → 账本 `DET-SCORE-OPTIMIZE-*` → ALIGN 账本 → `DEV_INSTRUCTIONS.md`

## 3. 证据

- 消融 W：`docs/mihuanyuantu-v2/input/DET-SCORE-OPTIMIZE-ablation-w-2026-11-14.txt`  
- W 结论：`.../DET-SCORE-OPTIMIZE-ablation-w-conclusion-2026-11-14.md`  
- R4 门禁+结论：`.../DET-SCORE-OPTIMIZE-r4-measure-gate-2026-11-14.md`  
- R4 全文：`.../DET-SCORE-OPTIMIZE-ablation-r4-2026-11-14.txt`  
- 协议 C 全文：`.../DET-SCORE-OPTIMIZE-protocol-c-2026-11-14.txt`  
- 协议 C 结论：`.../DET-SCORE-OPTIMIZE-protocol-c-conclusion-2026-11-14.md`  
- 主审计 / 可行性：`.../DET-SCORE-OPTIMIZE-main-audit-2026-11-14.md`、`.../feasibility-gate-2026-11-14.md`

## 4. 下一步（需管理员）

1. ~~SHORTFALL 下推送止血~~ → **已 push** · PR #55  
2. **非作者账号**审合 #55（squash；作者不得自评自合）  
3. 是否改裁 Q1——**不得**借 SHORTFALL 放宽 PASS_SCORE；是否另开新测量门禁（不得升 R4 默认）
