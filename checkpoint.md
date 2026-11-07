# 蜜獾原图 v2 · 检查点

时区：Asia/Shanghai。本文件只记录**当前可核实状态**；不是发布说明，也不等同生产验收。

## 0. 每次会话必填（最小集）

| 字段 | 当前值 |
| --- | --- |
| updated | 2026-11-07 CST（Asia/Shanghai） |
| branch | `cursor/product-gap-a-9973`（基线 `origin/main`=`922ef06`，已含 #27/#28） |
| HEAD | 以推送后该分支 tip 为准；合入仅经 PR squash，禁止直推 `main` |
| 文档态 | PRD **2.10**；架构 **1.7**；`s5_exited=true`；S7 未开 |
| 代码态 | PRODUCT-GAP-A：A2 `SEED_UNSUPPORTED`；A3 预设 AI 正/负向提示词；A4 `phone/dslr/mirrorless/action`（`camera`→`dslr`）；A5 延后 `cost=null`；A6 站内信 30 天清理；A7 旧预设激活+MakerNote（管理员 2026-11-07 允许写入）；A8 开发机真浏览器 DOM。未接通 URL 真导入；非生产收费 |
| 验证态 | `/tmp/product-gap-a-e2e.log` `PRODUCT_GAP_A_E2E_PASS` 且 `production_billing=false` `url_import_connected=false`；浏览器 `/tmp/product-gap-a-browser.txt` `PRODUCT_GAP_A_BROWSER_PASS`；截图 `/tmp/product-gap-a-browser-shots/`；不得开 S7 |
| 当前阶段 | S5 已退出收口；S6 管理员已结束；PRODUCT-GAP-A 开发机端测+浏览器冒烟已通过，待 Owner 审 PR |
| 下一步 | 审阅 https://github.com/nancywrayg57-jpg/mihuanyuantu-v2/pull/29 ；仅非作者账号 squash；不得开 S7；A5 仍延后 |

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
| BLOCKING-FIX / PARTIAL-ALIGN | 已合入 `origin/main`（#27/#28 → `922ef06`） |
| PRODUCT-GAP-A | A2–A4/A6–A8 端测+浏览器 PASS；A5 延后；待 PR 合入 |
| S7 | **须管理员确认** |

过程进度：`docs/mihuanyuantu-v2/progress.yaml`。
