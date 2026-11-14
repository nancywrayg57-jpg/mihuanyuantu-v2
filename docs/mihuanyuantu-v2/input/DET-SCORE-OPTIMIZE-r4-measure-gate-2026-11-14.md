# DET-SCORE-OPTIMIZE · R4 测量门禁 + 协议 C 授权

日期：2026-11-14  
管理员裁决：选项 **1 + 2**（聊天）  
前提：协议 W 消融已显示 CA 近零后 8mm mean_v3≈62（史≈49），相对 v2 仍约 −4；色差 reason 0/12。

## 裁定

| 项 | 裁定 |
| --- | --- |
| R4 测量编码 | **OPEN_MEASUREMENT_ONLY** |
| 协议 C 冲 Q1 | **授权跑测**（不改 PASS_SCORE） |
| 默认常量落库 | **禁止**在未出测量结论前把 R4 数值写成新默认 |
| Q1 | 仍以协议 C、`gain≥10` 为准；W/R4 不得冒充 Q1 |
| 推送 | 仍 **暂不推送**（除非另裁） |

## R4 白名单（仅测量覆写）

允许通过 **Settings / env 空默认覆写**（空=沿用代码默认）读取：

- `ALIGN_LAYER0_OPTICAL_STRENGTH`：测量臂 `0.16`（默认代码仍 0.32）
- `ALIGN_NOISE_INTENSITY`：测量臂 `1.0`（默认代码仍 1.55）
- `ALIGN_FIXED_MODE_SCALE`：测量臂 `1.0`（默认代码仍 0.85）

可改文件：`config.py`（三键空默认）、`five_layer.py`（读取覆写的辅助函数；**不改**模块级默认常量数值）、测量脚本、测试（覆写行为）。

禁止：改 `PASS_SCORE`、换模型、开指纹/几何、把测量值 commit 为新默认、生产切 v2。

## 协议 C

- 样本：合同 12 张；seed=`20261113`；26mm；`score_fn` 多包选优  
- Layer0：本轮先用默认 `ALIGN_LAYER0_IMG2IMG=0`（与止血一致）；结果表单独标注  
- 退出：`gain≥10` → `ALIGN_W5_E2E_PASS`；否则 `SHORTFALL`，停止把 R4 当达标手段加码  

## 证据路径

- R4：`docs/mihuanyuantu-v2/input/DET-SCORE-OPTIMIZE-ablation-r4-2026-11-14.txt`  
- 协议 C：`docs/mihuanyuantu-v2/input/DET-SCORE-OPTIMIZE-protocol-c-2026-11-14.txt`  
- 协议 C 结论：`docs/mihuanyuantu-v2/input/DET-SCORE-OPTIMIZE-protocol-c-conclusion-2026-11-14.md`

## 测量结论（已跑完）

### R4（协议 W · 8mm · 光学/噪声降档覆写）

| 指标 | 值 |
| --- | --- |
| mean_v2 | 66.83 |
| mean_r4 | **63.0** |
| gain_vs_v2 | **−3.83** |
| vs 协议 W 后 8mm mean_v3=62.17 | **Δ+0.83** |
| P-V3-OVERDRIVE | **`NOT_CONFIRMED`**（\|R4−prior\|&lt;3） |
| 默认落库 | **禁止**；覆写仅测量 |

### 协议 C（Q1 · 26mm · score_fn · Layer0=0 · R4 关）

| 指标 | 值 |
| --- | --- |
| mean_v2 | 65.75 |
| mean_v3 | **66.92** |
| gain | **+1.17**（目标 ≥10） |
| 门禁 | **`ALIGN_W5_E2E_SHORTFALL`** |
| Q1 | 仍 **UNPROVEN** / 本臂未达标 |

### 统一停止线

R4 未证实过驱动主因；协议 C 未达 Q1。**停止**把光学/噪声再降档当达标手段加码；`PASS_SCORE=75` 不改；未授权不推送。
