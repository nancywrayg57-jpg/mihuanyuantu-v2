# 蜜獾原图 v2 · 检查点

时区：Asia/Shanghai。本文件只记录**当前可核实状态**；不是发布说明，也不等同生产验收。

## 0. 每次会话必填（最小集）

| 字段 | 当前值 |
| --- | --- |
| updated | 2026-11-11 CST（Asia/Shanghai） |
| branch | `cursor/product-gap-fix-9973` |
| HEAD | （推送前见 git；合入前以 PR 为准） |
| 文档态 | PRD **2.10**；架构 **1.7**；S7 未开 |
| 代码态 | PRODUCT-GAP-FIX G1–G5 已实现；G6 仅回归；FR-025 未重做 |
| 验证态 | `/tmp/product-gap-fix-e2e.log`：`PRODUCT_GAP_FIX_E2E_PASS=true`；`S7_OUT_OF_SCOPE=true`；`G6_NO_REIMPLEMENT=true`；G1–G6 分项均为 true |
| 当前阶段 | PRODUCT-GAP-FIX-2026-11-11（端测绿，待 Owner 合入） |
| 下一步 | 开/更新 PR；非作者 Owner squash；不得开 S7；不得把 FR-025 写成「本单新实现」 |

## 1. 约束说明

- G1：Web 登录必须 captcha → `/api/v1/realphotos/auth/*` + cookie 会话 30 天 refresh。
- G2：提交前查 `RealphotosImageLock`；命中 `IMAGE_LOCKED`，无冻结/无入队。
- G3：`POST /assets/batch`；`len>20` → `UPLOAD_BATCH_REJECTED` 整批拒。
- G4：业务只写 outbox；`python -m scripts.run_realphotos_notify_worker`；最多 3 attempt；补发不扣费。
- G5：鉴权下载仓内 OpenAPI 制品；商家 API 凭证页入口。
- G6：仅回归 `opsMetrics.cost`；禁止改 `provider_usage` 口径。

## 2. 阶段状态（摘要）

| 阶段 | 状态 |
| --- | --- |
| PRODUCT-GAP-FIX | 端测 PASS；待 PR 合入 |
| FIVE-LAYER-PHYS-TUNE | 已合入 #44 |
| MODEL-API-CONFIG | 已合入 #43 |
| S7 | **须管理员确认；本工单不纳入** |
