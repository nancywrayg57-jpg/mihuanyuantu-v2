# 蜜獾原图 v2 · 新会话移交

## 1. 一分钟接手

项目：蜜獾原图 v2（多租户图片资源 + 相机参数处理 + 积分）。

**开工入口（编码工具）**：`docs/mihuanyuantu-v2/DEV_INSTRUCTIONS.md`  
必读根目录职责文件：`AGENTS.md`、`handoff.md`（本文件）、`anchor.md`、`checkpoint.md`。  
过程续作权威：`docs/mihuanyuantu-v2/progress.yaml` 的 `next_action` / 阶段状态。

## 2. 权威顺序

1. 产品行为 → `docs/蜜獾原图-v2-PRD-v2.0.md`
2. 落地结构 → `docs/蜜獾原图-v2-项目架构-v1.0.md`
3. 阶段划分与路径 → `docs/mihuanyuantu-v2/DEV_INSTRUCTIONS.md`

冲突则停并提问。过程技能见 `aidevops/SKILL.md`。

## 3. 位置与版本

| 项 | 路径 / 说明 |
| --- | --- |
| 仓库根 | `AGENTS.md`、`handoff.md`、`anchor.md`、`checkpoint.md`、`aojuai-main/`、`docs/`、`prototype/`、`输入材料/`、`aidevops/` |
| 本功能文档区 | `docs/mihuanyuantu-v2/` |
| 编码指令 | `docs/mihuanyuantu-v2/DEV_INSTRUCTIONS.md` |
| 底座 | `aojuai-main/` |
| 业务包 | `aojuai-main/backend/app/capabilities/realphotos/` |
| 分支约定 | 见 `AGENTS.md` §7；后缀保持 `-9973` |
| 密钥 | 仓库忽略 `生产物料/`；需要时只读本机物料，不入库 |

当前实现状态摘要见 `checkpoint.md`。

## 4. 关键导航

| 范围 | 打开 |
| --- | --- |
| 阶段 S0–S7 | `docs/mihuanyuantu-v2/DEV_INSTRUCTIONS.md` |
| 约束条目 | `anchor.md` |
| 就绪/未就绪事实表 | `checkpoint.md` |
| 协作纪律 | `AGENTS.md` |
| 旧版 55 键对照 | `docs/mihuanyuantu-v2/legacy-preset-parameter-map.md` |
| 旧版目录 | `输入材料/旧版可复用模块/02_设备参数/` |

## 5. 下一步（摘要；以 progress 为准）

- **待合入**：`cursor/preset-bulk-import-9973`（工单 `PRESET-BULK-IMPORT-2026-11-07`），依赖/叠入 PRODUCT-GAP-A https://github.com/nancywrayg57-jpg/mihuanyuantu-v2/pull/29 。
- **证据**：`/tmp/preset-bulk-import-e2e.log` 含 `PRESET_BULK_IMPORT_E2E_PASS`；`legacy_activated_count=405`；`placeholder_presets_removed=true`；`legacy_param_keys_complete=true`；`production_billing=false`。
- **要点**：先清 Honeybadger/s1 占位；405 全量启用；快照含完整 `legacyParameters`；GPS 源模式保留、不伪造坐标。
- **不得开 S7**；不得接通 URL 真导入；不得自评自合。

## 6. 风险提醒

- Cloud 服务端测 ≠ 开发机 PostgreSQL 验收。
- 菜单缓存多 worker 无 Redis 仍需重启（IA_C6）。
- 旧版 GPS override 禁止继承固定坐标：模式可保留，坐标不得发明。

## 7. 新会话粘贴提示词（复制即用）

```text
你是蜜獾原图 v2 的续作 Agent。先按顺序只读、不要改代码：
1) 仓库根 handoff.md、anchor.md、checkpoint.md、AGENTS.md
2) docs/mihuanyuantu-v2/DEV_INSTRUCTIONS.md
3) docs/mihuanyuantu-v2/progress.yaml（以 next_action / 冲突裁决为准）
硬约束：中文回复、标识符英语；不提交真实密钥；不直推/不合并 main；不开 S7；不得自评自合。
当前工作：读 checkpoint §0 与 progress.next_action；找到 cursor/preset-bulk-import-9973 与 #29 状态。
```
