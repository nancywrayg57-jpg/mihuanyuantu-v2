# 旧模块对照笔记（只读 · W0）

对照源：`输入材料/旧版可复用模块/01_源码参考/原样快照/server/`（见同目录 `*-legacy-snapshot-sha256.json`）。  
旧 GitHub `gzhbs/mihuanyuantu.git`：本机未检出；不以远程未验证 commit 为准。

## 参数表（定性 → v3 映射）

| 旧模块 | 关键参数/行为 | v2（five-layer-2） | v3 获准动作 |
| --- | --- | --- | --- |
| imagePhysicalizer | `isoToNoiseSigma=0.5√(ISO/100)` | 阻尼曲线顶 1.85 | 加强但仍封顶 2.40 |
| imagePhysicalizer | `apertureToVignettingStrength` 最大 0.35 | 无暗角 | 弱暗角，角点压暗 ≤~8% |
| imagePhysicalizer | 色差 composite 缺陷 | 无 | **允许受控弱色差**（Q4 复裁）；禁止搬旧烂桩（丢弃 composite + 仅饱和度×1.02） |
| imagePhysicalizer | JPEG 重压 / 锐化 | 无 | 弱锐化 + 中间 JPEG 重压（Q5） |
| frequencyProcessor | 逐行 1D FFT，低频 5% 保护，相位扰动 ~0.004 | 仅 2D rfft2 | 保留 2D + **新增 1D 对照路径** |
| fingerprintDestroyer | 稀疏像素；另有几何/调色 | 稀疏 512 | 稀疏增强；极弱频谱；**禁几何/可见调色** |
| exifToolWriter | 多 tag + CAMERA_SPECS FocalPlane | 核心 + 部分可选 | 对照清单 + FocalPlane 库；空值跳过 |
| uploadSimulator | 平台矩阵/resize | 通用电商 profile | 保持通用；不迁平台矩阵 |
| sizeOptimizer | 60%–80% 体积 | 字节下限 | 保持下限 |
| Layer0 aiImageProcessor | 图生图 | 光学 Layer0 默认；可选供应商 img2img | **Q8 复裁放开**；快照仍缺文件 → ASSUMPTION 本地光学 + `ALIGN_LAYER0_IMG2IMG=1` |

## 层序差异（不得回迁旧「入口内先频域」）

旧 physicalizer 入口可先调 frequency；v2/v3 **必须** L1→L2→L3→L4→L5。
