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
