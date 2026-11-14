# DET-SCORE · 协议 C 冲 Q1 结论

日期：2026-11-14  
证据全文：`DET-SCORE-OPTIMIZE-protocol-c-2026-11-14.txt`  
门禁：`DET-SCORE-OPTIMIZE-r4-measure-gate-2026-11-14.md`（管理员选项 1+2）

## 跑测配置

| 项 | 值 |
| --- | --- |
| 样本 | 合同 12 张（`product_01`…`12`），seed=`20261113` |
| 焦距 | 26mm |
| score_fn | 开（多包选优） |
| Layer0 | `ALIGN_LAYER0_IMG2IMG=0`（本轮止血默认） |
| CA | `_CA_INTENSITY=0`（代码） |
| R4 覆写 | **关**（光学/噪声用代码默认，非测量档） |
| PASS_SCORE | **75 未改** |

## 结果

| 指标 | 值 |
| --- | --- |
| mean_baseline_v2 | **65.75** |
| mean_v3 | **66.92** |
| gain（相对 v2） | **+1.17**（目标 ≥**10**） |
| v3 过 75 | **2/12** |
| 门禁标记 | **`ALIGN_W5_E2E_SHORTFALL`** |
| 脚本 rc | 4 |

对照历史同合同臂：英短最好 gain≈**3.83**；C1 中文 gain=**1.00**。本臂 Layer0 关 + CA 恒等 + score_fn → **+1.17**，仍远低于 Q1。

## 假设裁定（本臂）

| 假设 | 裁定 | 依据 |
| --- | --- | --- |
| Q1 / P-ARCH-CEILING | **UNPROVEN → 本臂仍 SHORTFALL** | gain=1.17≪10；停止把剩余光学/噪声/R4 当达标手段加码 |
| P-CA-PHONE | 与 W 一致：非本臂主因 | CA=0；合同 26mm |
| P-L0-ASYNC | 已止血；本臂 Layer0 关 | `layer0_note=None` |
| P-V3-OVERDRIVE | 见 R4 测量 | R4 臂 `NOT_CONFIRMED`；协议 C 未开 R4 |

## 停止线

- **不**放宽 `PASS_SCORE` / Q1 阈值。  
- **不**把 R4 测量值写成新默认。  
- **不**在未授权下 push / S7。  
- 下一动作仅管理员：改裁 Q1、授权推送止血、或另开**新**测量门禁（不得复用本 SHORTFALL 当达标）。
