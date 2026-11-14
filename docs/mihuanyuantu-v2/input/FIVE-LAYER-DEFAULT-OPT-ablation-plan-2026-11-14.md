# FIVE-LAYER-DEFAULT-OPT · 消融计划（W1）

日期：2026-11-14  
相对 H0：当前 main 止血默认；**一次一变量**。

## 矩阵

| 臂 | 杠杆 | 覆写 | 档位 | 预期维 | 退出 |
| --- | --- | --- | --- | --- | --- |
| H0 | 基线 | 全空 | optical=0.32 noise=1.55 sharpen=on vignette=0.85 Q=_QUALITIES | — | 冻 mean / 过75 |
| A1a–c | 光学 Layer0 | `ALIGN_LAYER0_OPTICAL_STRENGTH` | **0** / **0.16** / **0.24**（相对 H0=0.32） | noise/overall | Δ≥+3 或伤分停该杠杆 |
| A2a–b | L1 噪声 | `ALIGN_NOISE_INTENSITY` | **0.85** / **1.0**（相对 H0=1.55） | noise | 同上 |
| A3 | 锐化 | `ALIGN_SHARPEN=0` | off vs H0 on | overall/noise | 同上 |
| A4 | 暗角 | `ALIGN_VIGNETTE_SCALE=0.50` | 减弱 vs H0=0.85 | light | 同上 |
| A5 | JPEG | `ALIGN_JPEG_MILD_SWEEP=1` + `90,93,96` | 换掉 98/100 | noise/清晰 | 掉分则否决 |
| A6 | PG | `ALIGN_PG_NOISE=1` scale=0.40 | 仅测量 | noise | **不升默认**除非 §2.4 |

## 达标（§2.2）

- `DEFAULT_OPT_MEAN_GAIN`：相对 H0 mean Δ≥**+3.0** 且无维均 Δ≤−5  
- `DEFAULT_OPT_PASS75_LIFT`：过 75 张数 **+2**  
- 升默认另需单变量归因 + 管理员确认  

## 脚本

`aojuai-main/backend/scripts/det_score_default_opt_e2e.py`  
`DEFAULT_OPT_ARM=H0|A1|A2|A3|A4|A5|A6` + 臂内档位 env。
