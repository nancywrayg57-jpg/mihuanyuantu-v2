# FIVE-LAYER-LEGACY-ALIGN · 旧仓算法提取报告（2026-11-14）

角色：旧版蜜獾原图技术处理模块只读研究员。  
本报告只做静态阅读，不改代码、不跑旧 Node 后端、不整包迁 Node、不放宽硬约束、不私自把注释和可执行语句调和成「作者本意」。

- 旧仓：`/home/hbs/hbs-projects/_refs/mihuanyuantu`
- HEAD：`4a3f2ade0532cab1cd69f01b0b00cdce5c78c5e7`（`4a3f2ad docs(governance): 完整重命名 Codex工程文件.md → Codex工程经验.md`）
- 快照：`输入材料/旧版可复用模块/01_源码参考/原样快照/server`
- 既有冲突账本（只读，本报告不删改其结论）：`docs/mihuanyuantu-v2/input/FIVE-LAYER-LEGACY-ALIGN-research-conflicts-2026-11-14.md`
- 对照用的现行实现（仅用于「是否已经移植 / 杠杆是否还空着」，不是旧仓事实）：`aojuai-main/backend/app/capabilities/realphotos/services/five_layer.py`（`PIPELINE_VERSION = "s2-five-layer-3"`）

证据分级：

| 标记 | 含义 |
| --- | --- |
| 代码事实 | 该修订上的可执行语句 |
| 注释 | 与代码可能不一致；不能单独当运行时行为 |
| 库契约推断 | 调用点没写死的 sharp 默认值；本报告未执行 sharp |
| 缺证 | 仓库里没有实测、没有样本输出、没有 Gemini 分数 |

---

## 1. 硬约束（逐条入报告，未放宽）

| ID | 约束 | 本报告处置 |
| --- | --- | --- |
| Q1 | 同样本 Gemini `total_score` 均分相对 `s2-five-layer-2` 提升 ≥10，不可下调 | 只判断旧仓能否**证明**这件事；不把旧检测阈值 70 或 75 拿来替换 |
| Q2 | 样本集 `测试用/图片` 不改 | 未触碰样本 |
| Q3 | 弱暗角允许 | 旧暗角表可摘录；不把 f/1.4 的 0.35 自动升格为「弱」 |
| Q4 | 色差允许 | 摘录旧色差的**实际输出**和**被丢弃的通道运算**；二者都保留 |
| Q5 | 弱锐化 + 中间 JPEG 重压允许 | 摘录 blur+sharpen 与各次 JPEG quality；不把多次重压自动当成提分手段 |
| Q6 | 须有旧式 1D 频域对照 + 双路径证据 | 摘录旧 1D 相位公式；不把「先频域」顺序写回 v2 |
| Q7 | 稀疏增强 + 极弱频谱；禁几何与可见调色 | 旧指纹的 hue/sat/gamma、旋转裁切、棋盘格、8/16/32 正弦标为不可照搬 |
| Q8 | Layer0 允许 | 只在现行 generation 合同内讨论提示词；不把换模型写成已授权 |
| Q9 | EXIF + FocalPlane；空值跳过 | 按字段摘录「缺了就不写」；空 `gps_mode` 的行为与「跳过」不一致，列入裁决 |
| Q10 | 真 Gemini；`PASS_SCORE=75` 不改 | 旧仓另有 70 与 75 两套说法，都不拿来改 75 |
| Q11 | MAD 仅观测、不否决；禁故意糊图提分 | 旧仓没有 MAD。强制 `blur` 不作为提分杠杆推荐 |
| Q12 | 端测通过才可 PR | 本报告不是端测，不能当 PR 依据 |
| 红线 | 不整包迁 Node；不跑旧 Node 后端 | 遵守。全部结论来自阅读 |
| 红线 | 字节下限；禁 60%–80% 与平台 resize | `sizeOptimizer` / `uploadSimulator` 只入禁止表 |
| 红线 | 层序必须 Layer0→L1→L2→L3→L4→L5 | 旧 `physicalizeImage` 入口先频域，禁止回迁该顺序 |

---

## 2. 矛盾 / 歧义 / 缺失前置（先列，不选边）

下列条目要么账本已有、本报告用行号加细，要么是本次新见。加细不撤销账本原句。

| ID | 类型 | 两边原文 | 未决点 |
| --- | --- | --- | --- |
| C-NOTES-Q4 / C-WO-Q8 / C-WO-Q11 / C-LAYER0-API / C-ORDER / C-SIZE-UPLOAD / C-FAIL-SILENT / C-PASS-SCORE / C-FEAS-Q1 | 账本已列 | 见冲突账本 §B | 本报告不改账本结论 |
| C-CA-BUG-GATE（加细 C-CA-BUG） | 代码分支 | 进入 `shift>=1` 时，composite 结果被 `.then` 丢掉，只对**原 buffer** `modulate({saturation:1.02})`（`imagePhysicalizer.ts` `applyChromaticAberration` 247–264）。同一函数在 `shift<1` 时直接 `return imageBuffer`（219），饱和度也不改 | 默认 `intensity=1` 时，只有焦距 ≤14mm 才进饱和度分支；24/35/50mm 调用了函数但输出是恒等。账本「最终仅 saturation 1.02」描述的是**进了分支之后**，不是所有广角调用 |
| C-CA-COMPOSITE-INCOMPLETE | 死代码质量 | composite 只挂了 `rScaled`，`gChannel`/`bScaled` 算完未用（225–256） | 即便不丢弃，合并式也不是完整 RGB 色差。与「色差允许」不自动等价于「把这段搬过去」 |
| C-VIGNETTE-COMMENT | 注释对注释 | 接口注释：「小光圈=大 f 值=更强暗角」（`imagePhysicalizer.ts` 32）。函数注释：「大光圈（小 f 值）暗角更强」（81–83）。表：f≤1.4 → 0.35，f>8 → 0.04（85–92） | 可执行表与函数注释一致，与接口注释相反。产品词「弱暗角」没有定义 0.35 算不算弱 |
| C-STRENGTH-DEAD（加细） | 死参数 | `finalStrength` 只进返回值（557、584）。`callAIImageEdit` 参数列表没有 strength（448–456、566–574）。DashScope body 无 strength、无 size（194–215）。分类默认 phone=0.12 只在 `DEFAULT_PROMPTS`（154），`processImageWithAI` 不用 `defaults.strength`。路由固定 `strength: aiStrength ?? 0.15`（791） | 生产路径上 phone 0.12 不会被选中，任何强度数字都不会进 API |
| C-STRENGTH-UI | 前后端范围 | 后端夹紧 `[0.05, 0.30]`（557）。前端文案「0.05–0.50」（`client/src/pages/ParameterConfig.tsx` 2484） | 0.30–0.50 会被夹掉；夹掉之后仍然不进 API |
| C-MODEL-DEFAULT | 默认模型两套字符串 | 真正调用：`QWEN_IMG2IMG_MODEL ?? "qwen-vl-plus"`（`getQwenModel` 43–45）。成功后的展示名：`QWEN_IMG2IMG_MODEL ?? 'qwen-image-2.0-pro'`，再 `includes('qwen')` 就写成「通义千问」（`routers.ts` 882–885） | 库里的 `model_version` 可以和落库的 `apiProvider` 不一致。没有一次成功调用记录证明 `qwen-vl-plus` 会在该 endpoint 返回图 |
| C-GEMINI-BODY-DEAD | 死请求体 | `callGeminiFormatOnce` 先造了带空 `inline_data.data` 的 `requestBody`（341–358），实际 `JSON.stringify` 的是 `requestBodyWithUrl`：只有把 URL 拼进文本（361–380） | 旧 Gemini「图生图」没有把像素附上去。不能把它当成已验证的 img2img |
| C-OPENAI-SIZE | 几何 | OpenAI 兼容体写死 `size: "1024x1024"`，图片只作为提示词里的 URL（280–288） | 与禁几何冲突。不是可移植尺寸策略 |
| C-PROMPT-GEO-COLOR | 提示词 vs Q7 | 四类正向都写「保留构图、不改变五官姿态版型」，但 action 另含「轻微桶形畸变」（158）；dslr/mirrorless/phone/action 都含饱和度衰减或过艳后衰减（137、144、151、158） | 账本 C-LAYER0-GEO / C-LAYER0-COLOR 仍有效。剥离哪些从句要裁决，不能由本报告删句后当成原提示词 |
| C-LAYER-NAMES | 注释层号 vs 调用序 | 频域文件自称第一层；指纹文件自称第五层；上传文件自称第四层。`processImage` 实际是 AI → physicalize（内部先频域）→ 指纹 → 上传 → 尺寸+EXIF | 禁止按注释层号重排。禁止把「先频域」搬回 v2 |
| C-UPLOAD-WHEN | 文件头 vs 路由 | `uploadSimulator.ts` 27–28 写「必须在 EXIF 写入之后」。同文件 261–264 写调用方应在此之后重写 EXIF。`routers.ts` 837 在 EXIF 之前调用 | 以路由为准描述**实际顺序**；文件头不覆盖路由 |
| C-JPEG-QUALITY-CLOBBER | 参数被后续编码盖掉 | `extractPhysicalizerOptions` 按 ISO 设 82/85/87/88/92（423–427），`applyJpegRecompression` 用该值（395–396）。紧接着 `applyNaturalSharpening` 的 `blur().sharpen().toBuffer()` **没有** `.jpeg({quality})`（304–311、399） | 离开 physicalize 的字节不一定是 ISO 表上的 quality。sharp `^0.34.5` 的 JPEG 文档默认 quality 是 80；本报告未运行 sharp，故「一定是 80」是库契约推断 |
| C-FFT-NOT-POW2 | 算法前提缺失 | `fft1d` 是按长度 `n` 做位反转的 Cooley–Tukey（42–92），没有补到 2 的幂。注释声称幅度扰动 &lt;0.5%（111），循环只改相位、不改幅度（128–136）。文件头写 DCT 系数微扰（9），全文没有 DCT | 常见宽度（非 2 的幂）上，这段不是正确 FFT。v2 的 `np.fft.rfft` 是另一种实现。Q6 要的「旧式 1D 对照」必须单独规定：对齐相位公式，还是对齐这份错误变换 |
| C-1D-UNUSED-EDGE | 死入口 | `applyEdgeFrequencyPerturbation`（276–328）全仓无调用方 | 不在生产链上。边带 15%、强度 0.006 不能写成现行参数 |
| C-PHYS-DEAD-FIELDS | 未使用字段 | `extractPhysicalizerOptions` 写入 `sensorType/cameraMake/cameraModel`（434–436），`physicalizeImage` 解构时不读它们 | 噪声与机身无关，只与 ISO 数字有关 |
| C-FP-COMMENT | 注释范围大于代码 | 色彩注释写 hue ±3°、饱和 −5%～+3%、亮度 ±2%、gamma 0.95–1.05（219–222）。代码是 hue `0..4`、饱和 `0.95..1.03`、亮度 `0.98..1.02`、gamma `1.0..1.08`（230–242），没有负向色相，gamma 只往大于 1 | 以代码区间为准描述输出；注释区间不能当参数 |
| C-PHASH-COMMENT | 注释与概率 | 注释「约 60% 的块被扰动」（102）。代码 `if (Math.random() > 0.6) continue`（103）即 random≤0.6 才扰动，期望 60% | 一致。列入是为了避免以后改成「跳过 60%」 |
| C-EXIF-DIM | 元数据与像素可能不一致 | 无预设宽高且机型不在表内时，`ExifImageWidth/Height` 默认 4032×3024（331–332、360–361） | 空模型会写入与真实像素无关的宽高。这是元数据，不是像素缩放 |
| C-GPS-EMPTY | 与 Q9「空值跳过」的字面差 | FocalPlane：两个分辨率都真值才写（379–382）。GPS：`gps_mode` 缺省当成 `'auto'`（449），坐标空则 `generateGpsCoords`（460–466）。`gps_mode==='none'` 才整段不写 | 「空值跳过」覆盖 FocalPlane/Make/ISO 等；**不覆盖**缺省 GPS。室内/影棚还有 50% 返回 null（203–204） |
| C-LEGACY-SCORE-70-75 | 旧检测自己打架 | 验证提示词：「score >= 75 且 passed = true」（`exifVerifier.ts` 134）。落库：「score >= 70 标记为 pass」（`routers.ts` 941–943） | 两套都不是 v2 的 `PASS_SCORE`。禁止把 70 移植过去。旧 `score` 也不是 v2 的 `total_score` |
| C-VERIFY-VS-Q1 | 指标不是同一个 | 旧验证把预设 EXIF **写进提示词**再看图（`buildPrompt` 93–107），字段名是 `score`。Q1 要的是 v2 Gemini `total_score` 相对 `s2-five-layer-2` | 旧仓没有任何「相对 s2-five-layer-2 +10」的测量。提示词再完整也不能代替这条缺证 |
| C-SILENT-PARTIAL | 失败继续 | AI catch 用原图（814–817）。AI 下载 `!ok` 时不抛错，仍用原图（809–813）。physicalize / 指纹 / 上传 / EXIF 失败都返回输入（408–409、395–397、352–354、520–523） | 账本 C-FAIL-SILENT 成立。v2 不能把这种「退原图仍 completed」搬过来 |
| C-NO-MAD | 旧仓无此门 | 全处理链没有 MAD、没有保真否决 | Q11 的「只观测」无法在旧码里找到对应实现。高 ISO σ 无上限，和「禁故意糊」之间没有旧阈值可抄 |

缺失前置（没有这些，就不能把旧行为说成已验证的提分方案）：

1. 没有任何一次 DashScope / OpenAI / Gemini 图生图的响应样例、输出宽高、或 Gemini `total_score`。
2. `qwen-vl-plus` 在 `multimodal-generation/generation` 上是否回图：缺证。
3. 模型是否改分辨率、是否改几何：请求体没锁尺寸，也没有输出测量。
4. 非 2 的幂宽度上 1D FFT 的数值误差：未跑。
5. `applyNaturalSharpening` / 色差 `toBuffer()` 的实际 JPEG quality：未跑 sharp。
6. 分类中文提示词在 v2 `gpt-image-2` `/images/edits` + 现有 blend 上的分数：账本已写明未测（C-FEAS-Q1）。

---

## 3. 快照 vs clone

对快照目录 18 个文件与 clone `server/` 同名文件做了字节比较：**18/18 相同**。快照没有多出来的文件。

| 文件 | sha256 | 结论 |
| --- | --- | --- |
| `imagePhysicalizer.ts` | `978a7f85d0f1a77803e31a701bb75f03a23ea1b52b3f767cabafd8c0438d5ff2` | 相同 |
| `frequencyProcessor.ts` | `2d8066912f235da23e9457679ed1cb090cb0c146e635b322030a2e3c594a7406` | 相同 |
| `fingerprintDestroyer.ts` | `9a2652182e1fff22cacecdcc05167f0403a6fb5453a231c3b96a4f1faca860d4` | 相同 |
| `exifToolWriter.ts` | `c2ddc01919ee32680e22ac3f66f142791426d30d2dfe7e7e3c7c22fe6fcb5f45` | 相同 |
| `uploadSimulator.ts` | `0b264d822ffa46e77abad2d4c74c3972c54e31b493bc94cd7c771555f860f039` | 相同 |
| `sizeOptimizer.ts` | `3eae4a15a2ba15d4de8d704e3856034012f2047d442c6753553ccf36be88e118` | 相同 |
| `aiImageProcessor.ts` | `37ca598b8bb3af49fd3dcd454b7118788ac24208dc105b6406dcfde58af5b9fb`（20988 B） | **只在 clone**。与任务书给定 hash 一致 |
| `aiImageProcessor.test.ts`、`routers.ts` | — | **只在 clone**。编排顺序的证据不在快照里 |

因此：像素/EXIF/上传/体积六文件可以用快照或 clone 互证；Layer0 提示词、strength 是否进 API、以及 `processImage` 时序，**只能引用 clone**。账本 C-LAYER0-SRC 成立。

---

## 4. A. 编排时序

唯一生产编排是 `server/routers.ts` 的 `processImage`（689 起）。`textToImage`（1345 起）在带参考图时也会调 `processImageWithAI`（1378），那是另一条入口：不跑 physicalize / 指纹 / 上传 / EXIF。下面的时序只描述 `processImage`。

```
输入 base64
  → [可选] processImageWithAI          进度 15  「第零层」
  → physicalizeImage                   进度 40
        步骤0 applyFrequencyPerturbation   先于噪声
        步骤1 injectCMOSNoise              仅 iso>=200
        步骤2 applyVignetting
        步骤3 applyChromaticAberration     仅 focalLength<=50，且传入 intensity*0.5
        步骤4 applyJpegRecompression
        步骤5 applyNaturalSharpening
  → destroyFingerprints                进度 55  文件自称第五层
        频谱正弦 → pHash 棋盘 → 色彩 → 旋转/裁切/拉回
  → simulatePlatformUpload             进度 68  文件自称第四层；默认平台 generic
  → optimizeImageSize(finalize=writeExifToJpeg)  进度 74
  → storagePut 标 completed
  → verifyExifWithGemini（失败不阻断；落库 pass 线是 70）
```

依据：`routers.ts` 753–856、930–943；`imagePhysicalizer.ts` 363–400；`fingerprintDestroyer.ts` 364–387。

和 v2 强制序的差异（禁止回迁的是顺序，不是每个公式）：

| 旧步骤 | 旧位置 | v2 强制位置 |
| --- | --- | --- |
| AI 图生图 | 最前，失败则跳过 | Layer0，且现行合同是 `gpt-image-2` edits + 像素 blend |
| 1D 频域 | physicalize **内部第一步** | L2，必须在 L1（噪声/暗角/色差）之后 |
| 噪声、暗角、色差、中间 JPEG、锐化 | 频域之后，仍在同一函数 | L1 与 L5；中间 JPEG 在编码段 |
| 指纹（含几何与调色） | EXIF 前 | Q7 禁止几何与可见调色，不能整段映射到 L3 |
| 平台缩放/色彩矩阵 | EXIF 前 | 红线禁止 |
| 60%–80% 体积带，且度量含 EXIF | 最后一次重编码 | 红线禁止；v2 是字节下限（输出不低于源） |
| EXIF | 与体积搜索绑在同一次 finalize | L4 |

`physicalizeImage` 顶部注释（321–327）把流水线写成「噪声→暗角→色差→JPEG→锐化」，**没写频域**；函数体 363–374 先跑频域。注释与函数体冲突时，本报告把函数体当实际顺序，不把注释改写成另一套顺序。

---

## 5. B. 逐层参数表

「层」按**实际调用**命名，并注明旧注释里的层号。禁止项同时出现在 §8，避免只看表就拿去实现。

### B0. Layer0 · `processImageWithAI`

| 项 | 值 | 来源 |
| --- | --- | --- |
| 何时跑 | `enableAI!==false` 且（自定义正向提示非空，或 category ∈ dslr/mirrorless/phone/action）。路由写死 `enableAI: true` | `shouldApplyAIProcessing` 596–605；`routers.ts` 760–764 |
| 未知 category 且无自定义提示 | 不跑。注意：若绕过该门、直接调用 `processImageWithAI` 且正向为空，`getDefaultPromptForCategory` 会落到 dslr（173） | 两套门，不要并成一条 |
| 默认 API | `dashscope` | 549 |
| 默认模型 | 环境变量，否则 `qwen-vl-plus` | 43–45 |
| URL | `https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation`；custom 时拼到 `baseUrl` 同一路径 | 25–26、190–192 |
| Key | `overrideApiKey` 否则 `QWEN_IMG2IMG_API_KEY` | 33–40、560 |
| 路由上的 key | `rds.getImg2ImgApiKey()` 的 `key_value/model_version/api_format/base_url`；没有则环境变量 | `routers.ts` 776–785 |
| 超时 | 120000 ms | 224、299、380 |
| 重试 | 额外 2 次，间隔 3000 ms；仅 Abort/Timeout、`fetch failed`、`ECONNRESET`、消息里 5xx。4xx 与 `result.code` 不重试 | 29–31、47–61、459–490 |
| DashScope body | `model`；`messages[0].content = [{image:url},{text:prompt}]`；`parameters.n=1`；`negative_prompt`；`prompt_extend:false`；`watermark:false`。无 strength、无 size、无 seed | 194–215 |
| 负向缺省（请求层） | 空则 `"低分辨率，低画质，AI生成痕迹，过度平滑，蜡像感，卡通感。"` | 209–211 |
| 负向缺省（函数层） | `negativePrompt ?? defaults.negative`。空字符串**不**回退到分类长负向；随后请求层再用上面的短句 | 556 |
| strength 夹紧 | `clamp(strength, 0.05, 0.30)`，默认入参 0.15。只写入 `usedStrength` | 545、557、584 |
| 分类表 strength | dslr/mirrorless/action 0.15，phone 0.12 | 140、147、154、161 |
| 输出容器 | 下载后 `storagePut(..., "image/png")`，key `ai-processed/...png`。Gemini 分支直接存 png | 416–418、522–524 |
| 尺寸 | DashScope 不传。OpenAI 分支固定 1024×1024。没有拉回原尺寸 | 287 |
| 失败 | 路由 catch 后继续用原图，主流程仍可 `completed` | `routers.ts` 814–817 |
| 几何/调色 | 代码不旋转不裁切。提示词要求保留构图，同时要求景深、暗角、色差、饱和度变化；action 要求桶形畸变。模型是否照做：缺证 | 137–161 |

分类正向（全文，即实际送进 API 的控制面）：

- dslr（136–137）：保留构图与人物；f/2.8 景深；暗部亮度噪点；高光紫边与轴向色差；四角暗角；阴影与高光溢出；**色彩饱和度轻微衰减**；RAW 未调色；纹理锐利、保留毛孔；不改五官姿态版型。
- mirrorless（143–144）：同上，光圈写成 f/1.8。
- phone（150–151）：计算摄影直出；暗部彩色噪点；边缘过锐化白边；色阶断层与降噪涂抹；**轻微过艳后衰减**；过锐与快拍感。
- action（157–158）：超广角；红绿色彩噪点；**轻微桶形畸变**；全局深景深；生硬过曝与死黑；饱和度干涩；机内锐化。

分类负向：三类相机共用「AI 痕迹、过度平滑、蜡像、卡通、过度锐化、过度降噪、合成感、无瑕皮肤、过度饱和、HDR、后期痕迹」（138–139、145–146）。phone 负向把「单反景深虚化、胶片颗粒」也列入（152–153）。action 负向同样禁止单反虚化（159–160）。

`prompt_extend: false`（212）表示这段中文就是全部指令，没有服务端扩写开关被打开。

### B1. physicalize 步骤0 · 1D 频域（旧注释称第一层；v2 应在 L2）

调用点硬编码，不读预设：

```367:371:server/imagePhysicalizer.ts
      const perturbedBase64 = await applyFrequencyPerturbation(freqBase64, {
        perturbStrength: 0.004,
        processAllRows: false, // 每隔一行处理，性能优化
        channelMode: 'luminance',
      });
```

`applyFrequencyPerturbation` 默认值与这次传入相同（179–183）。

| 项 | 公式 / 阈值 | 行 |
| --- | --- | --- |
| 亮度 | `Y = 0.299R + 0.587G + 0.114B` | 210 |
| 行抽样 | `processAllRows=false` 时 `y % 2 !== 0` 跳过（只处理偶数行） | 201 |
| 频段 | `low = floor(n*0.05)`，`high = floor(n*0.45)`，扰动 `k ∈ [low, high)` | 124–127 |
| 相位 | `phaseNoise = (Math.random()-0.5) * perturbStrength * 2π`。strength 0.004 时半幅最大约 `0.004π` 弧度（约 0.72°） | 129 |
| 幅度 | 保持 `magnitude`，只改相位 | 130–136 |
| 共轭 | 若 `n-k > high`，把 `n-k` 写成共轭。在上述 high=0.45n 且 k&lt;0.45n 时条件恒真 | 139–144 |
| 写回 | `origLum>0` 时 RGB 乘 `newLum/origLum`；否则三通道加同一 `round(delta)` | 224–234 |
| 编码 | JPEG quality **92** | 259–261 |
| 失败 | 返回原 base64 | 266–268 |

未接入的边缘函数：上下各 `floor(height*0.15)` 行，强度写死 0.006，同样 JPEG 92（276–321）。无调用方。

没有 2D FFT，没有 DCT，没有按 8/16/32 周期打频率格点（格点正弦在指纹模块，不在这里）。

### B2. physicalize 步骤1 · 噪声（v2 L1 的一部分）

| 项 | 公式 / 阈值 | 行 |
| --- | --- | --- |
| 是否调用 | `enableNoiseInjection && iso>=200`。两者默认都满足；ISO 缺省 400 | 339、377 |
| σ | `isoToNoiseSigma = 0.5 * sqrt(iso/100)`，再乘 `intensity`（生产写死 1.0） | 76–77、123 |
| 内部门 | `sigma < 0.3` 则原样返回。`intensity=1` 时约 ISO&lt;36。与外部门 ISO≥200 同时成立时，内部门到不了 | 125–127 |
| 分布 | 每通道独立 Box–Muller，均值 0。`u1=0` 时 `log(0)` 无保护 | 59–63、142–147 |
| 暗部 | 像素值 &lt;64 再乘 1.5 | 146–147 |
| 量化 | `clamp` 含 `Math.round` | 67–68 |
| 编码 | 中间 JPEG quality **95** | 151–153 |
| 不用 | 传感器、品牌、型号 | 434–436 写入后无读取 |

数值（intensity=1，未乘暗部 1.5）：

| ISO | σ |
| --- | --- |
| 100（函数直接调才会用；主流程不注入） | 0.50 |
| 200 | 0.707 |
| 400（缺省） | 1.00 |
| 800 | 1.414 |
| 1600 | 2.00 |
| 3200 | 2.828 |
| 6400 | 4.00 |
| 25600 | 8.00 |
| 51200 | 11.314 |
| 102400 | 16.00 |

无上帽。

### B3. physicalize 步骤2 · 暗角（Q3）

| 项 | 值 | 行 |
| --- | --- | --- |
| 开关 | 默认开。`strength < 0.03` 跳过。表的最小值是 0.04，故 intensity=1 时永不跳过 | 167、383 |
| 表 | ≤1.4→0.35；≤2.0→0.28；≤2.8→0.22；≤4.0→0.16；≤5.6→0.10；≤8.0→0.06；否则 0.04。再乘 intensity | 85–92、165 |
| 缺省光圈 | 4.0 → 表值 0.16 | 340、418 |
| 中心 | `cx=width/2`，`cy=height/2`（不是 `(n-1)/2`） | 176–177 |
| 半径 | `r = dist / sqrt(cx^2+cy^2)` | 179、185 |
| 模型 | `cos4 = cos(atan(r*1.5))^4`；`factor = 1 - strength*(1-cos4)` | 188–189 |
| 编码 | JPEG quality 95 | 198–200 |

角点 `r=1`：`atan(1.5)≈0.9828`，`cos^4≈0.0947`，`1-cos4≈0.905`。角点保留亮度 ≈ `1 - 0.905*strength`。

| f | strength（I=1） | 角点约剩 |
| --- | --- | --- |
| ≤1.4 | 0.35 | 0.683（约暗 32%） |
| ≤2.0 | 0.28 | 0.747 |
| ≤2.8 | 0.22 | 0.801 |
| ≤4（缺省） | 0.16 | 0.855 |
| ≤5.6 | 0.10 | 0.909 |
| ≤8 | 0.06 | 0.946 |
| &gt;8 | 0.04 | 0.964 |

0.35 是否仍叫「弱暗角」：未决，见 C-VIGNETTE-COMMENT。

### B4. physicalize 步骤3 · 色差（Q4）

焦距表 `focalLengthToCAStrength`（99–107）：

| 焦距 mm | 表值 |
| --- | --- |
| ≤14 | 2.0 |
| ≤24 | 1.5 |
| ≤35 | 1.0 |
| ≤50 | 0.7 |
| ≤85 | 0.5 |
| ≤135 | 0.4 |
| 更长 | 0.3 |

主流程额外门（388–391）：

- 只在 `focalLength<=50` 时调用。缺省焦距 50，会调用。
- 传入的 intensity 是 `options.intensity * 0.5`。生产 `intensity=1`，故传入 0.5。
- 85mm 及以上的表值在主流程里不会被用到。

函数内（213–219）：

- `caStrength = 表值 * 传入intensity`
- `caStrength < 0.3` → 原图
- `shift = round(caStrength * 0.5)`（JavaScript `Math.round`，正数 .5 向远离 0）
- `shift < 1` → 原图（饱和度也不动）
- 否则做通道缩放后**丢弃**，对进入函数时的 buffer `saturation: 1.02`，且 `toBuffer()` 不指定 quality

生产 intensity=1（传入 0.5）时：

| 焦距 | caStrength | shift | 实际输出 |
| --- | --- | --- | --- |
| ≤14 | 1.0 | round(0.5)=1 | 饱和度 ×1.02；通道错位结果被丢 |
| ≤24 | 0.75 | round(0.375)=0 | 恒等 |
| ≤35 | 0.50 | round(0.25)=0 | 恒等 |
| ≤50 | 0.35 | round(0.175)=0 | 恒等 |
| &gt;50 | 不调用 | — | 恒等 |

要让 24mm 的 shift≥1，需要 `round(1.5 * I * 0.25)≥1`，约 `I≥1.333`。`extractPhysicalizerOptions` 把 intensity 写成 1.0（440），预设改不了。

### B5. physicalize 步骤4–5 · 中间 JPEG 与锐化（Q5）

ISO → `jpegQuality`（423–427），比较顺序是 ≥3200、≥1600、≥800、≤200、否则：

| ISO | quality | 4:2:0 | mozjpeg / trellis / overshoot / optimiseScans |
| --- | --- | --- | --- |
| ≥3200 | 82 | 是 | 全 false |
| ≥1600 | 85 | 是 | 全 false |
| ≥800 | 87 | 是 | 全 false |
| ≤200 | 92 | 是 | 全 false |
| 其余（含缺省 400） | 88 | 是 | 全 false |

行 273–288、395–396。这是**这一步**的参数。下一步锐化不带 quality。

锐化（296–311），主流程传入 `intensity * 0.5` = 0.5（399）：

- `blur` 的 sigma = `max(0.3, 0.3 * 传入intensity)` = `max(0.3, 0.15)` = **0.3**。传入值 ≤1 时模糊量不变。
- 随后 `sharpen({ sigma: 0.5, m1: 0.5, m2: 0.3 })`。
- 无 quality。

因此「弱锐化」在旧码里是先模糊再锐化，不是单独 unsharp。Q11 禁止把糊图当提分手段；这段 blur 是否算，留给裁决，本报告不把它列入可移植提分杠杆。

physicalize 整段失败返回原 base64（407–409）。元数据没有宽或高也返回原图（356–358）。注释写「验证 JPEG」（354），代码只检查宽高，PNG 也能过。AI 步骤产出的 PNG 会在频域步被收成 JPEG 92。

### B6. 指纹（旧注释称第五层；整段禁止回迁）

`extractFingerprintOptions`（405–419）：

| ISO | intensity | 只作用于频谱正弦的 `baseAmplitude` |
| --- | --- | --- |
| ≥1600 | 1.2 | 1.2×1.2=1.44 |
| ≥800 | 1.0 | 1.2 |
| 其他（含缺省 400） | 0.9 | 1.08 |

pHash 级别恒为 2；色彩与几何开关恒 true，且**不乘** intensity。

频谱正弦 `destroyDiffusionSpectrumFingerprint`（164–195）：

- 周期 8、16、32。
- `baseAmplitude = 1.2 * intensity`。
- 第 i 个分量幅度 `baseAmplitude / (i+1)`。
- `sin(2πx/period + φx)*0.5 + sin(2πy/period + φy)*0.5`，相位每次随机。
- 再加 `(Math.random()-0.5)*0.5`。
- 三通道加同一偏移。
- JPEG quality 93。

同向叠满时，幅度数量级约 `1.833 * baseAmplitude` 再加 ±0.25。intensity=0.9 时大约 2 个像素级。这不是「极弱频谱」的已证明形态。

pHash `destroyPerceptualHash`（86–130）：

- 幅度表 level 1/2/3 → 3/6/10。生产 level 2。
- `blockSize = max(8, floor(min(w,h)/32))`。
- 约 60% 块被扰。
- 块内幅度 `perturbMagnitude * (0.7+0.6*U)`，再乘棋盘 ±1 与 `(0.8+0.4*U)`。level 2 的像素偏移大约 3.4～9.4。
- JPEG 93。

色彩 `destroyColorFingerprint`（230–251），生产必跑：

| 项 | 代码区间 |
| --- | --- |
| hue | `floor(random*5)` → 0、1、2、3、4 度（只有正向） |
| saturation | `0.95 + random*0.08` → [0.95, 1.03) |
| brightness | `0.98 + random*0.04` → [0.98, 1.02) |
| gamma | `1.0 + random*0.08` → [1.0, 1.08) |
| 编码 | JPEG 93 |

几何 `applyGeometricPerturbation`（275–313），生产必跑：

- 旋转 `(U-0.5)*0.4` 度，即 ±0.2°，背景黑。
- 每边裁 `floor(U*2)` 即 0 或 1 像素（注释写 1–2，代码是 0–1）。
- `safeCrop` 至少 `width-4`。
- Lanczos3 `fit:'fill'` 拉回**当前**宽高（不是保证等于用户原图；若上游 AI 已改尺寸，这里跟着 AI 尺寸）。
- JPEG 93。

失败返回原 base64（395–397）。

### B7. 上传模拟（旧注释称第四层；整段禁止回迁）

`PLATFORM_PROFILES`（80–151）。主流程默认 `generic`（`routers.ts` 698、836）。

| 平台 | JPEG q | 色度 | 最大边 | 量化偏置 | 加噪声 | 亮度 | 饱和 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| tiktok | 92 | 4:2:0 | 4096 | 2 | 是 | 1.00 | 1.02 |
| xiaohongshu | 90 | 4:2:0 | 4096 | 3 | 是 | 1.01 | 1.05 |
| instagram | 92 | 4:2:0 | 4096 | 2 | 否 | 1.00 | 1.00 |
| wechat | 90 | 4:2:0 | 4096 | 5 | 是 | 0.99 | 0.98 |
| weibo | 90 | 4:2:0 | 4096 | 4 | 否 | 1.00 | 1.00 |
| douyin | 92 | 4:2:0 | 4096 | 2 | 是 | 1.00 | 1.03 |
| generic | 92 | 4:2:0 | 4096 | 2 | 否 | 1.00 | 1.00 |

即便 generic：超 4096 用 Lanczos3 `fit:'inside'` 缩小（287–292）；`toColorspace('srgb')`（297）；先 JPEG q=95、4:4:4（308–314）；再 JPEG q=92、4:2:0，mozjpeg/trellis/overshoot/optimiseScans 全 false（329–338）。噪声路径还有一次 JPEG 95，并用 piexif 把 EXIF 贴回去（217–233）。失败返回原图（352–354）。

### B8. 体积带 + EXIF finalize（体积带禁止回迁；EXIF 字段规则可单独看）

`optimizeImageSize` 默认（80–88、104–155）：

| 项 | 值 |
| --- | --- |
| 目标带 | 原文件的 **0.6–0.8** |
| 跳过门 | 原图 &lt; 40 KiB → `tiny-original-skipped`，仍跑 finalize |
| quality | 地板 60，天花板 96，初值 88，最多 6 次 |
| 编码 | 每次从**平台输出**重编，不叠代损伤；`withMetadata()`；4:2:0；mozjpeg 等全 false |
| 度量 | 传入 `finalize` 时，量的是 EXIF 之后的字节 |

这与 v2「输出字节 ≥ 源字节」方向相反。禁止为提分启用。

`writeExifToJpeg`（304–529）字段规则（Q9 相关）：

| 字段 | 空则 |
| --- | --- |
| Make / Model / Software / Artist / Copyright / Lens | 不写（338–342、419–422） |
| ISO | `if (preset.iso)` 才写；0 被跳过。写入前 `normalizeISO`（最近的标准 ISO，按 `abs(log2)`，表到 102400）（220–233、385–391） |
| 快门 | 空串在解析函数里会变成 `1/125`，但外层 `if (preset.shutter_speed)` 空串不进（266–267、395） |
| 光圈 | 真值才写。`normalizeAperture` 对非有限或 ≤0 返回 1.8（236–241、402–408） |
| 焦距 | 真值才写。`normalizeFocalLength` 对 ≤0 **没有**守卫，`log2` 变 NaN 时比较失败、保持初值 8（251–263、412–417） |
| FocalPlaneX/Y + Unit | 预设值或机型表，**两个分辨率都真**才写。Unit 缺省 2（cm）。未知机型且预设空 → 三个都不写（132–140、375–382） |
| 机型表 | `CAMERA_SPECS` 81–130。查找：`"make model"`、再 model、再互相 `includes`（132–140） |
| GPS | `gps_mode` 缺省 **auto** 并可能随机生成，不是跳过。`'none'` 不写。`'fixed'` 缺坐标不生成（449–468） |
| 始终写的 | DateTime、Orientation=1、分辨率 72、ExifVersion 0230、ColorSpace、ExifImageWidth/Height（缺省可成 4032×3024）、曝光补偿 0、若干 0 值、ImageUniqueID、测光/白平衡码（343–369、425–446） |
| 缩略图 | 160×120、`fit:'inside'`、JPEG 70，失败只告警（491–501） |
| 整函数失败 | 返回输入 base64，上游仍当处理成功（520–523） |

像素噪声用的是**未标准化**的 ISO；EXIF 里写的是标准化 ISO。例如 300 会按 log2 靠近 320 写入标签，噪声仍按 300。两套数字不要合成一个。

旧检测（不是 Q1 指标）：`verifyExifWithGemini` 把品牌/型号/镜头/ISO/快门/光圈/软件写进提示词（93–107），Gemini 走 inline jpeg base64（158–165）。提示词里的及格线是 75（134）。路由落库及格线是 70（941–943）。

---

## 6. `aiImageProcessor.ts` 深挖（几何 / 调色 / 与后层衔接）

1. **模型。** 头注释列举 dashscope、openai、gemini、custom（6–10）。生产默认格式 dashscope、默认模型字符串 `qwen-vl-plus`。另一处展示默认值是 `qwen-image-2.0-pro`。数据库 `model_version` 可以覆盖调用，不能覆盖那段展示逻辑。没有响应样本。
2. **prompt。** 分类中文长提示是唯一进 DashScope `content[].text` 的正向文本（554–555、203）。`prompt_extend:false`。负向单独字段。OpenAI/Gemini 路径不传负向字段（`callOpenAIFormatOnce` / `callGeminiFormatOnce` 的签名没有 negative）。
3. **strength 没有进 API。** 计算了 `finalStrength`，`callAIImageEdit` 的实参是 URL、正向、负向、key、model、format、baseUrl。返回值里的 `usedStrength` 会让调用方以为强度生效。测试 `aiImageProcessor.test.ts` 只断言默认表的 strength 区间，没有断言请求体。
4. **尺寸。** DashScope 不传 size。函数返回后，路由把 URL 再下载成 base64（808–812），**不**检查宽高是否与输入一致。后层 sharp 按「手头这张图」的宽高处理。指纹几何拉回的是当时的宽高。上传只在 &gt;4096 时缩小。没有「AI 输出必须等于原图像素尺寸」的代码。
5. **与后层衔接。** 设计注释是 AI → 五层物理化 → 检测（3–4、532）。实现是 AI 的 PNG/JPEG 字节进入 `physicalizeImage`，第一步就做 1D 频域并重编码 JPEG 92，再噪声/暗角/色差/JPEG/锐化。AI 失败或下载失败则后层吃原图。后层不读 `usedStrength`。
6. **几何。** 本文件的像素代码不旋转、不裁、不缩放。OpenAI 分支的 `1024x1024` 会改几何。action 提示词要求桶形畸变。模型是否改构图：缺证。
7. **调色。** 本文件没有 `modulate`。四类提示都要求某种饱和度变化。那是交给模型的话，不是像素公式。
8. **Gemini 分支不是 edits。** 空的 `inline_data` 对象没有被发送。发出去的是「请增强这张图：URL」的文本，再把返回的 base64 存成 png。
9. **重试与静默。** 见 B0。路由把异常吃掉。下载非 200 也不抛。

现行 v2（对照，不是旧事实）：`_maybe_layer0_img2img` 用 `gpt-image-2`、英文短句、参考图 `max_edge=1280` quality 85，再把输出拉回原尺寸，并用 α=`_LAYER0_IMG2IMG_STRENGTH`（0.12，可被环境变量覆盖）与原图 blend（`five_layer.py` 204–277）。旧仓没有 blend，是整张替换。账本已记录英短提示 + edits 的增益低于 10，中文分类提示尚未在 v2 实测。换模型不在本轮已授权范围内（账本 C-LAYER0-API）。

---

## 7. 边界枚举

### 7.1 ISO

| 情况 | 噪声 | JPEG 表（会被后续未指定 quality 的编码盖住，见 C-JPEG-QUALITY-CLOBBER） | EXIF | 指纹正弦 |
| --- | --- | --- | --- | --- |
| 缺省 | 400，σ=1 | 88 | 不写 ISO（无字段） | intensity 0.9 |
| 0 | 不注入（&lt;200），且 EXIF 条件为假 | 92 | 跳过 | 0.9 |
| 1～199 | 不注入 | ≤200 为 92 | 标准化到最近档，最小表值 50 | 0.9 |
| 200 | σ≈0.707 | 92 | 200 | 0.9 |
| 400 | 1.0 | 88 | 400 | 0.9 |
| 800 | 1.414 | 87 | 800 | 1.0 |
| 1600 | 2.0 | 85 | 1600 | 1.2 |
| 3200 | 2.828 | 82 | 3200 | 1.2 |
| 51200 | ≈11.3；暗部再 ×1.5 | 82 | 51200 | 1.2 |
| 102400 | 16 | 82 | 102400 | 1.2 |
| 更大 | 继续按 sqrt 涨，无帽 | 82 | 吸到 102400 | 1.2 |
| 负数 | `iso>=200` 为假，不注入。若作为 EXIF 真值进入 `normalizeISO`，`log2` 为 NaN | ≤200 分支要看是否 ≤200 | 行为未定义（NaN 比较） | `typeof==='number'` 成立则按 &lt;800 走 0.9 |

像素 ISO 与标签 ISO 可以不同，见 §5 B8。

### 7.2 光圈

| 情况 | 暗角 | EXIF |
| --- | --- | --- |
| 缺省 | f/4 → strength 0.16 | 不写 FNumber |
| ≤1.4 | 0.35 | 标准化到表内最近档（1.0～22） |
| &gt;8（含 +∞） | 0.04，不跳过 | 最近档，表上最大 22 |
| 0 或负数 | 第一档 `<= 1.4` 成立，strength **0.35**（不是落到 0.04） | `if (preset.aperture)` 对 0 为假，不写 FNumber。负数是真值，`normalizeAperture` 因 `<=0` 返回 1.8 |
| NaN | 所有 `<=` 比较为假，落到 0.04 | 非有限在 `normalizeAperture` 里返回 1.8；主流程要先过 `typeof==='number'` |

暗角没有「光圈缺失就跳过」；缺失用 4.0。

### 7.3 焦距

| 情况 | 色差实际输出（I=1） | EXIF |
| --- | --- | --- |
| 缺省 50 | 调用后 shift=0，恒等 | 不写 |
| ≤14 | 饱和度 ×1.02，无通道错位输出 | 标准化 |
| 15～50 | 恒等 | 标准化 |
| &gt;50 | 不调用 | 标准化；表到 1000，更长吸到 1000 |
| 0 | `<=50` 为真，表值 2.0，与 ≤14 相同，饱和度 ×1.02 | `if (focal_length)` 为假，不写 |
| 负数 | `<=50` 为真，表第一档 2.0，同样饱和度分支 | 真值；`log2` NaN，函数可能返回 8 |

### 7.4 空 EXIF 预设

`writeExifToJpeg(..., {})` 仍会写日期、方向、72 dpi、版本、色彩空间、默认 4032×3024、若干 0、测光/白平衡默认码，并按 landscape 区域随机 GPS（`scene` 空 → `generateGpsCoords` 用 landscape，202–213）。FocalPlane 不写。Make/ISO/光圈/焦距不写。这不是空操作。

`gps_mode:'none'` 才没有 GPS。`gps_mode:'fixed'` 且坐标空：不生成、也不写 GPS。

### 7.5 非 JPEG

| 阶段 | 行为 |
| --- | --- |
| AI | 成功产物按 PNG 存储；失败则保留调用方字节 |
| physicalize | sharp 能读出宽高就继续，频域步收成 JPEG。读失败或抛错 → 原字节 |
| 指纹 / 上传 / 体积 | 依赖 sharp。抛错则指纹/上传返回原字节；体积循环 `catch` 后 `break`，退回当前最好 buffer（176–179） |
| EXIF | 写到临时 `.jpg` 再调 exiftool。失败返回输入。PNG 字节可能原样留下，而路由 `storagePut` 的 content-type 仍是 `image/jpeg`（876） |

没有「非 JPEG 就拒绝」的门。

### 7.6 高 MAD

旧链没有 MAD。下列步骤都会拉高像素差，且没有否决：

- 高 ISO 无帽高斯 + 暗部 ×1.5
- 暗角 0.35 在角上约 32% 亮度
- 指纹棋盘约 ±3～9、正弦约 2 像素、hue/sat/gamma、±0.2° 旋转与 Lanczos 拉回
- 多次 JPEG（92、95、ISO 表、锐化未指定 quality、指纹 93×4、上传 95 再 90/92、体积带可到 quality 60）
- Layer0 若成功则整张替换

Q11 不允许为了提分故意糊。旧锐化的 `blur(0.3)` 和高 ISO 噪声都没有「到此为止」的保真门。不能把「旧仓不管 MAD」翻译成「v2 可以用糊图换分」。

---

## 8. C. 禁止回迁（提分也不能搬）

1. **整包 Node / sharp 运行时**，以及「先把服务跑起来再抄行为」。
2. **`physicalizeImage` 先频域、再 L1 类像素** 的顺序（363–374）。公式可以单独讨论，顺序不能回迁。
3. **`fingerprintDestroyer` 整段**：hue/saturation/brightness/gamma（244–250）、旋转/裁切/Lanczos 拉回（295–311）、棋盘格（100–120）。频谱正弦默认幅度也不满足「极弱」的已写明标准，不作为默许项。
4. **`uploadSimulator` 平台矩阵、最大边 4096 缩放、亮度/饱和偏移**（80–151、287–302）。generic 的双次 JPEG + sRGB 同样属于这条禁止链，不要拆出「只留 generic」来绕过。
5. **`sizeOptimizer` 0.6–0.8 带、quality 地板 60、为了体积把文件压小**（80–88）。与字节下限相反。
6. **色差烂桩原样搬迁**：丢弃 composite、只在超广角做 saturation 1.02（247–264）。账本禁止项第 5 条仍然有效。本报告加细的门闩（多数焦距根本是恒等）不是「可以搬恒等」的许可，也不是「应该改成真正通道错位」的私下裁决。
7. **失败退原图仍算成功**（AI、下载、physicalize、指纹、上传、EXIF）。
8. **OpenAI 分支 1024×1024** 与 **Gemini 空图文生图**。
9. **action 提示词里的桶形畸变**，以及任何旋转、裁切、改宽高。
10. **把旧落库及格线 70 写成 v2 `PASS_SCORE`。** 75 不动。
11. **`applyEdgeFrequencyPerturbation`**（无调用方）不要忽然接上。
12. **用 `blur(0.3)` 或无帽高 ISO 噪声故意把图弄糊来换 Gemini 分。**

---

## 9. D. 与 +10 相关的可移植杠杆（按证据排序，不是实施单）

排序规则：先看「旧码里它是否真的作用于像素或请求」，再看「v2 是否已经测过且 &lt;10」，再看「是否撞红线」。没有任何一条有「相对 s2-five-layer-2 的 Gemini 均分 ≥10」的证据。

| 序 | 杠杆 | 旧码证据 | 与现行 v2 的空档 | 约束内？ | 对 Q1 的证据强度 |
| --- | --- | --- | --- | --- | --- |
| 1 | 在**现有** `gpt-image-2` edits 合同里，用四类中文正向提示替换英文短句。负向若接口没有单独字段，只能作为同一次提示实验的第二部分，不能假造一个 DashScope `negative_prompt` 参数 | 送进 API 的只有提示词；strength 是死的（194–215、557–574）。`prompt_extend:false` | 账本：英短 + edits，n=12，gain=3.83；blend 扫描最好约 2.25。中文分类提示**未测** | 仅当删掉桶形畸变，且饱和度从句按裁决改写或标 `[NEEDS CLARIFICATION]`。不换模型，不取消 v2 已有的拉回原尺寸与 blend | **唯一未测的高杠杆**。仍是缺证，不是已证明的 +10 |
| 2 | 不要移植 strength 数字 | `finalStrength` 不进 body；phone 0.12 在路由上被 `?? 0.15` 盖住 | v2 的 α=0.12 是 v2 自己的 blend，不是旧 API 参数。α 扫描已经做过 | 再扫 α 不是旧仓新发现 | 已有测量低于 10。降权 |
| 3 | 1D 相位公式对照（strength 0.004、5%–45% bin、偶数行、亮度比例写回） | 367–371、113–151、216–234 | v2 `_l2_freq_1d_luminance` 已有偶数行、相近截止、相位噪声；写回是三通道加 delta，不是 `new/old` 比例；用的是正确 `rfft` 不是这份 Cooley–Tukey | Q6 要求对照与双路径，**不**要求把 FFT 挪到 L1 之前。非 2 的幂是否要逐语句复刻错误 FFT：未决 | 相位本身极小（约 0.72° 半幅）。没有分数证据表明把它改到 0.004 能贡献 10 分。它是对照项，不是提分主杠杆 |
| 4 | ISO 条件的中间 JPEG quality 与 4:2:0（82/85/87/88/92） | 273–288、423–427 | v2 中间质量固定 85，最终编码 `subsampling=0`（4:4:4） | Q5 允许中间重压。必须仍满足字节下限。多次 95 再加上锐化未指定 quality，不能整串搬 | 无 Gemini 证据。符号不确定（量化痕迹 vs 发糊）。低优先级实验，不是方案承诺 |
| 5 | 暗角表去掉 v2 的 0.85 缩放，用满 0.16～0.35 | 85–92 | v2 `aperture_vignette_strength` 在表后再乘 `_VIGNETTE_LEGACY_SCALE=0.85`，固定模式还会再乘 0.85 | Q3 写的是**弱**暗角。0.35 在角上约暗 32%，是否仍弱：未决 | 无分数证据。不排序为「因此能 +10」 |
| 6 | 把噪声改回「ISO&lt;200 不注、高 ISO 不封顶、无粗粒混合」 | 76–77、377 | v2 有 ISO 地板 400、强度 1.55、σ 夹在约 0.85–2.20，并混了模糊后的粗噪声 | 高 ISO 不封顶更容易糊，撞 Q11 的禁止方向。低 ISO 改回「不注」是减弱而不是旧仓证明过的加分 | 不支持 Q1 |
| 7 | 色差：移植「真正的通道错位」或移植「实际的恒等/+2% 饱和」 | 208–265 与 388–391 | v2 已做通道位移，并用 ceil 让 50mm 附近也会位移，末尾还有 ×1.02 饱和 | 烂桩禁止原样搬。再加大位移不是旧输出。饱和 ×1.02 与「禁可见调色」的冲突账本已列（C-V2-CA-SAT） | 不支持把色差当成 +10 杠杆 |

明确不进杠杆表：平台矩阵、60%–80%、指纹调色与几何、先频域、整张 AI 替换且不拉回尺寸、OpenAI 1024、检测阈值 70。

---

## 10. E. 需主代理裁决（本报告不选）

1. **提示词剥离范围。** action「轻微桶形畸变」必须去掉（Q7，已是红线，不是开放题）。开放题是：景深/虚化、饱和度衰减、过艳后衰减、死黑、过锐白边，算不算可见调色或几何。未裁决前不能把四段原文当成可直接粘贴的 v2 prompt。
2. **模型边界。** 是否允许离开 `gpt-image-2` edits，改到 DashScope `qwen-vl-plus` / `qwen-image-2.0-pro`。账本写明本轮未授权。旧默认模型能否回图仍缺证。
3. **Layer0 替换方式。** 旧仓是整张替换且不检查尺寸；v2 是拉回尺寸再 α blend。只换提示词、保持 blend，才是合同内实验。取消 blend 会接近旧行为，也会放大几何/MAD 风险，需单独授权。
4. **色差产品语义。** A) 对齐旧**输出**（默认焦距大多恒等，≤14mm 只有饱和 +2%）。B) 对齐旧**注释中的通道错位**（v2 已经做得更强）。C) 删掉 v2 末尾 ×1.02。三者不能同时叫「忠实旧仓」。
5. **1D 对照的数学对象。** 对齐相位与行抽样（现行 numpy），还是对齐非 2 的幂上的错误 Cooley–Tukey。Q6 的「旧式」一词覆盖不了这个差别。
6. **锐化里的 `blur(0.3)`** 算不算 Q5 的弱锐化，还是算 Q11 禁止的糊。未裁决前不 port 这段 blur。
7. **空 GPS。** Q9「空值跳过」与旧码「缺省 gps_mode 就随机坐标」冲突。FocalPlane 空则跳过，这一点与 Q9 一致，不必等裁决。
8. **暗角 0.35** 是否超出「弱」。未裁决前不要为提分把 v2 系数抬到满表。
9. **中间 JPEG 的 4:2:0** 能否在字节下限之下做对照实验。可以列为实验，不能列为已授权改动。
10. **旧检测 70 vs 提示词 75。** 只记录。v2 保持 75。不需要为了「对齐旧落库」再裁一次。

---

## 11. F. 可行性初判（能否支撑 Q1）

**不能支撑「Q1 已经可达」。** 可以支撑的只有一句更窄的话：在不许换模型、不许搬 Node、不许改样本、不许改 75、不许先频域、不许 60%–80%、不许几何与可见调色的前提下，旧仓里还剩**一条没在 v2 样本上量过的合同内杠杆**，就是分类中文提示词（且必须先裁畸变句，饱和度句等裁决）。

依据：

- Q1 的指标是 v2 Gemini `total_score` 相对 `s2-five-layer-2`。旧仓的 `score` 是另一套提示词（还把 EXIF 文本喂给模型），落库线还是 70。仓库内没有对照实验。
- 旧 Layer0 真正送进默认 API 的是中文提示，不是 strength。v2 已经用英文短提示 + edits 测到 gain=3.83，α 扫描约 2.25（账本 F-E2E-SHORT / C-FEAS-Q1）。这条中文提示还没测，所以存在上探空间；**上探空间不是 +10 的证明**。
- 旧仓里更「重」的像素手段（指纹调色、旋转裁切、平台缩放、体积压到 60%–80%、无帽高 ISO、先做频域、AI 整张替换）正好落在红线上。把它们算进「旧算法所以能 +10」是在放宽约束。
- 噪声表、暗角表、1D 相位、色差表，v2 已经有对应或更强的变体。旧色差在默认参数下对 24–50mm **没有像素输出**。这些公式解释不了 10 分的缺口。
- 本报告没有跑检测，也不能用旧 Node 去补这个实验。Q12：没有端测就不能 PR。

缺证（要证明 Q1，至少还缺这些，且都不在本报告范围内）：

1. 同一 `测试用/图片` 上，现行流水线只替换为裁剪后的中文提示（模型、α、层序、75 不动）的 `total_score` 均值与 `s2-five-layer-2` 的差。
2. 该实验若改几何或出现可见偏色，应判为撞 Q7，而不是记成有效增益。
3. 若增益仍 &lt;10，旧仓剩余可移植公式没有第二条同等权重的未测杠杆。届时「对齐旧仓」本身不足以承诺 Q1，需要主代理改目标或改授权，而不是继续搬 Node。

---

## 12. 结论（放在矛盾之后）

1. clone HEAD 与任务书一致。六份处理文件与快照字节相同。`aiImageProcessor.ts` 与 `routers.ts` 只在 clone，hash 与任务书一致。
2. 实际顺序是 AI →（频域→噪声→暗角→色差→JPEG→锐化）→ 指纹 → 平台上传 → 0.6–0.8 体积搜索且每次量 EXIF。这与 Layer0→L1→L2→L3→L4→L5 不一致。只禁止回迁顺序，不在本报告里重排成新需求。
3. Layer0 的强度是返回字段，不是 API 字段。可审计的控制面是四段中文提示、负向字段、`prompt_extend:false`、`watermark:false`、`n:1`。默认模型字符串是 `qwen-vl-plus`，没有成功回图的证据。
4. 默认参数下，色差不对 24/35/50mm 产生输出；≤14mm 只增加 2% 饱和度。通道运算被丢弃。
5. 1D 频域是偶数行、亮度、相位、0.004、5%–45% bin，然后 JPEG 92。它不是 DCT，而且长度不是 2 的幂时变换不正确。边缘函数未调用。
6. 指纹、上传模拟、60%–80% 体积带、失败冒充成功、OpenAI 固定 1024、检测线 70，都不能为了 Q1 回迁。
7. 可行性：旧仓**不能**证明 Q1。它只指出一个尚未测量、且仍要过 Q7 裁决的提示词实验。
