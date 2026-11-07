# 蜜獾原图 v2 · 检查点

时区：Asia/Shanghai。本文件只记录**当前可核实状态**；不是发布说明，也不等同生产验收。

## 0. 每次会话必填（最小集）

| 字段 | 当前值 |
| --- | --- |
| updated | 2026-11-07 CST（Asia/Shanghai） |
| branch | `cursor/align-gap-a5bc-9973`（基线 `origin/main`=`7017443`，已含 #29/#30） |
| HEAD | `61e3a8a` 已推送；PR #31 待审合 |
| 文档态 | PRD **2.10**；架构 **1.7**；`s5_exited=true`；`nd020_021_archived=true`；S7 未开 |
| 代码态 | ALIGN-GAP-A5BC G1–G8：五层归档、输出到期清理、OpenAPI 离线制品、geocoder 预留、版本矩阵 accepted_risk、fixed GPS 诚实、生图尺寸审计、IA_C6 方案 B。未接通 URL 真导入；非生产收费 |
| 验证态 | `/tmp/align-gap-a5bc-e2e.log` `ALIGN_GAP_A5BC_E2E_PASS`；`ND020_021_ARCHIVE_PASS`；`output_cleanup=ok`；`geocoder_mode=reserved`；`version_align=accepted_risk`；`honesty=no_silent_none`；`size_audit=ok`；`IA_C6=mitigated_with_ops_note`；`production_billing=false` |
| 当前阶段 | ALIGN-GAP-A5BC 已开 PR #31，待非作者 Owner squash |
| 下一步 | Owner 审合 #31；不得开 S7 |

## 1. 仓库与文档基线

| 项目 | 值 |
| --- | --- |
| 仓库 | `https://github.com/nancywrayg57-jpg/mihuanyuantu-v2.git` |
| 文档工作区 | `docs/mihuanyuantu-v2/` |
| 现行 PRD | `docs/蜜獾原图-v2-PRD-v2.0.md`（document_version **2.10**） |
| 项目架构 | `docs/蜜獾原图-v2-项目架构-v1.0.md`（version **1.7**） |
| Agent 开发指令 | `docs/mihuanyuantu-v2/DEV_INSTRUCTIONS.md` |
| 根目录职责文件 | `AGENTS.md`、`handoff.md`、`anchor.md`、`checkpoint.md` |

## 2. 阶段状态（摘要）

| 阶段 | 状态 |
| --- | --- |
| S0–S6 | 既有证据；非生产收费 |
| PRODUCT-GAP-A / PRESET-BULK | 已合入 `origin/main`（#29/#30） |
| OPS-QUALITY-D | D1 已吸收进 ALIGN G8；D2 本地 PASS |
| ALIGN-GAP-A5BC | G1–G8 本地 PASS；**未推送** |
| S7 | **须管理员确认** |

过程进度：`docs/mihuanyuantu-v2/progress.yaml`。
