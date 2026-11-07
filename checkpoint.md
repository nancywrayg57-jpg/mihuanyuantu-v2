# 蜜獾原图 v2 · 检查点

时区：Asia/Shanghai。本文件只记录**当前可核实状态**；不是发布说明，也不等同生产验收。

## 0. 每次会话必填（最小集）

| 字段 | 当前值 |
| --- | --- |
| updated | 2026-11-07 CST（Asia/Shanghai） |
| branch | `cursor/partial-align-9973`（基线含 blocking-fix tip `d58a86a`；`origin/main` 仍为 `ad9ebf5`/#25） |
| HEAD | 以推送后该分支 tip 为准；合入仅经 PR squash，禁止直推 `main` |
| 文档态 | PRD **2.10**；架构 **1.7**；`DEV_INSTRUCTIONS` §10.7 S5 `exit_evidence` 已齐并收口 |
| 代码态 | PARTIAL-ALIGN A–F：客户预审默认 live/unconfigured；运营指标真实聚合（cost 诚实空态）；目录选择器+降级；405 导入浏览；三 GPS 模式运营可见；菜单缓存进程内 bump；`s5_exited=true`。阻断级能力仍在本分支祖先。不是生产收费已开放 |
| 验证态 | `/tmp/partial-align-e2e.log` `PARTIAL_ALIGN_E2E_PASS` 且 `production_billing=false`；浏览器 `/tmp/partial-align-browser.txt`；`/tmp/s5-pg-e2e.log` 仍绿；URL 导入仍未接通；不得开 S7 |
| 当前阶段 | S5 退出已收口（非生产收费）；S6 管理员已结束；PARTIAL-ALIGN 开发机端测已通过，待 Owner 审 PR |
| 下一步 | 推送并开 `cursor/partial-align-9973` PR；若 #27 未合须在 PR 声明依赖；仅非作者账号 squash；不得开 S7 |

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
| S0–S4 | 开发机证据在案；非生产收费 |
| S5 | **`s5_exited=true`**（`/tmp/s5-pg-e2e.log`；`supplier_connected=false`；`production_billing=false`） |
| S6 | 管理员结束；`s6_exited` 未靠重跑改写 |
| PARTIAL-ALIGN | A–F 端测 PASS；待 PR 合入 |
| S7 | **须管理员确认** |

过程进度：`docs/mihuanyuantu-v2/progress.yaml`。
