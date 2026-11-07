# 旧版设备预设 `legacy_parameters` 字段对照表（55 键）

工单：`PRESET-BULK-IMPORT-2026-11-07` · B3  
权威来源：`输入材料/旧版可复用模块/02_设备参数/按旧分类/*.json`  
落点规则：除 `excluded` 外，**禁止读了不保存**；每条激活快照必须含完整 `legacyParameters` 原样副本。

| 键 | 落点 | 说明 |
| --- | --- | --- |
| camera_make | column + snapshot | 列 `brand`；快照 `legacyParameters` |
| camera_model | column + snapshot | 列 `model_name`；快照原样 |
| category | snapshot | 设备分类展示；运行时类型用行级 `device_type`（来自 `legacy_category`/`family_hint`） |
| name | snapshot | 预设显示名 |
| description | snapshot | |
| image_description | snapshot | 非客户表单；仅运营/快照 |
| keywords | snapshot | |
| iso | column + snapshot | 列 `iso` |
| iso_range | snapshot | |
| shutter_speed | column + snapshot | 列 `shutter` |
| shutter_type | snapshot | |
| aperture | column + snapshot | 列 `aperture`；**默认值策略**：源为空时填 `f/1.8`（本批 405 源均非空，仅兜底） |
| focal_length | column + snapshot | 列 `focal_length`；源为空时填 `26mm`（兜底） |
| focal_length_equiv | snapshot | |
| focal_plane_res_unit | snapshot | |
| focal_plane_x_res | snapshot | |
| focal_plane_y_res | snapshot | |
| focus_distance | snapshot | |
| lens_make | snapshot | |
| lens_model | snapshot | |
| lens_max_aperture | snapshot | |
| white_balance | snapshot | |
| metering_mode | snapshot | |
| exposure_mode | snapshot | |
| exposure_compensation | snapshot | |
| ev_value | snapshot | |
| flash_mode | snapshot | |
| scene_mode | snapshot | |
| scene_type | snapshot | |
| ambient_light | snapshot | |
| color_space | snapshot | 五层另有 sRGB 合同；本键仍原样入库 |
| color_mode | snapshot | |
| color_depth | snapshot | |
| color_temperature | snapshot | |
| image_format | snapshot | |
| image_width | snapshot | |
| image_height | snapshot | |
| image_orientation | snapshot | |
| pixel_density | snapshot | |
| compression_ratio | snapshot | |
| sensor_type | snapshot | |
| sensor_size | snapshot | |
| noise_reduction | snapshot | |
| sharpening | snapshot | |
| stabilization | snapshot | |
| software | snapshot | 非作者/版权表单字段；快照保留 |
| file_number | snapshot | |
| burst_sequence | snapshot | |
| raw_version | snapshot | |
| gps_mode | column + snapshot | 列保留源模式（`none`/`fixed`/`random_by_scene`）；**不得**静默改成 `none` 而不在快照保留源值。旧版 `v2_runtime_overrides.gps` 声明不继承固定坐标 → `gpsConfig` 无坐标时不伪造，EXIF 写入走诚实失败原因 |
| maker_note_template | column + snapshot | 列 `maker_note`；本轮管理员授权写入 EXIF |
| ai_positive_prompt | column + snapshot | 列 `ai_positive_prompt` |
| ai_negative_prompt | column + snapshot | 列 `ai_negative_prompt` |
| ai_strength | snapshot | 第一版处理语义不强制启用 Layer0；仍入库 |
| ai_img2img_strength | snapshot | 同上 |

## excluded（PRD / 工单明确）

本批 55 键清单中**无**独立 `author` / `copyright` / `ip_geo` 键。  
旧版 `v2_runtime_overrides.author_and_copyright` 仅作策略注释写入快照 `legacyRuntimeOverrides`，**不得**变成客户可编辑表单字段，也不得按违禁 EXIF 策略写入作者/IP-GEO。

## 默认值策略摘要

| 字段 | 有源值 | 无源值 |
| --- | --- | --- |
| aperture | 原样（缺 `f` 前缀则补） | `f/1.8` |
| focal_length | 原样（缺 `mm` 则补） | `26mm` |
| iso | 原样 | `100` |
| shutter_speed | 原样 | `1/125` |
| 其余 snapshot 键 | 原样（含空串） | 原样空值，不删键 |

## 验收指针

- 对照表 55/55 有落点：本文件。  
- 运行时：`snapshot.legacyParameters` 键集合 ⊇ 该条源 JSON 键集合。  
- 端测标记：`legacy_param_keys_complete=true`。
