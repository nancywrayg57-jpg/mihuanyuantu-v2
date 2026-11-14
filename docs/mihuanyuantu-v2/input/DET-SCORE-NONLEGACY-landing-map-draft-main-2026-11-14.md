# DET-SCORE-NONLEGACY · 落点映射（主会话草稿 · 待与子代理 A 合并）

源码：`aojuai-main/backend/app/capabilities/realphotos/services/five_layer.py`  
配置：`aojuai-main/backend/app/core/config.py`（`ALIGN_*`）

## 现有层序（止血后）

| 步 | 函数/位置 | 默认 |
| --- | --- | --- |
| Layer0 img2img | `_maybe_layer0_img2img` ~353+ | `ALIGN_LAYER0_IMG2IMG="0"` |
| Layer0 optical | `_layer0_optical` via `_l1_l3` ~946–950 | strength 0.32；可 `ALIGN_LAYER0_OPTICAL_STRENGTH` 覆写 |
| L1 噪声 | `_l1_l3` ~952–966 | `l1_noise_sigma(iso)*noise_mult`；高斯 fine+coarse，非 Poisson–Gaussian |
| CA | `_apply_chromatic_aberration` ~202+ | `_CA_INTENSITY=0` → 恒等 |
| L2/L3 | `_l2_freq_*` / `_l3_sparse_and_spectral` | 弱频域 |
| L4 EXIF | `_write_and_read` | 已有 |
| L5 encode | `_finalize_jpeg` / `_encode` ~585+ / ~991+ | quality 扫档 + byte floor |

## 候选落点表

| 候选方向 | 建议落点 | 现有重叠 | 测量 env 键建议 | 默认是否改动 | 恒等回退 | 风险 |
| --- | --- | --- | --- | --- | --- | --- |
| 弱 Bayer mosaicing→噪声→demosaic | 新 `_weak_bayer_roundtrip`；插在 L1 噪声前或后（推荐 **optical 后、现有 L1 前**） | 无真 Bayer；L1 为 RGB 高斯 | `ALIGN_BAYER_ROUNDTRIP=0\|1` + `ALIGN_BAYER_STRENGTH` | **否**（默认关） | strength=0 或 flag=0 → 拷贝输入 | 可见棋盘/色纹；须极弱 |
| 平坦区 Poisson–Gaussian | 新分支于 `_l1_l3` 噪声段，或 `noise_mult` 旁路函数 `_poisson_gaussian_noise` | 现 L1 已是加性高斯 | `ALIGN_PG_NOISE=0\|1` + `ALIGN_PG_SCALE` | **否** | flag=0 → 现有 L1 | 过强毁「过干净」以外的画质；与 R4 噪声降档正交 |
| JPEG 温和扫档 | 仅调 `_finalize_jpeg` mid_q / quality 网格；不新对抗 | 已有 encode 层 | `ALIGN_JPEG_MILD_SWEEP=0\|1` | **否** | 关则现网格 | 可能伤五维「清晰/噪点」 |
| Layer0 测量臂 | 已有 `_maybe_layer0_img2img` | 已实现 | `ALIGN_LAYER0_IMG2IMG=1`（已有） | **保持 0** | 无 Key / 失败 → 原字节 + error_type | 再开默认 = 违反 Q-HEMO |

## 白名单编码文件（若 OPEN_PILOT）

1. `five_layer.py` — 新测量函数 + `_l1_l3`/`process` 挂钩（默认关）  
2. `config.py` — 空默认 `ALIGN_BAYER_*` / `ALIGN_PG_*` 字符串键  
3. `tests/.../test_s2_five_layer.py` — 强度 0 恒等、flag 关恒等  
4. `scripts/det_score_nonlegacy_*_e2e.py` — 测量臂脚本（GOV-10 allowlist）  
5. **禁改**：`PASS_SCORE`、检测提示、计费、S7  

## 与止血不冲突检查

- 不改 `_CA_INTENSITY`  
- 不改 `ALIGN_LAYER0_IMG2IMG` 默认 `"0"`  
- 新杠杆默认关；仅 env 测量臂开启  
