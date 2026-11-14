# DET-SCORE-NONLEGACY · 联网研究（R1）

日期：2026-11-14  
角色：研究子代理 R1（只检索、只写本文件；未改 `five_layer.py`，未改生产默认）  
工单：`docs/mihuanyuantu-v2/input/DET-SCORE-NONLEGACY-LIFT-work-order-2026-11-14.md`  
检索方式：本会话自行 WebSearch / WebFetch（arXiv HTML、IEEE/DOI 摘要、GitHub、CVF open access、项目文档）。侧聊种子表只作对照，不作为唯一来源。

评分对象（代码事实，本会话读到 `gemini_detector.py`）：Gemini 返回 `noise`、`depthOfField`、`lighting`、`colorRealism`、`overallRealism`、`total_score`、`passed`、`reason`。五维与 `total_score` 各自为 0–100 整数，`total_score` 不是五维平均。工单锁定 `PASS_SCORE=75`。代码注释写明管理员可覆盖及格线；本单不讨论改线。

---

## 1. 种子假设：核实了什么

| 种子说法 | 本会话结论 |
| --- | --- |
| `PASS_SCORE=75` 固定 | 工单与约束账本锁定。检测提示默认走 `PASS_SCORE`。本会话未改。 |
| 止血：CA 关、Layer0 默认关 | 账本 `Q-HEMO`：`ALIGN_LAYER0_IMG2IMG` 默认 0、`_CA_INTENSITY=0`。未重读运行中的环境变量。 |
| 协议 C：相对 v2 gain **+1.17**，`SHORTFALL` | 账本冻结：`mean_v2=65.75`，`mean_v3=66.92`，`hemo_baseline=66.92`，过 75 为 2/12。数字来自账本，本会话未重跑端测。 |
| 优先弱 ISP / Bayer / Poisson–Gaussian；拒绝 ISPCloak 式武器化 | **独立核实成立。** ISPCloak 摘要自称为 *weaponizing* ISP 的对抗框架，并叠加「生成伪影抑制 + 自适应 mask」。见 §4 禁项。 |
| Bayer 方差可区分真照片与生成图 | **独立核实。** Zhang 等 ICIPW 2025（one-class VAE，只训真图）；Wong & Ng 的局部方差（绿通道插值点方差更低）；Zhong 等 DCCT（2026-01）把 CFA 颜色相关写成可证的分布差。这三篇是**检测器**，不是可直接插进产线的滤镜。 |
| JPEG 再压缩会降低「AI 检测置信」 | **对取证分类器成立，对 Gemini 五维未证实。** Grommelt 等：生成图被 JPEG 后，检测器召回下降、精度仍接近 1，即更常被判成自然图。Cannas 等：JPEG AI 神经压缩会留下**类似合成图**的频谱峰。因此 JPEG 不是安全提分器。 |
| 弱正向链「马赛克 → 噪声 → 去马赛克」可作良性仿真 | **机理与开源实现核实成立；Gemini 提分未证实。** Brooks 的 forward 顺序、colour-demosaicing 的 `mosaicing_CFA_Bayer`、DeepLens 文档中的 Bayer+shot/read，都支持这条链。没有任何公开结果说这条链能抬高本仓五维分。 |

未核实、不得写成结论：任何候选已经在本仓 Gemini 上超过止血基线 66.92，或相对 v2 达到 +10。

---

## 2. 明确排除：旧 ALIGN / `aiImageProcessor` 杠杆

下列不是本单新候选。协议 C 已经测过止血后的旧对齐，gain +1.17，标记 `ALIGN_W5_E2E_SHORTFALL`。再复跑它们不算 NONLEGACY。

| 排除项 | 为何排除 | 初判 |
| --- | --- | --- |
| 旧仓先做 1D 频域相位（`imagePhysicalizer` / `frequencyProcessor`） | 旧生产序；工单写明禁先频域。相位扰动不可解释成传感器物理 | 禁 |
| 几何指纹（色相/饱和/亮度/gamma + 旋转裁切拉回） | `fingerprintDestroyer` 是反取证，不是相机 ISP | 禁 |
| 平台上传缩放与 60%–80% 体积带 | `uploadSimulator` / `sizeOptimizer`；工单禁止 | 禁 |
| 旧 CA：`focalLength<=50` 时饱和度 ×1.02，通道合成被丢掉 | 烂桩。现行通道错位 CA 已由止血关掉 | 禁 |
| 现行色差强度、暗角表、光学 Layer0 残差、噪声地板/夹紧、偶数行 1D、中间 JPEG 85 | 已在 v3 / ALIGN 里。R4 降档相对协议 W 仅约 +0.83，`P-V3-OVERDRIVE NOT_CONFIRMED`，禁止升默认 | 禁 |
| Layer0 img2img 当默认提分 | 英短最好 gain≈3.83，中文 C1 gain=1.00，都不到 +10。只保留账本里的测量臂，不作为本研究新杠杆 | 禁 |
| 只写 EXIF、改检测提示、放宽 `PASS_SCORE` | 工单硬拒绝。Gemini 五维看像素，不看元数据主效应 | 禁 |

旧噪声公式 `σ=0.5*sqrt(ISO/100)`（伽马域、暗部 ×1.5、无光子均值–方差关系）也排除。下面的 Poisson–Gaussian 是**线性域、方差随信号走**的另一套模型，不是把旧 σ 再加大。

---

## 3. 五条检索主题（独立阅读后的要点）

### 3.1 Bayer / CFA 与生成图检测（2024–2026）

真相机多数是单传感器 + Bayer：每个点只测一个颜色，另外两个颜色由去马赛克插出来。插值点是邻域的加权平均，局部方差低于实测点。生成模型直接写 RGB，没有这条采样约束。

- Zhang, Tohidypour, Wang, Nasiopoulos，ICIPW 2025。只用真图训练 one-class VAE，抓去马赛克造成的像素方差差，并对 Bayer 排列做不变。DOI `10.1109/icipw68931.2025.11386324`。IEEE 正文未开放，本会话核实到摘要、作者与 dblp 页码 505–510。
- Zhong, Xu, Zou，arXiv:2601.22778（2026-01）。DCCT：按 Bayer 掩膜把 RGB 拆成「单通道观测 + 两通道重建目标」，在高通残差上自监督训练。论文声称摄影图与生成图在 CFA 混叠子带上的 1-Wasserstein 距离有非零下界，并在 20 个以上未见生成器上泛化。这是检测训练，算力是 U-Net，不能当产线滤镜。
- Wong, Ng，arXiv:2310.16684（2023-10，窗口前的机理论文）。绿通道局部方差 + FFT；对缩放和 JPEG 仍有效。含义：轻度 JPEG **不能代替** CFA 仿真，也擦不掉已有的 Bayer 方差纹。
- 韩国学会 2024，DOI `10.17548/ksaf.2024.09.30.333`。摘要称用再插值区分拍摄图与生成图。无公开代码，正文未读到。只作旁证。

对试点的含义：若要让像素带上「插值点更平滑」的结构，噪声必须加在**马赛克之后、去马赛克之前**。先去马赛克再给 RGB 加独立噪声，不会产生这篇文献里的方差交替。

### 3.2 相机 ISP 与 Poisson–Gaussian

传感器噪声在 RAW 上近似可解释：光子到达是 Poisson（shot），读出是与信号无关的 Gaussian（read）。常用一个异方差高斯近似（Foi 等 2008；Brooks 等 CVPR 2019）：

`y ~ Normal(x, σ_read² + σ_shot² · x)`

2024–2026 仍在用同一物理，只是标定更细：

- DualDn，Li 等，arXiv:2409.18783（2024-11）。`R ~ K·Poisson(R*/K) + Normal(0, σ_r²)`。可微 ISP 只在训练去噪器时使用，推理丢掉。项目网站：https://openimaginglab.github.io/DualDn/ 。许可证 CC BY-NC-SA。去噪网络本身会**抹掉**颗粒，方向与「补传感器噪声」相反。
- Wang 等，arXiv:2504.12204（2025-04），代码 https://github.com/SMBU-MM/LLIE 。逆 ISP 回 RAW，再在 RAW 加低光 Poisson–Gaussian，然后白平衡、色彩转换、tone、gamma。目标是低光增强训练数据，不是商品图提分。低光退化会伤 `lighting` / `colorRealism`。
- Bhatt, Kaiser，arXiv:2512.15905（SNIC，2025-12）。用暗场标定异方差噪声，合成 RAW 相对厂商噪声曲线把 PSNR 缺口缩小 54–64%。强调 Bayer 上两个绿通道可以不同，转成 RGB 后做不到。适合以后选 λ，不适合第一刀试点。
- Tedla, Punnappurath, Zhao, Brown，arXiv:2504.07145（2025-07）。联合去马赛克+去噪，覆盖 Quad/Nona-Bayer。需要训练权重。手机主摄的 Quad-Bayer 与经典 RGGB 不是同一掩膜；第一刀不要上神经网络去马赛克。
- DeepLens `RGBSensor` 文档：https://deeplens.readthedocs.io/en/latest/api/sensor/ 。Bayer、shot+read、可逆 ISP。同一页有两套顺序：`Sequential(blc, demosaic, awb, ccm, gamma)`，后文又写 black → WB → demosaic → CCM → gamma。未实测代码，试点不要整包搬入。
- DiffPhysCam，Chen, Batagoda, Negrut，arXiv:2508.08831（2025-08）。Poisson 近似高斯 + 读出/FPN，另加暗电流、热像素和光学层。光学像差会把已关掉的色差问题带回来。

Brooks forward（CVPR 2019，仍是被 2024–2025 引用的可复现骨架）：线性 RAW → 白平衡 → 双线性去马赛克 → CCM → gamma。逆过程在加噪声**之前**做马赛克。代码：https://github.com/timothybrooks/unprocessing/blob/master/unprocess.py （TensorFlow 1 时代，当公式参考，不当依赖）。

### 3.3 反取证与相机指纹（只进否决清单）

这些工作的目标是骗过检测器或来源鉴定，不是解释性的相机仿真。

- ISPCloak，Zhao 等，arXiv:2607.21897。逆 ISP 网络投到 RAW，注入 Poisson–Gaussian，再正向 ISP，并做生成伪影抑制和自适应 mask。摘要写明 adversarial、weaponize、universally evasive。PDF 的 ACM 页眉仍是 2018 模板占位，按预印本对待。**整套禁止。** 其中「固定增益的马赛克+泊松高斯+去马赛克」与武器化套件必须拆开：只允许前者的非自适应、无检测损失版本。
- StealthDiffusion，arXiv:2408.05669。潜空间对抗优化 + Control-VAE，把频谱拉向真图以逃避取证分类器。
- PRNU 转移攻击，LNCS / ISBA 2025，DOI `10.1007/978-3-032-08124-7_17`。把一部相机的 PRNU 注入另一来源或 AI 图，摘要称平均破坏率 85.5%（含 Amped Authenticate）。全文未读，数字来自 Springer 摘要。
- 乘法指纹消除，arXiv:2508.03067（2025-08）。用只在真图上训练的对抗矩阵抹掉生成痕迹，摘要称对 6 个归因模型平均 ASR 97.08%。
- Smudged Fingerprints，arXiv:2512.11771（v2，2026-01）。系统评估指纹移除与伪造；白盒移除常高于 80%。论文是安全评估，其中的攻击策略禁止落地。
- DIPPAS，arXiv:2012.03581。Deep Image Prior 做 PRNU 匿名化。年份较早，仍属于反取证。
- CAP，NeurIPS 2024。可微 ISP 代理服务于行人检测对抗补丁，不是照片真实感。

### 3.4 JPEG、频谱与检测置信

- Grommelt, Weiss, Pfreundt, Keuper，arXiv:2403.17608。GenImage 上的检测器把 JPEG 当捷径：压缩越强，生成图越容易被判成自然图（精度接近 1、召回下降）。自然图从 PNG 约 80.4% 到 JPEG Q=95 约 94.8%，再到 Q=60 约 100%。即便 Q=95 也有明显分类偏移。这是 ResNet/Swin，不是 Gemini。
- Synthbuster，Bammey，IEEE OJSP 2023，DOI `10.1109/ojsp.2023.3337714`，代码 https://github.com/qbammey/synthbuster 。扩散图在周期 2/4/8 的 FFT 峰与 JPEG 峰重叠；方法按质量因子分模型。轻度 JPEG 与「去掉合成频谱」不是一回事。
- Corvi 等，CVPRW 2023，arXiv:2304.06408。潜扩散上采样 4 或 8 会在 1/4、1/8 频率留下峰。背景文献，说明频域痕迹来自生成器，不是来自 Bayer。
- Cannas 等，ICCVW 2025，arXiv:2412.03261。JPEG AI 在残差频谱上出现类似合成图的峰；重压缩提高取证误报。用神经压缩冒充相机 JPEG，方向反了。
- SIDBench 博客（https://mever.gr/post/sidbench-assessing-synthetic-image-detection-methods/）：高斯模糊与 JPEG 再压缩通常降低合成图检测准确率，JPEG 更多伤 TPR。博客综述，未重读论文表。
- DCT vs FFT，DOI `10.1109/cicn67655.2025.11368196`。只读到摘要：DCT 特征在 Q=10 仍有 72.67% 准确率，高于 FFT。说明「压 JPEG 就能抹掉频域检测」对较新检测器不成立。

本仓 C1 理由里已经出现过 compression artifacts。再压 JPEG 有机会伤 `noise` 和 `overallRealism`。

### 3.5 良性弱正向 ISP（与攻击的分界）

允许的形态：固定公式、固定小增益、增益为 0 时输出等于输入、异常时恒等回退。不读取检测器梯度，不用自适应 mask，不抑制「生成伪影」这一目标函数。

可复现骨架（CPU，NumPy/SciPy）：

1. 近似线性化（反 gamma；不做大幅白平衡或 CCM，避免色偏）。
2. `mosaicing_CFA_Bayer`（RGGB 即可；第一刀不扫四种排列）。
3. 在单通道马赛克上加异方差高斯，λ 很小，暗部略高、边缘不额外放大。
4. `demosaicing_CFA_Bayer_bilinear` 或 Malvar 2004。Menon 2007 更慢，第一刀不需要。
5. gamma 回到 sRGB。与原图的混合系数若使用，必须是预先写死的少数档，不能对着 Gemini 搜索。

开源：https://github.com/colour-science/colour-demosaicing （BSD-3-Clause；检索到的最新 release 为 v0.2.7，2025-12-06；`mosaicing_CFA_Bayer`、bilinear、Malvar2004、Menon2007）。文档：https://colour-demosaicing.readthedocs.io/en/latest/colour_demosaicing.bayer.html 。

`rawpy` 适合读真 RAW，不适合把已经是 sRGB 的生成图再包一层 LibRaw。LibRaw 默认 AHD，且 GPL 去马赛克包不在 MIT 的 wheel 里。第一刀不用 rawpy。

---

## 4. 候选表

关系列全部是**机理假说**。没有任何一条有本仓 Gemini 测量。

| 名称 | 机理 | 开源/可复现性 | 算力 | 视觉可感知风险 | 与 Gemini 五维可能关系 | 红线(是/否) | 初判(试/缓/禁) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| WEAK-BAYER-RT | 线性化后 Bayer 马赛克，再双线性或 Malvar 去马赛克；噪声增益固定为 0，只留下插值相关 | colour-demosaicing，BSD-3，纯 NumPy | CPU，单张毫秒到数百毫秒量级；未在本仓计时 | 边缘拉链、假色；全量替换会糊 | 主要碰 `colorRealism`（通道相关）和 `overallRealism`。几乎不动 `depthOfField` / `lighting`。过强会掉 `overallRealism` | 否 | 试 |
| LINEAR-PG | 近似线性亮度上 `Normal(x, σ_r²+σ_s²x)`，平坦区略强，不加马赛克 | 公式公开（Foi 2008；Brooks 2019；DualDn 式(1)）。不必用 SNIC 数据 | CPU，可忽略 | 过大像脏噪点或涂抹；伽马域加噪声会不像光子噪声 | 主要碰 `noise`。不制造景深。过强掉 `overallRealism` | 否 | 试 |
| WEAK-FWD-ISP | 上两项按摄影顺序串起来：线性化 → 马赛克 → 弱 PG → 去马赛克 → gamma。无 CCM 漂移、无色差、无自适应 mask、无检测损失 | 同上，可单测「增益 0 = 恒等」 | CPU，与 Malvar 同量级 | 拉链 + 颗粒叠加；应用很小的固定混合上限 | `noise` 与 `colorRealism` 同时动一点；`lighting` 仅在 gamma 近似误差时被动。`depthOfField` 不应指望提升 | 否 | 试 |
| MILD-JPEG-Q | 在现有编码上用相机常见的高 Q（建议只预注册 92 与 95 两档，4:2:0），不按分数搜 Q | Pillow/现有 encode 即可 | CPU，可忽略 | 块效应、色度渗色；C1 已出现压缩理由 | 取证文献说分类器更像「自然图」；Gemini 可能把块效应打进 `noise`/`overallRealism` 扣分 | 否（若改成对检测器搜 Q 则升级为是） | 缓 |
| DEEPLENS-FULL | Torch 可微 sensor+ISP 整包，含黑电平、WB、CCM、gamma、tone | https://github.com/vccimaging/End2endImaging ；文档顺序自相矛盾 | GPU/Torch 新依赖 | 白平衡和 CCM 容易偏色；文档未锁定顺序 | 可能同时动 `colorRealism` 与 `lighting`，方向不可控 | 否 | 缓 |
| DIFFPHYSCAM | 光学 PSF/像差 + shot/read/暗电流/FPN | arXiv:2508.08831 | 研究代码，重于弱 ISP | 像差≈色差，与止血冲突 | `depthOfField` 可能动，但是已证明有害的光学伪影邻域 | 否 | 缓 |
| SNIC-CAL | 暗场标定的异方差 λ，按机型 | arXiv:2512.15905，作者称开源标定 | 标定本身重；套用公式轻 | 照搬手机高 ISO 会过噪 | 只影响 `noise` 的参数真实性 | 否 | 缓 |
| DUALDN-NET | RAW+sRGB 双域去噪网络 | arXiv:2409.18783，CC BY-NC-SA，需权重 | GPU | 把颗粒抹平 | `noise` 可能更「干净」从而更不像传感器 | 否 | 缓 |
| LLIE-UNPROCESS | 逆 ISP + 低光 RAW 退化 + 正向 ISP | https://github.com/SMBU-MM/LLIE | 训练重；只借用逆变换则中等 | 欠曝、偏色、噪声被放大 | `lighting`、`colorRealism` 风险高 | 否 | 缓 |
| NEURAL-DEMOSAIC | 联合去马赛克与去噪，含 Quad/Nona | arXiv:2504.07145 | 需新权重，管理员另批 | 过平滑 | 可能同时改 `noise` 与 `colorRealism`，不可解释 | 否 | 缓 |
| DCCT-DIAG | 用 CFA 条件分布当离线诊断，不写回图像 | arXiv:2601.22778，需训练 U-Net | GPU 训练 | 不改图则为零 | 不能抬分；只能事后看颜色相关有没有变 | 否（若把 DCCT 或 Zhang VAE 当损失则升级为是） | 缓 |
| BAYER-VAE-ZHANG | one-class VAE 检测去马赛克方差 | DOI `10.1109/icipw68931.2025.11386324`；正文未开放 | 未知，论文无代码链接 | 不改图 | 同上，只解释「方差纹为什么重要」 | 否 | 缓 |
| JPEG-AI | 神经图像压缩，制造类合成频谱峰 | arXiv:2412.03261，ICCVW 2025 | 编解码器重 | 牙齿/边缘一类神经伪影；低频糊 | 频谱更像生成图，`overallRealism` 风险高；同时是反取证效应 | 是 | 禁 |
| ISPCLOAK | 可逆 ISP 网络 + PG + 正向 ISP + 伪影抑制 + 自适应 mask，目标是逃避检测 | arXiv:2607.21897 | 网络 + 攻击目标 | 论文声称不可察觉；本仓无法接受其目标函数 | 即使五维上升，也是对抗逃逸，不是相机仿真交付 | 是 | 禁 |
| STEALTHDIFF | 潜空间对抗 + 频谱匹配真图 | arXiv:2408.05669 | 扩散模型级 | 论文称人眼难辨 | 针对取证分类器，不是五维物理 | 是 | 禁 |
| PRNU-XFER | 把真实相机 PRNU 印到生成图上以通过来源鉴定 | DOI `10.1007/978-3-032-08124-7_17` | 需指纹估计 | 弱噪声状，但是设备指纹伪造 | 与 `noise` 表面相似，目的是欺骗鉴定 | 是 | 禁 |
| FP-ELIM | 乘法对抗矩阵消除生成指纹 | arXiv:2508.03067 | 需训练攻击模型 | 论文强调感知损失约束 | 归因逃避 | 是 | 禁 |
| FP-FORGE | Smudged Fingerprints 中的移除/伪造攻击 | arXiv:2512.11771 | 白盒或黑盒攻击 | 视攻击而定 | 安全评估对象，不是产品滤镜 | 是 | 禁 |
| DIPPAS | DIP 优化去掉 PRNU | arXiv:2012.03581 | 每张图迭代优化 | 质量–匿名折中 | 反取证 | 是 | 禁 |
| CAP-PATCH | 对抗补丁 + ISP 代理，骗行人检测 | NeurIPS 2024 | 补丁优化 | 可见补丁 | 与商品图五维无关 | 是 | 禁 |
| SCORE-SEARCH | 把 ISP/JPEG/噪声参数对 Gemini 或任何检测器做梯度或无约束搜索 | — | 每次端测都要打分 | 过拟合 12 张图 | 把 `total_score` 当攻击目标 | 是 | 禁 |

预注册的少数固定档（例如 PG 的 2–3 个 λ，或 JPEG 的两档 Q）属于测量，不是 `SCORE-SEARCH`。条件是档位先写进实验计划，不按单张 `reason` 改公式。

---

## 5. 初判为「试」的前三项

1. **WEAK-FWD-ISP**（优先测量臂，默认关）  
   唯一同时碰到文献里的两件事：CFA 插值相关，以及噪声发生在去马赛克之前。实现边界：colour-demosaicing 或等价 NumPy；Malvar 与 bilinear 二选一先做 bilinear（更快、更易恒等测试）；λ 与混合系数写死且很小；强度 0 必须字节级或容差内等于输入；失败恒等。不要接 Torch、不要接 CCM 随机、不要接色差。

2. **LINEAR-PG**（与上一项拆开做消融）  
   若五维里偏低的是 `noise` 而不是颜色，单独的线性域异方差噪声更干净。它不声称制造 Bayer 纹。禁止把噪声加在 gamma 编码后的 8-bit 上还叫做光子噪声。

3. **WEAK-BAYER-RT**（噪声为零的对照）  
   用来回答「只靠插值相关，够不够」。若拉链已让 `colorRealism` 下降，则第 1 项也应降增益或放弃马赛克，而不是加 mask 去盖。

这三项都**不能**事先写成能超过 75 或相对 v2 +10。止血基线是 66.92。成功标准留给可行性门禁和开发机端测。

---

## 6. 全部「禁」

新文献侧：

- JPEG-AI
- ISPCLOAK（含「伪影抑制 + 自适应 mask」这一目标，即使换名）
- STEALTHDIFF
- PRNU-XFER
- FP-ELIM
- FP-FORGE
- DIPPAS
- CAP-PATCH
- SCORE-SEARCH（对 Gemini 或取证器优化参数）

旧 ALIGN / 旧仓侧（§2，同样禁止当本单方案）：

- 先频域 1D 相位
- 几何指纹破坏
- 平台缩放与 60%–80% 体积
- 旧 CA 饱和度 ×1.02 与现行色差（止血保持关闭）
- 把 Layer0、R4、暗角表、旧 σ、中间 JPEG 85、EXIF 堆叠重新当成加码
- 改检测提示或放宽 `PASS_SCORE`

---

## 7. 引用

检测 / CFA

- Zhang, Tohidypour, Wang, Nasiopoulos. *Real Images Hold the Key to Detecting AI-Generated Images Using Bayer Pattern Analysis.* ICIPW 2025, pp. 505–510. https://doi.org/10.1109/icipw68931.2025.11386324  
  作者页：https://dml.ece.ubc.ca/publication_conference/2025-09-real-images-hold-the-key-to-detecting-ai-generated-images-using-bayer-pattern-analysis/
- Zhong, Xu, Zou. *Color Matters: Demosaicing-Guided Color Correlation Training…* arXiv:2601.22778, 2026-01. https://arxiv.org/html/2601.22778v2
- Wong, Ng. *Local Statistics for Generative Image Detection.* arXiv:2310.16684. https://arxiv.org/html/2310.16684
- *The AI-generated Images Authenticity Determination with Bayer Pattern Artifacts.* 2024. https://doi.org/10.17548/ksaf.2024.09.30.333 （仅摘要）

ISP / 噪声

- Brooks 等. *Unprocessing Images for Learned Raw Denoising.* CVPR 2019. https://openaccess.thecvf.com/content_CVPR_2019/papers/Brooks_Unprocessing_Images_for_Learned_Raw_Denoising_CVPR_2019_paper.pdf  
  https://github.com/timothybrooks/unprocessing/blob/master/unprocess.py
- Li 等. *DualDn.* arXiv:2409.18783. https://arxiv.org/pdf/2409.18783  
  https://openimaginglab.github.io/DualDn/
- Wang 等. *Towards Realistic Low-Light Image Enhancement via ISP-Driven Data Modeling.* arXiv:2504.12204. https://arxiv.org/html/2504.12204  
  https://github.com/SMBU-MM/LLIE
- Bhatt, Kaiser. *Closing the Real-to-Synthetic Gap with SNIC.* arXiv:2512.15905. https://arxiv.org/html/2512.15905
- Tedla 等. *Examining Joint Demosaicing and Denoising…* arXiv:2504.07145. https://arxiv.org/abs/2504.07145
- Chen, Batagoda, Negrut. *DiffPhysCam.* arXiv:2508.08831. https://arxiv.org/pdf/2508.08831
- DeepLens sensor：https://deeplens.readthedocs.io/en/latest/api/sensor/  
  架构页：https://www.ai4optics.com/end2endimaging/architecture/
- colour-demosaicing：https://github.com/colour-science/colour-demosaicing  
  API：https://colour-demosaicing.readthedocs.io/en/latest/colour_demosaicing.bayer.html
- Foi, Trimeche, Katkovnik, Egiazarian. *Practical Poissonian-Gaussian noise modeling and fitting for single-image raw-data.* IEEE TIP 2008.（DCCT 引用；本会话未重读全文）

反取证

- Zhao 等. *ISPCloak.* arXiv:2607.21897. https://arxiv.org/pdf/2607.21897.pdf
- *StealthDiffusion.* arXiv:2408.05669. https://arxiv.org/html/2408.05669
- *Spoofing Camera Source Attribution via PRNU Transfer Attacks…* 2025. https://doi.org/10.1007/978-3-032-08124-7_17
- *Untraceable DeepFakes via Traceable Fingerprint Elimination.* arXiv:2508.03067. https://arxiv.org/abs/2508.03067
- *Smudged Fingerprints.* arXiv:2512.11771. https://arxiv.org/pdf/2512.11771
- *DIPPAS.* arXiv:2012.03581. https://arxiv.org/abs/2012.03581
- CAP. NeurIPS 2024. https://proceedings.neurips.cc/paper_files/paper/2024/file/0f5cb62a8e3331b253c232e229cd551e-Paper-Conference.pdf

JPEG / 频谱

- Grommelt 等. *Fake or JPEG?* arXiv:2403.17608. https://arxiv.org/html/2403.17608v2
- Bammey. *Synthbuster.* DOI `10.1109/ojsp.2023.3337714`. https://github.com/qbammey/synthbuster
- Corvi 等. *Intriguing properties of synthetic images.* arXiv:2304.06408. https://arxiv.org/html/2304.06408
- Cannas 等. *Is JPEG AI going to change image forensics?* arXiv:2412.03261，ICCVW 2025. https://arxiv.org/html/2412.03261v1
- SIDBench 说明：https://mever.gr/post/sidbench-assessing-synthetic-image-detection-methods/
- DCT vs FFT 摘要：https://doi.org/10.1109/cicn67655.2025.11368196

未当作候选：CameraBench（arXiv:2504.10090）与 Generative Photography（CVPR 2025）是生成时的相机控制或 VLM 摄影问答，不处理已经生成的 sRGB。Carlson 等 2018 的合成数据相机效应包含色差，与止血冲突，不列入试。

---

## 8. 交给主会话的边界

- 本文件只达到「候选与红线」，不是 `NONLEGACY_FEASIBILITY_PASS`。落点、是否测量臂、与 L1–L5 的插入层序应由适配子代理对照 `five_layer.py` 再写。
- 建议试点顺序就是 §5 的 3 → 2 → 1 的消融，而不是三个一起默认打开。默认路径保持止血。
- 未改任何生产默认，未改 `PASS_SCORE`。
