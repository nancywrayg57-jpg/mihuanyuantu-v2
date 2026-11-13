# FIVE-LAYER-LEGACY-ALIGN-SCORE-2026-11-13 · Constraint Ledger

工单：桌面 `蜜獾原图-v2-五层对齐旧版提分工单-2026-11-13.md`  
管理员确认：2026-11-13 初裁（Q1=A … Q12）；**2026-11-13 复裁放宽**（聊天）

## 已锁定裁决

| ID | 裁决 | 追溯 |
| --- | --- | --- |
| Q1 | 同样本均分 `total_score` 提升 ≥10（**保持**） | 初裁 A；复裁「保持提分标准」 |
| Q2 | 样本 `测试用/图片`（50 JPG + manifest）（**不改**） | 初裁；复裁「样本集不改」 |
| Q3 | 允许弱暗角 | 初裁 |
| Q4 | **允许色差**（复裁放开） | 复裁「Q4/8允许放开」 |
| Q5 | 允许弱锐化 + 中间 JPEG 重压 | 初裁 |
| Q6 | 增加旧式 1D 频域对照路径（须双路径证据） | 初裁 |
| Q7 | 增强稀疏像素；允许非几何极弱频谱扰动；禁几何与可见调色 | 初裁 |
| Q8 | **允许 Layer0**（复裁放开；旧 `aiImageProcessor` 快照仍缺，见下方 ASSUMPTION） | 复裁 |
| Q9 | EXIF 扩旧对照清单 + FocalPlane 库；空值跳过 | 初裁 |
| Q10 | 必须真 Gemini；不改 PASS_SCORE=75 | 初裁 |
| Q11 | MAD **仅观测、不否决**（复裁）；仍禁故意糊图提分 | 复裁「Q11改成仅观测，不否决」 |
| Q12 | 端测通过后允许推送/PR；**允许先冻结分支** | 初裁 + 复裁 |
| §9 | 授权本单编码 | 初裁 |

## 冲突 / 歧义（不私自调和）

| ID | 说明 | 处置 |
| --- | --- | --- |
| C-PHYS-TUNE | s2-five-layer-2 曾阻尼噪声 vs 本单提分加强 | 升 `s2-five-layer-3`；v2 可切回 |
| C-OLD-REPO | GitHub 旧仓本机未 clone | W0 以本地快照 SHA 为准 |
| C-EXIF-PARTIAL | main 已有 optional_exif 子集 | W3 补全 + FocalPlane |
| C-LAYER0 | 旧 Layer0 快照缺 `aiImageProcessor.ts` | **[ASSUMPTION]** 默认本地光学 Layer0（微反差+质感预通道）；`ALIGN_LAYER0_IMG2IMG=1` 且 generation Key 可用时改走供应商图生图（低 strength） |

## 硬红线（仍有效）

- 不整包迁 Node；不跑旧 Node 后端
- 不改 PASS_SCORE；fixture 不作验收
- 字节下限；禁 60%–80% 与平台 resize
- 层序：**Layer0（可选）→** L1→L2→L3→L4→L5
- 密钥只读 `生产物料/`
- 禁故意糊图提分（Q11 观测不等于允许糊图刷分）

## 参数假设（复裁后可扫档）

- 暗角：legacy cos^4 × scale≈0.85（可测）
- 色差：legacy 焦距→强度表；红/蓝通道亚像素级错位
- Layer0：光学预通道 strength≈0.18；可选 img2img strength≈0.12
- L1：ISO 地板 400 + legacy `0.5*√(ISO/100)×intensity`
- L2/L3：加强；`freq_mode=auto` 选优；hybrid 留证
- MAD：日志观测（prefer 3.5 / 参考硬顶 6.0），**不淘汰参数组、不 fail 端测**
- Pipeline：`s2-five-layer-3`
- 冻结点：`190d4c4`（放宽前 checkpoint）

## 样本与对照证据指针

- 样本哈希：`docs/mihuanyuantu-v2/input/FIVE-LAYER-LEGACY-ALIGN-sample-sha256.json`
- 旧快照哈希：`docs/mihuanyuantu-v2/input/FIVE-LAYER-LEGACY-ALIGN-legacy-snapshot-sha256.json`
- 对照笔记：`docs/mihuanyuantu-v2/input/FIVE-LAYER-LEGACY-ALIGN-compare-notes.md`
- 端测日志：`/tmp/five-layer-legacy-align-e2e.log`

## 端测瓶颈纪要

### 放宽前
禁色差/Layer0 + MAD 硬否决：`gain≈1.42`（n=12）。

### 复裁后（Q4/Q8/Q11）
- 已实现：色差、光学 Layer0、MAD 仅观测、Gemini 多包选优（`detector_score`）。
- 供应商图生图 Layer0：代码已接 `generate_images`；**本机解析 `apis.aoju.ai` 失败**（ConnectError / 曾 Proxy 403），端测无法走真 img2img。
- 光学+CA+选优后增益仍约 **1.6～1.7**（n=8/12），未达 Q1≥10。
- 冻结点：`190d4c4`；后续复裁改动在同分支继续提交。
