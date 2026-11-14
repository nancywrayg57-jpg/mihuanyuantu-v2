# DET-SCORE-NONLEGACY-LIFT · 红线过滤（R2）

日期：2026-11-14  
角色：研究子代理 R2（对抗文献红线过滤）  
工单：`DET-SCORE-非旧版提分联网方案工单-2026-11-14.md` §1.3、§5  
账本：`docs/mihuanyuantu-v2/input/DET-SCORE-NONLEGACY-constraint-ledger.md`  
范围：只判定文献与产品动作是否可进入可行性门禁。不改应用代码，不改 `PASS_SCORE`，不改 `five_layer` 默认行为。

产品定位（过滤基准）：电商真照片增强；真 Gemini 五维打分；及格线保持 75。可用的是可解释、前馈、弱强度的相机物理仿真。不可用的是以攻击成功率、检测器逃逸、梯度伪装或骗分为目标的管线。

## 0. 计数与建议

| 裁决 | 数量 | 内容 |
| --- | --- | --- |
| **REJECT** | **19** | 攻击 / 反取证文献管线（整包拒绝，不得入库） |
| **REJECT-POLICY** | **3** | 产品动作：放宽及格线或改提示骗分；把 CA / Layer0 设回默认；对 Gemini 或替代检测器做梯度闭环 |
| **ALLOW_BENIGN_SUBSET** | **4** | 从攻击论文中剥掉攻击目标后，仍可送可行性门禁的物理片段 |

建议：只把固定 Bayer 往返和弱泊松–高斯前馈仿真送入可行性门禁；ISPCloak、FPBA、StealthDiffusion 及其同类的攻击目标、梯度掩膜和检测器损失全部拒绝，`PASS_SCORE` 维持 75，色差与 Layer0 保持默认关闭。

证据等级：下表「一次文献」指本轮 WebSearch 打开的论文摘要或正文；「账本」指工单/约束账本已锁定的产品规则。侧聊 §1.3 只作种子，不作为许可。

## 1. 硬 REJECT（武器化 / 对抗 / 梯度伪装 / 骗分）

优化目标列写的是论文自己声明要最大化或达成的东西。`optimization-free`、前馈、或「为了研究检测器鲁棒性」都不改变裁决：目标仍是误导检测器。

| # | 名称 | 优化目标（一次文献） | 拒绝原因 | 触线 |
| --- | --- | --- | --- | --- |
| 1 | **ISPCloak** | 把 ISP 武器化，制造能误导 deepfake / AIGC 检测器的对抗样本；指标是 ASR。摘要写明 *weaponizes the ISP pipeline*。管线：DnCNN 压制生成痕迹 → 可逆 ISP 投到 RAW → 注入泊松–高斯 → **自适应梯度掩膜** → 正向 ISP。作者称相对 StealthDiffusion，在 AIDE 上 ASR 约 86.59% | 整包是物理伪装攻击。无迭代 PGD 不等于无对抗。梯度掩膜是伪装控制，不是光子噪声模型 | Q-NO-ADV |
| 2 | **FPBA** | Frequency-based Post-train Bayesian Attack。在频域加扰动，把单个替代模型变成贝叶斯后验，提高对异质 AIGI / deepfake 检测器的黑盒迁移攻击成功率 | 频域梯度攻击 + 替代检测器。与「温和 JPEG」不是同一件事 | Q-NO-ADV |
| 3 | **StealthDiffusion** | 任务被作者命名为 AIGC-S（让生成图同时骗过检测器和人眼）。Latent Adversarial Optimization 在 Stable Diffusion 潜空间做对抗优化；Control-VAE 把频谱拉向真图，使法医分类器把伪造图判成真图 | 潜空间对抗 + 频谱对齐骗分。不是相机 ISP | Q-NO-ADV |
| 4 | **StatAttack / MStatAttack** | 用曝光、模糊、噪声等「自然退化」对抗地缩小真伪统计差，并用分布损失把特征推向自然图，以逃避 deepfake 检测器 | 退化本身无害，但被检测器损失闭环驱动。禁止把模糊/噪声/曝光搜成攻击 | Q-NO-ADV |
| 5 | **R²BA** | 用粒子群，依检测器的 fake 概率，融合优化高斯模糊、JPEG、高斯噪声和光斑，使 AIGC 检测器把假图当真图 | 后处理强度由检测器分数搜索。禁止用 Gemini 分数当这个搜索的奖励 | Q-NO-ADV |
| 6 | **TIGA** | 在 DDIM 采样轨迹里注入替代检测器梯度，并用黑盒有限差分估计目标检测器方向，生成可逃逸图 | 生成期对抗攻击 | Q-NO-ADV |
| 7 | **SpoC** | GAN 把目标相机痕迹注入合成图，并压低生成痕迹，使相机模型分类器和 GAN 检测器把图判成该相机所拍 | 指纹欺骗。只要样本图、不必白盒，仍然是攻击 | Q-NO-ADV |
| 8 | **Diffusion counter-forensics**（Tailanián 等，WACV 2024） | 用扩散纯化擦掉篡改在相机流水线上留下的痕迹，欺骗取证方法 | 反取证擦痕，不是增强 | Q-NO-ADV |
| 9 | **Diff-PGD** | 用扩散模型引导 PGD，使对抗样本更隐蔽、更可迁移，并更抗纯化 | 梯度攻击。ISPCloak 将其列为对照攻击 | Q-NO-ADV |
| 10 | **Adversarial RAW** | 构造对抗 RAW，经 ISP 与缩放后变成攻击图像；含梯度不可用时的代理 ISP | ISP 被放进攻击环，不是成像仿真 | Q-NO-ADV |
| 11 | **FakePolisher** | 用真实图像字典做浅层重建，去掉 GAN 伪影，从而降低 deepfake 检测准确率 | 以降低检测率为目标的痕迹清除 | Q-NO-ADV |
| 12 | **TraceEvader** | 向高频注入模仿痕迹、向低频加对抗模糊，逃避伪造模型归因 | 归因逃避 | Q-NO-ADV |
| 13 | **改进指纹拷贝**（Li 等） | 把估计的 PRNU 分块、随机、部分地叠到目标图上，同时骗过相机识别和三角检验 | 指纹移植攻击 | Q-NO-ADV |
| 14 | **PRNU 去除**（Zeng 等，ICIP 2015） | 估计并减掉 PRNU，使基于传感器的来源识别失效 | 指纹抹除。隐私叙述不改变对本产品的拒绝 | Q-NO-ADV |
| 15 | **GAN 相机模型反取证**（Chen 等，TIFS 2019） | 生成器在白盒或替代网络上对抗训练，伪造 CNN 相机模型痕迹且尽量不可见 | 对抗生成器伪造机型 | Q-NO-ADV |
| 16 | **FGSM / JSMA 相机模型反取证** | 用梯度符号或显著图扰动，改变 CNN 对相机型号的判断 | 经典梯度伪装 | Q-NO-ADV |
| 17 | **Neural noiseprint transfer** | 优化或注入网络，使伪造图的 noiseprint 接近真实图，从而破坏定位和来源识别 | 噪声指纹移植 | Q-NO-ADV |
| 18 | **扩散图清洗**（IEEE Access 2025） | 先用 GAN 去掉频域指纹，再用 I-FGSM 扰动，降低 UniFD、DIGBD、SSIP 等检测准确率 | 指纹移除 + 迭代梯度，两段都是攻击 | Q-NO-ADV |
| 19 | **JPEG 反取证**（Stamm 等） | 在 DCT 上加反取证抖动并去块效应，掩盖双重量化和拼接历史 | 隐蔽压缩历史。不是质量因子微调 | Q-NO-ADV |

### 1.1 产品动作（与文献并列，硬拒绝）

| # | 动作 | 原因 | 触线 |
| --- | --- | --- | --- |
| P1 | 放宽 `PASS_SCORE=75`，或改检测提示 / 评分合约，使同样本更容易 `passed` | 账本已锁。达标只能来自处理图在原合约下的分数变化 | Q-PASS |
| P2 | 把 `_CA_INTENSITY` 或 `ALIGN_LAYER0_IMG2IMG` 设回默认开 | 止血基线是 Layer0=0、CA=0。色差曾是 v3 伪影主因。Layer0 只允许测量臂（环境变量显式为 1），默认仍为 0 | Q-HEMO |
| P3 | 以 Gemini 五维分、其替代检测器、ASR、或梯度掩膜做闭环搜索 / 训练 | 事后在少数预设强度上报告 Δ，是端测。沿着检测器梯度或 fake 概率把强度搜过决策边界，是攻击 | Q-NO-ADV，并与 Q-PASS 冲突 |

ISPCloak 相关工作里还提到 ProjAttacker、CAP：把可微 ISP 放进对抗补丁优化。本轮未单独打开这两篇全文，只按 ISPCloak 的定性作 **REJECT（二次证据）**，不计入上面的 19。

### 1.2 ISPCloak 组件拆开后仍必须丢掉的部分

| 组件 | 裁决 |
| --- | --- |
| DnCNN（或任何网络）压制生成伪影 | REJECT。目的是擦数字痕迹 |
| 预训练可逆 ISP 权重，RGB→RAW 再正向重建 | REJECT（本单）。Xing 等 InvISP 本身是成像模型，但在 ISPCloak 里是攻击载具；新权重也要管理员另批 |
| 自适应梯度掩膜 \(M=f(\lVert\nabla I\rVert)\)，把扰动藏进纹理、平坦区压到近 0 | REJECT。这是梯度伪装，不是 Foi 模型 |
| 以 ASR / 检测器 logit 为损失或扫参奖励 | REJECT |

「优化无关、数十毫秒、前馈」只说明它不用迭代反传。摘要同时写明目标是 *mislead the judgment of deepfake detectors* 和 *universally evasive adversarial examples*。

第三方页面曾质疑该预印本的元数据与同行评审状态。裁决不依赖是否已发表：已核到的 arXiv 摘要本身把目标写成攻击。

## 2. ALLOW_BENIGN_SUBSET

只保留攻击目标被去掉之后仍然成立的物理片段。默认路径保持止血行为；下列各项若进入编码，只能是测量臂，强度 0 时输出等于输入，异常时恒等回退。不得把 Gemini 分数当作训练损失。

| # | 可保留片段 | 从哪剥出来 | 必须同时丢掉 | 为何还能留 |
| --- | --- | --- | --- | --- |
| A1 | **固定 Bayer 往返**：RGB 按 RGGB 抽成单通道马赛克，再用固定线性去马赛克（双线性或 Malvar–He–Cutler）回到 RGB | ISPCloak 的「正向 ISP / CFA」物理事实；经典去马赛克文献 | DnCNN、可逆 ISP 权重、梯度掩膜、任何检测器损失；不得顺带恢复色差或饱和抬升 | 真相机 CFA 会留下可解释的通道相关。实现是无学习、前馈、强度可关。ICIPW 2025 Bayer one-class、局部统计、DCCT 是**检测器**，只解释该现象，禁止拿来当损失 |
| A2 | **弱泊松–高斯**：按 Foi 模型 \(\sigma^2 \approx a\mu+b\) 在马赛克域做小增益、信号相关的噪声；平坦区用局部均值（光子散粒），不是用检测器梯度 | ISPCloak 注入的噪声方程；Foi 等的传感器噪声模型（原文目标是噪声估计与滤波，不是逃逸） | 梯度掩膜、把噪声幅度搜到 ASR 最大、大强度毁掉商品质感 | 真图平坦块有信号相关噪声，生成图往往过干净。必须弱，且与现有噪声层参数解耦，便于相对止血基线 A/B |
| A3 | **现有编码层的标准 JPEG 质量因子 / 量化表微调** | 工单 §1.3 的「二次 JPEG」；与 Stamm 反取证、R²BA 区分 | DCT 反取证抖动、去块效应伪装、由 fake 概率搜索的 Q、为降检测置信而加的模糊 | 只扫少量预设档，看五维分是否下降。下降则该臂否决，不改 75 |
| A4 | **极弱、固定核的光学模糊**（测量臂） | 仅当把它当成镜头 MTF，而不是 StatAttack / TraceEvader / R²BA 的攻击模糊 | 对抗模糊、按检测器分数调节的 σ | 工单允许极弱。五维语义或观感下降则否决 |

不计入 ALLOW、本单不入库、但可以当参考文献的：

- Xing 等 **InvISP**（CVPR 2021）：可逆 RAW↔RGB 成像模型，训练目标不是检测器。本单用经典抽采样代替它，避免把攻击载具和未批准权重带进来。
- **EXIF**：账本与工单写明 Gemini 对元数据依赖弱，现有路径可辅助保留，不单开为提分杠杆。
- **Layer0 img2img**：不是本类文献的良性子集。Q-HEMO 允许脚本里 `ALIGN_LAYER0_IMG2IMG=1` 的测量臂；默认必须仍为 0。

明确不是处理配方、禁止优化对准的检测文献：Zhang 等 ICIPW 2025（Bayer one-class VAE）、局部 Bayer 方差统计、DCCT（去马赛克色相关训练）。它们说明 CFA 统计从哪来，不能变成损失函数。

## 3. 映射到 Q-NO-ADV / Q-PASS / Q-HEMO

三条均为账本 **LOCKED**。

| 候选 | Q-NO-ADV | Q-PASS | Q-HEMO |
| --- | --- | --- | --- |
| ISPCloak 整包，含梯度掩膜与 DnCNN | 违反。目标是检测器逃逸与物理伪装 | 若用 ASR 或过线率当奖励，同时是骗分 | 正向 ISP 的色度相关容易重演已止血的色差伪影。不得借此把 CA 开回默认 |
| FPBA、StealthDiffusion、Diff-PGD、TIGA、StatAttack、R²BA、SpoC、指纹拷贝/去除、noiseprint、JPEG 反取证、FakePolisher、TraceEvader、扩散反取证、Adversarial RAW、相机模型 GAN/FGSM | 违反。优化目标是误导检测、归因或来源识别 | 把「更像真」定义成检测器 logit，就是在改判定而不改及格线数字，仍视为骗分 | 不改变止血默认；也不许用它们替换止血 |
| A1 Bayer 往返 | 符合，只要无检测器损失、无梯度掩膜、无可逆 ISP 攻击权重 | 符合，只要 75 不动；测量失败就丢弃该臂 | 符合，只要默认仍是 CA=0、Layer0=0，且往返不引入饱和/色差增益。强度 0 = 恒等 |
| A2 弱 Foi 噪声 | 符合，只要增益是预设小网格，不是梯度搜索 | 同上。网格结果事后报告 Δ，不过线不改门槛 | 符合，只要不把噪声做成可见色污，且不触 R4 光学/噪声降档升默认（另条 Q-NO-R4-DEFAULT） |
| A3 标准 JPEG 扫档 | 符合，只要不是 Stamm 抖动或 R²BA | 五维下降则否决该档，不降低 75 | 只动已有编码层参数时，不恢复 CA/Layer0 |
| A4 极弱固定模糊 | 符合的条件同上；一进入检测器闭环即违反 | 语义分下降则否决 | 不得当作把图磨糊来刷分的默认 |
| 放宽 75 / 改提示 | — | 违反 | — |
| CA 或 Layer0 恢复为默认 | Layer0 若用来追逐检测分，还会碰到 Q-NO-ADV | 不得用默认重开来制造过线 | 违反。测量臂例外只覆盖 Layer0 显式开关，不覆盖把 CA 或 Layer0 写回默认 |

Q-NO-LEGACY-LOOP、Q-E2E、Q-PR、Q12、Q-NO-S7、Q-GATE 本文件不改写：没有 `NONLEGACY_FEASIBILITY_PASS` 之前，不得改 `five_layer` 默认行为。本文件只提供红线输入，不宣告该门禁已过。

## 4. 引用 URL

核验日期：2026-11-14。

### 4.1 REJECT 一次文献

1. ISPCloak：https://arxiv.org/abs/2607.21897 （正文 https://arxiv.org/html/2607.21897）
2. FPBA：https://arxiv.org/abs/2407.20836 （代码页 https://github.com/nxZhai/FPBA/ ；论文内另写 https://github.com/onotoa/fpba）
3. StealthDiffusion：https://arxiv.org/abs/2408.05669 ；ACM MM：https://dl.acm.org/doi/10.1145/3664647.3681535
4. StatAttack：https://openaccess.thecvf.com/content/CVPR2023/html/Hou_Evading_DeepFake_Detectors_via_Adversarial_Statistical_Consistency_CVPR_2023_paper.html
5. R²BA：https://arxiv.org/html/2412.06727
6. TIGA：https://arxiv.org/html/2607.25894
7. SpoC：https://arxiv.org/abs/1911.12069
8. Diffusion counter-forensics：https://openaccess.thecvf.com/content/WACV2024/html/Tailanian_Diffusion_Models_Meet_Image_Counter-Forensics_WACV_2024_paper.html
9. Diff-PGD：https://arxiv.org/abs/2305.16494
10. Adversarial RAW：https://ar5iv.labs.arxiv.org/html/2206.01733
11. FakePolisher：https://arxiv.org/abs/2006.07533
12. TraceEvader：https://ojs.aaai.org/index.php/AAAI/article/view/29973
13. 改进指纹拷贝：https://arxiv.org/abs/1707.07795
14. PRNU 去除（ICIP 2015，检索到的会议页副本）：https://www.researchgate.net/publication/305181626_Removing_camera_fingerprint_to_disguise_photograph_source
15. GAN 相机模型攻击：https://doi.org/10.1109/tifs.2019.2945198
16. FGSM/JSMA 相机模型反取证：https://arxiv.org/abs/1805.02131
17. Neural noiseprint transfer：https://doi.org/10.7717/peerj-cs.1359
18. 扩散图指纹移除 + I-FGSM：https://doi.org/10.1109/access.2025.3597641
19. JPEG 反取证：https://doi.org/10.1109/icassp.2010.5495491 ；扩展 https://doi.org/10.1109/icip.2010.5652553

DUMB 基准把 FPBA 与 PGD、FGSM 并列为 deepfake 攻击（佐证，非新管线）：https://arxiv.org/abs/2601.05986

### 4.2 ALLOW 所依据的成像 / 检测文献（检测文献本身不是处理许可）

- Foi 泊松–高斯 RAW 噪声模型：https://doi.org/10.1109/tip.2008.2001399
- Malvar–He–Cutler 去马赛克：https://www.ipol.im/pub/art/2011/g_mhcd/article.pdf
- InvISP（只作参考，本单不入库）：https://yzxing87.github.io/InvISP/index.html
- Bayer one-class 检测（ICIPW 2025）：https://doi.org/10.1109/icipw68931.2025.11386324
- 局部 Bayer 统计检测：https://arxiv.org/html/2310.16684
- DCCT 检测：https://arxiv.org/html/2601.22778v2

### 4.3 产品规则

- 工单 §1.3、§5：桌面 `DET-SCORE-非旧版提分联网方案工单-2026-11-14.md`（仓库副本 `docs/mihuanyuantu-v2/input/DET-SCORE-NONLEGACY-LIFT-work-order-2026-11-14.md`）
- 约束账本：`docs/mihuanyuantu-v2/input/DET-SCORE-NONLEGACY-constraint-ledger.md`（Q-PASS、Q-HEMO、Q-NO-ADV 均为 LOCKED；止血基线 mean_v3 = 66.92）
