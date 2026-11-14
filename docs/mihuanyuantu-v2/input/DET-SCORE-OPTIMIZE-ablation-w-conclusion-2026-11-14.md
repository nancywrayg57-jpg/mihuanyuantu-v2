# DET-SCORE · 协议 W 消融结论（OPEN_PARTIAL 后）

日期：2026-11-14  
证据全文：`DET-SCORE-OPTIMIZE-ablation-w-2026-11-14.txt`（同源 `/tmp/det-score-ablation-e2e.log`）  
条件：n=12，seed=20261113，`score_fn=None`，`ALIGN_LAYER0_IMG2IMG=0`，`_CA_INTENSITY=0`，真 Gemini，`PASS_SCORE=75` 未改。

## 汇总

| 焦距 | mean_v2 (R0) | mean_v3 (R_post) | gain_vs_v2 | v3 过 75 | 色差类 reason |
| --- | ---: | ---: | ---: | ---: | ---: |
| 8mm | 66.25 | **62.17** | **−4.08** | 0/12 | **0/12** |
| 26mm | 66.33 | **61.67** | **−4.67** | 0/12 | **0/12** |

对照：白名单前预览库 v3 均分≈**49.3**（CA 开、短焦错位）。本臂 8mm mean_v3≈**62.2** → 相对历史塌陷约 **+13** 回升（仍非 Q1）。

## 假说判定（按消融矩阵预先规则）

| ID | 判定 | 依据 |
| --- | --- | --- |
| P-CA-PHONE | **支持（非唯一因）** | 色差/红蓝 reason **0/12**；短焦均分从≈49 回到≈62 |
| P-V3-OVERDRIVE | **仍待测** | 相对 v2 仍约 −4；reason 转向噪点/光影/合成；**本轮未开 C/R4** |
| P-L0-ASYNC | 缺陷已修；本臂 flag=0 **未测提分方向** | R3（显式 Layer0=1）未跑 |
| P-ARCH-CEILING / Q1 | **仍 UNPROVEN / 本臂非 Q1** | 协议 W 无 score_fn；gain_vs_v2&lt;0 且 ≠合同协议 C |

## 门禁后续

- **保留** A+D+B 默认（缺陷修复 + CA 近零 + Layer0 默认关）——有止血证据。  
- ~~不自动开 R4~~ → 管理员选项 1：**已测**；**P-V3-OVERDRIVE NOT_CONFIRMED**（`DET-SCORE-OPTIMIZE-r4-measure-gate-2026-11-14.md`）。  
- ~~另跑协议 C~~ → 管理员选项 2：**已跑**；gain=**+1.17** → `ALIGN_W5_E2E_SHORTFALL`（`DET-SCORE-OPTIMIZE-protocol-c-conclusion-2026-11-14.md`）。  
- **不宣称** `ALIGN_W5_E2E_PASS`；**暂不推送**；**不升** R4 测量值为默认。  
