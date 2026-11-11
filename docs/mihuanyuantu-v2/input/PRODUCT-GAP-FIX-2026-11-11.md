# 蜜獾原图 v2 · 任务工单

| 字段 | 内容 |
| --- | --- |
| 工单编号 | PRODUCT-GAP-FIX-2026-11-11 |
| 创建日期 | 2026-11-11 |
| 修订 | 2026-11-11：G6（FR-025）降级为**仅回归**——计量已由 MODULE-A A2 交付，本单不再重做实现 |
| 范围 | **开发五项**：FR-001 登录验证码、FR-006 锁图执法、FR-028/AC-002 本地≤20 批量上传、FR-023 消息 outbox/可重试投递（含 AD-001 最小独立消费）、FR-033 对外 OpenAPI 可达。**回归一项**：FR-025 运营成本（不新开功能） |
| 不做 | **S7 本工单不纳入**；**不重做 FR-025 调用时计量/成本汇总实现**；生产收费（`production_billing=false`）；OSS 真切换；正式 ND-012 供应商冒充；ZIP；改 `PASS_SCORE`；复制门闩合同形重写（§6.2 / AD-005）；AD-009 全量生成 SDK（本单仅 FR-033 可达性）；架构 front-matter 大修；自评自合 PR；清空业务库 |
| 依据 | PRD 2.10：FR-001 / ND-001 / FR-006 / AC-003–004 / FR-028 / AC-002 / FR-023 / FR-033 / AC-024；（FR-025 / AC-015 仅回归引用）架构 1.7：AD-001、§7 outbox、§9.2.1；`MODULE-A-GAP-2026-11-10` A2；`AGENTS.md` |
| 管理员裁决（本工单） | ① **必须端测通过**并留证据才可标完成；② **S7 不做**；③ **FR-025：不再开发**——承认 MODULE-A `A2_cost_metering: done_e2e_pass`；侧聊「成本 deferred/空」多为无单价时的合同内空态，不是缺实现；G6 只做回归冒烟；④ 消息路径采用 **outbox + 可独立启动的投递消费**，不做完整多机拓扑 |
| 验证环境 | 开发机（`hbs@192.168.19.128`）FE `3000` / API `38000` + PostgreSQL + worker；证据 `/tmp/product-gap-fix-e2e.log` |
| 分支约定 | `cursor/product-gap-fix-9973`（Collaborator）；合入仅非作者 Owner squash |

---

## 0. 开干前硬约束

1. 权威顺序：PRD → 架构 → 本工单 → `DEV_INSTRUCTIONS.md`；冲突停问，禁止发明需求。
2. 密钥只读同级 `生产物料/` / 本机 `.env`；禁止入库。
3. **开发项** G1–G5 须有：修复项 / 如何修复 / 预期结果 / 端测断言；G6 仅回归清单，**禁止**借机重写 `provider_usage` 或改成本口径。
4. **不得开 S7**；不得宣称生产收费就绪；不得改检测门槛刷分。
5. 改动落在 `aojuai-main` realphotos 能力与相关前端页；不扩到未点名系统。
6. 主会话编码完成后**自行按物料 SSH 开发机端测**；Cloud 不可替代 PostgreSQL/`claim_one` 类项。

---

## 1. 任务总览

| ID | 类型 | 修复项 | 优先级 | 端测标记（建议） |
| --- | --- | --- | --- | --- |
| G1 | 开发 | FR-001 Web 登录验证码路径 | P0 | `G1_LOGIN_CAPTCHA_PASS` |
| G2 | 开发 | FR-006 提交处理强制校验图片锁 | P0 | `G2_IMAGE_LOCK_ENFORCE_PASS` |
| G3 | 开发 | FR-028/AC-002 本地多文件 + 服务端 20 硬限 | P0 | `G3_UPLOAD_BATCH20_PASS` |
| G4 | 开发 | FR-023 消息 outbox + 可重试投递（AD-001 最小） | P1 | `G4_MSG_OUTBOX_PASS` |
| G5 | 开发 | FR-033 对外 OpenAPI 可达（制品+入口） | P1 | `G5_OPENAPI_REACHABLE_PASS` |
| G6 | **仅回归** | FR-025 运营成本（MODULE-A A2 已交付） | — | `G6_OPS_COST_REGRESSION_PASS` |
| — | 排除 | S7 | **排除** | `S7_OUT_OF_SCOPE=true` |

总通过标记：`PRODUCT_GAP_FIX_E2E_PASS=true`（**G1–G5 均 PASS** + **G6 回归 PASS** + `S7_OUT_OF_SCOPE=true`）。

---

## 2. 任务明细

### G1 · FR-001 Web 登录接到 realphotos 验证码路径

| 字段 | 内容 |
| --- | --- |
| 修复项 | Web 登录须用户名 + 密码 + **随机验证码**；会话 30 天；后端不得省略（ND-001 / PG-001） |
| 当前现状 | 后端已有 `/api/v1/realphotos/auth/challenges` 与配套 login；前端 `login-client.tsx` / `auth-api.ts` 走底座 `/api/v1/auth/login`，**无验证码** |
| 如何修复 | 1）前端登录页改为：先拉 challenge → 展示验证码图/文本 → 提交用户名/密码/challenge_id/captcha 到 **realphotos** 登录路由（勿再直打底座无验证码 login）。2）确认成功响应写入与现会话一致的 cookie/JWT，TTL 对齐 30 天。3）错误码区分：验证码错误 / 密码错误 / 锁定；密码连续 5 次错误锁定逻辑若已在 realphotos 侧则复用，勿与 FR-006 预审冻号计数混用。4）单测或契约测覆盖「无 captcha 拒绝」「错误 captcha 拒绝」「正确路径成功」。 |
| 预期结果 | 浏览器登录必须过验证码；无验证码或错码无法拿会话；正确验证码可登录且会话可用；端测日志含 `G1_LOGIN_CAPTCHA_PASS` |
| 端测要点 | 开发机：错误 captcha → 401/422；正确 captcha → 200 且后续带会话可访问商家页；抓包/日志证明未绕过 challenges |

---

### G2 · FR-006 处理提交强制校验 `RealphotosImageLock`

| 字段 | 内容 |
| --- | --- |
| 修复项 | 同图二次预审失败后锁图；锁定图**不可再进入处理**（AC-003）；申诉不自动解锁 |
| 当前现状 | `s6_ops` 可写入 `RealphotosImageLock`；`s1_processing` 提交路径**未查询锁**，锁定图仍可能入队 |
| 如何修复 | 1）在处理提交（单张与批量）入口，按 `tenant_id` + `owner_account_id` + `image_identity`（与锁表一致）查询未删除锁。2）命中则拒绝提交，明确错误（如 `IMAGE_LOCKED`），**不冻结积分、不入队**。3）资源库/处理页对锁定资源展示「图片锁定」态，隐藏或禁用「去处理」。4）补测：制造二次预审失败 → 有锁行 → 再提交应拒；未锁定图仍可提交。5）不在本工单改账号冻结 streak 全链路（若已有则保持）。 |
| 预期结果 | 锁定图提交 100% 被拒；未锁定图行为不变；端测 `G2_IMAGE_LOCK_ENFORCE_PASS` |
| 端测要点 | DB 插入或真实二次失败产生锁 → `POST` 处理返回业务错误 → 无新 `execution_job` / 无新冻结 |

---

### G3 · FR-028 / AC-002 本地多文件上传 + 服务端 20 张硬限

| 字段 | 内容 |
| --- | --- |
| 修复项 | 本地上传支持单次最多 20 张；第 21 张起**整批拒绝**；硬校验同 FR-003 |
| 当前现状 | 资源库上传控件基本单文件；无「20 张一批」服务端硬闸 |
| 如何修复 | 1）前端资源库「本地上传」：`input multiple`，一次可选多文件；UI 在选超 20 时本地拦截并提示。2）后端提供批量上传接口或现有上传接受多文件：`len(files) > 20` → **整批 413/422**，已收文件不入库。3）`1…20` 张逐张硬校验（格式/大小/像素等）；单张非法时按现行合同（整批拒或逐张失败——**以实现与 PRD AC-002「超 20 整批拒」为准**；单张非法保持与现单文件行为一致并在证据写明）。4）成功张写入资源库，列表可见。5）**本工单不强制改服务端分页**（另项）；若顺手不破坏现列表即可。 |
| 预期结果 | 20 张内可批量入库；21 张整批拒绝且库无部分脏写；端测 `G3_UPLOAD_BATCH20_PASS` |
| 端测要点 | 造 20 张小 JPEG 上传成功计数=20；21 张请求被拒且 DB 无新增；单文件路径回归仍通 |

---

### G4 · FR-023 消息 outbox + 可重试投递（AD-001 最小）

| 字段 | 内容 |
| --- | --- |
| 修复项 | 站内消息首次投递失败后最多自动重试 3 次；补发不重跑任务、不重复扣费；投递与业务写路径可恢复 |
| 当前现状 | 业务路径多直接写 inbox；无 outbox / `notification_attempt` 消费；失败易丢通知 |
| 如何修复 | 1）引入（或启用已有）`outbox`/`notification` 表字段：payload、接收账号、租户、状态、`attempt_count`、`next_attempt_at`。2）业务事务内**只写 outbox**（或同事务写 outbox + 业务），不在业务路径「直接成功算投递完成」。3）独立消费入口：`realphotos_notify_worker`（或等价 CLI/systemd 单元名）轮询认领 outbox → 写入 inbox → 标记 sent；失败则 `attempt_count+1`，指数/固定间隔重试，**上限 3 次**后标 dead 并可运营可见。4）「补发」API：对已有通知再投一次，不创建新处理任务、不碰积分。5）图片 heartbeat **可不再兼任**唯一投递路径；至少提供可单独启动的投递进程入口以满足 AD-001 最小要求（完整多机拓扑本单不做）。 |
| 预期结果 | 模拟投递失败可见重试直至成功或 3 次耗尽；补发不扣费；端测 `G4_MSG_OUTBOX_PASS` |
| 端测要点 | 注入失败钩或临时坏写入 → 观察 attempt 递增；成功后 inbox 可读；补发前后 ledger 无额外冻结/消费 |

---

### G5 · FR-033 对外 OpenAPI 可达（制品版本化 + 对接入口）

| 字段 | 内容 |
| --- | --- |
| 修复项 | 客户业务 API（`X-API-Key` + `image_processing`）具备**可对接的 OpenAPI 制品**与明确获取入口（AC-024）；不只依赖 DEBUG 在线文档 |
| 当前现状 | 仓库有 `contracts/realphotos_image_processing.openapi.json` 与对接说明；生产常关在线 OpenAPI；商家侧缺少稳定「规范入口」 |
| 如何修复 | 1）固化版本化制品：合同 JSON 带 `info.version`；对接说明指向固定相对路径与版本号。2）商家「业务 API 凭证」页（或系统帮助区）增加：**下载/查看本平台 image_processing OpenAPI**（静态托管或鉴权后下载仓内制品），文案写明鉴权头与 scope。3）核对实现路径与 OpenAPI 一致（以现网 `/assets` 等为准时，**改文档/制品对齐实现**，本单不强制改名为 `/resources`）。4）回归：仅 Key、无会话可走上传→处理→查询→下载（沿用既有 B1 证据思路，复跑一条最短路径）。5）**不做** AD-009 全量前端 generated SDK。 |
| 预期结果 | 登录商家可从产品内拿到规范；制品版本可核对；Key 主路径仍通；端测 `G5_OPENAPI_REACHABLE_PASS` |
| 端测要点 | HTTP 下载制品 200 且含 `image_processing`/`X-API-Key`；无会话 Key 冒烟 PASS；日志记录制品 version |

---

### G6 · FR-025 运营成本 — **仅回归（不开发）**

| 字段 | 内容 |
| --- | --- |
| 类型 | **回归验收**，不是本工单开发项 |
| 为何不重做 | MODULE-A-GAP 任务 A2 已交付：`cap_realphotos_provider_usage` 调用时计量、`ops_cost_summary`、工作台 `opsMetrics.cost`/`costReason`；`progress.yaml` 已标 `A2_cost_metering: done_e2e_pass`。无 `REALPHOTOS_UNIT_COSTS_JSON` 时 `cost=null` +「暂无上游单价」属**合同内诚实空态**，曾被侧聊误判为缺口 |
| 禁止动作 | 禁止新建第二套成本表/汇总；禁止用客户积分倒推成本；禁止为「看起来有数」写假金额；禁止借回归大改 `provider_usage.py` 口径（若发现真回归缺陷，另开缺陷单） |
| 回归步骤 | 1）确认表与服务仍在：`RealphotosProviderUsage` / `record_call` / `ops_cost_summary`。2）读管理员工作台 API：`opsMetrics` 含 `cost`、`costReason`（及已知的 `costKnownAmount`/`costUnknownCount` 若有）。3）前端 `costCell`：有数显示金额；`unit_price_missing` / `no_upstream_calls` 等显示诚实文案，**不得显示假 0**。4）日志引用既有证据路径（如 `/tmp/module-a-gap-e2e.log` 中 `A2_COST_METERING_PASS`）并本次冒烟复检。 |
| 预期结果 | 回归通过即 `G6_OPS_COST_REGRESSION_PASS=true`；**不**产出新的成本功能 PR  diff（除非冒烟失败且确认为本分支误伤，仅恢复既有行为） |
| 端测要点 | 工作台成本块结构存在；无单价时非假 0；证据写 `G6_NO_REIMPLEMENT=true` |

---

## 3. 明确排除 / 已交付不重做（写入证据）

| ID | 项 | 裁决 |
| --- | --- | --- |
| OUT-S7 | 部署清单 / systemd / Nginx / 上线证据包 | **本工单不纳入**；日志强制 `S7_OUT_OF_SCOPE=true` |
| OUT-BILLING | 生产收费 | `production_billing=false` |
| REUSE-FR025 | FR-025 调用时计量与工作台成本块 | **已由 MODULE-A A2 交付**；本单仅 G6 回归；日志 `G6_NO_REIMPLEMENT=true` |
| OUT-COPY-GUARD | §6.2 `guard_epoch` / `ACCOUNT_SPEND_BUSY` 合同形对齐 | 另单 |
| OUT-AD009-SDK | OpenAPI → 前端 generated SDK | 另单；本单仅 G5 可达性 |
| OUT-PAGINATION | 资源库服务端分页 | 另单（本单 G3 只做批量上传硬限） |
| OUT-OSS | OSS 适配器真实现 | 首版不做 |

---

## 4. 端测脚本要求（开发机必跑）

证据文件：`/tmp/product-gap-fix-e2e.log`（追加写入，含时间戳与 git SHA）。

最低用例：

1. **G1**：challenge → 错码失败 → 正码登录 → 会话访问受保护页。
2. **G2**：锁定资源提交处理被拒；未锁资源可提交（可用 fixture 锁行）。
3. **G3**：20 张上传成功；21 张整批拒；抽查 DB 计数。
4. **G4**：outbox 失败重试至成功或 3 次耗尽；补发前后积分不变。
5. **G5**：制品可下载；Key 无会话最短处理路径冒烟。
6. **G6（回归）**：工作台 `opsMetrics` 成本块可读；无单价时非假 0；记录 `G6_NO_REIMPLEMENT=true`（可引用 MODULE-A 证据，但须本次复检）。
7. 结尾打印：

```text
S7_OUT_OF_SCOPE=true
G6_NO_REIMPLEMENT=true
G1_LOGIN_CAPTCHA_PASS=true|false
G2_IMAGE_LOCK_ENFORCE_PASS=true|false
G3_UPLOAD_BATCH20_PASS=true|false
G4_MSG_OUTBOX_PASS=true|false
G5_OPENAPI_REACHABLE_PASS=true|false
G6_OPS_COST_REGRESSION_PASS=true|false
PRODUCT_GAP_FIX_E2E_PASS=true|false
```

**退出准则**：G1–G5 开发项均为 `true`，G6 回归为 `true`，且 `S7_OUT_OF_SCOPE=true`、`G6_NO_REIMPLEMENT=true`，才可标本工单完成；任一失败则返修（G6 失败只修回归缺陷，不重开计量方案），不得开 S7。

---

## 5. 交付与合入

1. 功能分支：`cursor/product-gap-fix-9973`；PR 标题建议：`fix(realphotos): product gap G1–G5 (captcha, lock, upload20, outbox, openapi)`（**勿**写成重做 cost）。
2. PR 描述引用本工单编号、端测日志路径，并注明 **FR-025 = regression only / MODULE-A A2**。
3. CI：密钥扫描 + 相关单测；全量存量 ruff/pytest 失败不得假装已绿。
4. 合入：仅 Owner 在非本人作者 PR 上 squash；Collaborator 不合并、不打 Tag、不部署。
5. 完成后回写：`docs/mihuanyuantu-v2/progress.yaml`、`wiki.md`、必要 checkpoint；**不**启动 S7；进度中 FR-025 保持已交付/回归通过，不写成「本单新完成计量」。

---

## 6. 回滚要点

- G1 若会话体系异常：可紧急开关回底座登录**仅作运维止血**，但不得在未改合同前标 FR-001 完成。
- G3 批量上传：保留单文件 API 兼容。
- G4 outbox：消费进程可停；未 sent 消息留表可补发，禁止清库「修复」。
- G6：无新功能可回滚；若本分支误伤成本 API，恢复 MODULE-A 行为即可。

---

## 7. 完成定义（DoD）

- [ ] G1–G5 开发合入目标分支（或已开 PR 且端测绿）
- [ ] G6 仅回归通过（`G6_OPS_COST_REGRESSION_PASS` + `G6_NO_REIMPLEMENT`）
- [ ] `/tmp/product-gap-fix-e2e.log` 含 `PRODUCT_GAP_FIX_E2E_PASS=true`
- [ ] 日志含 `S7_OUT_OF_SCOPE=true`
- [ ] 进度文件已更新；未宣称 S7/生产收费完成；未把 FR-025 记成「本单新实现」
