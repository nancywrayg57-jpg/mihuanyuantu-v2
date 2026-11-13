# 预设参数补全 + 清原型文案 · Constraint Ledger

任务原文：2026-11-12 管理员更新需求；**暂不推送**；改完重启预览与 API。

## 硬性要求（原文追溯）

1. 每条设备预设参数对照旧版补全空缺；旧版不足则查 `https://realphotos.zennolab.cloud`。
2. 旧版没有的参数可删除（例：背景「原型有 / 旧版 55 键无」）。
3. 每条预设的**版权信息**一并补充导入。
4. 清除全站原型标注类文本（含设备预设页「运行台账…不含作者/版权、IP-GEO…」等）。
5. 禁止 Honeybadger 占位品牌。
6. 不推送。

## 已识别冲突 / 歧义

| ID | 类型 | 说明 | 处置 |
| --- | --- | --- | --- |
| C-COPYRIGHT-PRD | 冲突 | 本任务要求导入版权；PRD/对照表曾排除 `author`/`copyright` 客户表单与 EXIF；脱敏 JSON `excluded_fields` 含二者 | **本任务优先**：从旧站 live API 导入到预设快照/管理台「版权信息」页签展示与可编辑保存。**IP-GEO 仍不入库/不展示**（任务清除文案未要求开放 IP-GEO；脱敏与 PRD 仍禁）。 |
| C-EXIF-AUTHOR | 边界 | 旧站 EXIF 可写 Artist/Copyright；v2 处理路径仍拒 author/IP-GEO | **[ASSUMPTION]** 本轮只补预设台账数据与 UI；**不**放宽 EXIF 写入 author/copyright/IP-GEO（与 MakerNote 已授权不同）。若需写入 EXIF 须另批。 |
| C-GPS-COORDS | 边界 | live 含 `gps_latitude/longitude/altitude`；脱敏曾排除 | 仅当 `gps_mode=fixed` 时写入 `gpsConfig`；不引入独立 GPS 页。 |
| C-PROTO-KEYS | 裁决 | `lighting`/`background`/`post_processing` 旧版 55 键无 | **删除**字段定义与 UI；不保留空态原型标注。 |
| C-ANNOTATION | 裁决 | 「运行台账…不含作者/版权…」等为原型/工单注释文案 | **清除**；换短产品说明，不堆约束自述。 |
| C-DATA-SOURCE | 事实 | 本地脱敏包无 author/copyright；DB 405 的 `legacyParameters` 对脱敏非空键已齐 | 版权与坐标以 **旧站 live `parameters.list`** 为准补洞。 |

## 非目标

- 不推送；不打 Tag；不启 S7；不接 OSS 真桶。
- 不把 IP-GEO 做成表单字段。
- 不把 Honeybadger 演示品牌重新注入台账。

## 执行记录（2026-11-12）

1. 旧站 live `parameters.list` 精简字段落盘：`.tmp/legacy-live-copyright.json`（405；author/copyright 全量非空）。
2. DB 合并脚本：`aojuai-main/backend/scripts/merge_live_copyright_into_presets.py` → 405 `legacy_import` 已写入 author/copyright，fixed 且有坐标 243。
3. 本地 55 键空缺对照：脱敏包对 `ambient_light`/`burst_sequence`/`file_number`/`raw_version` 等本就为空的条目保持空态；有值键已在先前激活中入库。
4. 删除 FE 原型专有字段 `lighting`/`background`/`post_processing`；版权页签改为可编辑；清除预设页原型标注横幅。
5. 后端 `save_preset`：legacyParameters 允许 author/copyright，仍剥 IP-GEO；独立 `author`/`ip_geo` kwargs 仍拒。
6. 重启预览 FE/API（不推送）：`scripts/restart-local-preview.sh`；同壳探测 `api:200` / `fe:200`（unix socket `DATABASE_URL_OVERRIDE`）。若桌面浏览器连不上本机 3000/38000，在系统终端再执行该脚本（Agent 沙箱 netns 与宿主浏览器隔离）。
7. 未推送。

## 执行记录（2026-11-12 · 清假预设 + 再核参数）

1. **硬性新增**：清除设备预设假预设（手机 RuntimeCam 等），只留真实预设；逐条对照无遗漏则立刻补全；暂不推送。
2. 软删启用中假预设 **20** 条（RuntimeCam / BizCam / align-* / biz-* / bef-* / opsd-* / s1-* admin）；台账启用仅剩 `legacy_import` **405**。
3. `PLACEHOLDER_BRANDS` / `PLACEHOLDER_BRAND_BLOCKLIST` 纳入 RuntimeCam、BizCam；清理 API 一律 soft-delete 演示品牌。
4. 405 条对照本地 55 键 + live 版权/GPS：**剩余缺口 0**（local_fill/live_fill/author_miss/fixed_miss_lat 均为 0）。
