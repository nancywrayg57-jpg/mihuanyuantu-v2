# 替代方案调研报告 v1（D2）

| 字段 | 内容 |
| --- | --- |
| 工单 | MH-YT-20261031-01 v1.1 |
| 日期 | 2026-10-31 Asia/Shanghai |
| 声明 | **仅为模型判定能力调研，不构成 TikTok/小红书/微信等平台验收承诺** |
| Gemini 对比局限 | 按 Q8 **不复跑 Gemini**；差异为定性对照（见 §4） |
| 链接核实 | 下列主表链接均于 2026-10-31 经 GitHub API / HTTP / HF API 打开核实 |

---

## 1. 结论先行

### 推荐（Top3，进入阶段 C POC）

| 排名 | 候选 | 路线 | 理由（成本优先） |
| --- | --- | --- | --- |
| 1 | **lynote-ai/ai-image-detector**（默认 UnivFD） | 监督式 / CLIP 特征 | MIT；`pip` 即用；CLI+API；活跃（2026-08）；零调用费 |
| 2 | **e3ntity/nonescape**（mini ONNX） | 监督式分类器 | Apache-2.0；官方权重 CDN；ONNX 可 CPU；零调用费 |
| 3 | **buildborderless/CommunityForensics-DeepfakeDet-ViT**（社区权重，源码 JeongsooP/Community-Forensics） | 大规模监督 ViT | MIT；2.7M/4803 生成器训练叙事；可本地 transformers；零调用费 |

### 并行观察（不进本轮 Top3 全量，因密钥/算力）

- **多模态零样本**：Qwen2.5-VL / Qwen3-VL 低价 API（最接近 Gemini 可解释路线，但需 Key，单张成本需按 token 折算）。
- **商用交叉验证**：Sightengine（免费 2000 ops/月）、Illuminarty（基础检测宣称免费）、Hive（需绑卡领额度）。

### 不推荐作为本项目主替代

- **纯 EXIF 规则引擎**：处理流水线本身改写元数据，单靠它无验证意义（工单技术路线 1）。
- **NPR / FreqNet 官方仓**：核实日 **无 SPDX 许可证** → 按规则剔除，不得进正式主表。
- **Smogy/SMOGY / Organika/sdxl-detector**：HF 卡片为 **CC-BY-NC** → 商业 SaaS 主路径不合规。
- **AEROBLADE**：重建误差路线对扩散有效，但需多 AE + GPU 级算力，且仓库许可证 API 为空；本环境无 GPU。
- **「永远判 physical」退化策略**：触犯 §6.6 反指标。

### 对蜜獾原图的关键定性判断

本项目处理含**频域扰动**。频域/指纹类检测器可能被「骗过」导致未通过率虚低（风险 R1），也可能仍抓住残留痕迹导致不达标（R2）。因此：**必须先过原图有效性门禁，再看处理图 B 指标**；Top3 交叉验证，禁止单检测器定论。

---

## 2. 候选长名单（≥20，初筛）

| # | 候选 | 链接 | 一句话定位 | 初筛 |
| --- | --- | --- | --- | --- |
| L1 | lynote-ai/ai-image-detector | https://github.com/lynote-ai/ai-image-detector | UnivFD 封装 + 多后端集成 | 入主表 |
| L2 | WisconsinAIVision/UniversalFakeDetect | https://github.com/WisconsinAIVision/UniversalFakeDetect | UnivFD 原论文实现 | 入主表（与 L1 同源，合并讨论） |
| L3 | e3ntity/nonescape | https://github.com/e3ntity/nonescape | 开源权重 + JS/Python/ONNX | 入主表 |
| L4 | JeongsooP/Community-Forensics | https://github.com/JeongsooP/Community-Forensics | Community Forensics 训练代码 | 入主表 |
| L5 | HF CommunityForensics-DeepfakeDet-ViT | https://huggingface.co/buildborderless/CommunityForensics-DeepfakeDet-ViT | 社区打包 ViT 推理权重 | 入主表（L4 权重入口） |
| L6 | Michel-liu/FatFormer | https://github.com/Michel-liu/FatFormer | CVPR2024 伪造自适应 Transformer | 入主表 |
| L7 | jonasricker/aeroblade | https://github.com/jonasricker/aeroblade | 扩散 AE 重建误差（CVPR2024） | 入主表（许可待确认） |
| L8 | Ekko-zn/AIGCDetectBenchmark | https://github.com/Ekko-zn/AIGCDetectBenchmark | 多检测器基准套件 | 入主表（工具集） |
| L9 | sadjadeb/DetectZoo | https://github.com/sadjadeb/DetectZoo | 统一多模态检测工具包 | 入主表 |
| L10 | truebees Image-Deepfake-Detectors-Public-Library | https://github.com/truebees-ai/Image-Deepfake-Detectors-Public-Library | 八检测器统一 CLI | 入主表 |
| L11 | Sightengine AI Detection | https://sightengine.com/pricing | 商用 API，免费档 2000/月 | 入主表 |
| L12 | Illuminarty | https://www.illuminarty.ai/en/ | 商用/免费基础检测 + API | 入主表 |
| L13 | Hive AI-Generated Content API | https://thehive.ai/apis/ai-generated-content-classification | 商用深度伪造/AIGC API | 入主表（兜底） |
| L14 | Qwen2.5-VL via OpenRouter/SiliconFlow | https://openrouter.ai/qwen/qwen2.5-vl-72b-instruct | 多模态零样本（类 Gemini） | 入主表 |
| L15 | chuangchuangtan/NPR | https://github.com/chuangchuangtan/NPR-DeepfakeDetection | 邻域像素上采样痕迹 | **剔除：许可证不明** |
| L16 | chuangchuangtan/FreqNet | https://github.com/chuangchuangtan/FreqNet-DeepfakeDetection | 频域感知检测 | **剔除：许可证不明** |
| L17 | Smogy/SMOGY-Ai-images-detector | https://huggingface.co/Smogy/SMOGY-Ai-images-detector | HF 分类器 | **剔除主路径：CC-BY-NC-4.0** |
| L18 | Organika/sdxl-detector | https://huggingface.co/Organika/sdxl-detector | SDXL 风格检测器 | **剔除主路径：CC-BY-NC-3.0** |
| L19 | graydove/Awesome-AIGC-Image-Detection | https://github.com/graydove/Awesome-AIGC-Image-Detection | 综述/榜单导航 | 仅索引，非检测器 |
| L20 | 纯 EXIF 规则引擎（自研） | n/a | 读 Make/Software/C2PA | **辅助信号，不进 Top3** |
| L21 | DIRE（经 AIGCDetectBenchmark） | 见 L8 | 扩散重建误差+分类器 | 算力高，作长名单观察 |
| L22 | ArtLens (rishiigupta04) | https://github.com/rishiigupta04/ArtLens | 热力图解释 + HF Space API | stars≈0，成熟度不足，观察 |

核实摘录（GitHub API，2026-10-31）：

| repo | stars | license | pushed_at (UTC) |
| --- | --- | --- | --- |
| lynote-ai/ai-image-detector | 333 | MIT | 2026-08-05 |
| e3ntity/nonescape | 71 | Apache-2.0 | 2025-08-20 |
| WisconsinAIVision/UniversalFakeDetect | 379 | MIT | 2026-08-19 |
| JeongsooP/Community-Forensics | 62 | MIT | 2026-01-06 |
| Michel-liu/FatFormer | 139 | Apache-2.0 | 2024-08-15 |
| jonasricker/aeroblade | 75 | *(API 空)* | 2024-12-09 |
| Ekko-zn/AIGCDetectBenchmark | 436 | *(API 空)* | 2026-03-09 |
| sadjadeb/DetectZoo | 19 | *(API 空)* | 2026-10-23 |
| truebees-ai/...Public-Library | 4 | Apache-2.0 | 2026-10-16 |

---

## 3. 五列对比表（正式候选，缺一不可）

> 未核实链接不得写入；许可证不明已剔除（L15/L16）。AEROBLADE / DetectZoo / AIGCDetectBenchmark 许可证 API 为空：保留说明但 **不得进入 Top3**。

### 3.1 lynote-ai/ai-image-detector（UnivFD 默认）

| 字段 | 内容 |
| --- | --- |
| 项目仓库链接 | https://github.com/lynote-ai/ai-image-detector （MIT，已核实）；上游 https://github.com/WisconsinAIVision/UniversalFakeDetect |
| 部署成本 | 一次性：CPU 可跑（ViT-L/14 特征，内存敏感）/ 可选 GPU；存储约数 GB（CLIP）；持续：¥0；集成：0.5–1 人天 |
| 适用场景 | 能：跨生成器假图概率；不能：局部编辑定位、平台合规证明；对 JPEG/截屏/后处理敏感 |
| 与原 Gemini 差异 | 范式=判别概率≠五维主观分；输入=仅像素（默评测变量）；输出=概率需映射；阈值=可配；可解释性=弱于五维；失败语义=需适配器包装 tech_fail |
| 风险点 | 对蜜獾频域扰动可能失效（R1）；CLIP 依赖；新生成器衰减 |

### 3.2 e3ntity/nonescape

| 字段 | 内容 |
| --- | --- |
| 项目仓库链接 | https://github.com/e3ntity/nonescape （Apache-2.0）；权重 CDN 见 README |
| 部署成本 | 一次性：mini ONNX 轻量；持续：¥0；集成：0.5 人天 |
| 适用场景 | 能：整图 AI/真实；不能：保证对即梦/豆包特化；截屏/二次压缩未保证 |
| 与原 Gemini 差异 | 同 3.1（像素分类器）；无 EXIF 上下文；无可比五维 |
| 风险点 | 2025-08 后提交偏少；训练分布未知；被对抗后处理绕过 |

### 3.3 Community Forensics ViT

| 字段 | 内容 |
| --- | --- |
| 项目仓库链接 | 代码 https://github.com/JeongsooP/Community-Forensics （MIT）；权重 https://huggingface.co/buildborderless/CommunityForensics-DeepfakeDet-ViT （卡片宣称 MIT / 兼容 OpenRAIL 叙事，POC 前再核卡片） |
| 部署成本 | 一次性：~36M ViT，CPU/GPU；持续：¥0（本地）或 HF Inference 按量；集成：1 人天 |
| 适用场景 | 能：大规模生成器覆盖的假图检测叙事；不能：元数据仲裁；人脸特化非目标 |
| 与原 Gemini 差异 | 监督分类 vs 零样本多模态；无五维；阈值自定 |
| 风险点 | HF 打包方≠论文作者；评测数据与国内生成器（即梦/豆包）可能分布外；权重许可表述需再核 |

### 3.4 FatFormer

| 字段 | 内容 |
| --- | --- |
| 项目仓库链接 | https://github.com/Michel-liu/FatFormer （Apache-2.0） |
| 部署成本 | 一次性：需按 README 取权重；GPU 友好；集成：1.5–3 人天 |
| 适用场景 | 能：GAN/扩散泛化（论文声称）；不能：免运维 API |
| 与原 Gemini 差异 | 伪造自适应+频域适配器，与本项目频域扰动**直接对抗**——最该测的一类，但部署重 |
| 风险点 | 2024-08 后维护弱；权重获取链路长；与扰动对抗不确定 |

### 3.5 AEROBLADE

| 字段 | 内容 |
| --- | --- |
| 项目仓库链接 | https://github.com/jonasricker/aeroblade （**许可证 API 空，未进 Top3**） |
| 部署成本 | 高：多 AE（SD1/SD2/Kandinsky）+ LPIPS；需 GPU；集成 2–4 人天 |
| 适用场景 | 能：潜空间扩散重建误差；不能：非扩散生成器、无 GPU 环境 |
| 与原 Gemini 差异 | 训练免费重建误差 vs 主观多模态 |
| 风险点 | 许可不清；算力；对物理化后处理敏感 |

### 3.6 Sightengine AI Detection

| 字段 | 内容 |
| --- | --- |
| 项目仓库链接 | 产品文档/定价 https://sightengine.com/pricing （HTTP 200 核实） |
| 部署成本 | 一次性：0；持续：免费 2000 ops/月，超出约 $0.002/op（约合可低于 0.01 元视汇率）；集成：0.5 人天 |
| 适用场景 | 能：托管 AI/deepfake 图像检测；不能：本地离线、数据不出境 |
| 与原 Gemini 差异 | 黑盒分数；无五维对齐；失败靠 HTTP 错误码 |
| 风险点 | 数据出境（R6）；阈值不透明；免费额度不够 2376 图次（Top3×792），需付费或抽样 |

### 3.7 Illuminarty

| 字段 | 内容 |
| --- | --- |
| 项目仓库链接 | https://www.illuminarty.ai/en/ |
| 部署成本 | 基础分类宣称 $0；Basic $10/月含 10k req/天 API |
| 适用场景 | 能：AI 概率 + 生成器识别（付费）；不能：离线 |
| 与原 Gemini 差异 | 黑盒；可有局部检测（付费） |
| 风险点 | 出境；SLA；免费档是否覆盖批量需实测 |

### 3.8 Hive AI-Generated Content

| 字段 | 内容 |
| --- | --- |
| 项目仓库链接 | https://thehive.ai/apis/ai-generated-content-classification ；定价 https://thehive.ai/pricing |
| 部署成本 | 绑卡后 $50+ 试用额度；按图计费 |
| 适用场景 | 能：生产级 AIGC/deepfake；交叉验证兜底 |
| 与原 Gemini 差异 | 企业黑盒 |
| 风险点 | 出境；成本；供应商锁定同类问题 |

### 3.9 Qwen2.5-VL / 低价多模态 API

| 字段 | 内容 |
| --- | --- |
| 项目仓库链接 | 模型卡/定价参考 https://openrouter.ai/qwen/qwen2.5-vl-72b-instruct ；国内可达 SiliconFlow / DashScope |
| 部署成本 | 按 token；小图+短 JSON schema 有望压到 ≤0.01 元/张（需实测）；无固定 GPU |
| 适用场景 | 能：零样本+可解释文字（最接近 Gemini）；不能：稳定指纹检测、成本锁定难 |
| 与原 Gemini 差异 | **范式最接近**；仍建议默认不喂预设 EXIF，或与「喂 EXIF」对照；可仿五维 JSON schema |
| 风险点 | 主观漂移（RK-01 同类）；提示词敏感；需 Key；可能偏「看起来真实」而非「来源真实」 |

### 3.10 DetectZoo / AIGCDetectBenchmark / truebees Library

| 字段 | 内容 |
| --- | --- |
| 项目仓库链接 | DetectZoo https://github.com/sadjadeb/DetectZoo ；Benchmark https://github.com/Ekko-zn/AIGCDetectBenchmark ；truebees https://github.com/truebees-ai/Image-Deepfake-Detectors-Public-Library （Apache-2.0） |
| 部署成本 | 套件级，集成 2–5 人天；依赖各子检测器许可 |
| 适用场景 | 能：一次接入多算法做交叉；不能：开箱即 SaaS |
| 与原 Gemini 差异 | 工具层 |
| 风险点 | DetectZoo/Benchmark 根许可证 API 空；子模块许可分裂 |

---

## 4. 与原 Gemini 差异矩阵（定性，Q8）

| 维度 | Gemini 基线 | Top1 lynote/UnivFD | Top2 nonescape | Top3 CommunityForensics | Qwen-VL（观察） |
| --- | --- | --- | --- | --- | --- |
| 判定范式 | 多模态主观真实感 | CLIP 线性头概率 | 分类概率 | ViT 分类 | 多模态主观（可仿） |
| 输入 | 像素+预设 EXIF | 像素 | 像素 | 像素 | 像素±文本 |
| 输出 | passed/score/五维 | p(fake) | label/score | label/score | JSON 可设计 |
| 阈值 | ≥75 且 passed | 自定（建议校准） | 自定 | 自定 | 自定 |
| 可解释性 | 五维+文案 | 弱 | 弱 | 弱 | 强（文案） |
| 失败语义 | 禁止 0 分伪装 | 需适配器 | 需适配器 | 需适配器 | 需适配器 |

---

## 5. 评分表（先验分；权重固定）

评分 1–5。有效性为公开证据先验，**全量实测后用指标 A 覆写分数，不改权重**。

| 候选 | 有效性×0.3 | 成本×0.3 | 集成×0.1 | 延迟×0.1 | 可解释×0.1 | 活跃×0.05 | 合规×0.05 | 总分 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lynote/UnivFD | 4 | 5 | 5 | 3 | 2 | 5 | 5 | **4.20** |
| nonescape | 3 | 5 | 5 | 4 | 2 | 3 | 5 | **3.85** |
| CommunityForensics ViT | 4 | 5 | 4 | 3 | 2 | 4 | 4 | **4.00** |
| FatFormer | 4 | 4 | 2 | 2 | 3 | 2 | 5 | **3.45** |
| Sightengine | 3 | 4 | 5 | 4 | 2 | 4 | 3 | **3.50** |
| Qwen2.5-VL API | 3 | 3 | 4 | 3 | 5 | 5 | 3 | **3.35** |
| Hive | 3 | 2 | 4 | 4 | 2 | 4 | 2 | **2.70** |
| AEROBLADE | 3 | 2 | 2 | 1 | 3 | 2 | 1 | **2.20** |

Top3 = lynote/UnivFD、CommunityForensics ViT、nonescape。

---

## 6. Top3 深度分析与 POC 方案

### 6.1 lynote-ai/ai-image-detector

- **架构**：CLIP ViT-L/14 + 线性 fake/real 头（UnivFD）；另可选 hybrid/nonescape/ultra 后端。
- **部署**：`pip install` 后 `aidetect detect image.jpg`；或 FastAPI `/detect`。
- **POC**：适配器 `adapters/lynote_univfd.py`；阈值默认 0.5，可配置；缓存 sha256。
- **成本测算**：本地 ¥0；792 图次仅电费/时间。
- **本环境**：无 GPU，CPU 推理可行但慢——全量需批量队列。

### 6.2 e3ntity/nonescape

- **架构**：官方分类权重；mini ONNX 适合 CPU。
- **部署**：下载 `nonescape-mini-v0.onnx`；Python/JS API。
- **POC**：`adapters/nonescape_onnx.py`。
- **成本**：¥0。

### 6.3 CommunityForensics ViT

- **架构**：ViT-Small@384，大规模生成器监督。
- **部署**：`transformers`/`timm` 加载 HF 权重。
- **POC**：`adapters/community_forensics.py`。
- **成本**：¥0 本地；注意与国内生成器分布差。

### 混合策略建议（阶段 D 预告）

**开源像素检测器（Top1–3 交叉）+ 可选低价 VL 做抽检解释**，比单一替换 Gemini 更符合 R1/R2 风险控制；生产替换决策必须等 O3/O4 实测。

---

## 7. 风险与规避

| 风险 | 规避 |
| --- | --- |
| R1 频域扰动骗过检测器 | 原图门禁 + 三检测器交叉 |
| R2 检测器过强整轮不达标 | 分轮次趋势；定位处理层 |
| 许可/NC | NC 模型不进主路径 |
| 数据出境 | 优先本地 Top3；商用仅交叉 |
| 无测试图 | 见 `00-BLOCKERS.md`；禁止伪造结果 |

---

## 8. 下一步 POC 计划

1. 解阻：入库 792 图 + 输入材料（B-01/B-02）。
2. `python -m eval.build_manifest` 生成 `data/manifest.csv`。
3. `python -m eval.run_eval --detectors lynote_univfd,nonescape_onnx,community_forensics` 各 792 图次。
4. `python -m eval.metrics` 出 A/B/C 与置信区间；过门禁者进主口径。
5. 若 Top3 均未过门禁：启动 Qwen-VL 小样本校准提示词（仍不复跑 Gemini），或扩样。
