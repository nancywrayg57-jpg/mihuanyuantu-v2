# FIVE-LAYER-LEGACY-ALIGN-SCORE-2026-11-13 · Constraint Ledger

工单：桌面 `蜜獾原图-v2-五层对齐旧版提分工单-2026-11-13.md`  
管理员确认：2026-11-13 聊天（Q1=A … Q12 端测后可推）

## 已锁定裁决

| ID | 裁决 | 追溯 |
| --- | --- | --- |
| Q1 | 同样本均分 `total_score` 提升 ≥10 | 管理员勾选 A |
| Q2 | 样本 `测试用/图片`（50 JPG + manifest） | 路径书面指定 |
| Q3 | 允许弱暗角 | 书面「Q3允许恢复」 |
| Q4 | 禁止色差 | 书面「Q4否」 |
| Q5 | 允许弱锐化 + 中间 JPEG 重压 | 书面「Q5是」 |
| Q6 | 增加旧式 1D 频域对照路径（须双路径证据） | 书面 |
| Q7 | 增强稀疏像素；允许非几何极弱频谱扰动；禁几何与可见调色 | 书面 |
| Q8 | 不做 Layer0 | 书面「Q8否」 |
| Q9 | EXIF 扩旧对照清单 + FocalPlane 库；空值跳过 | 书面 |
| Q10 | 必须真 Gemini；不改 PASS_SCORE=75 | 书面 |
| Q11 | 不把 MAD=3.5 当提分一票否决；禁故意糊图。[ASSUMPTION] 优选≤3.5；硬顶≤6.0 | 书面 + 计划假设 |
| Q12 | 端测通过后允许推送/PR | 书面 |
| §9 | 授权本单编码 | 书面 |

## 冲突 / 歧义（不私自调和）

| ID | 说明 | 处置 |
| --- | --- | --- |
| C-PHYS-TUNE | s2-five-layer-2 曾阻尼噪声 vs 本单提分加强 | 升 `s2-five-layer-3`；v2 可切回 |
| C-OLD-REPO | GitHub 旧仓本机未 clone | W0 以本地快照 SHA 为准（见 `FIVE-LAYER-LEGACY-ALIGN-legacy-snapshot-sha256.json`） |
| C-EXIF-PARTIAL | main 已有 optional_exif 子集 | W3 补全对照清单 + FocalPlane 库查找 |
| C-LAYER0 | 旧 Layer0 快照缺 aiImageProcessor.ts | Q8 本单不做 |

## 硬红线（未放宽）

- 不整包迁 Node；不跑旧 Node 后端
- 不改 PASS_SCORE；fixture 不作验收
- 字节下限；禁 60%–80% 与平台 resize
- 层序 L1→L2→L3→L4→L5
- 密钥只读 `生产物料/`

## 参数假设（可扫档）

- 暗角：角点相对中心压暗 ≤约 6%（中灰探针）
- L1：处理 ISO 地板 280 + `σ = clamp(0.55*sqrt(ISO/100)+1.00, 1.35, 2.40)`；auto 强度档可再乘 1.0–1.3
- L2 2D：高频门限 `_L2_RADIUS=0.42`、`_L2_SIGMA=0.030`；1D 相位约 `0.0035`；默认 `auto` 在 2d/1d×强度档按 MAD 优选（hybrid 仅留证）
- L3 稀疏上限 2200；极弱频谱 `0.004`
- 中间 JPEG 重压质量 92；弱 unsharp（radius=0.65, percent=48）
- Pipeline：`s2-five-layer-3`

## 样本与对照证据指针

- 样本哈希：`docs/mihuanyuantu-v2/input/FIVE-LAYER-LEGACY-ALIGN-sample-sha256.json`
- 旧快照哈希：`docs/mihuanyuantu-v2/input/FIVE-LAYER-LEGACY-ALIGN-legacy-snapshot-sha256.json`
- 对照笔记：`docs/mihuanyuantu-v2/input/FIVE-LAYER-LEGACY-ALIGN-compare-notes.md`
- 端测日志：`/tmp/five-layer-legacy-align-e2e.log`

## 端测瓶颈纪要（2026-11-13，真 Gemini）

在 **不改 PASS_SCORE、禁色差/Layer0、MAD 硬顶 6、弱暗角** 前提下，多轮参数扫描（含 1D/2D、结构化噪点、Gemini 多包重排）后：

| 对照 | 观察 |
| --- | --- |
| v3 − v2 | 同样本均分增益约 **0–5**，达不到 Q1 的 **≥10**；单张 delta 常被检测器方差（±5～15）淹没 |
| v3 − source | 偶发单张 +10～17，均分仍常 <10 |
| 过强 FFT/噪声 | Gemini reason 出现 AI artifacts / composite，总分回落 |

**结论（书面停加码）**：瓶颈在「检测器对电商原图的粗粒度打分 + 硬红线禁止的旧版强手段（色差/Layer0/强糊化）」；继续加码像素易超 MAD 或引入伪影，不能稳定兑现 Q1。不改 `PASS_SCORE`；W5 以 `ALIGN_W5_E2E_SHORTFALL` 留证，PR 按 Q12 须等增益达标。

**最近一次可审计数字（ALIGN_SAMPLE_N=12，seed=20261113，真 Gemini）**：
`mean_baseline_v2=65.08`；`mean_v3=66.50`；`gain=1.42`（目标 ≥10）。日志：`/tmp/five-layer-legacy-align-e2e.log`。
