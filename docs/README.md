# 蜜獾原图 v2 文档

现行合同以本目录根文件与 `architecture_decisions/` 为准。被替代的 PRD、原型交接和增量 ADR 在 [`archive/`](archive/README.md)。

## 现行入口

| 文档 | 用途 |
|---|---|
| [PRD v2.0](蜜獾原图-v2-PRD-v2.0.md) | 产品需求；document_version **2.9**（含客户业务 API FR-033） |
| [待决策清单](蜜獾原图-v2-待决策清单-v1.0.md) | ND 裁决（**1.30**）；与 PRD 冲突时以现行 PRD 为准 |
| [Gemini Vision 检测与自动重做](蜜獾原图-v2-Gemini-Vision检测与自动重做方案-v1.0.md) | 生产检测与 FR-026 合同 |
| [项目架构](蜜獾原图-v2-项目架构-v1.0.md) | 目标实现设计 **1.5**（LocalDisk 默认；含 FR-033 客户业务 API 表/路由）；尚未证明已上线 |
| [生产物料清单](蜜獾原图-v2-生产物料清单-v1.0.md) | 开发机 VM、生产拓扑与上线阻塞项 |
| [AidevOps 工作区](mihuanyuantu-v2/progress.yaml) | grill-me 确认后的首期阶段与进度文件 |
| [Agent 开发指令](mihuanyuantu-v2/DEV_INSTRUCTIONS.md) | 阶段划分与依据路径；引用根目录职责文件 |
| [移交 handoff](../handoff.md) | 仓库根；新会话一分钟接手 |
| [约束锚点 anchor](../anchor.md) | 仓库根；现行业务/实现边界条目 |
| [检查点 checkpoint](../checkpoint.md) | 仓库根；可核实状态；非发布说明 |
| [HTML 原型](../prototype/README.md) | 离线交互原型；不等于后端已实现 |

## 现行裁决

| 文档 | 用途 |
|---|---|
| [grill-me 逻辑架构裁决](architecture_decisions/蜜獾原图-v2-grill-me逻辑架构裁决-2026-11-04.md) | 2026-11-04 LocalDisk / 首期 / 积分与角色 |
| [继续使用 Gemini Vision](architecture_decisions/蜜獾原图-v2-继续使用Gemini-Vision最终检测-2026-11-02.md) | 2026-11-02 生产检测器确认 |
| [自动重做与统一生成历史](architecture_decisions/蜜獾原图-v2-自动重做与统一生成历史裁决-2026-10-25.md) | FR-026 / 历史页确认 |
| [设备预设原型导入](architecture_decisions/蜜獾原图-v2-设备预设原型导入裁决-2026-10-25.md) | 405 条预设导入口径 |
| [架构设计裁决](architecture_decisions/蜜獾原图-v2-架构设计裁决与交接-2026-10-23.md) | 经济起步与实现边界 |
| [审计整改裁决](architecture_decisions/蜜獾原图-v2-审计整改裁决-2026-10-23.md) | PRD 审计后有效裁决 |
| [生产物料编制口径](architecture_decisions/蜜獾原图-v2-生产物料清单编制口径-2026-10-23.md) | 物料口径演进结论 |
| [旧版复用材料提取](architecture_decisions/蜜獾原图-v2-旧版复用材料提取交接-2026-10-23.md) | 405 条预设等提取范围 |
| [本地仓库整理](architecture_decisions/蜜獾原图-v2-本地仓库整理-2026-10-24.md) | Git 忽略与行尾约定 |

原始输入在仓库根目录 `输入材料/`；生产凭据在 `生产物料/`（Git 忽略）。改原型主脚本后执行 `node prototype/sync-inline.js`。
