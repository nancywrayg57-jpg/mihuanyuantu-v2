# FIVE-LAYER-LEGACY-ALIGN · 现行 v2 五层管线审计（子代理）

日期：2026-11-14  
角色：现行管线只读审计。未改代码，未改 PASS_SCORE，未调用 Gemini，未调用供应商。  
代码根：`aojuai-main/backend/app/capabilities/realphotos/services/five_layer.py`（1440 行，`PIPELINE_VERSION = "s2-five-layer-3"`）。  
原则：矛盾并列表述。本报告不把账本、对照笔记、可行性草案或端测叙事收成单一结论。

## 0. 读过的证据

| 材料 | 用途 |
| --- | --- |
| `five_layer.py` | 常量、公式、层序、blend、字节下限、色差 |
| `supplier_clients.py` | `/images/edits` 实际字段 |
| `gemini_detector.py`、`redo_policy.py` | 五维键、`PASS_SCORE=75` |
| `camera_specs.py` | FocalPlane 库与查找 |
| `scripts/five_layer_legacy_align_e2e.py` | 日志里的 MAD / 分数是怎么来的 |
| `scripts/_align_blend_scan.py` | α 扫档脚本（仓库内无对应扫档日志文件） |
| 账本 `FIVE-LAYER-LEGACY-ALIGN-constraint-ledger.md` | Q1–Q12 与参数假设 |
| `FIVE-LAYER-LEGACY-ALIGN-compare-notes.md` | 与账本冲突的旧表述 |
| `FIVE-LAYER-LEGACY-ALIGN-research-conflicts-2026-11-14.md` | 主代理冲突账本，只引用不覆盖 |
| `FIVE-LAYER-LEGACY-ALIGN-feasibility-draft-2026-11-14.md` | 交叉，不代草案下判定 |
| `/tmp/five-layer-legacy-align-e2e.log` | `ts=2026-11-13T17:43:48Z`，n=6，gain=2.50 |
| `FIVE-LAYER-LEGACY-ALIGN-e2e-layer0-2026-11-13.log` | `ts=2026-11-13T17:05:04Z`，n=12，gain=3.83 |
| 只读复算 | 用当前 `five_layer` 对 `product_01.jpg` 做分阶段 MAD（seed=20261113，无 img2img） |
| clone `imagePhysicalizer.ts` / `aiImageProcessor.ts` / `frequencyProcessor.ts` | 仅用于给「账本说的 legacy 公式」标出现行偏差；不把 clone 升成新裁决 |

硬红线在本报告中的地位：不改 `PASS_SCORE`；不迁 Node；层序 Layer0→L1→L2→L3→L4→L5；禁几何与可见调色；禁糊图刷分；字节下限仍硬；未 `ALIGN_W5_E2E_PASS` 不开 PR。下面的补丁都停在「候选」，不授权编码。

## 1. 硬约束在现行代码里的落点

| 红线 | 现行事实 | 行号 |
| --- | --- | --- |
| 不改 PASS_SCORE | `redo_policy.PASS_SCORE = 75`。检测提示把 75 写进 prompt。端测 `must(int(PASS_SCORE) == 75)` | `redo_policy.py` 5；`gemini_detector.py` 17–25；e2e 160–163 |
| 不迁 Node | 像素路径是 NumPy/PIL + exiftool。无 sharp 运行时 | `five_layer.py` 全文 |
| 层序 | 见第 3 节。模块顶部 docstring 仍写「L1→L2→L3→L4→L5」，没写 Layer0 | `five_layer.py` 1–4 vs 498–533、729–787 |
| 禁几何 / 可见调色 | 无 rotate/crop/hue。输出宽高相对原图锁定。色差末尾仍有饱和度 ×1.02。B 通道缩小时用 0 填充边 | 511–518、456–457；197–201；194–196 |
| 禁糊图刷分 | 锐化注释写明删了预模糊，因为旧硬顶会被打破。Q11 改为只观测之后，预模糊没有加回。现行没有以模糊追分的分支 | 790–799 |
| 字节下限 | JPEG 源：`len(source)`。非 JPEG：同像素 quality-100 JPEG 的长度。不垫字节。不达下限抛 `OUTPUT_CONSTRAINT_UNSATISFIED` | 77–89、417–437 |
| 未 PASS 不开 PR | 端测 gain&lt;10 写 `ALIGN_W5_E2E_SHORTFALL` 并 `return 4` | e2e 253–266 |
| 60%–80% / 平台 resize | 现行编码不走该带。`subsampling=0`（4:4:4）使文件偏大 | 803–811 |

`FIDELITY_MAD_OBSERVE_ONLY = True` 在全后端只有定义、没有读取点。端测本身不因 MAD fail。这不等于内部排序完全不看 MAD，见第 6 节。

## 2. 常量与公式（`five_layer.py`）

### 2.1 常量

| 符号 | 值 | 行 |
| --- | --- | --- |
| `PIPELINE_VERSION` | `s2-five-layer-3` | 23 |
| `PIPELINE_VERSION_BASELINE` | `s2-five-layer-2` | 24 |
| `ENCODE_PROFILE` | `s2-ecommerce-1` | 25 |
| `_QUALITIES` | 85, 88, 90, 93, 96, 98, 100 | 26 |
| `FIDELITY_MAD_MAX` | 3.5 | 28 |
| `FIDELITY_MAD_HARD_MAX` | 6.0 | 29 |
| `FIDELITY_MAD_OBSERVE_ONLY` | `True`（死常量） | 30 |
| `_L2_SIGMA` | 0.036 | 32 |
| `_L2_RADIUS` | 0.35（仅扰动半径大于此的 2D 频率） | 33 |
| `_L2_1D_PHASE` | 0.0045 | 34 |
| `_L2_1D_LOW_CUT` | 0.05 | 35 |
| `_L2_1D_HIGH_CUT` | 0.45 | 36 |
| `_L3_SPARSE_MAX` | 2500 | 37 |
| `_L3_SPECTRAL_SIGMA` | 0.012，且只动半径 &gt; 0.60 的频率 | 38、722–724 |
| `_VIGNETTE_LEGACY_SCALE` | 0.85 | 40 |
| `_SHARPEN_RADIUS` / `_SHARPEN_PERCENT` | 0.6 / 48，`threshold=2` | 41–42、794–799 |
| `_MID_JPEG_QUALITY` | 85 | 43 |
| `_MAD_PREFER_TARGET` | **3.0**（账本写 prefer 3.5） | 44 |
| `_ISO_PROCESS_FLOOR` | 400 | 45 |
| `_NOISE_INTENSITY` | 1.55 | 46 |
| `_FIXED_MODE_SCALE` | 0.85 | 47 |
| `_LAYER0_OPTICAL_STRENGTH` | **0.32**（账本写 ≈0.18） | 48 |
| `_LAYER0_IMG2IMG_STRENGTH` | 0.12 | 49 |
| `_CA_INTENSITY` | 1.15 | 50 |
| `_SMOOTH_LAP_VAR_THR` | 12.0 | 51 |
| `_AUTO_TIERS_LIGHT` | `(1.00, 0.90, 0.75, 0.85)`、`(1.20, 1.10, 0.90, 1.00)` | 52–55 |
| `_AUTO_TIERS_STRONG` | `(1.25, 1.15, 1.00, 1.10)`、`(1.45, 1.35, 1.10, 1.25)` | 56–59 |
| `_AUTO_TIERS` | 赋值为 STRONG，**挑选函数不读它** | 60 vs 361–362 |
| `_RERANK_PACKS` | 三组全是 `2d`：`(0.90,0.85,0.55,0.65)`、`(1.30,1.25,1.00,1.10)`、`(1.10,1.55,0.70,0.95)` | 61–65 |

元组顺序是 `(noise_mult, vignette_mult, l2_mult, sparse_mult)`。

### 2.2 公式

L1 噪声（101–110）：

```text
iso' = clamp(parse(iso), 50, 6400) 后再 max(iso', 400)
sigma = clamp(0.5 * sqrt(iso'/100) * 1.55, 0.85, 2.20)
```

端测预设 ISO 字符串是 `"400"`，地板不改变该值，σ=1.55，封顶不生效。ISO 6400 时未封顶为 6.2，会被压到 2.20。

暗角表（113–133）与旧 `apertureToVignettingStrength` 数值相同，再乘 0.85：

| f | 表内 raw | ×0.85 |
| --- | --- | --- |
| ≤1.4 | 0.35 | 0.2975 |
| ≤2.0 | 0.28 | 0.238 |
| ≤2.8 | 0.22 | 0.187 |
| ≤4.0 | 0.16 | 0.136 |
| ≤5.6 | 0.10 | 0.085 |
| ≤8.0 | 0.06 | 0.051 |
| 更大 | 0.04 | 0.034 |

余弦四次方（648–660），与旧 `imagePhysicalizer.ts` 188–189 同一式：

```text
r = hypot(x-cx, y-cy) / hypot(cx, cy)
cos4 = cos(atan(r * 1.5)) ** 4
factor = 1 - strength * (1 - cos4)
```

角点 r=1 时 `1-cos4 ≈ 0.9047`。端测光圈 `f/1.8` 落在 ≤2.0 档。只读复算：

| 乘数 | strength | 角点压暗 |
| --- | --- | --- |
| 表×0.85，不再乘 | 0.238 | 21.6% |
| 再乘固定档 0.85（2d/1d/hybrid 证据路径） | 0.202 | 18.3% |
| auto 轻档实际会选中的 1.10 | 0.262 | 23.7% |
| rerank 暗角档 1.55 | 0.369 | 33.4% |

旧表在 f/1.4、intensity=1 时 strength=0.35，角点压暗约 31.7%。rerank 的 1.55 在 f/1.8 上略超过这一档。

焦距→色差表（136–155）与旧函数相同：≤14→2.0，≤24→1.5，≤35→1.0，≤50→0.7，≤85→0.5，≤135→0.4，否则 0.3。

现行位移（181–183）：

```text
ca = table(focal) * intensity * 1.15
shift = ceil(ca * 0.55)  若 ca >= 0.35，否则 0
```

端测 26mm：table=1.0，ca=1.15，shift=1。实现是整通道双三次缩放（R 放大后中心裁，B 缩小后贴回），不是亚像素平移。B 的空边用 `Image.new("L", ..., color=0)`，即黑边（194–196）。随后饱和度（197–201）：

```text
out = mean(RGB) + (RGB - mean) * 1.02
```

旧调用链是另一套数，此处只作对照、不当成新裁决：`physicalizeImage` 在焦距≤50 时才调用色差，且传入 `intensity * 0.5`；函数内 `shift = round(caStrength * 0.5)`。26mm、外层 intensity=1 时，该 round 结果为 0，函数直接返回，复合通道被丢掉之前就已经 return。旧源里复合结果被丢弃、只剩 `modulate({saturation:1.02})` 的事实，冲突账本记为 F-CA-BUG。现行代码把「缩放通道」做实了，并且保留 ×1.02。

L1 噪声混合（764–778）：`0.65*细高斯 + 0.35*3×3 盒模糊后的粗高斯`；像素 &lt; 64 再 ×1.5。暗部 ×1.5 与旧噪声循环一致。粗细混合与盒模糊不在账本参数行里。

显式 `2d`/`1d`/`hybrid` 且四个乘数都是 1 时，四个乘数被改成 0.85（752–759）。auto / rerank 传入的乘数不是全 1，不走这道阻尼。

L2 1D（680–705）：隔行、Rec.601 亮度、低频 5% 与高频 45% 截止、只改相位。相位幅度是 `0.0045 * phase_mult`，旧默认 `perturbStrength=0.004`（`frequencyProcessor.ts` 180，`imagePhysicalizer.ts` 368）。截止与隔行和旧 1D 一致。现行多了一路 2D 乘性幅度噪声（663–677），旧 physicalizer 入口的频域是 1D 相位。

L3（708–726）：稀疏点数 `min(2500 * sparse_mult, H*W)`，±1 加到抽中的像素。另有极弱 2D 频谱。无 hue、无旋转、无裁切。

光学 Layer0（158–174）：5×5 盒差做局部反差，`out += strength * detail`，再加 `N(0, 0.55*strength)`。`strength=0.32`。

Layer0 img2img（204–278）：

- 环境变量默认 `"auto"`。只有 `0/false/off/no` 才关。有 generation secret 就调用。账本 ASSUMPTION 的措辞是 `ALIGN_LAYER0_IMG2IMG=1` 才改走供应商。
- 模型固定 `gpt-image-2`。`preset` 被丢弃（224）。
- 英文短提示，末尾拼 `Strength 0.12`。
- 参考图经 `prepare_reference_jpeg(..., max_edge=1280, quality=85)`。
- 返回图若宽高不同，LANCZOS 拉回原宽高，再 `Image.blend(原图, 编辑, α)`。α 默认 0.12，可被 `ALIGN_LAYER0_BLEND_ALPHA` 覆盖，并夹到 [0,1]。
- 混合结果以 JPEG quality=95、`subsampling=0` 写回。
- 任意异常、缺 key、空图：`return None`。调用方不记日志。

`/images/edits` 实际 POST 字段只有 `model`、`prompt`、`n`、`size` 和文件 `image`（`supplier_clients.py` 128–132）。没有 strength，没有 negative_prompt。`seed` 明确不发送（116–117）。

### 2.3 调用顺序（评分路径 `algorithm=v3` 且 `freq_mode=auto`）

1. 可选 img2img。成功则 `work_source` 换成混合 JPEG（498–505）。
2. `baseline = decode(work_source)`（506）。宽高若与原图不同，LANCZOS 拉回（511–518）。
3. 拉普拉斯 &lt; 12 用 STRONG 档，否则 LIGHT 档，在 `2d`/`1d` 间按 rank 选一张（339–402、555–563）。
4. `_l1_l3`：光学 Layer0 → 噪声 → 暗角 → 色差 → L2 → L3 → clip（760–787）。
5. UnsharpMask（459–460、790–799）。
6. 中间 JPEG quality=85，解码回 RGB。同一次中间文件还跑了 exiftool，返回值丢掉（419–423）。
7. 按 `_QUALITIES` 终编码，exiftool 写回，宽高与字节下限都满足才入选。排序键是「MAD 是否 ≤6」再按 MAD 升序。MAD 的参照是步骤 2 的 `baseline`，不是处理前的浮点缓冲（424–440）。
8. 若传入 `score_fn`：上面的 auto 结果再加 3 个 rerank 包，各调一次检测，只保留 `total_score` 最大者（576–620）。五维 dict 被丢掉。

`v2` 不走 img2img、不走暗角/色差/锐化，中间 JPEG 用 90，质量列表从 90 起（520–532）。

`freq_mode` 为 `2d`/`1d`/`hybrid` 时不做 img2img（501–502）。端测双路径因此测到的是「无供应商」像素链。

字节下限的 `source` 参数在生产路径上仍是原始上传（524、547），不是 `work_source`。这一点和扫档脚本不同，见第 6 节。

## 3. 账本参数假设对照

账本「参数假设」原文（constraint-ledger 42–51 行）是对照基准。状态只用：已实现 / 弱实现 / 错误实现 / 账本未锁。

| 假设 | 状态 | 依据 |
| --- | --- | --- |
| 暗角 = legacy cos^4 × scale≈0.85 | 公式已实现；「弱」是否成立与笔记冲突 | 表与 cos^4 同旧源。scale=0.85 在 40、133 行。端测 f/1.8 角点压暗 18%–33%，取决于乘数。compare-notes 写「角点压暗 ≤~8%」。两份文档冲突，见第 4 节 |
| 色差 = 焦距表 + 红/蓝亚像素错位 | 错误实现 | 表在。位移是 `ceil` 整像素保底，注释写明是为了避开 banker's round 导致的 0（182–183）。B 边为 0 不是亚像素。另有账本没写的 ×1.15。26mm 旧整数公式会得到 shift=0，现行得到 1 |
| 色差允许（Q4 复裁）且禁可见调色（Q7） | 两半都在代码里，互相顶着 | 通道缩放是色差方向；×1.02 是全局饱和度。冲突账本 C-V2-CA-SAT 已列。本审计不删、不留作最终裁定 |
| Layer0 光学 strength≈0.18 | 错误实现（偏强） | 常量 0.32（48）。只读复算：product_01 上 0.32 的孤立 MAD=1.51，0.18 为 0.87 |
| 可选 img2img strength≈0.12 | 弱实现 | 常量 0.12 用作 blend α，并写进提示句子。API 无 strength 字段。`preset` 不参与提示。失败变 `None` |
| 账本 C-LAYER0：「改走」供应商 | 与代码叠加，措辞未调和 | img2img 成功后 `_l1_l3` 仍 `layer0=True`，光学 0.32 再跑一遍（760–762）。「改走」与「叠加」本报告不合并成一种语义 |
| L1：地板 400 + `0.5*√(ISO/100)×intensity` | 骨架已实现；intensity 与封顶未在账本锁死 | 地板 400、系数 0.5 在。intensity 被写成 1.55。封顶 [0.85, 2.20]。compare-notes 写封顶 2.40，与代码又不一致。端测 ISO=400，封顶与地板都不改变 σ |
| L2/L3 加强；auto 选优；hybrid 留证 | 弱实现 | 1D 相位 0.0045、稀疏上限 2500、另有 2D。auto 会选。hybrid 只在显式 `freq_mode` 和端测首张留证里出现，rerank 三包全是 2d。证据路径被 0.85 阻尼且不含 img2img，与评分路径不是同一工作点 |
| MAD 只观测，prefer 3.5 / 参考硬顶 6.0，不淘汰参数组、不 fail 端测 | 端测不 fail；内部分数仍用 MAD | 硬顶 6.0 只影响编码排序的优先组（438），不抛错。`_pick_v3_pixels` 的 rank 含 `abs(mad - 3.0)*0.02`（382–386），目标是 3.0 不是 3.5。权重小，噪声乘数更大的档几乎总赢。死常量 `FIDELITY_MAD_OBSERVE_ONLY` 没有把它关掉 |
| Pipeline `s2-five-layer-3` | 已实现 | 23 行。端测断言同一字符串 |
| 层序 Layer0 → L1 → … → L5 | 代码顺序符合账本；文件头 docstring 仍是旧的 L1 起 | 见 2.3。频域在噪声之后，没有把旧「入口先频域」搬回来 |
| Q10 真 Gemini | 端测路径是真 `detect_jpeg`。v3 落盘分数不是五维报告 | e2e 107–121、216–218 |
| Q2 样本不改 | 端测读取 `测试用/图片/product_*.jpg`。默认 n=12，不是 50 | e2e 18–22、149–152 |
| Q9 FocalPlane + 空值跳过 | 本预设能查到 iPhone 15 Pro | `camera_specs.py` 306–313；`five_layer.py` 987–1008。查找还有子串误配，见第 6 节。端测预设用的是全名，不踩中 |

账本没锁、代码里有的加项（不升格为违约，也不当成已批准的提分手段）：粗细噪声混合、`_CA_INTENSITY=1.15`、`_FIXED_MODE_SCALE`、中间 JPEG 85 再终编码、锐化 percent=48、编码 `subsampling=0`。旧 JPEG 重压写的是 quality 默认 88 且 `chromaSubsampling: '4:2:0'`（`imagePhysicalizer.ts` 273–286）。可行性草案 P3 想靠拢 4:2:0。账本只写了 Q5「允许弱锐化 + 中间 JPEG」，没有锁色度抽样。

## 4. 必须标出的文档矛盾（不调和）

### 4.1 compare-notes 仍写 Q4 禁色差

`FIVE-LAYER-LEGACY-ALIGN-compare-notes.md` 第 12 行，imagePhysicalizer 色差一行的「v3 获准动作」是 **「禁止（Q4）」**。

账本第 13 行：Q4 = **允许色差**（复裁放开）。

冲突账本 C-NOTES-Q4 已写「以账本为准；notes 待修订」。本审计确认 notes 文件至今仍是「禁止（Q4）」。代码走的是允许色差（通道缩放 + ×1.02），不是 notes 的禁止。  
本报告不把 notes 改写成账本，也不把代码回退到禁止。两份文档同时有效于各自文件，冲突保持打开。

同文件还有这些过时或互相顶着的句子，一并列出：

| 位置 | notes 原文方向 | 账本 / 代码 |
| --- | --- | --- |
| 第 10 行 | 噪声加强但仍封顶 2.40 | 代码封顶 2.20。账本没写 2.40 也没写 2.20 |
| 第 11 行 | 弱暗角，角点 ≤~8% | 账本只锁 cos^4×0.85。f/1.8 复算角点 18%–33% |
| 第 12 行 | 色差禁止 | 账本允许 |
| 第 19 行 | Q8 已放开，与第 12 行的 Q4 禁止写在同一张表里 | notes 内部也不一致：Q8 单元格已改，Q4 单元格没改 |
| 第 23 行 | 必须 L1→L5 | 账本在 L1 前加了可选 Layer0。代码有 Layer0 |

### 4.2 与可行性草案并列、但不合并的说法

| 议题 | 草案 | 现行代码 / 本审计复算 | 处置 |
| --- | --- | --- | --- |
| 色差 | 「真实 R/B 错位 + 仍留 ×1.02，应去掉饱和度尾巴」 | ×1.02 在，孤立贡献 MAD≈0.074。另外还有整像素 `ceil`、×1.15、B 黑边。26mm 旧整数 shift 会是 0 | 草案没覆盖后三项。去掉 ×1.02 仍是合规候选，不因此等于 Q1 杠杆 |
| 暗角 | 「×0.85，获准弱化」 | 公式与 scale 在。测到的角点不是 8% | 不把「弱化」改写成「已是弱观感」 |
| 噪声 | 「已偏强，非主缺口」 | product_01 上噪声相对光学之后只再增加约 0.25 MAD | 与「非主缺口」同向。intensity=1.55 仍属未锁加码 |
| Layer0 失败 | 「返回 None 则跳过，可接受」 | 代码如此，且端测头仍印 `layer0_img2img=on` | 与冲突账本 C-FAIL-SILENT「不得静默成功冒充完成」并列。不选择哪一句作废 |
| Q1 | `UNPROVEN` | 本审计维持未证明。不升格成「已证明不可达」，也不升格成「补提示词即 +10」 | 见第 8 节 |
| P4 默认 α=1 仅作 raw edit | 草案表内句子 | 账本默认 α=0.12。α=1 就是 n=12 那种整图重写工作点（MAD 均值 53.8） | 扫档协议与生产默认不是同一件事。本报告不把生产默认改到 1 |

### 4.3 端测叙事与日志数字

账本 76 行把 `/tmp` 这次 n=6、gain=2.50 称为「blend α=0.12 重跑」。日志头没有打印 α，也没有逐张打印 img2img 是否成功。MAD 分布见第 5 节：它不像「六张都做了 α=0.12」。本报告同时保留账本的命名和日志的 MAD，不把其中一份改成另一份。

α 扫档「最好约 +2.25」只出现在账本 77 行。仓库里有 `_align_blend_scan.py`，没有找到该次 stdout 的落盘文件。本审计没有重跑扫档，不把 +2.25 复算出来，也不否定账本那一行的存在。

## 5. gain≈4 的卡点（五维）

### 5.1 先写证据洞

两份日志里每一行 `gemini_v3` 都是：

```text
noise=None dof=None light=None color=None overall=None reason='rerank_pick'
```

原因在端测脚本，不在检测器：

- `run_five_layer` 在比较候选时只用 `report["total_score"]`，胜出报告的其余字段丢弃（`five_layer.py` 604–620）。
- e2e 若拿到 `detector_score`，就地造一个只有总分的 dict，`reason='rerank_pick'`（e2e 216–218）。
- 检测器本身要求五个整数键（`gemini_detector.py` 15–21）。v2 行能打出五维，是因为 v2 不走 rerank，e2e 对 v2 JPEG 又调用了一次完整 `detect_jpeg`。

因此 **不存在 v3 的 noise / depthOfField / lighting / colorRealism / overallRealism 增量**。下面不允许把 +3.83 分配进某一个 v3 维度。能用的只有：v2 五维剖面、两边的总分、以及像素 MAD。

`total_score` 按提示词「不要写成五维平均」（`gemini_detector.py` 21）。即使将来留下五维，也不能用五维均值代替总分。

### 5.2 n=12 整图编辑（17:05Z）总分

`mean_v2=63.00`，`mean_v3=66.83`，`gain=3.83`。复算 12 张 v2 总分之和 756，v3 之和 802，差 46，46/12=3.833。与日志一致。

v2 五维均值（仅 baseline，n=12）：

| 维 | 均值 | 备注 |
| --- | --- | --- |
| noise | 66.17 | 12 张里多在 65–72 |
| colorRealism | 64.00 | |
| lighting | 61.58 | 低尾：product_11=45，product_08=50 |
| overallRealism | 61.25 | 低尾：product_11=40，product_08=48 |
| depthOfField | 59.42 | 五维里最低。低尾：product_11=40，product_08=45 |
| total_score | 63.00 | 独立字段，不是上表平均 |

逐张总分（v2 → v3，delta）：

| 样本 | v2 总分 | v3 总分 | delta | v3 MAD |
| --- | --- | --- | --- | --- |
| product_01 | 68 | 71 | +3 | 50.081 |
| product_02 | 62 | 68 | +6 | 59.396 |
| product_03 | 63 | 68 | +5 | 48.272 |
| product_04 | 67 | 69 | +2 | 48.642 |
| product_05 | 66 | 72 | +6 | 45.007 |
| product_06 | 65 | 68 | +3 | 41.916 |
| product_07 | 67 | 65 | −2 | 71.553 |
| product_08 | 49 | 70 | +21 | 42.989 |
| product_09 | 70 | 67 | −3 | 75.779 |
| product_10 | 70 | 68 | −2 | 43.812 |
| product_11 | 45 | 58 | +13 | 52.741 |
| product_12 | 64 | 58 | −6 | 65.374 |

MAD 之和 645.562，均值 **53.80**。12 张全部 `passed=False`。v3 最高 72，离 75 还有 3 分。Q1 要的是均值 +10，不是单张过线；两件事都没发生：均值只到 66.83（还差 6.17 才到 +10，还差 8.17 才到 75）。

delta 的结构：+21 与 +13 落在 v2 最差的两张（49 与 45），这两张的 v2 低维是 dof / light / overall，不是 noise。已经在 67–70 的四张里有三张为负（07、09、10），product_12 为 −6。12 张里 4 张为负。均值 +3.83 是「两张大救援 + 若干小正 + 四张回落」，不是全体上移。

### 5.3 无 img2img 的 MAD≈29 是暗角，不是频域

端测双路径只跑在 product_01，且 `freq_mode` 不是 auto，因此不调用 img2img：

```text
dual_path mad_2d=28.928 mad_1d=28.935 mad_hybrid=28.925
```

三路几乎相同，说明 1D/2D/hybrid 的差异不是这 29 的来源。

只读复算（当前代码，product_01，800×800，seed=20261113，ISO 400，f/1.8，26mm，固定档乘数 0.85，无 img2img）相对原图的累计 MAD：

| 阶段 | MAD |
| --- | --- |
| 光学 0.32 | 1.509 |
| +噪声 ×0.85 | 1.761 |
| +暗角 ×0.85 | **26.862** |
| +色差与 ×1.02 | 28.300 |
| +L2 2D ×0.85 | 28.310 |
| +L3 | 28.321 |
| +UnsharpMask | 29.092 |
| 终编码 q=88 | **28.928** |

q=88 的 28.928 与日志 `mad_2d` 逐位相同。该张双路径选中的就是这条质量档（字节 184761，日志 185211，差额与事后 EXIF 同量级；EXIF 不改像素，故 MAD 能对上）。

孤立项，仍是 product_01：暗角 strength=0.238 的 MAD=31.17；色差+饱和度=2.45；光学 0.32=1.51；锐化=0.73。色差相对暗角之后的增量约 3.08，其中 ×1.02 相对通道缩放只再增加 0.074。B 黑边约占像素 0.50%，边上 B 通道均值为 0，边对原图的 MAD=114，内部 MAD=27.86。黑边很刺，但面积小，不是 29 的主体。

结论限定在这张图、这条无 img2img 路径：**MAD≈29 的主体是 f/1.8 暗角乘子，大约 27 点；噪声、频域、稀疏、锐化、色差都是个位数或更小。** 账本允许弱暗角，公式也按 0.85 做了。测到的结果是全画面乘性压暗，均值绝对差约 27。这解释了「把 L1–L3 加强」为什么搬不动 10 分：评分路径上的包，主要差别也是暗角乘数 0.85–1.55 和噪声乘数，检测器若不对这种全局变暗给分，rerank 就没有 10 分的跨度。这是机制说明，不是 v3 lighting 维度的实测（该维度缺失）。

### 5.4 样本拉普拉斯：STRONG 档在这 12 张上没有打开

阈值 12。12 张原图的拉普拉斯方差从 182.80（product_09）到 4024.68（product_03），全部 `smooth=False`。auto 因此只用 LIGHT 两档。rank 偏向更高的 noise/vignette 乘数和 2d，实际胜出的 auto 包是 `2d (1.20, 1.10, 0.90, 1.00)`，再与三个 rerank 包比 Gemini 总分。`_AUTO_TIERS_STRONG` 与死别名 `_AUTO_TIERS` 不参与这批样本。

### 5.5 整图编辑把 MAD 从约 29 抬到约 54，总分没有跟着抬 10 分

n=12 的 v3 MAD 全部高于双路径本底，均值 53.80。多出来的二十余分是供应商整图与原图的差，再叠上同一套暗角链。提示词写了 “Preserve exact composition … and colors”，合同里没有 strength。MAD 50 说明这句英文没有把像素留住。

同一批里，MAD 最高的不是涨分最多的：product_09 MAD 75.8、delta −3；product_07 MAD 71.6、delta −2；product_12 MAD 65.4、delta −6。涨分最多的 product_08（+21）MAD 只有 43.0。不存在「越改像素越提分」的单调关系。

### 5.6 n=6 日志（17:43Z）不能单独证明 α=0.12

gain=2.50，`mean_v2=68.83`，`mean_v3=71.33`。逐张 v3 MAD：

| 样本 | mad_v3 | 与 n=12 同名 MAD | delta |
| --- | --- | --- | --- |
| product_01 | 52.679 | 50.081 | +4 |
| product_02 | 28.831 | 59.396 | +6 |
| product_03 | 25.498 | 48.272 | +1 |
| product_04 | 43.152 | 48.642 | −2 |
| product_05 | 29.356 | 45.007 | 0 |
| product_06 | 27.324 | 41.916 | +6 |

28 附近的四张（02、03、05、06）落在「无 img2img、暗角主导」带，与 product_01 双路径 28.93 同带。52.7 与 43.2 仍在整图重写带。

若六张都是 α=0.12：混合本身大约只贡献 `0.12 × 编辑差`，再叠加约 27 点的暗角本底，六张应挤在三十出头，不应留下 52 的整图峰。日志不是这个形状。

代码允许的另一形状是：异常被吃掉后该张退回原图，只跑光学+暗角，MAD≈28；没失败的张仍是高 α 或 α 未生效的整图。端测不打印成功与否，所以这只是与代码控制流相容的读法，不是已证实的逐张结论。

还有一个独立的混淆，即使 α 真是 0.12 也不能用 gain 从 3.83 降到 2.50 来证明「混合更差」：

- n=12 前六张的 v2 总分均值是 65.17（68+62+63+67+66+65）/6。
- 同一六张在 38 分钟后的 n=6 日志里，v2 均值是 68.83。v2 路径不含 img2img。逐张总分变化：0、0、+8、+5、+6、+3，均值 **+3.67**。
- 这六张的 v3 均值从 69.33 变为 71.33，只高了 2.00。
- gain 从这六张上的 4.17 变成 2.50，缩掉的 1.67 分等于「v2 检测漂移 3.67 − v3 漂移 2.00」。

冻结的 v2 管线在 temperature=0 的 Gemini 上，同六张平均漂了 3.67 分，与整次 n=12 的 gain 3.83 同一量级。+3.83 没有干净地大于检测器重测噪声。

n=6 还删掉了 product_07–12，其中既有 +21、+13，也有 −6、−3、−2。样本截断与 α、与检测漂移绑在同一次比较里。

### 5.7 五维各自能说什么、不能说什么

1. **noise**  
   v2 均值已经 66.17，是五维里最高的一档，离 75 的空间小于 dof。本地噪声在 product_01 上只贡献约 0.25 MAD。供应商提示要求颗粒，但合同把整图换掉。没有 v3 的 noise 分。不能说卡点「就是噪声分不够」，也不能说「再加 σ 就能 +10」。

2. **depthOfField**  
   v2 均值 59.42，是五维里最低的。两张大涨分的 v2 低分恰好落在 dof/light/overall，而不是 noise。端测预设是 iPhone 15 Pro，旧 phone 提示写的是计算摄影、暗部彩色噪点、过锐白边，不是单反虚化。现行提示是通用英文，且 `_ = preset`（224 行），设备类别没有进入 Layer0。这是未测的提示合同缺口，不是已经测到的 dof 增量。补上之后是否抬 dof，没有数据。

3. **lighting**  
   v2 均值 61.58。本地唯一的大光度杠杆是暗角，MAD≈27，角点 18%–33%。n=12 总分只动了 3.83，且四张为负。与「检测器不会按暗角 MAD 线性给 lighting 分」相容，但 v3 lighting 没被记下，所以停在相容，不写成已测维度归因。

4. **colorRealism**  
   v2 均值 64.00。×1.02 的光度只有 0.07 MAD，删掉它不会解释 6 分缺口，但它仍是全局色度操作，和「禁可见调色」顶着。整图编辑 MAD 50 必然包含颜色漂移，提示里的 “preserve colors” 没有在像素上成立。没有 v3 color 分。

5. **overallRealism**  
   v2 均值 61.25。大涨分发生在 overall 已经很差的 48 与 40 上；overall 已经不低的样本会出现总分下降。均值 66.83 仍低于通过线 75。rerank 已经在四个包里取了最高总分，取完仍是 +3.83。包与包之间共享同一次 img2img（若成功），差别主要是暗角/噪声乘数。这个选择集里没有出现 +10。

参考图缩边：`max_edge=1280`。n=12 里只有 product_05（1600）和 product_08（1440×1920）会缩小参考图。+21 的 product_08 同时是「v2 最差」和「参考图被缩小」。+13 的 product_11 是 800 边、不缩小。缩边不是 delta 符号的充分条件。

## 6. 隐性缺陷

下列都是现行代码行为。严重度是审计分类，不是修复授权。

### 6.1 blend / img2img JPEG 被当成后续像素源

`run_five_layer` 498–506：img2img 成功后 `baseline` 是混合 JPEG 的解码，不是客户原图。

后果：

- 拉普拉斯分档、auto 的 MAD 排序、终编码质量选择，参照的都是已经漂过的图。质量循环会挑「更像混合结果」的 JPEG，从而把供应商漂移用高质量留下来。端测日志的 MAD 是另一套：e2e 92–96 行比较的是原图与最终 JPEG，所以日志 MAD 能看见漂移。管线内部的 3.5/6.0 看不见这截漂移。
- 光学 Layer0 仍叠在混合图上（760–762）。账本「改走」与此并列，见第 3 节。
- 混合先存成 q=95 JPEG 再解码，L1 的输入不是内存里的 blend 浮点。
- 编辑图宽高不符时先 LANCZOS（256–257）。画布宽高可以回到原图，内容已经重采样。`_same_size` 只查宽高和 `mode=="RGB"`（815–817）。几何合同在端测里是「size_unchanged」，不包含构图。

扫档脚本把问题再推进了一步：`_align_blend_scan.py` 86–97 在 α&gt;0 时把混合 JPEG 当作 `run_five_layer(source=...)`。生产路径的字节下限仍用原上传；这条扫档路径的 `_byte_floor` 会改用混合 JPEG 的长度。若账本那次 n=4 就是这个脚本，则「+2.25」的字节下限参照与正式端测不是同一个源。没有落盘 stdout，无法确认那次是否就是这个脚本。缺陷在脚本里，这一点不依赖那次是否跑过。

### 6.2 字节下限本身

生产路径：JPEG 下限 = 原文件长度；比较发生在 exiftool 之后（417–429）。n=12 与 n=6 日志里的 `byte_floor_*` 都是 PASS。e2e 的断言（100–103）对 JPEG 同样是 `len(out) >= len(source)`。

没有发现「垫字节」或「用 60%–80% 带」的分支。

相关但不同的事实：`subsampling=0` 让文件变大，下限更容易过。product_01 原图 126395 字节，q=88 已是 184761。这是下限的合规方向，不是体积带。旧相机 JPEG 的 4:2:0 没有实现。若改成 4:2:0，小文件（product_09 原图 35915 字节、product_12 38092、product_04 45470）是否仍能过下限，现在没有证据。那是候选补丁的风险，不是现行失败。

中间 JPEG 那次 `_write_and_read` 的返回值被丢弃（423）。像素取的是写 EXIF 之前的编码。多一次可能失败的 exiftool，失败会把整次管线打成异常。不是下限计算错误。

### 6.3 几何合同

- 输出宽高被强制等于原图。双路径与 v3 的 `size_unchanged_*` 在两份日志里都是 PASS。
- 色差不改变画布尺寸，但 R/B 是整通道缩放。B 边 1px 为 0。这是通道填充缺陷，不是 rotate/crop。
- img2img 的 LANCZOS 回拉只保证画布。Q7 禁止的几何（旋转、裁切、再缩回）没有以 fingerprint 的形式出现。供应商若改了构图，现行检查看不见。MAD≈50 是像素已经大改的证据，不是某一类几何变换的分类结论。
- 参考图 1280 只影响送出去的条件图。product_01 为 800，不触发。

### 6.4 色差饱和度 ×1.02 与黑边、整像素

197–201 行仍在。冲突账本 C-V2-CA-SAT、草案「应去掉尾巴」、红线「禁可见调色」、以及「禁止原样搬迁旧烂桩」四句同时指向这一行。通道缩放本身是 Q4 允许的方向，×1.02 不是色差位移。

复算：×1.02 的 MAD 贡献约 0.074，黑边才是色差实现里刺眼的部分（边 MAD 114，B=0）。`ceil` 使 26mm 至少移动 1px；旧整数公式在同一焦距上是 0。账本写的「亚像素」两边都不是：旧的是「不足 1px 就跳过」，现行是「不足 1px 就抬到 1px」。

### 6.5 失败被吃掉，日志仍写 Layer0 开着

204–210、244–245、247–248 行：导入失败、无 key、供应商异常、空图，全部 `return None`。`run_five_layer` 于是继续用原图，并仍返回一份 v3 JPEG。e2e 133–142 行在进循环前就写下 `layer0_img2img=on`，之后没有逐张更正。

这与 C-FAIL-SILENT 的担忧同向，也与草案「返回 None 可接受」同向。不在这里二选一。可核验的缺口是：gain 的分母里可能混有「没跑成 img2img」的张，而日志看不出来。n=6 的 MAD 双峰与这个缺口相容。

### 6.6 检测五维在选优时被丢弃

见 5.1。这是测量缺陷。它不改变已发生的总分，但它使「五维卡点」无法从 v3 日志读出。下次端测若仍走 `rerank_pick`，仍会是 None。

### 6.7 其他

- `FIDELITY_MAD_OBSERVE_ONLY` 无引用。rank 仍含 MAD 项，目标 3.0 ≠ 账本 3.5。端测不因此 fail。
- 固定档 ×0.85 只作用在双路径证据上。证据 MAD 不能代表评分路径的强度。
- 拉普拉斯阈值 12 低于这 12 张两个数量级，STRONG 档是死路径（相对本样本集）。
- 锐化去掉预模糊的注释仍以旧 MAD 硬顶为理由（791）。Q11 已不否决。把预模糊加回去会碰到「禁糊图刷分」，本报告不把它列为提分补丁。
- `lookup_camera_spec`（`camera_specs.py` 415–417）：精确键未中时，`model in key`。`"iPhone 15"` 会先撞上 `"Apple iPhone 15 Pro"`。端测模型是完整的 `iPhone 15 Pro`，先走精确键 `"Apple iPhone 15 Pro"`，不触发。留作库的误配，不是这次端测的 EXIF 错误。
- 端测预设对全部样本锁死 Apple / iPhone 15 Pro / ISO 400 / 1/120 / f/1.8 / 26mm（e2e 46–63）。暗角与色差因此对 50 张都是同一光学点。Layer0 提示却不用这个预设。本地链是「手机光圈」，图生图是「通用英文」。

## 7. 不放宽约束下的候选补丁

每一项都不是实施许可。预期都不写成「因此 gain≥10」。Q12：没有 `ALIGN_W5_E2E_PASS` 就不开 PR。

| ID | 约束 | 机制 | 风险 | 要不要旧 `aiImageProcessor.ts` |
| --- | --- | --- | --- | --- |
| C1 | Q8、Q7、C-LAYER0-GEO、C-LAYER0-COLOR、C-LAYER0-API | 按预设类别送 phone/dslr/mirrorless 的旧正向提示。删掉 action 的「轻微桶形畸变」整类，或整段不用 action。饱和度衰减、过艳后衰减改成中性传感器表述，或标 `[NEEDS CLARIFICATION]` 先不动颜色句。不换模型，仍走 `gpt-image-2` + `/images/edits`。负向提示没有独立字段，不能假装已发送；若要保留语义，只能并进正向正文，并在日志里写明「负向未作为独立字段发送」 | 供应商仍可能整图重写，MAD 仍可到 50。旧提示未在 v2 测过。并进负向可能把禁止项说成要生成的内容 | **要。** 正文在 clone `aiImageProcessor.ts` 135–162。快照目录里没有该文件（冲突账本 F-AI-MISSING-SNAP / F-AI-IN-CLONE） |
| C2 | Q8、C-LAYER0 | 逐张记录 img2img 是否成功、实际 α、是否跳过光学叠加。失败不得再被汇总行写成「Layer0 开着且这张算成功」 | 只改可观测性时不提分。若改成失败即中止端测，会少样本，不能把缺样本的均值当成 Q1 | 不要 |
| C3 | Q8、测量框 | 内部拉普拉斯与编码排序的参照改回原图像素；字节下限保持原上传。blend 仍可作 Layer0 的像素输入，但不要同时当保真参照 | 质量档可能从「最像编辑图」改成「最像原图」。在暗角已经贡献 MAD≈27 时，各质量档相对原图只差约 0.3，对总分的影响应很小。不把这当成 +10 手段 | 不要 |
| C4 | Q4、Q7、C-V2-CA-SAT | 删除 197–201 的 ×1.02。保留或另案处理通道缩放 | 光度只有约 0.07 MAD。color 维未知。删尾巴是合规，不是提分证据 | 不要。这是反烂桩，不是移植烂桩 |
| C5 | Q4、账本「亚像素」 | B 边不要填 0（旧源复合路径写的是 128，且该复合被丢弃）。`ceil` 保底 1px 与「亚像素」以及 26mm 旧 shift=0 都不同。候选是：去掉保底，或改成真正的分数位移；不要为了「可测」再抬整像素 | 26mm 若回到 shift=0，现行这点色差消失，总分未知。黑边去掉能消掉边 MAD 114 的窄条，面积极小 | 不要 `aiImageProcessor`。对照的是 `imagePhysicalizer.ts` 的色差函数，且该函数的最终输出是烂桩 |
| C6 | Q3、Q7 | 不动 cos^4，也不把 compare-notes 的 8% 写成新上限（那是与账本冲突的句子）。把 rerank `vignette_mult=1.55` 标成「f/1.8 角点 33%，略高于旧表 f/1.4 的 31.7%」。若管理员认为这超出「弱」，再单独把乘数封在旧表 raw 之内 | 暗角是本地唯一大 MAD 项。压低它很可能不提分，只降低与原图的距离。压低不等于允许糊图 | 不要 |
| C7 | Q5 | 中间 JPEG 增加与旧重压同向的 4:2:0、quality 约 88 的对照档。字节下限仍硬，不够就维持能过下限的档，禁止垫字节，禁止 60%–80% | 小原图可能更难过下限。色度抽样会改变 color 维，方向未知 | 不要 `aiImageProcessor`。对照是 `imagePhysicalizer.ts` 的 `applyJpegRecompression` |
| C8 | Q11、账本 MAD 句 | 让 `FIDELITY_MAD_OBSERVE_ONLY` 真正被读到：rank 里去掉 `abs(mad-3.0)*0.02`，或只打日志。prefer 目标若保留，应是账本的 3.5 而不是 3.0。仍不 fail 端测 | 对这批样本，rank 本来就由噪声/暗角乘数主导，去掉 MAD 项几乎不改变 auto 胜者 | 不要 |
| C9 | Q10、测量 | `detector_score` 旁保留胜出包的五维与 `reason`。e2e 禁止再用空壳 `rerank_pick` 覆盖 | 不改变像素。不改 PASS_SCORE。否则下一次仍无法做五维归因 | 不要 |
| C10 | Q6 | 双路径日志注明「无 img2img、乘数被 0.85 阻尼」。不必为了留证去加强证据路径 | 无 | 不要 |
| C11 | 账本光学 0.18 | 把 `_LAYER0_OPTICAL_STRENGTH` 从 0.32 改回 0.18 | 孤立 MAD 1.51→0.87。不是主缺口 | 不要 |
| C12 | Q8 与「改走/叠加」歧义 | 不做默认行为切换。若编码，必须先由管理员选择：img2img 成功后跳过光学，或明确保留叠加并写进日志 | 现在选任何一边都是在调和 C-LAYER0 措辞 | 不要 |

明确不做（即使有人认为能提分）：

| 动作 | 约束 |
| --- | --- |
| 改 `PASS_SCORE`，或改 Q1 的 +10，或换样本集 | Q1、Q2、Q10、C-PASS-SCORE |
| 换 DashScope / qwen，或新开未批模型 | C-LAYER0-API |
| 迁 Node / sharp，或把频域搬回 L1 之前 | 红线、C-ORDER |
| hue/sat/brightness 总入口，rotate/crop/resize 回原尺寸 | Q7，冲突账本禁止清单 1 |
| 平台矩阵、60%–80% 体积带 | C-SIZE-UPLOAD |
| 把旧色差烂桩（丢掉复合、只留 ×1.02）当作「对齐旧行为」来实现 | 禁止清单 5；与 C4 方向相反 |
| 用预模糊或降质量把 MAD 做小来换分 | Q11 禁糊图刷分 |
| 失败时退原图并在汇总里算作 Layer0 成功 | C-FAIL-SILENT。C2 只要求留痕，不授权伪装 |
| 未出现 `ALIGN_W5_E2E_PASS` 就开 PR | Q12 |

C1 是清单里唯一依赖旧 `aiImageProcessor.ts` 正文的项。C5/C7 依赖的是 `imagePhysicalizer.ts`，不是该文件。其余候选只动现行 Python。

## 8. 判定（留给主代理合并，不代替主代理）

**编码可行性（C1–C12 作为候选，不是开工令）：** 与草案 `CONDITIONAL_YES` 无不可调和的代码冲突。C1 可以在现有 generation 合同内试提示词。C4、C8、C9 是合规与测量，不依赖旧 AI 文件。

**Q1 可达性：** `UNPROVEN`。维持草案，不升级。

依据只列已核验的，不把缺口写成承诺：

- 已测工作点的最好均值增益是 n=12 的 3.83，且 v3 五维缺失。
- 同六张 v2 重测漂移均值 3.67，与 3.83 同量级。
- 无 img2img 时 MAD≈29 的主体是暗角，不是未实现的频域。
- 整图编辑 MAD 均值 53.80，与总分涨跌不同号的样本同时存在。
- 旧中文分类提示尚未出现在 v2 端测里。这是未测杠杆，不是已测杠杆。
- n=6 的 2.50 与「均匀 α=0.12」在 MAD 形状上对不上，不能当作 α 扫描的干净下界。

若下一轮只做 C1 并复测后仍是 `ALIGN_W5_E2E_SHORTFALL`：按账本与 Q12 停止加码、不上 PR、把五维日志一并上报。不要改通过线。

## 9. 本审计没有做的事

- 没有改任何代码、笔记或账本。
- 没有重跑 Gemini，没有重跑 `/images/edits`，没有重跑 α 扫档。
- 没有把 compare-notes 的 Q4 禁止改成允许，也没有把代码里的色差撤掉。
- 没有宣布 +10 不可达。没有宣布补上中文提示就可达。
