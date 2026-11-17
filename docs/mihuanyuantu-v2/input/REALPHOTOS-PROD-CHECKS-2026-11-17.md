# 生产检测报告 · 2026-11-17

工单：`REALPHOTOS-S7-PROD-DEPLOY-E2E-2026-11-16` 追加检测（C1–C3）  
环境：`https://exif-demo.honeybadgersoft.com`（`47.242.28.49`），生产库 `realphotos_prod`

---

## C1 · 图片处理写入的参数：只写「部分」，不是预设每条都写

**结论：只写入部分参数。** 预设里 61 个参数中，实际写入 EXIF 的是「相机身份 + 曝光核心 + 一组显式映射的可选参数」；大量描述类/技术类参数不写。

### 证据

取已交付任务 `task 11`（`output_object_key=tenant/2/output/11.jpg`，2,044,384 B），其预设快照含 61 个参数；用 `exiftool -j -G1` 读回，关键标签：

```
IFD0:Make, IFD0:Model, ExifIFD:ISO, ExifIFD:ExposureTime, ExifIFD:FNumber,
ExifIFD:FocalLength, ExifIFD:ShutterSpeedValue, ExifIFD:ApertureValue, ExifIFD:ColorSpace,
IFD0:Software, ExifIFD:LensMake, ExifIFD:LensModel, ExifIFD:MaxApertureValue,
ExifIFD:FocalLengthIn35mmFormat, ExifIFD:FocalPlaneXResolution, ExifIFD:FocalPlaneYResolution,
ExifIFD:FocalPlaneResolutionUnit, ExifIFD:MeteringMode, ExifIFD:WhiteBalance,
ExifIFD:LightSource, ExifIFD:ExposureProgram, ExifIFD:Flash*, ExifIFD:MakerNote
```

### 已写入（映射自预设）

| 预设参数 | EXIF 标签 |
| --- | --- |
| brand / model（或 camera_make / camera_model） | `Make` / `Model` |
| iso | `ISO` |
| shutter | `ExposureTime` + `ShutterSpeedValue`（APEX） |
| aperture | `FNumber` + `ApertureValue`（APEX < 1 时省略，仅写 FNumber） |
| focalLength | `FocalLength` |
| focal_length_equiv | `FocalLengthIn35mmFormat` |
| lens_make / lens_model / lens_max_aperture | `LensMake` / `LensModel` / `MaxApertureValue` |
| focal_plane_x_res / y_res / res_unit | `FocalPlaneXResolution` / `Y` / `ResolutionUnit` |
| metering_mode | `MeteringMode`（枚举码） |
| white_balance | `WhiteBalance`（0/1）+ `LightSource` |
| exposure_mode | `ExposureProgram` + `ExposureMode` |
| flash_mode | `Flash` |
| scene_mode / scene_type | `SceneCaptureType` |
| color_space | `ColorSpace=sRGB`（AdobeRGB 时写 `Uncalibrated`） |
| software / image_description | `Software` / `ImageDescription` |
| makerNote / maker_note_template | `MakerNote` |
| gps_mode + gps_config | GPS 标签（`none` 时清空） |

### 未写入（只影响前端展示/快照，不落 EXIF）

`ai_positive_prompt`、`ai_negative_prompt`、`ai_strength`、`ai_img2img_strength`、`ambient_light`、`burst_sequence`、`category`、`color_depth`、`color_mode`、`color_temperature`、`compression_ratio`、`description`、`ev_value`、`exposure_compensation`、`file_number`、`focus_distance`、`image_format`、`image_width`、`image_height`、`image_orientation`、`iso_range`、`keywords`、`name`、`noise_reduction`、`pixel_density`、`raw_version`、`sensor_size`、`sensor_type`、`sharpening`、`shutter_speed`、`shutter_type`、`stabilization`

> 说明：上表按代码 `optional_exif_assignments()` + `_write_and_read()` 与实测标签交叉核对；空值参数一律不写（不是写成空标签）。若产品要求「预设的每条参数都写入」，需要新增映射并评估 EXIF 真实性风险。

---

## C2 · 图片资源 URL 导入三种方式：可用

测试对象：`http://47.85.47.252`（临时 API 型导入站），文件 `2974b120a883483a954ea9f361d506ef.jpg`（9.7 MB）。

| 方式 | 接口 | 结果 |
| --- | --- | --- |
| ① 图片 URL（每行一条） | `POST /api/v1/realphotos/resource-imports` `{payload:"<url>"}` | **PASS** `imported=1`，落库 asset，`creditsCharged=0`、`processingTasksCreated=0` |
| ② JSON 数组（粘贴文本） | 同上，`payload='[{"url":...}]'` | **PASS** `imported=1` |
| ③ JSON 文件上传 | `POST /api/v1/realphotos/resource-imports/files`（multipart） | **PASS** `imported=1` |
| 资源库可见 | `GET /assets` | **PASS** 导入结果出现在资源列表 |
| 主机白名单 | 非供应商主机 URL | **PASS** `IMPORT_URL_REJECTED` |
| 路径形态 | `/foo/a.jpg` | **PASS** `IMPORT_URL_REJECTED`（只允许 `/images/<file>` 或 `/api/images/<file>`） |
| 101 条上限 | 101 条 JSON | **PASS** `HTTP 400 INPUT_INVALID`（整单拒绝） |

关键实现约束（供后续配置参考）：运行时**总是**重写为 `GET {base}/api/images/<file>`，且主机必须在合同 Base URL 的 allowlist 内。因此「图片 URL」不是任意公网地址，而是该供应商的 `/images/...` 路径。

---

## C3 · 临时导入站与公网复测

### 3.1 临时站渠道处理

- 该渠道（`api-image-host` / `http://47.85.47.252`）本质是**内置种子行**：`DELETE /provider-contracts/import` 走软删除，但下一次读取时 `ensure()` 会按内置规格**自动重建**该行，所以「删掉」不成立。
- 实际处置：把 Base URL 恢复为种子默认值，并将该渠道**停用**；此时导入返回 `SERVICE_NOT_CONFIGURED`（功能关闭，不会误用临时站）。
- 若要彻底从后台消失，需要改 `supplier_config._SPECS`（去掉 import 种子）或加迁移，属于产品决策，待管理员确认。

### 3.2 复测：换一个宿主（已验证可用）

用生产机本地静态服务模拟「另一家供应商」：`http://127.0.0.1:18999`，路径 `/api/images/test.jpg`（真实 1024×768+ JPEG）。  
通过「修改」把导入渠道 Base URL 指过去后，导入 `http://127.0.0.1:18999/images/test.jpg` → **PASS** `imported=1`，证明 Base URL 切换与导入链路正常（测试后已停止服务并停用渠道）。

### 3.3 公网候选站点复测结果

| 站点 | 路径 | 结果 |
| --- | --- | --- |
| `httpbin.org` | `/images/test.jpg` | 404 |
| `picsum.photos` | `/images/test.jpg` | 404 |
| `placehold.co` | `/images/test.png` | 404 |
| `dummyimage.com` | `/api/images/test.png` | 200 但返回 `text/html`（"Too small"，22 B），非图片 |

**结论：公开图床都不满足本产品的 API 型导入契约**（必须是「根路径下 `/api/images/<file>` 直接返回 ≥1024×768 的真实图片字节」）。若需要一个长期可用的公网测试源，建议自建一个静态桶/对象存储并把 `base` 指过去；否则维持「关闭外部导入」状态。

---

## 当前生产状态

- 导入渠道：**已停用**（`SERVICE_NOT_CONFIGURED`），Base URL 为种子默认值，临时站不再生效。
- 其余四个职责（generation / prompt_review / prompt_opt / final_detection）保持 2026-11-17 的 `gemini-2.5-flash` 配置。
- 检测消耗的积分：导入不计费（`creditsCharged=0`），未产生额外扣费。

---

## 补充修复（2026-11-17）

| 问题 | 原因 | 修复 | 验证 |
| --- | --- | --- | --- |
| 图片资源「来源」列对导入图片显示「未知来源」 | 导入资产 `origin_kind=url_import`，但 `originKindLabel` 只映射了 local_upload / text_to_image / image_to_image | 增加 `url_import → URL导入`（并兼容 `url-api` / `url_api` 历史写法），资源页来源筛选同步增加该选项 | Playwright：列表显示「URL导入」、全文无「未知来源」、下拉含该项 |

---

## P0 实施：相机 EXIF 骨架（2026-11-17，已上线）

对照旧版 `D:\workspace\蜜獾原图\server\exifToolWriter.ts` 补齐「真机 JPEG 必有」的骨架标签；**不写任何枚举默认值**（P2），并修正两处旧版会造假的写法。

### 写入清单

| 标签 | 取值 | 说明 |
| --- | --- | --- |
| `IFD0:ModifyDate` / `ExifIFD:DateTimeOriginal` / `ExifIFD:CreateDate` | 写入时刻 `YYYY:MM:DD HH:MM:SS` | `-DateTime=` 会落到 XMP，故显式写 IFD0 |
| `ExifIFD:SubSecTime`（+Original/Digitized） | 毫秒前两位 | 与上述时间一致 |
| `IFD0:XResolution` / `YResolution` / `ResolutionUnit` | 72 / 72 / 2(inches) | 用 `-IFD0:...=#` 数值写，避免落到 JFIF/IFD1 |
| `IFD0:YCbCrPositioning` | 2(Centered) | — |
| `ExifIFD:ExifVersion` / `FlashpixVersion` | 0230 / 0100 | — |
| `ExifIFD:ComponentsConfiguration` | `1 2 3 0` | — |
| `ExifIFD:ImageUniqueID` | 32 位随机 hex | 每张唯一 |
| `ExifIFD:ExifImageWidth` / `ExifImageHeight` | **实际输出像素** | 旧版用预设的 8256×5504，与实际 3072×4096 矛盾；本版不照搬 |
| `IFD1:ThumbnailImage` | 160×120 JPEG（约 1.7 KB） | 真机照片必有 IFD1 缩略图 |

### 刻意**不写**的

- `Orientation`：旧版强制写 1。实测源图/输出方向并不一致（曾出现写入后为 3），且写 1 会改变看图软件的旋转语义。本版**不写**，保留编码器结果，避免“元数据说正立、像素却旋转”的矛盾。
- 枚举默认值（`MeteringMode`/`WhiteBalance`/`ExposureProgram`/`SceneCaptureType`/`LightSource`/`Flash`）：预设没有就不写（P2）。
- `ExposureBiasValue`/`CustomRendered`/`SensingMethod`/`DigitalZoomRatio`/`Contrast`/`Saturation`/`Sharpness`/`SubjectDistanceRange`：这些是旧版的常量默认值，属于“编造”，不写。
- 预设里的 `image_width`/`image_height`：只在预设页展示，绝不作为 EXIF 尺寸来源。

### 生产验证（task 14）

```
[IFD0]   Modify Date            : 2026:11:17 11:29:22
[ExifIFD] Date/Time Original    : 2026:11:17 11:29:22
[ExifIFD] Create Date           : 2026:11:17 11:29:22
[ExifIFD] Sub Sec Time          : 04
[IFD0]   X Resolution           : 72     [IFD0] Resolution Unit : inches
[IFD0]   Y Cb Cr Positioning    : Centered
[ExifIFD] Exif Version          : 0230   [ExifIFD] Flashpix Version : 0100
[ExifIFD] Components Configuration : Y, Cb, Cr, -
[ExifIFD] Image Unique ID       : 0CC97F44FED54BB888CFAD88C32F1F50
[ExifIFD] Exif Image Width      : 3072   [ExifIFD] Exif Image Height : 4096
ThumbnailImage: 1715 bytes (IFD1)
```

- 实际像素 3072×4096 与 `ExifImageWidth/Height` 一致；
- 缺省参数抽样（Keywords/Category/Subject/Rating/UserComment）仍为 absent；
- 骨架软校验日志：修复后**无新增** mismatch（历史 8 条均为已移除的 Orientation 期望）。

---

## P1 实施：参数归一化 + 两个标准标签（2026-11-17，已上线）

按管理员确认执行 **P1a + P1b，不做 P1c**；不新增 `writtenParams` 快照。

### P1a 归一化（写入前吸附到真机档位）

| 输入 | 输出 | 说明 |
| --- | --- | --- |
| `ISO 57` | `64` | 按 log2 距离吸附到标准 ISO 序列（50…102400） |
| `ISO 500` | `500` | 已是标准档，不变 |
| `30s` / `15s` | `30` / `15` | 去掉 `s` 后缀，保证 `ExposureTime` 合法 |
| `0.5` | `1/2` | 小于 1 秒统一成 `1/N` |
| `1/2000` | `1/2000` | 保持原样 |
| `f/1.37` | `1.4` | 吸附到 1/3 档光圈序列 |
| `83mm` | `85` | 吸附到常见焦段序列 |

- 归一化后的值同时用于**写入**与**回读校验**（`requested` 用归一值），因此不会出现“校验不一致”误报。
- 现有 405 条预设的 ISO/光圈/焦距**全部已是标准值**（扫描结果 0 条异常），所以今天不会改变任何输出；价值是防止后续管理员录入非标准值。仅 10 条长曝光预设的 `30s/15s/10s/20s` 会被规范化。

### P1b 新增两个标签（仅当预设带值）

| 预设字段 | EXIF 标签 | 抽样覆盖 | 样例 |
| --- | --- | --- | --- |
| `exposure_compensation` | `ExposureCompensation`（EV，数值写） | 12 / 25 | `0.7` → `+0.7` |
| `focus_distance` | `SubjectDistance`（米，数值写） | 12 / 25 | `4.8` → `4.8 m` |

两个标签都加入 `_NUMERIC_EXIF_TAGS`（写 `-Tag#=`）并使用数值近似校验；预设无值则不写（P2）。

### P1c 明确不做

`description`（25/25 预设都有值，内容是中文场景文案）→ **不写** `ImageDescription`，避免交付图里出现营销描述。现状只写预设的 `image_description` 字段（有值时）。

### 生产验证（task 15，预设 `legacy-legacy-online-713`）

预设：ISO 500 / 1/500 / f/2.5 / 85mm / EV +0.7 / 焦距 4.8m

```
[ExifIFD] ISO                  : 500
[ExifIFD] Exposure Time        : 1/500
[ExifIFD] F Number             : 2.5
[ExifIFD] Focal Length         : 85.0 mm
[ExifIFD] Exposure Compensation: +0.7
[ExifIFD] Subject Distance     : 4.8 m
[ExifIFD] Shutter Speed Value  : 9        (APEX = log2(500) ≈ 8.97)
[ExifIFD] Aperture Value       : 2.6      (APEX = 2·log2(2.5) ≈ 2.64)
```

骨架标签（P0）与“缺省不写”规则同时复核通过。

---

## 缩略图性能修复 + 申诉迁移 + 全站样式套用（2026-11-17）

### 缩略图

- 原因：资源库用 `/gateway/objects/<原始key>` 拉**原图**（2.7–10.9 MB），串行加载且 `Cache-Control: no-store`。
- 实测（修复前）：单张 6.49 / 7.12 / 7.00 秒，一页 10 行约 60–70 秒。
- 修复：网关新增 `?thumb=<px>`（Pillow LANCZOS → JPEG q75 → `.thumbs/<sha1>-<w>.jpg` 磁盘缓存，`private, max-age=86400`）；前端改拉 160px、并发 4、`loading="lazy"`。
- 实测（修复后 10 张）：冷启动 1.49 秒、命中缓存 0.59 秒、平均 4.5 KB（最大 6.1 KB）。

### 图片申诉迁移（方案 A）

- 工作台移除「图片申诉」卡片（保留最近历史）。
- 任务详情新增「图片申诉」区块：填写原因 → 创建 `image_appeal` 工单（原因前缀 `任务 #<id>：`）。
- 任务详情页顶部新增「我的申诉（N）」折叠列表。

### 全站样式套用

- 22 个 `realphotos` 页面统一为 P0/P1 规范：卡片 `rp-card`、按钮 `rp-btn`/`rp-btn-sm`、表格 `rp-table`、输入 `rp-input`、弹窗 `rp-dialog`。
- 清理了 0 处遗留的 `rounded-xl border border-border bg-card`、`border px-2 py-1` 写法。
