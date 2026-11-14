# DET-SCORE-OPTIMIZE · 因果消融与可行性门禁候选

日期：2026-11-14  
角色：研究子代理（只出方案；不改业务代码；不 push）  
状态：**候选**。`OPEN` / `CLOSED` 由主代理写入可行性门禁。本文不构成编码授权。  
承接：`DET-SCORE-OPTIMIZE-constraint-ledger.md`（R3 可行性输入）  
硬锁沿用：Q1 相对 `s2-five-layer-2` 同样本均分 `total_score` ≥10；`PASS_SCORE=75` 不动。

```text
coding_gate_recommendation: OPEN_PARTIAL
q1_status: UNPROVEN
pass_score: 75
```

`OPEN_PARTIAL` 的含义：只放行「缺陷修复」和「与旧仓有效像素对齐、且不触红线」的改动。现有真 Gemini 证据下，这些改动**没有**证明 Q1 可达。C1 端测 `gain=1.00` 仍有效。消融后若合同样本 gain 仍 &lt;10，停止加码，回到管理员改裁。

---

## 0. 证据分层（本子代理）

| 标签 | 含义 |
| --- | --- |
| 用户要求 | 本轮指令与 ALIGN/DET 账本里管理员已锁条款 |
| 代码事实 | 本子代理重读现行 `five_layer.py`、`s1_processing.py`、`worker_runtime.py`、`config.py`、旧仓 `imagePhysicalizer.ts` |
| 测试事实 | 已落盘的端测、worker 日志、账本已核库表。本子代理**未重查**检测库 |
| 待验证推断 | 消融前不得写成根因或可达分数 |

---

## 1. 已核事实（消融必须分开的两条路径）

### 1.1 代码事实 · Layer0 在 worker 里静默跳过

- `worker_runtime.run_worker_cli` 用 `asyncio.run(_amain())` 起循环（`worker_runtime.py`）。
- 处理入口 `_five_layer_jpeg` 是 `async def`，在循环线程上**同步**调用 `run_five_layer`（`s1_processing.py`）。
- `run_five_layer` 在 `algorithm!=v2` 且 `freq_mode` 为 auto 时调用 `_maybe_layer0_img2img`。
- 该函数执行 `asyncio.run(generate_images(...))`。协程对象先被创建；循环已在跑时 `asyncio.run` 抛错，被 `except Exception: return None` 吃掉。
- 测试事实：`/tmp/local-preview-worker.log` 有 **11** 次 `RuntimeWarning: coroutine 'generate_images' was never awaited`，指向 `five_layer.py` 该 `return None`。
- 因此 worker 生产像素是 **光学 Layer0 + L1–L5，没有供应商 img2img**。Gemini 写「生成瑕疵」时，不得默认归因到 img2img 成图。
- 同步、无运行中循环的路径可以跑通 img2img。C1 端测即此路径：`layer0_note` 12/12 `ok=1`，`ALIGN_LAYER0_IMG2IMG=1`，`ALIGN_LAYER0_BLEND_ALPHA=1.0`。

死锁约束（编码时）：在**同一**运行中循环的线程上 `asyncio.run`，或 `run_coroutine_threadsafe(...).result()` 死等该循环，会卡住 worker。允许的修法是下面二者之一：

1. 把 `await generate_images` 传到已经是 async 的 `_five_layer_jpeg`（`run_five_layer` 改为 async 时，只改调用处的 await / 脚本顶层 `asyncio.run`，不改像素公式）。
2. 在**另一线程**里用该线程自己的 `asyncio.run(generate_images)`，循环线程只 `join`。`generate_images` 是 HTTP；不得把请求上的 SQLAlchemy session 带进该线程。

两种修法都必须：失败时打出 `error_type`，禁止再无日志 `return None`。

### 1.2 代码事实 · 现行色差不是旧仓有效像素

现行 `_apply_chromatic_aberration`（`intensity=1`，`_CA_INTENSITY=1.15`）：

`ca = focal_table × 1 × 1.15`，`shift = ceil(ca × 0.55)`（`ca≥0.35`）。

| 焦距 | 表值 | 现行 shift |
| --- | ---: | ---: |
| 8mm（预览预设类） | 2.0 | **2 px** |
| 26mm（ALIGN 端测预设） | 1.0 | **1 px** |
| 50mm | 0.7 | **1 px** |

旧仓 `physicalizeImage` 调用的是 `applyChromaticAberration(..., intensity * 0.5)`（默认 `intensity=1`）。函数内 `shift = Math.round(table × 0.5 × 0.5) = Math.round(table × 0.25)`，`shift<1` 直接返回原缓冲。

| 焦距 | 旧调用点 shift | 旧函数实际写出的像素 |
| --- | --- | --- |
| ≤14mm（含 8mm） | `round(0.5)=1`，进入后续 | composite **被丢弃**；只对原图 `saturation: 1.02` |
| 24 / 26 / 35 / 50mm | `round ≤ 0` | **像素恒等**（提前 return） |
| &gt;50mm | 调用点 `focalLength<=50` 不进函数 | 恒等 |

`saturation×1.02` 属于冲突账本禁止回迁的色差烂桩，也触 Q7 可见全局调色。红线允许的旧有效残差是：**各焦距通道错位为 0（近零恒等）**。

`focal_length_to_ca_strength` 的表本身与旧函数一致（测试已锁 14→2.0、26→1.0、100→0.4）。分叉在调用强度、`ceil(×0.55)`、额外 `_CA_INTENSITY=1.15`，以及旧 composite 被丢弃。

### 1.3 测试事实 · 两套分数不能混读

| 观测 | 条件 | 结果 | 能说明什么 |
| --- | --- | --- | --- |
| 账本 F-SCORE-DROP | 库内历史任务。v2 n=29 均分≈65.5；v3 n=6 均分≈49.3。本子代理未重查库 | 下降约 16 | 生产 v3（Layer0 未跑、短焦 CA）低于历史 v2。样本不是同一批 12 张合同图 |
| 账本 F-SCORE-V3 | 任务 273/272/271/269/268/267 = 55/35/42/48/71/45，均 &lt;75 | 未过门闩 | 与 F-REASON-CA（271/272 点名色差/红蓝）和 F-REASON-AI（267/269/273 点名生成瑕疵）并存 |
| C1 端测 | n=12，`product_01..12`，seed `20261113`，焦距 **26mm**，Layer0 **开**且 blend **1.0**，v3 **传入 `score_fn` 做多包选优** | `mean_v2=66.00` `mean_v3=67.00` **`gain=1.00`** | 合同 Q1 的现行最好中文轮。worker **不传** `score_fn`，故这不是生产路径的复现 |
| 英短提示轮（ALIGN 账本） | 同合同样本，整图 edits | gain≈**3.83** | 合同内已测最好，仍 &lt;10 |

Q1 只认合同样本相对 v2 的均分差。8mm 生产塌陷解释的是「为何预览分低」，不能替代 Q1。

### 1.4 代码事实 · v2 像素路径仍在，生产版本号是 v3

- `PIPELINE_VERSION = "s2-five-layer-3"`；`algorithm="v2"` 走冻结的 `_l1_l3_v2`（无暗角、无 1D、无锐化、无 CA、无光学 Layer0、无 img2img）。
- `s1_processing` 把 `_PIPELINE` 写成任务的 `pipeline_version`。切生产到 v2 会改写这个版本号。
- ALIGN 账本参数假设写明 Pipeline：`s2-five-layer-3`。测试 `test_pipeline_version_is_s2_five_layer_3` 锁定该字符串。
- ALIGN 冲突行 C-PHYS-TUNE 有「v2 可切回」字样，指的是升 v3 之前的噪声阻尼注记，不是本轮把生产任务改回 v2 的授权。

---

## 2. 根因假说证伪矩阵

假说来自 DET 账本 §3。下表给出**预先写死**的确认/证伪，避免看分后再改口径。

| ID | 假说 | 若成立，消融应看到 | 证伪（看到即推翻该假说为唯一因） | 现况 |
| --- | --- | --- | --- | --- |
| P-CA-PHONE | 短焦真实通道错位被 Gemini 判成色差滤镜，压低 `color_realism` / `overall` | 协议 W、8mm：CA 恒等臂相对现行 2px 臂，「色差/红蓝/色差滤镜」reason 计数下降，且 color+overall 均值上升 | 恒等臂 reason 仍以这类词为主，或 color+overall 均值差绝对值 &lt;3（单次 Gemini，无重复测时的噪声带） | 待验证。支持线索是测试事实（271/272 reason）+ 代码事实（8mm shift=2）。C1 是 26mm 且 Layer0 整图替换，**不能**用来确认或推翻本假说 |
| P-V3-OVERDRIVE | `_LAYER0_OPTICAL_STRENGTH=0.32`、`_NOISE_INTENSITY=1.55`、频域/自动档倍数把分数从 v2 打到 v3 | 在 CA 已恒等、Layer0 img2img 关闭时，再降光学/噪声/频域，8mm 均分仍明显靠近 v2 | CA 恒等之后均分已靠近该焦距上的 v2，降档臂相对 CA 恒等臂均值差绝对值 &lt;3 | 待验证。账本 P-V3-OVERDRIVE 不是已证明唯一因 |
| P-L0-ASYNC | worker 上 img2img 没执行，故生产分与 C1 不可比；修通后分数会变（方向未知） | 修复后：循环内不再出现 never awaited；`ALIGN_LAYER0_IMG2IMG=0` 时输出字节与修复前一致；显式 `=1` 时 `last_note` 含 `ok=1` 或失败日志含 `error_type` | 修复后日志仍 never awaited；或 flag=0 仍改像素 | 缺陷本身是测试事实。**提分方向未测**。C1 在 flag=1、blend=1.0、26mm 上 gain 只有 1.00，不能外推成「修 async 就会 +10」 |
| P-ARCH-CEILING | 修缺陷并对齐旧有效 CA 之后，合同样本相对 v2 的 gain 仍 &lt;10 | 协议 C、26mm、n=12：白名单允许的臂里最好 gain 仍 &lt;10 | 某一**白名单内**臂 gain≥10 | 测试事实已支持「尚未达到」：C1 gain=1.00，英短最好 3.83。这不是数学上的不可能，是**未证明可达** |

读表规则：一项成立不自动证明另一项。P-CA-PHONE 即使成立，也只解释 8mm 生产分；Q1 仍看协议 C。

---

## 3. 消融实验设计

### 3.1 样本与对照

两套样本**分表报告，禁止合并均值**。

| 集 | 文件 | 预设 | 回答的问题 |
| --- | --- | --- | --- |
| 合同集 C | `测试用/图片/product_01.jpg`–`product_12.jpg`，哈希以 `FIVE-LAYER-LEGACY-ALIGN-sample-sha256.json` 为准；n=12；seed=`20261113` | 端测脚本 `_preset()`：phone、ISO 400、f/1.8、**26mm** | Q1。唯一可与 C1 `gain=1.00` 对照的集 |
| 短焦集 W | **同一** 12 个文件、同一 seed | 仅把 `focalLength` 改为 **8mm**（对齐预览预设 `legacy-legacy-online-1073` 的焦距档，不改其它字段） | 生产色差假说。不能拿这套均值宣称 Q1 |

对照分母永远是同集、同 seed、`algorithm="v2"` 的单次真 Gemini（v2 路径无 CA、无 img2img）。检测器沿用 `detect_jpeg`，及格线保持 75。MAD 只记录，不否决（Q11）。

### 3.2 两条协议

| 协议 | 调用形状 | 用途 |
| --- | --- | --- |
| W 生产形 | `run_five_layer` **不传** `score_fn`；Layer0 默认关（与 worker 现状一致） | 解释预览低分 |
| C 合同形 | 与 C1 脚本相同：v3 传 `score_fn` 多包选优；v2 单次检测 | 与已发布 gain 可比。C1 已覆盖「26mm + 现行 CA + Layer0 blend=1.0」，**不必重跑这一格**，直接引用 `e2e-c1-zh-2026-11-14.txt` |

生产 worker 不选优。协议 C 的分数高于协议 W 时，差值记为「选优」，不得写成管线本身变强。

### 3.3 臂（按序；先证伪再加因子）

| 臂 | 协议 | Layer0 img2img | CA | 光学/噪声/频域 | 算法 | 目的 |
| --- | --- | --- | --- | --- | --- | --- |
| R0 | C 与 W 各一份 | 关 | v2 无此级 | v2 冻结 | `v2` | Q1 分母；也是生产对照，**不改版本号** |
| R1 | W，8mm 与 26mm | 关（flag `0`） | 现行公式 | 现行默认 | `v3` | 复现「worker 实际像素」 |
| R2 | W，8mm 与 26mm | 关 | **恒等**（shift=0，无饱和度） | 现行默认 | `v3` | 证伪 P-CA-PHONE。8mm 是主判据 |
| R3 | C，26mm；另记一格 W+8mm | 显式 `ALIGN_LAYER0_IMG2IMG=1`，blend 用代码默认 **0.12** | 26mm 用现行（与 C1 差在 blend）；8mm 在 R2 已确认色差有害时用恒等，否则用现行并在表上标明 | 现行默认 | `v3` | 证伪 P-L0-ASYNC 的分数方向。blend=1.0 的 26mm 已有 C1，不重跑 |
| R4 | 仅当 R2 证伪 P-CA-PHONE 时，W+8mm，n=12 | 关 | 与 R2 相同（恒等） | 光学 0.32→0.16；噪声强度对齐旧 `0.5*sqrt(ISO/100)`（去掉 ×1.55）；自动档倍数取 1.0 | `v3` | **只测量** P-V3-OVERDRIVE。不在本轮白名单。不得把 R4 常量写进同一次「缺陷修复」改动 |
| R5 | — | — | — | — | 生产改 `s2-five-layer-2` | **不跑、不编码**。R0 已提供 v2 像素对照 |

每臂记录：`total_score`、五维、`passed`、reason 原文、MAD、`pipeline` 算法名、Layer0 note 或失败 `error_type`、CA shift（对一张固定图量 R/B 相对 G 的平移，期望 R2 为 0）。

Gemini 单次噪声：本设计不要求每臂重复检测。判定带宽用「均值差绝对值 &lt;3 则不确认该假说」。带宽是证伪规则，不是新的及格线。

### 3.4 成功标准（与 Q1 分开）

| 门 | 通过条件 | 不通过时 |
| --- | --- | --- |
| A 缺陷修复可保留 | 有运行中循环的测试：`generate_images` 被 await（或在它线程的 loop 上跑完）；日志不再 never awaited；flag=`0` 时 JPEG 与修复前字节级一致；失败有 `error_type` | 修法死锁、或 flag=0 仍改图 → 回退该修法 |
| B 对齐可保留 | R2：8mm 与 26mm 的 CA 函数输出与输入恒等；无饱和度乘子；8mm reason 里色差类计数下降 | 恒等后仍满篇色差 reason → P-CA-PHONE 证伪，B 的「为了消色差判词」理由不成立。恒等本身仍是旧有效像素对齐；**是否留在默认值由主代理写进门禁**。无论留否，都不得写成提分成功 |
| Q1 | 仅协议 C、合同集、某一**已在白名单**的臂：`mean(v3)-mean(R0)≥10`，且 `PASS_SCORE` 仍为 75，日志出现 `ALIGN_W5_E2E_PASS` | `ALIGN_W5_E2E_SHORTFALL`。禁止改及格线、禁止换模型、禁止加 R4/R5 进同一次编码来「再冲一次」 |
| 预算停止 | R0–R3 跑完即停，除非 R2 证伪后主代理**另开** R4 测量 | R4 大涨也不自动入库 |

预期（待验证推断，不是计划目标）：以 C1 与英短轮为据，R3 在 26mm 上更可能落在 gain 0～4，而不是 ≥10。8mm 上 R2 有可能抬预览分；该抬升相对的是「现行 2px CA 的 v3」，不是 Q1 的 v2 分母，除非同表给出 R0。

---

## 4. 候选项裁定建议

| ID | 允许编码？ | 理由 | 风险 |
| --- | --- | --- | --- |
| A | **允许**（与 D 绑在一次改动里） | 正确性缺陷。用户要求的「缺陷修复」。worker 已在跑循环；`asyncio.run(generate_images)` 失败后当没发生。账本 C-L0-INTENT：必须修。修法见 §1.1，禁止同一 loop 上死等。 | 若只修 await、默认仍是 `auto`，worker 会在未扫档时开始真调 `gpt-image-2`（默认 blend 0.12，与 C1 的 1.0 不是同一条件）。分数可升可降。所以 A 必须和 D 一起落地：默认关，扫档时显式打开。API 费用与供应商改图属于打开 flag 之后的事，不在默认路径。 |
| B | **允许，仅「近零恒等」这一档** | 与旧有效行为对齐且不触红线。旧调用点在 ≤14mm 的唯一写出是已禁止的 `saturation×1.02`；24mm 及以上旧 CA **本来就不改像素**。现行 8mm 为 2px 通道错位，Gemini 已点名。允许的实现：`_CA_INTENSITY=0` 或等价地让 `ca<0.35` 从而走已有的 `shift<1 → return arr`。保留 `focal_length_to_ca_strength` 表，供测试与以后主代理改裁。 | **与上一份可行性门禁冲突**：该门禁写「保留现行通道错位（本轮不改 shift 公式）」。也与 Q4「允许色差」的字面宽读冲突——宽读会要求留下可见错位。本建议把 Q4 读成「允许存在 CA 函数与焦距表」，有效像素对齐旧仓红线内残差（恒等）。主代理若维持旧句「不改 shift」，从白名单删 B，门禁仍可对 A+D 保持 `OPEN_PARTIAL`。另一风险：恒等后 8mm 分不升（P-CA-PHONE 证伪），则 B 只剩对齐价值，没有提分价值。中间档（例如把 2px 改成 1px、或 `_CA_INTENSITY` 改成 0.5 仍 `ceil` 出 1px）**不允许**，那是未证明的提分扫档。 |
| C | **不允许**（本轮不改默认常量） | 降低光学 0.32 / 噪声 1.55 / 频域倍数是提分希望。P-V3-OVERDRIVE 未证伪也未证实。ALIGN 账本里的光学假设约 0.18，与代码 0.32 不一致，但那条是参数假设，不是旧仓有效像素的测量。R4 可以在 R2 证伪后由主代理另开测量，测量改动不进入本次白名单。 | 若夹进 A/B 同一次改动，分数变化无法归因。降噪/降光学也可能被检成「更平、更 AI」。 |
| D | **允许**（作为 A 的默认值，不单独当提分） | 现状：配置默认 `auto`（有 generation key 就开），worker 却因 A 的缺陷永远 `return None`。默认改 `"0"` 使配置与现行 worker 像素一致，直到 async 修完且 R3 扫档。扫档与 C1 复现必须显式设 `ALIGN_LAYER0_IMG2IMG=1`。 | 依赖「默认 auto 即开启」的本地脚本会跳过 img2img。端测脚本已 `setdefault(..., "1")`，显式值仍生效。在 async 未修时把默认改回 `auto` 会恢复「名义开启、实际跳过」。 |
| E | **不允许**。标冲突 `C-PIPE-V2-HEMOSTASIS` | 生产切回 `s2-five-layer-2` 会改 `PIPELINE_VERSION` 与任务 `pipeline_version`，与 ALIGN 已锁「Pipeline：`s2-five-layer-3`」以及 `test_pipeline_version_is_s2_five_layer_3` 冲突。C-PHYS-TUNE 的「v2 可切回」不构成推翻该锁。R0 已能用 `algorithm="v2"` 做像素对照，无需改生产版本。即便均分从约 49 回到约 65，相对 v2 的 gain 为 0，Q1 仍失败。止血不是达标。 | 版本回退后，ALIGN 端测 `PASS pipeline_v3` 失败；后续 v3 消融失去生产对照语义。 |
| F | **禁止** | 换模型、改 `PASS_SCORE`、指纹几何（rotate/crop）或可见全局调色，都在硬锁 H-PASS / H-FP 与冲突账本 §C。即使得分上升也不编码。包含：改 `redo_policy.PASS_SCORE`、检测提示里的 75、`gemini` 模型名、`model_id="gpt-image-2"`、任何 hue/sat/几何刷分。 | 用及格线或换模型制造 `passed=true` 会直接破坏 Q10。 |

---

## 5. 门禁候选（主代理可直接抄进 feasibility-gate）

| 项 | 建议裁定 | 依据 |
| --- | --- | --- |
| 编码门禁 | **OPEN_PARTIAL** | 仅 A+D 与 B-近零。C、E、F 关闭 |
| Q1 可达 | **UNPROVEN** | C1 gain=1.00；英短最好 3.83；本消融未跑。OPEN 不等于已证明 +10 |
| A Layer0 循环 | 允许修 `_maybe_layer0_img2img` 的 await；失败要日志 | §1.1；worker 日志 ×11 |
| D 默认 | `ALIGN_LAYER0_IMG2IMG` 默认由 `auto` 改为 `0`，直到 R3 扫完由主代理另裁是否改回 | 与 A 绑定。扫档用环境变量显式 `=1`，不改回默认来「顺便开启」 |
| B 色差 | 允许有效 shift=0（`_CA_INTENSITY=0` 或等价早退）。禁止 `saturation×1.02`。不改焦距表。禁止中间档 | C-CA-BUG-GATE；Q7；F-REASON-CA。**推翻**上一门禁句「不改 shift 公式」才成立；主代理不推翻则删本行，A+D 仍 OPEN_PARTIAL |
| C 光学/噪声/频域 | 关闭。R4 不进本次 diff | P-V3-OVERDRIVE 未证 |
| E 生产 v2 | 关闭。冲突 `C-PIPE-V2-HEMOSTASIS` | `PIPELINE_VERSION` 保持 `s2-five-layer-3` |
| F 模型 / 及格线 / 指纹 | 禁止 | H-PASS、H-FP、Q10 |
| 测量 | 先协议 W 的 R1→R2，再协议 C 的 R3；Q1 只认合同集相对 R0 | §3 |
| 退出 | gain≥10 且真 Gemini → 才可谈 `ALIGN_W5_E2E_PASS` 与 Q12。否则 SHORTFALL，停止加码 | 用户要求；ALIGN Q12 |

---

## 6. 白名单（文件 / 函数）

主代理若采 `OPEN_PARTIAL`，编码范围只到下列符号。范围外的行即使为了「顺手提分」也不改。

1. `aojuai-main/backend/app/capabilities/realphotos/services/five_layer.py`  
   - `_maybe_layer0_img2img`：循环安全的 await（§1.1）。  
   - `run_five_layer`：仅 Layer0 调用与 async 传递。  
   - `_apply_chromatic_aberration` 与常量 `_CA_INTENSITY`：只为使默认强度下 `shift<1` 并返回原数组。  
   - 不改：`_LAYER0_OPTICAL_STRENGTH`、`_NOISE_INTENSITY`、`_L2_*`、`_L3_*`、`_AUTO_TIERS*`、`_LAYER0_LEGACY_PROMPTS`、`PIPELINE_VERSION`、`focal_length_to_ca_strength` 表、`_l1_l3_v2`。

2. `aojuai-main/backend/app/core/config.py`  
   - `ALIGN_LAYER0_IMG2IMG` 默认值 `"auto"` → `"0"`。  
   - 不改 `ALIGN_LAYER0_BLEND_ALPHA` 的默认空值（代码默认 blend 仍 0.12）。

3. 仅当选择「async 向上传递」时：  
   - `s1_processing.py` 的 `_five_layer_jpeg`：对 `run_five_layer` 加 `await`。  
   - 已有 `run_five_layer(...)` 的测试与 `scripts/*e2e*.py`：只加顶层 `asyncio.run` 或 `await`，不改预设焦距、不改 `score_fn`、不改 `PASS_SCORE` 断言。  
   - 若选择「它线程 `asyncio.run`」则 **不要** 改这些调用处。

4. `aojuai-main/backend/tests/capabilities/realphotos/test_s2_five_layer.py`  
   - 增加：运行中循环内 Layer0 不再 never awaited；flag `0` 不改像素；8mm 与 26mm 的 `_apply_chromatic_aberration` 与输入恒等。  
   - 保留现有 `focal_length_to_ca_strength` 表断言与 `PIPELINE_VERSION == s2-five-layer-3`。  
   - 不改 `test_s3_detection.py` 里 `PASS_SCORE == 75`。

不在白名单：`gemini_detector.py`、`redo_policy.py`、`detection_pass_score.py`、`supplier_clients.generate_images` 的模型名、任何指纹/几何/饱和度模块、`s1_processing` 里除 await 以外的行。

---

## 7. 明确禁止（即使消融显示能提分）

- 改 `PASS_SCORE` 或检测提示中的 75。
- 更换 `gpt-image-2` / Gemini 模型。
- rotate、crop、resize 回原尺寸、hue/sat 全局刷分、旧 CA 的 `saturation×1.02`。
- 平台矩阵、60%–80% 体积带、先频域。
- 把 `PIPELINE_VERSION` 或生产任务改成 `s2-five-layer-2`。
- 在本轮 diff 里改光学/噪声/频域默认倍数（R4）。
- 把「希望提分」或 R2/R3 的单臂上涨写成 Q1 已达成。

---

## 8. 留给主代理的冲突（不在本文私自调和）

| ID | 冲突 | 本文建议 | 主代理可推翻的方式 |
| --- | --- | --- | --- |
| C-PRIOR-GATE-CA | 2026-11-14 可行性门禁写「不改 shift 公式、保留通道错位」；本候选要求有效 shift=0 | 采 B，并在新门禁写明推翻该句 | 删 B；A+D 仍为 OPEN_PARTIAL |
| C-Q4-VS-CA-GATE | Q4「允许色差」vs 旧有效像素为恒等（≤14mm 的饱和度已禁） | 保留焦距表与函数，有效像素恒等 | 书面要求保留可见错位 → B 关闭，回到「不改 shift」 |
| C-PIPE-V2-HEMOSTASIS | 生产止血想切 v2 vs 已锁 `s2-five-layer-3` | E 关闭；对照只用 `algorithm="v2"` | 只有管理员书面改裁 Pipeline 后才能重开 E |
| C-Q1-STILL-OPEN | 用户要求冲 Q1≥10；已测最好 3.83 / 1.00 | 门禁 OPEN 只修缺陷与对齐；Q1 维持 UNPROVEN | 管理员改裁 Q1、或批准换模型（那是 F，本候选禁止） |

## 9. 假设

| ID | 假设 | 若假设错 |
| --- | --- | --- |
| A-CALLSITE-INTENSITY | 旧有效 CA 以 `physicalizeImage` 的 `intensity * 0.5` 为准，而不是 `applyChromaticAberration` 单独被默认 `intensity=1` 调用 | 单独以函数默认 1.0 计算时，24mm 与 35mm 也会进入「丢弃 composite + sat×1.02」。红线内残差仍是恒等，B 的结论不变 |
| A-LEDGER-DB | 均分 65.5 / 49.3 与任务 reason 以 DET 账本为准；本子代理未重查库 | 若库表与账本不符，P-CA-PHONE 的「已点名」线索要降级，R2 仍可照跑 |
| A-GEMINI-NOISE | 单次检测均值差绝对值 &lt;3 视为不确认假说 | 主代理可要求每臂重复 2 次再收紧带宽；那是加测，不是放宽 Q1 |
