# DET-SCORE-NONLEGACY · 落点映射（已对照源码）

日期：2026-11-14  
状态：对照当前源码复核；种子草稿 `DET-SCORE-NONLEGACY-landing-map-draft-main-2026-11-14.md` 只作对照，行号与 JPEG 选择行为以本文件为准。  
本文件不授权改默认管线。无 `NONLEGACY_FEASIBILITY_PASS` 不得改 `five_layer` 默认行为（Q-GATE）。

源码：

- `aojuai-main/backend/app/capabilities/realphotos/services/five_layer.py`
- `aojuai-main/backend/app/core/config.py`（`Settings`，约 345–353 行）
- 工人入口：`aojuai-main/backend/app/capabilities/realphotos/services/s1_processing.py` `_five_layer_jpeg` 约 1266–1282 行
- `PASS_SCORE`：`aojuai-main/backend/app/capabilities/realphotos/services/redo_policy.py` 第 6 行，值为 **75**。不在 `five_layer.py` / `config.py`。本映射不改它。

依赖：`five_layer.py` 只用 `numpy` 与 `Pillow`。后端 `requirements.txt` 有二者，无 `opencv` / `cv2`。全后端 `*.py` 无 `bayer` / `mosaic` / `demosaic` / `poisson`。

## 止血默认（保持）

| 项 | 代码事实 | 本映射 |
| --- | --- | --- |
| `ALIGN_LAYER0_IMG2IMG` | `config.py` 347 行默认 `"0"` | 不改 |
| `_CA_INTENSITY` | `five_layer.py` 55 行 `0.0` | 不改；新臂不得乘回 CA |
| `_LAYER0_OPTICAL_STRENGTH` | 51 行 `0.32`，光学预通默认开 | 不升、不降；R4 覆写不升默认（Q-NO-R4-DEFAULT） |
| `PASS_SCORE` | `redo_policy.py` 6 行 `75` | 不改 |

## 现有 v3 / auto 层序（工人路径）

`s1_processing._five_layer_jpeg` 调用 `run_five_layer(source, preset, seed)`，即 `freq_mode="auto"`、`algorithm="v3"`、`score_fn=None`。文件头注释仍写 L1→L5；实现已在像素层前插入 Layer0。

| 步 | 函数 / 位置 | 默认行为 |
| --- | --- | --- |
| Layer0 img2img | `_maybe_layer0_img2img` 350–427；旗标 362–364；调用点 `run_five_layer` 681–685 | 仅非 v2 且 `freq_mode` 为 `auto`/空。`"0"` → `None`，原字节继续。`"2d"`/`"1d"`/`"hybrid"` 根本不调用 |
| 解码 | `_decode_baseline` 827–830 | RGB `float32`；几何必须与原图一致（691–699、636–637） |
| 分档 | `_pick_v3_pixels` 519–582 | 整图 `_laplacian_var`（504–516）对照 `_SMOOTH_LAP_VAR_THR=12`（56 行）选 `_AUTO_TIERS_*`。这是整图档，不是像素平坦掩膜 |
| Layer0 optical | `_layer0_optical` 183–199；`_l1_l3` 945–950 | 默认开，强度 `0.32`。`strength<=1e-9` 时原样返回。含 `0.55*strength` 高斯颗粒 |
| L1 噪声 | `_l1_l3` 952–966；`l1_noise_sigma` 124–135 | 加性高斯：`fine` + 3×3 模糊 `coarse`（0.65/0.35）；`arr<64` 再 ×1.5。**不是** Poisson–Gaussian。σ 来自 `max(ISO, 400)` × `0.5*sqrt(ISO/100)` × 强度；强度默认 `_NOISE_INTENSITY=1.55`（49 行），夹在 `[0.85, 2.20]` |
| L1 暗角 | `aperture_vignette_strength` 138–158；`_apply_vignette` 833–845；调用 967–968 | `cos^4` × `_VIGNETTE_LEGACY_SCALE=0.85`。`strength<=1e-9` 原样返回 |
| CA | `focal_length_to_ca_strength` 161–180；`_apply_chromatic_aberration` 202–228；调用 969 | `_CA_INTENSITY=0` → `ca<0.35` → `shift=0` → 返回输入（214–215）。无 saturation×1.02 |
| L2 | `_l2_freq_2d` 848–862；`_l2_freq_1d_luminance` 865–890；调用 970–973 | 弱 FFT。`auto` 先选 2d 或 1d，不是 hybrid |
| L3 | `_l3_sparse_and_spectral` 893–911；调用 974 | 稀疏 ±1 与高频微扰 |
| 锐化 | `_weak_sharpen` 978–988；`_pixels_to_output` 639–640 | v3 默认开。v2 路径 `sharpen=False` |
| L5 编码 | `_encode` 991–1000；`_finalize_jpeg` 585–620 | `subsampling=0`、`optimize=False`。网格 `_QUALITIES`（29 行）=`(85, 88, 90, 93, 96, 98, 100)`。`_MID_JPEG_QUALITY=85`（46 行）只做 EXIF 探测，字节丢弃（601–603），不是成品二次压缩 |
| L4 EXIF | `_write_and_read` 1266 起 | 写在 `_finalize_jpeg` 每个 Q 候选上（608 行），不是编码前的独立层 |

`ALIGN_FIXED_MODE_SCALE`（`config.py` 353；`_l1_l3` 937–944，模块默认 `_FIXED_MODE_SCALE=0.85`）只在四个乘数都为 1 时生效。`auto` 档传入的 `_AUTO_TIERS_*` 不是全 1，因此**不**走这条缩档。R4 的 `ALIGN_NOISE_INTENSITY` / `ALIGN_LAYER0_OPTICAL_STRENGTH` / `ALIGN_FIXED_MODE_SCALE` 已是测量覆写，空字符串保持模块默认（`_float_setting_override` 108–121）。禁止把 R4 测值写成新默认。

Settings：`model_config.extra="ignore"`（`config.py` 57–63），未声明字段的环境变量会被丢掉。`get_settings()` 有 `lru_cache`（373–376）。测量脚本要同时写环境变量和已创建的 `settings.<字段>`（现有 R4 脚本即此做法）。新旗标用字符串，空/`0`/`false`/`off`/`no` 视为关，对齐 362–364。

## 候选落点表

| 候选方向 | 建议落点(函数/层序) | 现有重叠 | 测量 env 键建议 | 默认是否改动 | 恒等回退如何做 | 风险 |
| --- | --- | --- | --- | --- | --- | --- |
| 弱 Bayer mosaicing 往返 | 新 `_weak_bayer_roundtrip`：RGGB 抽样 → 可选极弱 raw 噪声 → numpy 双线性 demosaic → 按强度与原 RGB 混合。插入 `_l1_l3`（914–975）里 `_layer0_optical` 之后、L1 高斯之前（950 与 952 行之间）。保持 `HxWx3`，不引入 `cv2` | 无 CFA。`_layer0_optical`（183–199）已加微对比和高斯颗粒；L1（952–966）是 RGB 高斯。其后 L2/L3 与 JPEG 会再冲淡 CFA 峰 | 新 `ALIGN_BAYER_ROUNDTRIP` 默认 `""`；新 `ALIGN_BAYER_STRENGTH` 默认 `""`。声明在 `config.py` 350–353 行附近。两端都为关/≤0 才算关 | **否** | 旗标关或 strength≤0：原样返回输入数组（对齐 `_layer0_optical` 185–186）。异常：记日志并返回输入，后面的 L1 仍按现状跑 | 棋盘/色纹可见；与 L1 叠加强度会盖住 CFA，单独测这一臂。禁止梯度、自适应 mask、可逆攻击网（Q-NO-ADV） |
| 平坦区 Poisson–Gaussian | 新 `_poisson_gaussian_flat_noise`，只挂 `_l1_l3` 952–966。旗标开且 scale>0：局部低方差像素用 `sqrt(read_var + gain * signal)` 替换该处高斯；纹理像素仍用现有 0.65/0.35 与暗部 ×1.5。不要用整图 `_laplacian_var` / `_SMOOTH_LAP_VAR_THR` 当像素掩膜 | 现 L1 是 ISO 加性高斯，`l1_noise_sigma`（124–135）可被 `ALIGN_NOISE_INTENSITY` 改强度（R4）。光学层另有高斯颗粒。`auto` 的 `noise_mult` 来自 `_AUTO_TIERS_*`（57–64） | 新 `ALIGN_PG_NOISE` 默认 `""`；新 `ALIGN_PG_SCALE` 默认 `""`。平坦阈值若要可测，另加 `ALIGN_PG_FLAT_THR`（空=仅测量臂内的代码常数）。**不要**拿 `ALIGN_NOISE_INTENSITY` 当开关。PG 项不乘 `noise_mult` | **否** | 旗标关：不调用新函数，952–966 保持字节级现状。旗标开但 scale≤0：仍用原高斯（避免平坦区变成 0 噪声）。异常：原高斯 | 过强会伤「过干净」以外的画质。与 R4 降噪正交，禁止把 R4 的 `1.0` 升为默认。和 Bayer 同开则 Δ 无法归因。平坦替换区不要再叠暗部 ×1.5 |
| JPEG / encode 温和扫档 | 不新造重压缩环。只在 `run_five_layer` 的 **v3** 分支（固定 mode 约 726–734，auto 约 744–752）把 `qualities` 传入 `_pixels_to_output`（623–651）→ `_finalize_jpeg`（585–620）。`_encode`（991–1000）保持 `subsampling=0`。v2 分支 700–712 的 Q 网格不动 | 已有扫档：`_QUALITIES`（29 行）与 mid 85（46 行）。排序按相对**处理前 baseline** 的 MAD 升序，并要求 `len>=_byte_floor`（84–96、606–619）。高 Q 通常更接近管线像素差，只追加更低 Q **往往不改变赢家**。mid 探测不是成品二次 JPEG | 新 `ALIGN_JPEG_MILD_SWEEP` 默认 `""`。为 1 时才解析 `ALIGN_JPEG_QUALITIES`。建议测量字符串 `90,93,96`（去掉选择器偏爱的 98/100），该字符串不是代码默认 | **否**。不改 `_QUALITIES`、`_MID_JPEG_QUALITY`、排序键 | 旗标关：现网格 + 现排序。列表解析失败，或温和网格全部不满足字节下限：再跑一遍 `_QUALITIES`，避免新的 `OUTPUT_CONSTRAINT_UNSATISFIED` | 去掉高 Q 后五维「清晰/噪点」可能下降。不要改排序去追检测分，不要二次对抗 JPEG，不要改 `subsampling` |
| Layer0 测量臂 | **已有，不新增函数**。`_maybe_layer0_img2img` 350–427；`run_five_layer` 681–685。混合在 `_blend_layer0_jpeg` 430–458，默认 α=`_LAYER0_IMG2IMG_STRENGTH=0.12`（52 行）。工人路径是 auto/v3，测量旗标为 1 时会进入 | 与 `_layer0_optical`（183–199，默认 0.32，调用 946–950）不是同一臂。光学默认开着。`ALIGN_LAYER0_OPTICAL_STRENGTH` 是 R4，本臂不写、不升默认。`ALIGN_LAYER0_BLEND_ALPHA`（config 349）空则用 0.12 | **已有** `ALIGN_LAYER0_IMG2IMG`（config 347）。测量设 `"1"`。可选 α 沿用已有 `ALIGN_LAYER0_BLEND_ALPHA`，默认留空 | **否**。默认保持 `"0"`。`_CA_INTENSITY` 保持 `0.0` | `0/false/off/no`：362–364 直接 `None`，不调用供应商（`test_layer0_flag_0_jpeg_pixels_match_skip`，`test_s2_five_layer.py` 266 行起）。无 Key 或异常：`_layer0_img2img_fail`（314–318）后 `None`，原字节继续 | 默认改回 1 即违反 Q-HEMO。`freq_mode` 非 auto 时此函数不会跑。α=1 为整图替换。失败若改成抛错，会丢掉现在的回退 |

## 插入顺序（若多臂以后同时存在）

物理顺序是 optical → Bayer 往返 → 噪声（高斯或平坦区 PG）→ 暗角 → CA（恒等）→ L2/L3 → 弱锐化 → JPEG 候选。端测一次只开一个新旗标（工单 W4）。Bayer 与 PG 同时开不能当作单变量增益。

## 与止血、红线的核对

- 不改 `_CA_INTENSITY`（55 行），不为 CA 新增 env。8mm/26mm 恒等单测在 `test_chromatic_aberration_8mm_and_26mm_match_input`（`test_s2_five_layer.py` 256–263）。
- 不改 `ALIGN_LAYER0_IMG2IMG` 的模型默认 `"0"`（`test_align_layer0_img2img_default_is_off`，252–253 行）。
- 不改 `PASS_SCORE`、检测提示、计费、S7。
- 新行为只走新 env；空默认必须与今天的止血输出一致。
- 前馈、固定强度、无梯度。ISPCloak 一类对抗管线不落点。

## 相对种子草稿的修正

草稿把 img2img 写成「~353+」、把光学写成「`_l1_l3` ~946–950」。调用点大致对，但光学函数本体在 183–199，img2img 全函数在 350–427，且只在 auto 路径调用。草稿未写明：JPEG 按 MAD+字节下限挑选，温和扫档必须**换掉**高 Q 候选才会动到赢家；L4 写在每个 Q 候选上；`ALIGN_FIXED_MODE_SCALE` 不作用于 auto 档；PG 不能复用 `ALIGN_NOISE_INTENSITY`；Settings 未声明的 env 会被 `extra="ignore"` 丢掉。

## 若日后 OPEN_PILOT 的文件范围（本文件不执行）

1. `five_layer.py`：上述新函数 + `_l1_l3` / `run_five_layer` 挂钩，默认关。
2. `config.py`：新字符串字段，默认空。
3. `tests/capabilities/realphotos/test_s2_five_layer.py`：旗标关与强度 0 时与现路径一致；CA / Layer0 默认单测仍绿。
4. 新测量脚本沿用 `scripts/det_score_r4_measure_e2e.py` 的「改 settings 属性、不改模块常量」写法。
5. 不改：`redo_policy.py` 的 `PASS_SCORE`、`_CA_INTENSITY`、`ALIGN_LAYER0_IMG2IMG` 默认、`_QUALITIES`、`_LAYER0_OPTICAL_STRENGTH`。
