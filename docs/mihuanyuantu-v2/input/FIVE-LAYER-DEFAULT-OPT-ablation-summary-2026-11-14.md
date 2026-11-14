# FIVE-LAYER-DEFAULT-OPT · 消融汇总

日期：2026-11-14  
H0（score_fn=None）：mean=**61.42**，过75=**0/12**  
证据：`FIVE-LAYER-DEFAULT-OPT-e2e-h0-2026-11-14.txt` + `…-a1…a5-…`

## 单变量表（相对 H0）

| 臂 | mean | Δmean | 过75 | Δ过75 | MEAN_GAIN | PASS75_LIFT |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| A1 optical=0 | 65.92 | +4.50 | 2 | +2 | **Y** | **Y** |
| A1 optical=0.16 | 64.42 | +3.00 | 0 | 0 | **Y** | N |
| A1 optical=0.24 | **67.25** | **+5.83** | 2 | +2 | **Y** | **Y** |
| A2 noise=0.85 | 66.50 | +5.08 | 2 | +2 | **Y** | **Y** |
| A2 noise=1.0 | 63.00 | +1.58 | 0 | 0 | N | N |
| A3 sharpen off | 64.00 | +2.58 | 0 | 0 | N | N |
| A4 vignette=0.50 | 67.08 | +5.66 | 1 | +1 | **Y** | N |
| A5 JPEG 90/93/96 | 65.75 | +4.33 | **3** | **+3** | **Y** | **Y** |

五维：上表达标臂均无维均 Δ≤−5。

## 升默认裁定（Q-ONE-VAR）

- **候选**：`_LAYER0_OPTICAL_STRENGTH` **0.32 → 0.24**（A1 最优 mean，双门禁）  
- **不本轮升**：噪声 0.85（另变量）、JPEG 网格（另变量）、vignette 0.50（未达 PASS75_LIFT）  
- **保持关**：CA、Layer0 img2img、Bayer；PG 不升  
- 旧 Q1：**未跑 probe**；**不宣称**相对 v2 +10  

## 确认端测（新默认无覆写）

证据：`FIVE-LAYER-DEFAULT-OPT-e2e-confirm-optical-024-2026-11-14.txt`  
mean=**67.25**，过75=**2/12**（与 A1_optical_0.24 一致）；相对旧 H0 Δ=+5.83、过75 +2 → 双门禁复验 **PASS**。

## 一句话

**默认已优化并达标（光学 Layer0 0.32→0.24）**；消融单变量证据满足 MEAN_GAIN + PASS75_LIFT；确认端测复现。
