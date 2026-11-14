# DET-SCORE-OPTIMIZE · 旧仓杠杆对照（2026-11-14）

角色：研究子代理。只读旧仓与现行 `five_layer.py`，不改代码、不 push、不改 `PASS_SCORE`。  
旧仓：`/home/hbs/hbs-projects/_refs/mihuanyuantu` HEAD `4a3f2ade0532cab1cd69f01b0b00cdce5c78c5e7`。  
`aiImageProcessor.ts` sha256=`37ca598b8bb3af49fd3dcd454b7118788ac24208dc105b6406dcfde58af5b9fb`（本会话 `sha256sum` 复算一致）。  
现行：`aojuai-main/backend/app/capabilities/realphotos/services/five_layer.py`，`PIPELINE_VERSION=s2-five-layer-3`。

硬红线不放宽：Q1 相对 `s2-five-layer-2` 同样本均分 `total_score` ≥10 仍锁；`PASS_SCORE=75` 不改；不迁 Node；禁几何指纹与可见调色刷分；禁 60%–80% 与平台 resize；禁先频域；禁旧 CA 烂桩原样；Layer0 模型未批前不换 qwen；失败不得静默当成功。

证据分级：代码事实 = 本会话读到的语句；测试事实 = 已落盘端测/日志；账本引用 = DET/ALIGN 账本所载、本会话未重查库。不相容的句子并列，不选边改写。

---

## 0. 已知事实的交叉核验（不吞成假设）

| # | 命题 | 本会话核验 | 结论 |
| --- | --- | --- | --- |
| 1 | v3 本地真 Gemini 均分相对 v2 下降（~65→~49）；reason 点名色差/生成瑕疵 | **未重查** `cap_realphotos_detection_results`。数字与 reason 原文只存在于 DET 账本 F-SCORE-V3 / F-SCORE-DROP / F-REASON-CA / F-REASON-AI（任务 273=55, 272=35, 271=42, 269=48, 268=71, 267=45；n=29≈65.5 vs n=6≈49.3）。C1 端测日志里的 reason 是另一批样本，且**没有**「色差滤镜」这句（见下行） | 机制与「色差/生成瑕疵」相容，但 65.5/49.3 与那 6 条 reason **不是本报告重读的库行**。n 与样本也不与 Q1 的 12 张配对 |
| 2 | 8mm → 表值 2.0、`_CA_INTENSITY=1.15`、shift≈2px | **复算成立**。`focal_length_to_ca_strength(8)=2.0`；调用点 `intensity=1.0`；`ca=2.0*1.15=2.3`；`ceil(2.3*0.55)=ceil(1.265)=2`。代码见下行。worker 日志在 Layer0 警告之后继续写 `Huawei P60 Art` EXIF，与测试夹具同机型，但**该日志没打印 focalLength**；「预览预设就是 8mm」仍是账本 F-CA-8MM，本会话未重读 `preset_snapshot` | 公式对任意传入的 `8mm` 成立。该预览任务是否传入 8mm：账本断言，日志只旁证机型 |
| 3 | 旧 CA：composite 常被丢弃；≤14mm 才 sat×1.02；中长焦有效近恒等 | **代码复读成立**（C-CA-BUG-GATE）。生产传入 `intensity*0.5`。8/14mm：`ca=1.0`，JS `round(0.5)=1`，进入分支后 composite 被 `.then` 丢掉，只对原 buffer `saturation:1.02`。24/26/35/50mm：`round` 后 shift=0，函数直接 return，像素恒等。焦距 >50 根本不调用 | 与现行「真通道错位、且无 ×1.02」不是同一输出。禁止把烂桩原样搬回；也不要把现行 1–2px 错位叫做「对齐旧有效行为」 |
| 4 | Worker 内 `asyncio.run(generate_images)` 失败 → Layer0 静默 `None`；e2e 同步路径 Layer0 可成功但 C1 gain=1.00 | **两边都复读到**。`/tmp/local-preview-worker.log` 有 11 次 `five_layer.py:331` `coroutine 'generate_images' was never awaited`，警告后 exiftool 仍继续写标签。C1 文件头 `layer0_img2img=on`，12/12 `ok=1`，`mean_v2=66.00 mean_v3=67.00 gain=1.00` | 失败路径与成功路径都存在，且不是同一人群 |
| 5 | 合同内已测最好 gain≈3.83<10 | **复读端测落盘成立**。`FIVE-LAYER-LEGACY-ALIGN-e2e-layer0-2026-11-13.txt`：`mean_baseline_v2=63.00` `mean_v3=66.83` `gain=3.83` `ALIGN_W5_E2E_SHORTFALL`。ALIGN 账本另记 blend α=0.12 的 n=6 gain=2.50、α 扫档最好约 +2.25；本会话未重跑扫档脚本 | 3.83 是已落盘配对增益的最大值，不是「所有允许杠杆的上界证明」 |

C1 日志中抽到的 reason（26mm、Layer0 成功、中文提示、`ca_sat_nudge=off`）与账本所引「色差滤镜」不是同一批：

- `product_01`：`lacks premium sharpness`（+4，72 vs 68）
- `product_11`：`unnatural lighting and composite-like appearance`（+3）
- `product_12`：`compression artifacts and flat lighting`（−4）

因此：把本地 ~49 的「色差」reason 和 Q1 样本上的 +3.83/+1.00 **加在一起解释**，本报告不做。

---

## 1. 证据表（文件:行号）

行号均为本会话读到的现行/旧仓文件。旧仓行号与 2026-11-14 旧仓提取报告一致，本会话抽读未发现漂移。现行 `five_layer.py` **相对** `FIVE-LAYER-LEGACY-ALIGN-subagent-current-audit-2026-11-14.md` 已漂移（该审计仍写饱和度 ×1.02、英文短提示、B 边填 0、`preset` 丢弃）；以本次读到的文件为准，不回改审计。

| ID | 事实 | 位置 |
| --- | --- | --- |
| E-HASH | `aiImageProcessor.ts` sha256 与任务书一致 | 本会话 `sha256sum`；冲突账本 F-AI-IN-CLONE |
| E-ORCH | 旧生产序：AI → physicalize（先频域）→ 指纹 → 平台上传 → 0.6–0.8 体积+EXIF | `routers.ts` 753–854 |
| E-AI-FAIL | AI catch 后仍用原图继续，主流程可完成 | `routers.ts` 814–817；下载 `!ok` 时 809–813 也不抛 |
| E-STRENGTH | `finalStrength` 只进返回值；`callAIImageEdit` 参数无 strength；DashScope body 无 strength | `aiImageProcessor.ts` 194–215、448–456、557、566–574、584 |
| E-PROMPT | 四类中文正向是默认 API 控制面；action 含「轻微桶形畸变」；phone/dslr 含饱和度衰减或过艳后衰减 | `aiImageProcessor.ts` 136–162 |
| E-ROUTE-STR | 路由写死 `strength: aiStrength ?? 0.15`，不用 phone 表内 0.12 | `routers.ts` 791 |
| E-FREQ-FIRST | physicalize 步骤 0 先 1D，strength 0.004，偶数行，亮度，再噪声 | `imagePhysicalizer.ts` 363–374 |
| E-FREQ-PHASE | 相位 `(U-0.5)*strength*2π`，不改幅度；写回是 `newLum/origLum` 比例 | `frequencyProcessor.ts` 124–136、216–228 |
| E-NOISE | `σ=0.5*sqrt(ISO/100)*intensity`；主流程 `iso>=200` 才注入；暗部 <64 再 ×1.5；无上帽 | `imagePhysicalizer.ts` 76–77、123–147、377–378 |
| E-VIG | 光圈表 0.35…0.04；`cos(atan(r*1.5))^4`；中心 `width/2` | `imagePhysicalizer.ts` 85–92、176–189 |
| E-CA-GATE | 仅 `focalLength<=50` 调用，且传入 `intensity*0.5` | `imagePhysicalizer.ts` 388–391 |
| E-CA-SHIFT | `shift=round(ca*0.5)`；`<1` 则原图返回 | `imagePhysicalizer.ts` 213–219 |
| E-CA-DROP | composite 只挂了 `rScaled`，结果被丢掉；落到 `modulate({saturation:1.02})` | `imagePhysicalizer.ts` 247–264 |
| E-CA-8-OLD | 8mm、外层 intensity=1：传入 0.5 后 shift=1，有效输出是饱和度 ×1.02，不是通道错位 | 上一行 + 本会话复算 |
| E-CA-26-OLD | 26mm：传入 ca=0.5，shift=0，恒等 | 同上 |
| E-JPEG | ISO→quality 82/85/87/88/92，色度 4:2:0；锐化 `blur` 后 `sharpen` 且不带 quality | `imagePhysicalizer.ts` 273–288、296–311、423–427 |
| E-FP | hue/sat/brightness/gamma 与旋转/裁切/拉回在生产链上 | `fingerprintDestroyer.ts` 230–249、275–313、364–387 |
| E-UPLOAD | 平台矩阵；超最大边 Lanczos `fit:'inside'` | `uploadSimulator.ts` 80–151、281–292 |
| E-SIZE | 目标带 0.6–0.8，quality 地板 60 | `sizeOptimizer.ts` 80–88 |
| E-PASS75 | 现行及格线 75 | `redo_policy.py` 6 |
| E-V3-CA | 现行：`ca=表*intensity*_CA_INTENSITY`，`_CA_INTENSITY=1.15`，`shift=ceil(ca*0.55)` 当 `ca>=0.35`；**注释写明不做**旧 sat×1.02；B 边填 128 | `five_layer.py` 50、179–204 |
| E-V3-8 | 8mm：ca=2.3，shift=2。26mm：ca=1.15，shift=1。85/135mm 现行 shift 仍为 1；旧仓焦距>50 不调用 | 本会话复算；调用点 `five_layer.py` 871 |
| E-V3-OPT | 光学 Layer0：`strength=0.32`，5×5 残差 + `N(0, 0.55*strength)`；img2img 之后 `_l1_l3` 仍默认 `layer0=True` | `five_layer.py` 48、160–176、850–852 |
| E-V3-NOISE | 地板 400、强度 1.55、σ 夹在 0.85–2.20，再乘档；0.65 细 + 0.35 粗；暗部 ×1.5。auto rank 用 `-noise_m*0.15` 偏好更强档 | `five_layer.py` 45–46、103–112、446–472、854–868 |
| E-V3-VIG | 旧表 ×0.85；中心用 `(n-1)/2` 而不是 `n/2`；固定全 1 档再 ×0.85 | `five_layer.py` 40、47、115–135、738–750、842–849 |
| E-V3-1D | 偶数行、5%–45%、相位 0.0045；写回是三通道加 delta，不是比例；`rfft` 不是旧 Cooley–Tukey。顺序在噪声/暗角/色差之后 | `five_layer.py` 34–36、770–794、872–875 |
| E-V3-ENC | 中间 JPEG 85；终编码 `subsampling=0`（4:4:4）；字节下限硬失败 | `five_layer.py` 43、79–91、506–522、893–901 |
| E-V3-L0 | 模型固定 `gpt-image-2`；中文三类提示（畸变已删、饱和度句已改写）；负向并进正向；参考图 `max_edge=1280` quality 85；输出 LANCZOS 拉回；blend 默认 0.12。异常 `return None` | `five_layer.py` 210–363；`supplier_clients.py` 125–135、163–180 |
| E-V3-LOOP | Worker 的 `_five_layer_jpeg` 是 async，里面同步调用 `run_five_layer`，后者 `asyncio.run`。失败则 `img2 is None`，继续用原图，不把任务标失败 | `s1_processing.py` 1266–1290；`five_layer.py` 319–331、587–590 |
| E-V3-RERANK | 只有传入 `score_fn` 才按 Gemini 选包。Worker 调用没传 `score_fn`。rerank 三包全是 `2d`，最轻一包 `(0.90, 0.85, 0.55, 0.65)`。CA 与光学 strength **不在**乘数网格里 | `five_layer.py` 61–65、658–710；`s1_processing.py` 1278–1282 |
| E-E2E-PRESET | Q1 端测预设是 phone、ISO 400、f/1.8、**26mm**，不是 8mm | `scripts/five_layer_legacy_align_e2e.py` 46–64 |
| E-GAIN-383 | 英短提示轮（文件未写 prompt 语言；账本写明英短整图 edits）gain=3.83，n=12 | `FIVE-LAYER-LEGACY-ALIGN-e2e-layer0-2026-11-13.txt` 257–263 |
| E-GAIN-100 | 中文 C1、`blend_alpha=1.0`、`ca_sat_nudge=off`、Layer0 12/12 ok，gain=1.00 | `FIVE-LAYER-LEGACY-ALIGN-e2e-c1-zh-2026-11-14.txt` 6–8、269–276 |
| E-LOG-11 | worker 日志 11 次 never-awaited，位置就是 `return None` | `/tmp/local-preview-worker.log` 计数；例：第 21–25 行后仍写 EXIF |

现行相对旧有效输出的色差（外层旧 intensity=1，现行 intensity=1）：

| 焦距 | 旧有效像素 | 现行 shift |
| --- | --- | --- |
| 8 / 14 | 饱和度 ×1.02（通道结果丢弃） | 2 |
| 24 / 26 / 35 / 50 | 恒等 | 1 |
| 85 / 135 | 不调用，恒等 | 1 |
| 200 | 不调用，恒等 | 0（ca=0.345<0.35） |

---

## 2. 杠杆枚举

「预期方向」只谈 Gemini `total_score` 的符号，不写成已测增量。  
「已测」区分：Q1 配对样本（`测试用/图片` 的 12 张、端测预设 26mm）与 8mm worker 人群。二者不可相加。

| ID | 旧行为 | 现行行为 | 红线 | 预期方向 | 已测 |
| --- | --- | --- | --- | --- | --- |
| L-CA-NEARZERO | 默认参数下 24–50mm 及更长焦**不改像素**；≤14mm 只 sat×1.02，通道结果丢弃 | 8mm 真错位 2px；26mm 与 50–135mm 真错位 1px；无 sat×1.02 | **条件**。Q4 允许色差，但没有要求 1–2px。把 shift 降到旧有效近零、且**不**加 sat×1.02，不是烂桩原样，也不是可见调色刷分。是否关到 0 仍是账本 C-CA-ALIGN，未裁 | 若检测器罚的是色边：向上。Q1 样本只有 1px，幅度未知。8mm 人群若 reason 属实，空间更大，但是另一人群 | 未做「只关 CA」析因。放宽前「禁色差且禁 Layer0」gain≈1.42，与本杠杆不是同一实验 |
| L-OPTICAL-BACKOFF | 无像素光学预通道。Layer0 只是图生图 | `_LAYER0_OPTICAL_STRENGTH=0.32`，且 img2img 成功后仍再跑一遍 | **允许**。不是几何、不是调色、不是换模型。账本假设曾写 ≈0.18，代码是 0.32；0.18 不是旧仓事实 | 不确定。若本地下降来自过驱动，减弱应靠近 v2，而不是自动变成相对 v2 的 +10 | 未单独测。3.83 与 1.00 的端测都走 `_l1_l3(layer0=True)`，光学是开着的 |
| L-ASYNC-AWAIT | 失败则 catch 后用原图继续，并仍可 completed（红线禁止照搬） | 已有事件循环时 `asyncio.run` 抛错，`return None`，流水线用原图做完 | **条件**。把协程改到当前 loop 里执行，使 worker 与 e2e 同步路径一致：允许。继续把 `None` 当成整单成功：**禁止**（见 L-SILENT-OK） | 分数符号不确定。e2e 上 Layer0 成功只有 +1.00 或 +3.83。本地 ~49 是 Layer0 **没跑成** 的人群，修通后可能升也可能因「生成瑕疵」再降 | 失败模式已复现（日志 ×11）。修通后的分数未测 |
| L-REF-NATIVE | DashScope 不传 size，也没有 1280 预缩放。OpenAI 分支写死 1024（禁止项，见下） | 参考图最长边 1280、quality 85，模型输出再 LANCZOS 拉回原宽高 | **条件**。这不是 `uploadSimulator` 的平台最大边矩阵。输出宽高仍必须等于原图。若实验改成不拉回，就变成几何，判禁止 | 若「文字扭曲/结构不对」来自 1280 再放大：向上。若模型本来就重绘：接近 0 | 未测。3.83 与 1.00 都经过这条预缩放 |
| L-NOISE-RANK | ISO 400、intensity=1 时 σ=1.0；无粗粒混合；无「更强档优先」 | σ≈1.55 再乘 auto 档至 1.45；rank 偏好更大噪声与暗角。Worker 不传 `score_fn`，用的就是这个 rank | **允许**（把偏好从「更强」改到「更弱或由检测分选」）。无帽高 ISO 把图弄糊来换分：**禁止** | Worker 人群：可能从过驱动往 v2 回。Q1 样本：e2e 已经在含更轻包的集合里按 Gemini 选过，均值仍 <10。再弱一档的效应未知，没有 +10 的证据 | Q1 上「现有网格内选最高分」已测（3.83 / 1.00）。网格外的更弱噪声、以及 worker 改 rank，未测 |
| L-PROMPT-STRIP | 中文正向要求紫边、轴向色差、过锐白边、色阶断层、饱和度变化；action 另要求桶形畸变 | C1 已删畸变、改写饱和度句，**仍保留**紫边/白边/色阶断层/暗角。负向并入正向。模型仍是 `gpt-image-2` | **条件**。再删紫边/白边/断层从句，仍不换模型：条件（Q7，避免提示词要求可见缺陷）。把 action 桶形畸变加回去：**禁止** | C1 整包已经比英短提示更差（1.00 vs 3.83）。再删从句的边际不确定，不能当成未测的高杠杆 | 中文整包已测，gain=1.00。英短整图替换已测，gain=3.83。只删紫边从句未测 |
| L-JPEG-420 | 中间 JPEG 按 ISO 取 82–92，4:2:0 | 中间质量固定 85；终编码 4:4:4；字节下限硬约束 | **条件**。Q5 允许中间重压。必须仍满足字节下限。不得借此走进 0.6–0.8 带 | 不确定。色度抽样可能加重已有的色彩投诉，也可能只改量化。没有分数证据 | 未测 |
| L-1D-RATIO | 相位 0.004；亮度比例写回；非 2 的幂上变换不正确；且位于噪声之前 | 相位 0.0045；加性 delta；正确 `rfft`；位于 L1 之后 | **允许**作为 Q6 对照（改比例写回或把 0.0045 改到 0.004）。把频域挪到 L1 之前：**禁止**。逐语句复刻错误 FFT：未决，不作为提分项 | 相位半幅约 0.7°。对均分的期望接近 0 | 公式差异未单独打分。双路径证据已在端测里跑过，不是分数析因 |
| L-VIG-WEAKEN | 满表。f/1.4 角点约暗 32%。中心是 `n/2` | 表 ×0.85，auto 档还可再乘 1.15–1.35，f/1.8 上可以接近或超过旧满表 | **允许**减弱。把 f/1.4 抬到满表 0.35 来换分：**条件**，且 Q3 写的是弱暗角，0.35 是否仍弱未决 | 检测 reason 没有单独点名暗角。期望幅度小 | 未单独测 |
| L-PROMPT-ZH | 分类中文长提示是旧 API 的真正控制面 | 已移植为改写后的中文，blend=1.0 | **允许**（已在合同内做完）。再换 qwen 来「真正复现」：**禁止** | 已测方向是相对英短提示更差 | **已测** gain=1.00 |
| L-BLEND-A | 旧仓无 blend，成功则整图替换；strength 不进 API | 默认 α=0.12；端测用过 1.0；账本记有 α 扫档 | **允许**但不是新杠杆 | 已测最好仍是整图替换 3.83；α 扫档约 +2.25 | **已测** |
| L-FP-COLOR-GEO | hue/sat/gamma + 旋转/裁切/拉回 + 棋盘 | 无 hue、无旋转裁切。L3 是 ±1 稀疏点与极弱频谱 | **禁止** | 不讨论提分方向 | 禁止，不测 |
| L-UPLOAD | 平台最大边缩放与亮度/饱和矩阵；generic 也在这条链上 | 无平台矩阵 | **禁止** | — | 禁止，不测 |
| L-SIZE-BAND | 压到原文件的 60%–80% | 字节下限：输出不得短于源 | **禁止** | — | 禁止，不测 |
| L-FREQ-FIRST | physicalize 入口先频域 | L1 之后才 L2 | **禁止**回迁顺序。相位公式另见 L-1D-RATIO | — | 禁止，不测 |
| L-CA-STUB | 丢弃 composite，只 sat×1.02 | 现行已不做 ×1.02（C1 日志 `ca_sat_nudge=off`） | **禁止**原样搬回。与 L-CA-NEARZERO 不是同一条：近零是「不改像素」，烂桩是「改饱和度」 | 饱和度 ×1.02 属于可见调色 | 禁止，不测 |
| L-MODEL-QWEN | 默认 `qwen-vl-plus`；展示名可以是另一字符串；没有成功回图样本 | `gpt-image-2` `/images/edits`，无 strength 字段 | **禁止**（未批换模型） | 旧仓不能证明换模型会 +10 | 禁止，不测 |
| L-PASS75 | 旧提示词写 75、落库写 70，都不是 v2 的 `total_score` | `PASS_SCORE=75` | **禁止**改 | — | 禁止 |
| L-NODE | sharp 全链 | NumPy/PIL | **禁止**整包迁 Node | — | 禁止 |
| L-SILENT-OK | 各步失败退原图仍算成功 | Layer0 失败 `return None` 后任务仍可做完 | **禁止**维持。对应的合规改法是 L-ASYNC-AWAIT，不是把静默失败留着 | 静默本身不提分 | 现行行为与红线冲突，已用日志证实 |
| L-BLUR-PRE | 锐化前 `blur(0.3)` | 现行 unsharp 无预模糊（注释写明预模糊会冲破 MAD） | **禁止**用预模糊或无帽噪声糊图换分 | — | 禁止，不测 |
| L-OPENAI-1024 | OpenAI 兼容体写死 1024×1024 | 输出宽高锁原图 | **禁止** | — | 禁止 |
| L-ACTION-BARREL | action 正向要求轻微桶形畸变 | 现行不返回 action 提示 | **禁止**加回 | — | 禁止 |

不单列成提分杠杆的旧差异：EXIF/GPS/FocalPlane（Q9，与像素 `total_score` 正交；旧检测还把 EXIF 文本喂进提示词，v2 检测提示词不这么做）。空 GPS 与「空值跳过」的字面差保持未决，不拿来刷分。

---

## 3. 矛盾与未决（不调和）

| ID | 两边 | 未决点 |
| --- | --- | --- |
| C-POPULATION | Q1 端测是 26mm、n=12、Layer0 在同步路径成功，最好 gain=3.83 / C1 gain=1.00。DET 账本的 ~65.5→~49.3 是 n=29 vs n=6、且本会话未重查库；worker 日志显示这条路径 Layer0 经常没跑成 | 不能把「修 CA 能捞回约 16 分」写成 Q1 的 +10。16 分下降若属实，也还没回到 v2，更没有超过 v2 十分 |
| C-CA-ALIGN | Q4 允许色差。旧有效行为在 26mm 上是恒等，在 8mm 上是 sat×1.02。现行是真错位。烂桩禁止原样搬 | 降到近零，还是保留可见错位再扫档：仍是 **[NEEDS CLARIFICATION]**。本报告只把「近零且不加饱和度」列为条件杠杆 |
| C-AUDIT-STALE | 现行审计写：末尾仍 ×1.02、英文短提示、B 边为 0、`preset` 丢弃。本次文件：不做 ×1.02、中文提示、B 边 128、`preset` 参与分类 | 审计描述的是更早的 `five_layer.py`。冲突账本 C-V2-CA-SAT 同样停在「现行仍 ×1.02」。以本次文件 + C1 日志 `ca_sat_nudge=off` 为代码事实，不回头改那两份文档 |
| C-L0-BLAME | 账本 reason 点名生成瑕疵；worker 上 Layer0 常失败；e2e 上 Layer0 成功时 gain 仍然 <10，且 C1 reason 点名锐度/光照/压缩，不点名色差 | 生成瑕疵不能默认归 Layer0，也不能默认归 CA。必须分路径 |
| C-Q1-VS-DROP | Q1 要相对 v2 **+10**。若本地 v3 已经低于 v2，先回到 v2 的杠杆（减弱噪声/光学/色差）只是止血 | 止血 ≠ 证明能再 +10。本报告不把二者收成一个方案 |
| C-LAYER0-API | 旧默认 DashScope/`qwen-vl-plus`，strength 不进 body。v2 是 `gpt-image-2`，也没有 strength 字段 | 未批前不换模型。再扫 α 或再写「Strength 0.12」不是旧行为复现 |
| C-PROMPT-REST | 裁决 A 已改饱和度句、已删桶形畸变。紫边/白边/色阶断层/景深仍在提示里 | 这些从句算不算 Q7 的可见缺陷：未裁。C1 是带着它们测的 |
| C-1D-OBJECT | Q6 要旧式 1D 对照。旧实现在非 2 的幂宽度上不是正确 FFT | 对齐相位与行抽样，还是对齐错误变换：未决。都不构成 +10 依据 |
| C-VIG-WEAK | Q3「弱暗角」没有定义 0.35 或现行叠加乘数算不算弱 | 不把满表升格为提分方案 |
| C-SCORE-SOURCE | 65.5/49.3 与任务 267–273 的 reason 文本 | 本会话没有重查数据库。只作为账本已记载的测试事实引用 |

---

## 4. 推荐消融顺序（仍不写代码）

只在 Q1 合同样本上打配对 `total_score`（同一 12 张、相对 `s2-five-layer-2`）。8mm / Huawei 预览只作诊断，不拿诊断人群的增量去填 Q1。每一步保持：不改 75、不换模型、不改样本、不先频域、不加 sat×1.02、失败不得记成成功。

1. **L-CA-NEARZERO**。冻结现行 Layer0 提示与光学/噪声。只比较「现行 shift」与「shift=0 且无饱和度」。Q1 预设是 26mm，现行只有 1px；这一步回答色边是否就是 Q1 缺口。8mm 的 2px 另记一列，不并进均值。
2. **L-OPTICAL-BACKOFF**。在步骤 1 较好的色差设定上，比较光学 0.32 / 0.18 / 0（img2img 成功后不再叠加）。0.18 只是账本假设，不是旧仓。
3. **L-REF-NATIVE**。仅当步骤 1–2 的 reason 仍写文字扭曲或结构不对：参考图不预缩到 1280，输出宽高仍锁原图。与平台 resize 矩阵无关。
4. **L-ASYNC-AWAIT**。在已有事件循环里执行 `generate_images`，禁止 `None` 后仍 completed。用同一张图证明 worker 字节与同步路径一致。这一步是红线合规；它在 Q1 样本上不会自动超过已经测过的「Layer0 成功」增益（1.00 与 3.83）。8mm 人群修通后的分数单独列表，不与 Q1 相加。
5. **L-NOISE-RANK**。仅当前四步的配对增益仍 <10：去掉「更强噪声优先」，并加一档低于现有最轻 rerank 包的噪声。不打开无帽高 ISO，不用预模糊。

做到第 5 步仍 <10 时，旧仓里没有下一条同等权重、且仍在红线内的未测杠杆。L-JPEG-420、L-1D-RATIO、L-VIG-WEAKEN、L-PROMPT-STRIP 可以记在附录实验里，不排进主顺序：要么期望接近 0，要么相邻整包已经测过且更差。

明确不要做的实验：指纹调色/几何、平台矩阵、60%–80%、先频域、色差烂桩、换 qwen、改 75、预模糊刷分、OpenAI 1024、action 桶形畸变。

---

## 5. 能否在不放宽下达到 Q1≥10

**UNPROVEN**

依据：

- 没有一次合同内测量 ≥10。已落盘配对增益：英短提示整图替换 **3.83**（63.00→66.83，n=12）；中文 C1 **1.00**（66.00→67.00，n=12，Layer0 12/12 成功）；账本所记 α=0.12 为 2.50、α 扫档最好约 2.25；放宽前禁色差且禁 Layer0 约 1.42。`PASS_SCORE` 仍是 75，这些均值都不过线。
- 旧仓不能把缺口补上。它的检测分不是相对 `s2-five-layer-2` 的 `total_score`。默认 Layer0 的 strength 不进 API。默认色差在 Q1 端测所用的 26mm 上有效输出是恒等，不是一套更强、尚未移植的像素公式。更重的旧步骤落在禁止表里。
- 也不能写成 PROVEN_NO。3.83 那一次捆绑了当时的提示词、开启的色差、光学 0.32 和 1280 参考图。色差与光学不在 rerank 乘数网格里，没有「只关色差 / 只关光学 / 参考图原尺寸」的配对分。本地账本所载的下降说明检测器对这条像素栈敏感，但那是未重查的另一人群，而且方向是向下。敏感性不是 +10 的存在性证明，也不是不可能性证明。
- 因此：在不放宽红线的前提下，**尚未证明能达到 Q1≥10，也尚未证明不可能**。已测高杠杆（中文提示、blend、整图替换）都停在 4 分以内。剩下的允许/条件项里，唯一还对得上「色差」指控、且没被析因的，是 L-CA-NEARZERO；它没有效应量，不能事先写成够 +10。
