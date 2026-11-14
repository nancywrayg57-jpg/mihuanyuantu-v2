# DET-SCORE-NONLEGACY · 可行性门禁（主会话裁定）

日期：2026-11-14  
输入：

- [R1](5ada87ba-7a02-45dc-949d-ce8c29ce8ece) `DET-SCORE-NONLEGACY-web-research-2026-11-14.md`
- [R2](d4da7652-33a5-4c91-a221-11a302510f58) `DET-SCORE-NONLEGACY-redline-filter-2026-11-14.md`
- [A](8996f9c5-8c99-4ea3-b63b-71384d5a8248) `DET-SCORE-NONLEGACY-landing-map-2026-11-14.md`
- 主交叉：`DET-SCORE-NONLEGACY-main-crosscheck-2026-11-14.md`

标记：`NONLEGACY_FEASIBILITY_PASS`（≥1 项 OPEN_PILOT，无红线）

## 1. 总裁定

| 标记 | 值 |
| --- | --- |
| `NONLEGACY_FEASIBILITY_PASS` | **YES** |
| 默认管线 | **仍止血**（CA=0、Layer0 默认 0）；试点仅 **env 测量臂** |
| PASS_SCORE | **75 不改** |
| 对抗管线 | **REJECT**（R2 全表） |
| 旧 ALIGN 加码 | **关闭**（Q-NO-LEGACY-LOOP） |

## 2. 分项判定

| ID | 候选 | 判定 | 理由 |
| --- | --- | --- | --- |
| P1 | 弱 Bayer RGGB 往返（无噪声） | **OPEN_PILOT** | R1 WEAK-BAYER-RT；R2 A1；落点 optical 后 / L1 前；numpy 前馈；默认关 |
| P2 | 平坦区弱 Poisson–Gaussian | **OPEN_PILOT** | R1 LINEAR-PG；R2 A2；只替换 L1 平坦像素；与 R4 `ALIGN_NOISE_INTENSITY` 解耦；默认关 |
| P3 | WEAK-FWD-ISP 串联（Bayer+PG） | **DEFER** | 须先单变量 H0/P1/P2；同开无法归因 |
| P4 | JPEG 温和扫档（换掉 98/100） | **DEFER** | 可能伤清晰/噪点；非本轮优先 |
| P5 | Layer0 测量臂 | **OPEN_MEASURE_EXISTING** | 代码已有；默认保持 0；仅脚本 `=1`；本轮不改正文默认 |
| — | ISPCloak / FPBA / StealthDiffusion / 梯度 mask / 改 PASS / 恢复 CA·Layer0 默认 | **REJECT** | Q-NO-ADV / Q-PASS / Q-HEMO |

## 3. OPEN_PILOT 编码白名单

| 文件 | 允许改动 |
| --- | --- |
| `five_layer.py` | `_weak_bayer_roundtrip`、`_poisson_gaussian_flat_noise`、`_flag_setting_on`；挂钩 `_l1_l3`（默认关） |
| `config.py` | `ALIGN_BAYER_ROUNDTRIP`、`ALIGN_BAYER_STRENGTH`、`ALIGN_PG_NOISE`、`ALIGN_PG_SCALE`、`ALIGN_PG_FLAT_THR`（空默认） |
| `test_s2_five_layer.py` | 旗标关/强度 0 恒等；开时形状不变 |
| `scripts/det_score_nonlegacy_pilot_e2e.py` | H0 vs P1/P2 真 Gemini |
| `governance_tools/runtime_env.py` | GOV-10 allowlist 新脚本 |

**禁改：** `PASS_SCORE`、`_CA_INTENSITY`、`ALIGN_LAYER0_IMG2IMG` 默认、`_QUALITIES`、R4 默认升档、检测提示。

## 4. 端测契约（W4）

- H0：止血（全新旗标关）· 对照冻结 mean **66.92**（同配置重跑以当次为准）  
- P1：仅 Bayer  
- P2：仅 PG  
- 开发机真 Gemini；合同 12 张；seed `20261113`  
- 增益标记 `NONLEGACY_PILOT_E2E_GAIN`；相对 v2≥10 另标 `NONLEGACY_Q1_PROBE` PASS/SHORTFALL  
- SHORTFALL **不**宣称产品达标  

## 5. 一句话

**可用并进入测量臂编码**：固定 Bayer 往返 + 弱平坦区 Poisson–Gaussian；对抗与默认恢复 CA/Layer0 仍禁。增益未测前不算产品达标。
