# FIX-FAILURE-RATE-TECH 约束与冲突台账（执行前）

工单：`FIX-FAILURE-RATE-TECH-2026-11-08`（Desktop 附件原文）  
记录时刻：2026-11-08  
目的：先识别矛盾/歧义/前置条件缺失，禁止私自调和。

## C1 · 已核实事实（相对仓库）

| ID | 事实 | 原文/证据 |
| --- | --- | --- |
| F-PR36 | PR #36 已 `MERGED`（`f50f26e`），工单表头仍写「待非作者 squash」→ **过时** | `gh pr view 36` state=MERGED；工单 §表头「关联」 |
| F-BASE | 本单从 `origin/main` tip `f50f26e` 新开 `cursor/fix-failure-rate-remain-9973` | 工单「分支约定：可在现分支续作，或新开 …remain-9973」 |
| F-SINGLE | 商家「单张」入口 = 资源库「去处理」→ `/realphotos/batch?assetIds=`；**无独立单张处理页** | `library/page.tsx` `goProcess`；工单 R4「若走 library…」 |
| F-LAN | 先前 Cloud 沙箱内探测 LAN **Network is unreachable**；**操作员确认本机即开发机**（`hostname -I` 含 `192.168.19.128`） | 工单 R6；用户 2026-11-08「本机就是开发机」 |
| F-PASS75 | 禁止改 `PASS_SCORE=75` | 工单 §0.4；R1「禁止修改 PASS_SCORE」 |
| F-NOGPSFAKE | 禁止伪造 GPS / 静默改 gpsMode | 工单 §3；PRD 诚实失败 |

## C2 · 矛盾 / 冲突（不自行调和）

| ID | 冲突 | 处理 |
| --- | --- | --- |
| X1 | 工单要求 R6 开发机 Worker+API；沙箱曾误判不可达 | **已闭合**：本机 PG `claim_one` 任务 158 `gpsMode=none` DELIVERED；`R6_E2E_PASS` |
| X2 | 全绿才可合入 vs 先开 PR | **已闭合**：`MERGE_READY=True`；仍禁止自评自合，仅非作者 Owner squash |
| X3 | R1 需 gemini 全任务状态 | **已闭合**：本机 SQLite+Worker `detection_mode=gemini`×3，含 status/failureMessage/gate |

## C3 · 歧义（按工单默认裁决，不发明产品）

| ID | 歧义 | 工单默认 | 本执行采取 |
| --- | --- | --- | --- |
| A1 | R4 fixed 无坐标：软提示可提交 vs 硬拦 | 「本条默认保持 skip+提示」 | skip+提示；不改后端 skip 政策 |
| A2 | R3 `MAKERNOTE_WRITE_FAILED` 是否可重试 | 「建议与 EXIF 同属可技术重试；改前看积分冻结语义」 | 纳入 `_RETRYABLE_FAILURES`（与 `EXIF_WRITE_FAILED` 同路径 `_hold_technical`/held） |
| A3 | R2 缺字段：拒保存 **或** 拒启用 | 「拒绝保存或拒绝启用」 | **两者**：缺字段拒保存；已有行若启用且缺字段也拒 |

## C4 · 前置条件

| 条件 | 状态 |
| --- | --- |
| F1–F6 不重复实现 | 遵守；仅索引 |
| `生产物料` | 仓内 gitignore 路径存在；口令不入库不外泄 |
| Gemini Key（本地 `.env`） | 存在，仅用于 R1 本地 detect 对齐；不打印 |
| 开发机 | **本机即是**；R6 已用本机 PG Worker 留证 |

## C5 · 禁止项复述（硬）

- 不把 `PASS_SCORE` 从 75 改低  
- 不伪造 GPS  
- 不提交密钥  
- 不直推 `main`  
- 不开 S7  
- 不自评自合  
- Cloud 单测 ≠ 本单端测（但本单允许/要求 pytest 作为 R6 第 3 条组成部分）
