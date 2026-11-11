# 蜜獾原图 v2 · 检查点

时区：Asia/Shanghai。本文件只记录**当前可核实状态**；不是发布说明，也不等同生产验收。

## 0. 每次会话必填（最小集）

| 字段 | 当前值 |
| --- | --- |
| updated | 2026-11-11 CST（Asia/Shanghai） |
| branch | `cursor/remain-gap-w1-9973` |
| HEAD | `df92b8a` · PR [#47](https://github.com/nancywrayg57-jpg/mihuanyuantu-v2/pull/47) · 基线 `main`=`f86b6af`（#46） |
| 文档态 | PRD **2.10**；架构 **1.7**；S7 **BLOCKED**；Web 登录入口见 `WEB_LOGIN_ENTRY.md` |
| 代码态 | REMAIN W1：R1 底座旁路关闭 + R2 资源库服务端分页；R3–R8 未做；R4 待管理员选 A/B |
| 验证态 | `/tmp/remain-gap-e2e.log`：`REMAIN_GAP_W1_PASS=true`；`R1_AUTH_BYPASS_CLOSED_PASS=true`；`R2_ASSET_SERVER_PAGE_PASS=true`；`R9_S7_BLOCKED=true`；`production_billing=false`；`R4_NEEDS_ADMIN_CHOICE=true` |
| 当前阶段 | REMAIN-GAP-PLAN-2026-11-11 · **W1**（端测绿，待 PR / 非作者 Owner squash） |
| 下一步 | 推 W1 PR；**不得**自评自合；**不得**开 S7；R4 等管理员书面选路径 A 或 B；W2+ 未授权不抢跑 |

## 1. 约束说明

- R1：`rp_*` 岗位调 `POST /api/v1/auth/login` → 403 `AUTH_CAPTCHA_REQUIRED`；合法入口 `/api/v1/realphotos/auth/*`。
- R2：`GET /api/v1/realphotos/assets?page=&pageSize=` 默认 20，最大钳制 100，返回 `items`+`total`；前端按页请求。
- R4：`[NEEDS CLARIFICATION]` 路径 A（`guard_epoch`/`ACCOUNT_SPEND_BUSY`）或 B（改合同承认 `copy_latch_*`）——**禁止本会话私自选**。
- R9：`R9_S7_BLOCKED=true`；`production_billing=false`；不部署、不改 Secrets、不打生产 Tag。
- 继承 #46：G1–G5 已在 main；本单不重复 captcha/锁图/batch20/outbox/OpenAPI 可达；不重做 FR-025；不改 `PASS_SCORE`。

## 2. 阶段状态（摘要）

| 阶段 | 状态 |
| --- | --- |
| REMAIN-GAP W1（R1+R2） | 端测 PASS；待 PR 合入 |
| REMAIN-GAP W2（R3+R4） | 未开工；R4 待管理员裁决 |
| PRODUCT-GAP-FIX | 已合入 #46 |
| FIVE-LAYER-PHYS-TUNE | 已合入 #44 |
| MODEL-API-CONFIG | 已合入 #43 |
| S7 | **`R9_S7_BLOCKED=true`；须管理员书面授权** |
