# 蜜獾原图 v2 · 任务工单

| 字段 | 内容 |
| --- | --- |
| 工单编号 | MODEL-API-CONFIG-2026-11-11 |
| 创建日期 | 2026-11-11 |
| 范围 | 系统管理「模型 API」页：各职责渠道可配置更换（非代码写死）；保存后全站对应模块同步使用新启用配置；布局/表单字段对齐 `prototype/` |
| 不做 | **跳过** gpt-image-2 尺寸控制 / B2-X；S7；生产收费；客户自建上游 Key；第一版 **Key 轮询**（原型最多 10 Key 权重；本单按 PRD FR-012 **每职责只启用一套**，不得静默打开轮询）；改 `PASS_SCORE`；自评自合 |
| 依据 | PRD 2.10 FR-012 / PG-011 / §7；架构 AD-008（每职责单启用配置）；`prototype/prototype.js` 系统管理·模型 API；AGENTS.md |
| 管理员裁决（本工单） | ① 跳过 gpt-image-2 尺寸合同收口；② 模型 API 各职责改为可配置；③ UI 参考原型；④ 更改后须同步全站模块 |
| 验证环境 | 开发机 FE `3000` / API `38000` + PostgreSQL + worker；证据 `/tmp/model-api-config-e2e.log` |
| 分支约定 | `cursor/model-api-config-9973`；合入仅非作者 Owner squash |

---

## 0. 开干前硬约束

1. 权威：PRD → 架构 → 本工单；UI 信息架构听 `prototype/`，**与 PRD 冲突时听 PRD**（尤其「不轮询」）。
2. 上游 Key **明文仅保存时写入保密存储**；列表/API 响应只回掩码/前缀；禁止入库真实 `.env`、禁止日志打印全文 Key。
3. 客户 / 订单客服 / 技术客服 **不可**改模型 API；仅平台管理员。业务 `X-API-Key` 不可登记上游配置（已有拒绝须保留）。
4. 运行时读「当前启用合同」，禁止各业务模块继续写死 model id / base URL 绕过合同表。
5. `ensure()` / 种子逻辑 **不得在每次启动时用硬编码 `_SPECS` 覆盖管理员已保存的启用配置**（可补缺行，不可无条件打回种子）。
6. `production_billing=false`；`s7_started=false`；本单不宣称 ND-011 已齐。

---

## 1. 现状（核实后写入证据）

| 项 | 现状 |
| --- | --- |
| 前端 `/realphotos/system?tab=models` | **只读表格**：duty / provider / modelId / credentialRef / enabled；无原型级表单；链到独立「模型合同」页 |
| 后端 | `RealphotosProviderContract` + `GET/POST /provider-contracts`；`POST` 目前主要改 `modelId` + 可选 `apiKey`；`_SPECS` 硬编码默认 generation/pre_review/prompt_opt/final_detection/import |
| 运行时 | 各客户端读 `enabled(duty)`，但种子/`ensure` 与物料路径仍强依赖默认规格 |
| 原型 | 表单：提供商、模型版本、用途、Base URL、API Key（可多槽）；已登记渠道表：启停/删除；用途四类 |

---

## 2. 职责映射（产品用途 ↔ 代码 duty）

| 原型「用途」 | 代码 `duty` | 全站同步模块 |
| --- | --- | --- |
| 图片预审 | `pre_review` | 处理提交预审、图生图参考图预审 |
| 生图渠道 | `generation` | 文生图 / 图生图 |
| 提示词优化 | `prompt_opt` | 提示词优化 |
| 最终检测 | `final_detection` | Gemini 最终检测、自动重做检测调用 |

说明：`import`（临时图床联调）**本单可不进管理员表单主路径**（或只读展示）；勿与上述四职责混为「客户可选模型」。检测基线文案（≥75 且 `passed=true`）保留只读提示，**不因换 model id 改通过规则**。

---

## 任务 M1 · 模型 API 页 UI 对齐原型（管理员）

| 字段 | 内容 |
| --- | --- |
| 任务项 | 将系统管理「模型 API」从只读表升级为原型同构的**配置台**：表单 + 已登记渠道列表 |
| 当前现状 | 只读；字段少于原型；无保存/启停/删除交互 |
| 如何完成 | 见步骤 |
| 预期结果 | 管理员可按用途登记/更新渠道；列表只见掩码；非管理员不可见可写；端测 `M1_MODEL_API_UI_PASS` |

### 完成步骤

1. **布局（参考 `prototype/prototype.js` 系统管理 → 模型 API）**
   - 顶部可保留只读「检测基线 · Gemini Vision」说明（通过标准不变）。
   - **表单区「大模型 API Key 配置与管理」**字段：
     - 提供商（select；选项可含原型列表 + 现网已用：`Gemini` / `DeepSeek` / `阿里千问` / `ChatGPT Image 2` / `aoju` 等，允许自定义或「其他」+ 文本）
     - 模型版本（input，即 `modelId`）
     - 用途（select：图片预审 / 生图渠道 / 提示词优化 / 最终检测）
     - Base URL（input，必填合理 URL）
     - API Key（**第一版仅 1 个明文槽**；保存后清空输入框；列表只显示掩码。原型「＋」多 Key：**本单禁止实现轮询**，UI 不提供第 2+ 槽，或禁用并注明「第一版不轮询」）
   - 操作：保存模型配置。
   - **已登记渠道表**：渠道/模型/Base URL、用途、Keys（掩码）、状态（启用/停用）、范围（平台）、操作（启用/停用；删除须确认）。
2. **中文运营密度**：表格优先；不为每个字段堆卡片；文案简体中文。
3. 技术客服：无模型 API 写入口（与现 F7 一致）；商家/订单客服不可见写能力。

### 端测（M1）

- 管理员打开 `/realphotos/system?tab=models`：见表单 + 列表。
- 非管理员：无保存或 403。
- 保存后输入框不再残留明文 Key；列表为掩码。
- `M1_MODEL_API_UI_PASS`

---

## 任务 M2 · 后端合同可写全字段 + 启动不覆盖

| 字段 | 内容 |
| --- | --- |
| 任务项 | 扩展保存 API，使 provider / modelId / baseUrl / 启停 / 凭据可持久化；启动种子不冲掉管理员配置 |
| 当前现状 | `POST` 字段过窄；`_SPECS` + `ensure()` 易把运行配置打回默认 |
| 如何完成 | 见步骤 |
| 预期结果 | DB 为启用配置真相；重启后仍为管理员保存值；端测 `M2_CONTRACT_PERSIST_PASS` |

### 完成步骤

1. **API（管理员）**
   - `GET /provider-contracts`：返回四职责（+ 可选 import 只读）掩码视图：`duty`、`provider`、`modelId`、`baseUrl`、`enabled`、`keyPrefix`/`masked`、`configVersion`、`gapNote`（可空）、**不含**明文 Key。
   - `PUT` 或扩展 `POST`：保存单职责配置，请求体建议：
     - `duty`（或原型 purpose → duty 映射）
     - `provider`、`modelId`、`baseUrl`
     - `apiKey`（可选；空则保留原密钥）
     - `enabled`（启停）
   - 校验：URL 形态；禁止空 `modelId` 却 `enabled=true`；同一 `duty` **仅一条启用**（新启用自动停用同职责旧行，或原地更新唯一行——首版推荐**每 duty 一行**原地更新）。
   - 删除：软删或停用；不得留下「无启用配置却假装 live」的静默成功（调用方应 `SERVICE_NOT_CONFIGURED` 或明确失败）。
2. **密钥存储**
   - 明文不进合同表展示列；写入现有物料/保密机制或底座加密字段（与现 `save(api_key=)` 路径对齐并补全 baseUrl/provider）。
   - 轮换：新 Key 保存成功后旧 Key 失效；列表掩码更新。
3. **`ensure()` 纪律**
   - 仅当该 `duty` **无行**时插入默认规格；
   - 已有行：**禁止**用 `_SPECS` 覆盖 `provider`/`model_id`/`base_url`/`enabled`/capabilities 中管理员已改字段；
   - 允许更新非冲突的元数据（如文档 gap_note）须在证据中写明白名单。
4. **配置版本**
   - 每次成功保存递增或刷新 `configVersion`；任务侧继续快照「提交时配置」（检测/生图已有快照处保持不可变）。

### 端测（M2）

- 保存预审 modelId → 重启 API → GET 仍为新值。
- 不传 apiKey 只改 modelId → 旧 Key 仍可用（若有）。
- 换 apiKey → 掩码变；旧明文不可再从 API 读出。
- `M2_CONTRACT_PERSIST_PASS`

---

## 任务 M3 · 全站模块同步使用启用配置

| 字段 | 内容 |
| --- | --- |
| 任务项 | 预审 / 生图 / 提示词优化 / 最终检测 **运行时只走**当前启用合同（provider、modelId、baseUrl、密钥），改配置后新请求生效 |
| 当前现状 | 部分路径已 `enabled(duty)`，仍夹硬编码默认与物料段落名 |
| 如何完成 | 见步骤 |
| 预期结果 | 改合同后无需改代码即可切换模型；旧进行中任务不被中途改模型（快照）；端测 `M3_RUNTIME_SYNC_PASS` |

### 完成步骤

1. **统一解析**
   - 所有上游调用前：`contract = enabled(duty)`；缺失/未启用 → `SERVICE_NOT_CONFIGURED`（或既有等价码），禁止回落到写死 model。
2. **覆盖点（须逐项勾选进证据）**
   - [ ] `pre_review` 直播预审
   - [ ] `generation` 文生图 / 图生图
   - [ ] `prompt_opt` 提示词优化
   - [ ] `final_detection` Gemini 检测（含自动重做轮次的新调度读新配置；**已创建轮次快照不改**）
3. **客户端适配**
   - `supplier_clients` 使用合同 `base_url` + `model_id`，不要写死 `GENERATION_BASE` / 单一常量作为唯一真相（常量仅作种子默认）。
4. **缓存**
   - 若有进程内缓存，保存合同后必须失效；单进程预览可立刻生效；多 worker 无 Redis 时在证据写明「须滚动重启」或做短 TTL（与菜单缓存诚实口径一致）。

### 端测（M3）

对至少 **两个职责**（建议 `prompt_opt` + `pre_review` 或 `final_detection` fixture/live 策略按环境）：

1. 记录当前 modelId → 改为可探测的另一值（或故意改错 baseUrl）→ 新请求行为变化（打到新模型或明确失败）。
2. 改回正确配置 → 恢复成功。
3. 生图/检测：**进行中任务**不因中途改配置而换模型（快照断言）。
4. `M3_RUNTIME_SYNC_PASS`

---

## 任务 M4 · 权限、审计与文案

| 字段 | 内容 |
| --- | --- |
| 任务项 | 权限矩阵、操作可追溯、客户侧不暴露供应商强制绑定文案 |
| 预期结果 | `M4_RBAC_AUDIT_PASS` |

### 完成步骤

1. 管理员：CRUD/启停；技术客服/商家/订单客服：写拒绝；Key 鉴权写拒绝。
2. 成功变更写入系统可查审计（操作者、duty、变更前后 model/provider/baseUrl/启停、**不写明文 Key**）。若现有「系统日志」仅账号变更，可记独立 admin audit 或扩展允许的模型配置成功事件——须在证据写明落点，且不违反 FR-030「不记录模型配置」若冲突则：**停问**或使用非 `user_action_log` 的运维审计表。  
   - **默认建议**：不写入 FR-030 用户操作日志；使用供应商合同表 `updated_at` + 应用日志脱敏字段；若产品坚持进系统日志，先问管理员（与 FR-030 可能冲突）。
3. 客户生图/优化文案仍称「提示词优化」等产品名，不强制展示上游厂商名。

---

## 总端测与退出

| 顺序 | 动作 |
| --- | --- |
| 1 | 分支 `cursor/model-api-config-9973` |
| 2 | 实现 M1→M2→M3→M4 |
| 3 | `/tmp/model-api-config-e2e.log` 须含：`M1_MODEL_API_UI_PASS` `M2_CONTRACT_PERSIST_PASS` `M3_RUNTIME_SYNC_PASS` `M4_RBAC_AUDIT_PASS`；`SKIP_GPT_IMAGE_SIZE=true`；`production_billing=false`；`s7_started=false`；`polling_enabled=false` |
| 4 | 回写 `progress.yaml` / `checkpoint.md` / `handoff.md` |
| 5 | 开 PR；不得自评自合；不得开 S7 |

### 总预期结果

- 管理员在系统管理「模型 API」按原型密度配置四职责渠道（单 Key、可换 provider/model/baseUrl）。
- 保存后全站预审/生图/优化/最终检测走新启用配置；重启不丢。
- 列表仅掩码；无轮询；跳过 gpt-image-2 尺寸收口。

---

## 风险与禁止

| 项 | 说明 |
| --- | --- |
| 轮询 | 原型 10 Key ≠ 本单范围；PRD 第一版不轮询 |
| 假同步 | 只改 UI 不改运行时读路径 → 不算完成 |
| 种子覆盖 | `ensure()` 覆盖管理员配置 → 禁止 |
| 密钥 | 明文不进 Git、响应、FR-030 用户日志 |
| 尺寸 | 本单跳过；不得借机改 PASS_SCORE 或刷检测分 |
| FR-030 冲突 | 模型配置是否进「系统日志」有歧义时停问，默认不进用户操作日志 |
