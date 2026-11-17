# 已处理图片的 EXIF 写入情况分析 · 2026-11-17

数据来源：生产库 `cap_realphotos_image_tasks`（`status=DELIVERED`，共 **58** 条）  
比对方式：任务快照 `preset_snapshot` ↔ 输出图 `exiftool -G1 -n` 实际标签  
时间分桶：P0（骨架）≈ 11:20 部署、P1（归一化 + 曝光补偿/对焦距离）≈ 11:42 部署

## 一、总体

| 分桶 | 数量 | 说明 |
| --- | --- | --- |
| A · P0 之前 | 4 | 无骨架标签（历史产物） |
| B · 仅 P0 | 0 | — |
| C · 当前管线（P0+P1） | **54** | 下文覆盖率以此为准 |

## 二、当前管线标签覆盖率（n=54）

| 标签 | 覆盖 | 结论 |
| --- | --- | --- |
| Make / Model | 54/54 | ✅ |
| ISO / ExposureTime / FNumber / FocalLength | 54/54 | ✅ |
| LensMake / LensModel / MaxApertureValue / FocalLengthIn35mm | 54/54 | ✅ |
| MeteringMode / WhiteBalance / LightSource | 54/54 | ✅ |
| ColorSpace（sRGB） | 54/54 | ✅ |
| Software | 54/54 | ✅ |
| IFD0:ModifyDate | 53/54 | ⚠️ 1 张为部署切换期产物（task 13，写的是 `-DateTime=`） |
| DateTimeOriginal / CreateDate / SubSecTime | 54/54 | ✅ |
| ImageUniqueID | 54/54 | ✅ |
| ExifImageWidth/Height（=实际像素） | 54/54 | ✅ |
| XResolution/YResolution/ResolutionUnit | 54/54 | ✅ |
| YCbCrPositioning | 54/54 | ✅ |
| IFD1 缩略图 | 54/54 | ✅ |
| GPS | 45/54 | ✅ 其余 9 张预设 `gpsMode=none`，按设计不写 |
| **ExposureProgram** | **9/54** | ⚠️ 只有 `Aperture Priority` 被映射，`Program AE` 未映射 |
| **Flash（EXIF IFD）** | **0/54** | ❌ 全部落到 `XMP-exif:FlashMode/FlashFired` |
| **MakerNote（EXIF IFD）** | **0/54** | ❌ 全部落到 `XMP-exif:MakerNote` |
| ImageDescription | 0/54 | 预设无 `image_description` 字段值，按设计不写 |

## 三、三个关键发现

### 1. Flash 写进了 XMP，而不是 EXIF（可修）

- 全部 58 条预设 `flash_mode=Off`，期望写 `ExifIFD:Flash=0x0`；
- 实测输出只有 `XMP-exif:FlashMode=0 / FlashFired=False / Composite:Flash=0`，EXIF IFD 内没有 Flash；
- 现场实验：`exiftool -Flash#=16` 只写 XMP；改用 `-EXIF:Flash#=16` 才写入 `ExifIFD:Flash`。
- **修复**：写 `Flash` 时加组限定 `-EXIF:Flash#=<code>`。

### 2. MakerNote 无法用文字写入 EXIF（技术限制）

- 现场实验：`exiftool -EXIF:MakerNote=Huawei` 直接报 `EXIF:MakerNote doesn't exist or isn't writable`；
- MakerNote 是厂商私有二进制块，exiftool 只能复制真实机型的 maker note，不能凭空创建；
- 当前实现写 `-MakerNote=Huawei` 只能落到 `XMP-exif:MakerNote`。
- **结论**：现有“写入 MakerNote”在 EXIF 层面并未生效；要真实 MakerNote 需引入真实机型样本的二进制块（改造成本与真实性问题都较大），建议先在产品说明里按 XMP 处理或明确不做。

### 3. ExposureProgram 映射不全（可修）

- 预设 `exposure_mode` 分布：`Program AE` 45 张、`Aperture Priority` 13 张；
- 覆盖率 9/54 ≈ 仅 Aperture Priority 生效，`Program AE` 缺少映射；
- **修复**：在曝光模式映射表补 `Program AE → 2`（并覆盖 `Manual/Auto/Shutter Priority` 等常见值）。

## 四、其他统计

| 项 | 结果 |
| --- | --- |
| 归一化改写次数 | ISO 0 / 光圈 0 / 焦距 0（本批预设本来就是标准档位） |
| GPS 模式 | `random_by_scene` 45 张、`none` 9 张（与预设一致） |
| 曝光补偿 / 对焦距离 | 本批 54 张的预设均不含这两项；P1 联调任务 15 已单独验证写入成功（`+0.7 EV` / `4.8 m`） |
| 骨架缺失 | 仅 P0 之前的 4 张（task 7/9/10/11）与部署切换期的 task 13 |

## 五、建议动作（按优先级）

1. **修 Flash 组限定**（`-EXIF:Flash#=`）——一行改动，影响全部图片的真实性完整度；
2. **补 ExposureProgram 映射**（Program AE 等）——覆盖 45/54 的常见场景；
3. **MakerNote 定性**：如果必须 EXIF 层，需评估“真实机型 maker note 样本”方案；否则在产品口径里说明“MakerNote 仅 XMP”；
4. 可选：把 `ImageDescription` 纳入映射（预设 `image_description` 有值时写）。

> 以上 1、2 均可复现验证：改完后重跑一张任务，用 `exiftool -G1 -n` 检查 `ExifIFD:Flash` 与 `ExifIFD:ExposureProgram` 是否出现。
