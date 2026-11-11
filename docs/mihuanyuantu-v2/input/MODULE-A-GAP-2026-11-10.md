# 蜜獾原图 v2 · 任务工单

| 字段 | 内容 |
| --- | --- |
| 工单编号 | MODULE-A-GAP-2026-11-10 |
| 创建日期 | 2026-11-10 |
| 范围 | 对照 PRD 2.10「A. 功能需求未完成 / 仅占位」收口：URL 联调导入、运营成本调用时计量、结果/消息定时清理；澄清项登记 |
| 不做 | S7；生产收费（`production_billing=false`）；正式外部导入供应商采购冒充；AC-009 随机种子（本工单跳过）；OSS 真切换；外部 geocoder 启用；自评自合 PR；清空业务库；改 `PASS_SCORE` |
| 依据 | PRD FR-028/003/019/025；AC-002/015/023；ND-012/033；架构 1.7（`rp_provider_usage`、LocalDisk）；物料清单 §4 临时图床；AGENTS.md |
| 管理员裁决（本工单） | ① URL：**临时图床允许联调**；② AC-009 种子：**跳过**；③ FR-025 成本：**调用时计量** |
| 验证环境 | 开发机本机（`192.168.19.128`）FE `3000` / API `38000` + PostgreSQL + worker；证据 `/tmp/module-a-gap-e2e.log` |
| 分支约定 | `cursor/module-a-gap-9973`（Collaborator）；合入仅非作者 Owner squash |

---

## 0. 开干前硬约束

1. 权威顺序：PRD → 架构 → `DEV_INSTRUCTIONS.md`；冲突停问。
2. 密钥只读同级/仓内 gitignore 的 `生产物料/`，禁止入库。
3. 临时图床仅联调：`http://47.85.47.252`（`POST /upload` → `GET /images/…`）。**不得**写成 ND-012 正式供应商已齐；合同行仍可标 `formalSupplier=false`，但须增加「联调图床已授权外呼」路径。
4. 成本计量**禁止**用客户积分倒推上游费用（架构 §模型调用量与成本）。
5. 端测通过并回写 `progress.yaml` / `checkpoint.md` 前，不得宣称本工单完成；不得开 S7。

---

## 跳过 / 澄清（写入证据，不实现）

| ID | 项 | 裁决 | 证据要求 |
| --- | --- | --- | --- |
| SKIP-AC009 | AC-009 / FR-010 随机种子 | **跳过**。`gpt-image-2` Images API 无 seed；仓库已 `gap-not-sent` + `SEED_UNSUPPORTED` | 日志写 `AC009_SKIPPED=true reason=gpt-image-2_no_seed` |
| CLAR-FR012 | FR-012 / ND-003 预审 | **本工单不改码**。预审已接百炼/`qwen3-vl-plus`；剩余属 ND-011 上线证据包，非接线缺口 | 日志写 `FR012_PRE_REVIEW_WIRED=true code_change=false` |
| OUT-OSS | 架构 OSS 适配器实现 | **首版不做**（LocalDisk 默认；OSS 仅预留接口） | 日志写 `OSS_IMPL_OUT_OF_SCOPE=true` |
| OUT-GEO | 外部 geocoder | **首版不做**（FR-008 仅预设 GPS；`NotConfiguredGeocoder` 保留） | 日志写 `GEOCODER_OUT_OF_SCOPE=true` |

---

## 任务 A1 · URL/JSON 导入联调（临时图床）

| 字段 | 内容 |
| --- | --- |
| 任务项 | 打通 FR-028 / FR-003 / AC-002 / AC-023 的 URL·JSON 导入**联调路径**：允许从临时图床拉取图片入库；上限与校验仍按 PRD |
| 当前现状 | `import_resources` 恒抛 `SERVICE_NOT_CONFIGURED`；`duty=import` 未启用；前端页提示「不外呼」；物料 T03 正式供应商仍缺，但管理员本工单授权临时图床联调 |
| 如何完成 | 见下方步骤 |
| 预期结果 | 联调 URL 可入库；101 条仍整单拒；业务 API Key 仍不可调导入；正式供应商未齐标记保留；端测 `A1_URL_IMPORT_STAGING_PASS` |

### 完成步骤

1. **合同/配置**
   - 更新 `duty=import`：provider 记为临时图床（如 `staging-image-host`），`base_url=http://47.85.47.252`，`capabilities` 含 `formalSupplier=false`、`stagingAllowed=true`（或等价键）。
   - `gap_note` 改为：「正式供应商 PENDING；管理员 2026-11-10 授权临时图床联调外呼，不得宣称 ND-012 正式闭合。」
   - 启用条件：管理员授权旗标（环境变量或合同 `enabled` + `stagingAllowed`），缺旗标则仍 `SERVICE_NOT_CONFIGURED`。

2. **后端拉图与入库**
   - 实现 `import_resources` / `import_resource_file`：解析三种输入（每行 URL、JSON 数组、JSON 文件）；计数 >100 → `INPUT_INVALID` 整单拒绝且不入库。
   - **仅允许**拉取：临时图床主机（`47.85.47.252`）上的 `http(s)://…/images/…`（或合同登记的 host allowlist）。**禁止**任意公网 SSRF。
   - 下载后走与本地上传同等硬校验：JPG/JPEG/PNG、≤20 MiB、≤40 MP、魔数/解码；失败逐条记原因，合格写入资源库（不建处理任务、不扣处理积分）。
   - JSON 字段顺序与必填语义按 FR-028（`name`/`sku`/`url`；`sku` 可空则生成 16 位内部编号）。
   - 文件名拼接与 `sku` 冲突规则按现有 `asset_naming`。
   - 运行中处理占用的资源禁删逻辑不变。

3. **前端**
   - `/realphotos/imports`：文案改为「联调图床可导入；正式供应商未齐」；支持粘贴文本 + JSON 文件上传（若 API 已有 `/resource-imports/files` 则接上）。
   - 成功展示入库条数/失败原因摘要；失败不假装「已导入」。

4. **安全**
   - 超时、大小上限、重定向策略写死；跟随重定向不得跳到 allowlist 外主机。
   - 审计：记录导入批次、操作账号、成功/失败计数；不写裸磁盘路径给客户。

### 端测（A1）

证据文件追加 `/tmp/module-a-gap-e2e.log`：

1. 无授权/未启用 → 仍 `SERVICE_NOT_CONFIGURED`，无外呼。
2. 启用联调后：先向临时图床 `POST /upload` 得一张可访问 URL（或使用物料已知样张 URL）。
3. 单条 URL 导入 → 资源库新增 1 条；`source` 含 import；可经网关读回；**不扣**处理积分。
4. JSON 数组 2 条（1 合法图床 URL + 1 allowlist 外 URL）→ 外链拒绝有原因；合法条入库或整批策略与实现文档一致（须在日志写明选定策略；推荐：逐条失败不影响其他条，除非 PRD 要求整单——PRD 对不合格为逐张拒绝合格继续，导入对齐该精神）。
5. 101 条 → `INPUT_INVALID`，库无新增。
6. `X-API-Key`（`image_processing`）调用导入 → 仍拒绝（FR-033 范围外）。
7. 标记：`A1_URL_IMPORT_STAGING_PASS`；`formal_supplier=false`；`production_billing=false`。

---

## 任务 A2 · 运营成本「调用时计量」（FR-025 / AC-015 / ND-033）

| 字段 | 内容 |
| --- | --- |
| 任务项 | 管理员工作台「成本」由空态升级为**基于上游调用记账**的真实数或诚实 UNKNOWN；禁止积分倒推 |
| 当前现状 | `opsMetrics.cost=null`，`costReason=no_upstream_invoice_ledger_v1`；`modelCalls`/`storageBytes` 已有；无 `rp_provider_usage` 表 |
| 如何完成 | 见下方步骤 |
| 预期结果 | 有调用则成本可汇总或标 UNKNOWN；无单价则不可用空态而非假 0；端测 `A2_COST_METERING_PASS` |

### 完成步骤

1. **数据模型**（对齐架构 `rp_provider_usage`）
   - 新增业务表（Alembic 业务链）：至少含 `duty`、`provider`、`model_id`、`config_version`、`tenant_id?`、`trace_id`/`request_id`、`units`、`unit_name`、`unit_cost`（可空）、`currency`、`amount`（可空）、`cost_status`（`known` / `unknown` / `unavailable`）、`created_at`、关联任务/尝试可选外键。
   - 不把上游 Key、完整签名 URL 写入该表。

2. **埋点（调用时）**
   - 在下列成功/失败可审计的上游出口写一行 usage（失败也可记 units=1、`cost_status=unknown`，按口径文档）：
     - 预审 `pre_review`
     - 生图 `generation`（按成功张或按请求，口径写进 wiki/证据）
     - 提示词优化 `prompt_opt`
     - 最终检测 `final_detection`（Gemini）
   - **不**为 fixture/未外呼路径记「已知费用」。

3. **单价来源**
   - 配置表或物料登记的「职责 × model → 单位成本」；本机可读、不入库密钥。
   - 有单价：`cost_status=known`，累加 `amount`。
   - 无单价：`cost_status=unavailable` 或 `unknown`；汇总时成本字段保持 `null` 并带 `costReason`（如 `unit_price_missing`），**禁止填 0 充数**。

4. **运营指标 API**
   - `opsMetrics.cost`：对 `known` 行求和；若期间仅有 unknown/unavailable → `null` + 明确 reason。
   - 可增加只读字段：`costKnownAmount`、`costUnknownCount`（可选，不破坏现有前端时可先只修 `cost`/`costReason`）。
   - 前端工作台：空态文案区分「暂无上游单价」与「尚无调用」。

### 端测（A2）

1. 迁移后空库：成本空态，非 0。
2. 触发至少一次 live 预审或 fixture 对照：fixture **不**增加 known 成本；live 调用增加 usage 行。
3. 配置测试单价后：再调一次 → `cost` 为可加总数字且等于 usage 之和。
4. 去掉单价：新调用不把历史 known 改成假 0；新行 status 正确。
5. 管理员可见；订单客服/商家 403。
6. 标记：`A2_COST_METERING_PASS`；证明未用积分余额倒推。

---

## 任务 A3 · 结果 / 消息到期清理入队（FR-019 / NFR-009）

| 字段 | 内容 |
| --- | --- |
| 任务项 | 处理结果 7×24h、站内消息 30 天到期后，除下载拒绝外，须有**可恢复的清理执行**（队列或等价调度），不只靠手工 HTTP |
| 当前现状 | `cleanup_expired_inbox` / `cleanup_expired_outputs` API 已有；`JOB_KIND_INBOX_CLEANUP` / `OUTPUT_CLEANUP` 常量存在；worker **不认领、不执行**这两类任务 |
| 如何完成 | 见下方步骤 |
| 预期结果 | 到期对象清理后不可下载；账本/审计保留；端测 `A3_CLEANUP_QUEUE_PASS` |

### 完成步骤

1. **入队**：提供安全的调度入口（管理员/系统 cron 调现有 cleanup API **或** `enqueue` cleanup job）；推荐 worker 认领 `inbox_cleanup` / `output_cleanup`。
2. **worker**：`claim` 的 `job_kinds` 纳入两类；`run` 调用现有 `cleanup_expired_*` 逻辑后 `complete_success`。
3. **语义**：过期结果下载仍拒；清理删对象副本，不删积分流水/检测摘要/任务摘要。
4. **可选**：开发机用短 TTL 夹具或把测试行 `expires_at`/`output_expires_at` 拨到过去再跑清理（禁止清生产客户数据；仅测库或显式测试租户）。

### 端测（A3）

1. 造一条已过期 inbox + 一条已过期 output（测库）。
2. 入队或触发 cleanup → worker 日志成功；再 download/list 行为符合「不可访问 / 已离列表」。
3. 核对积分流水与检测行仍在。
4. 标记：`A3_CLEANUP_QUEUE_PASS`。

---

## 总端测与退出

| 顺序 | 动作 |
| --- | --- |
| 1 | 分支 `cursor/module-a-gap-9973`；实现 A1→A2→A3（可同 PR，证据分段） |
| 2 | 跑通 `/tmp/module-a-gap-e2e.log`，须同时含：`A1_URL_IMPORT_STAGING_PASS`、`A2_COST_METERING_PASS`、`A3_CLEANUP_QUEUE_PASS`、`AC009_SKIPPED=true`、`FR012_PRE_REVIEW_WIRED=true`、`production_billing=false`、`formal_supplier=false`、`s7_started=false` |
| 3 | 回写 `docs/mihuanyuantu-v2/progress.yaml`、`checkpoint.md`；摘要 `handoff.md` |
| 4 | 开 PR；**不得自评自合**；不得开 S7 |

### 总预期结果

- 商家可用临时图床完成 URL/JSON **联调入库**（正式 ND-012 仍未闭合，文案与合同诚实）。
- 管理员工作台成本来自上游调用计量账本，缺单价则空态。
- 过期消息/结果可由 worker 清理，下载门禁与清理一致。
- 种子、正式 OSS、geocoder、S7、生产收费均不在本单交付范围。

---

## 风险与禁止

| 项 | 说明 |
| --- | --- |
| SSRF | 导入允许主机必须 allowlist；禁止用户任意 URL 直抓 |
| 假正式 | 不得把临时图床写成「正式供应商已验收」 |
| 假成本 | 不得用 0 或积分消费额冒充上游成本 |
| 数据 | 清理端测只用测数据；不清空真实商家资产 |
| 合入 | Collaborator 推 PR；Owner 非作者 squash |
