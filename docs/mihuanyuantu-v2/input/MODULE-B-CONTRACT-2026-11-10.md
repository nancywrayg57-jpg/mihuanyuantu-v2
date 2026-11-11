# 蜜獾原图 v2 · 任务工单

| 字段 | 内容 |
| --- | --- |
| 工单编号 | MODULE-B-CONTRACT-2026-11-10 |
| 创建日期 | 2026-11-10 |
| 范围 | Module B「已有骨架、第一版合同未收口」中主会话可自主推进的两项：① FR-033 对接合同工件 + 无会话端测复跑归档；② FR-010/011 生图尺寸合同（先取供应商证据，确认支持尺寸控制后再执行收口） |
| 不做 | S7；生产收费（`production_billing=false`）；改 `PASS_SCORE` / 刷 Gemini 分；AC-009 种子；ND-011 大陆节点归档冒充；ND-012 正式导入供应商采购；OSS；自评自合 PR；清空业务库 |
| 依据 | PRD 2.10 FR-033 / AC-024 / FR-010 / FR-011；架构 1.7（OpenAPI SSOT、尺寸不得静默改写）；物料清单生图入口 `https://apis.aoju.ai/v1` · `gpt-image-2`；AGENTS.md |
| 管理员裁决（本工单） | ① FR-033：做对接合同工件 + 无会话端测复跑归档；② FR-010/011：**先获取供应商合同并确认模型是否支持尺寸控制；确认支持后再执行代码/验收收口**；不支持则诚实登记缺口并停在门闸，不得假装合同已满足 |
| 验证环境 | 开发机本机 FE `3000` / API `38000` + PostgreSQL + worker；证据 `/tmp/module-b-contract-e2e.log` |
| 分支约定 | `cursor/module-b-contract-9973`（Collaborator）；合入仅非作者 Owner squash |

---

## 0. 开干前硬约束

1. 权威顺序：PRD → 架构 → `DEV_INSTRUCTIONS.md`；冲突停问。
2. 密钥只读 `生产物料/`（或仓内 gitignore 同名目录），禁止入库、禁止写入本工单正文。
3. 生图尺寸：**禁止**在适配器里把客户请求尺寸静默改成上游实图尺寸再对外宣称「已按客户尺寸交付」。
4. 尺寸项有**门闸**（见 B2）：未取得供应商「支持尺寸控制」书面/接口证据前，只允许做探测与缺口登记，不得标 B2 完成。
5. `production_billing=false`；`s7_started=false`；不得宣称 ND-011 / 生产检测收费已放行。
6. 端测通过并回写 `progress.yaml` / `checkpoint.md` 前，不得宣称本工单完成。

---

## 本工单明确排除（写入证据即可）

| ID | 项 | 处理 |
| --- | --- | --- |
| OUT-SCORE | Gemini 稳定 ≥75 / 90% 交付率 | 已判 NOT_DEFECT；本单不做；须另批产品策略 |
| OUT-ND011 | 大陆最终节点与上线证据包 | 本单不做 |
| OUT-AC009 | 随机种子 | 保持 `gap-not-sent` / `SEED_UNSUPPORTED`；本单不改 |
| OUT-ND012-FORMAL | 正式 URL 导入供应商 | Module A 仅联调；本单不升级为正式 |

证据要求日志含：`OUT_SCORE=true OUT_ND011=true OUT_AC009=true OUT_ND012_FORMAL=true`

---

## 任务 B1 · FR-033 对接合同工件 + 无会话端测复跑归档

| 字段 | 内容 |
| --- | --- |
| 任务项 | 固化 `image_processing` OpenAPI/对接说明，并复跑「仅 `X-API-Key`、无浏览器会话」主路径端测，归档为可复查证据 |
| 当前现状 | Key 签发、scope 白名单、S5 曾 PASS；仓库有 `aojuai-main/backend/contracts/realphotos_image_processing.openapi.json`；ND-017 仍记验收证据 PENDING；易被理解为「文档与实现可能漂移」 |
| 如何完成 | 见下方步骤 |
| 预期结果 | 规范与实现一致；无会话端测复跑 PASS；证据路径写入 progress；端测标记 `B1_FR033_CONTRACT_PASS` |

### 完成步骤

1. **核对实现 ↔ OpenAPI**
   - 用现有导出脚本（或等价）从运行中 FastAPI 生成 `image_processing` 子集，覆盖/更新 `contracts/realphotos_image_processing.openapi.json`。
   - 核对：鉴权头 `X-API-Key`；scope 能力名 `image_processing`；路径仅处理相关（上传供处理、提交处理、查询、下载）；**不含**生图、提示词优化、URL 导入、客服/管理、Key 自管。
   - 若导出与仓库文件 diff，以运行实现为准更新仓库工件，并在证据中列 path 增减摘要。

2. **对接说明（短文，中文）**
   - 在 `docs/mihuanyuantu-v2/` 或 `contracts/` 旁增加/更新一页对接说明（勿写密钥）：如何 Web 登录签发 Key、明文仅一次、scope 固定、错误码（缺头/错 Key/吊销/过期/scope 拒绝/跨租户）、主路径四步、明确不做列表。
   - 说明中声明：本工件支持对接联调与验收复跑；**不等于**生产已收费上线。

3. **无会话端测复跑**
   - 登录态 `POST /business-api-keys`，`scopes=["image_processing"]`；省略/空/`*`/培训路径前缀 → 拒。
   - 仅持 Key：上传（供处理）→ 提交处理 → 查到终态 → 逐张下载（无 ZIP、无裸路径）。
   - 同 Key 调提示词优化 / URL 导入 / 再签发 Key → 拒绝。
   - 检测可用 fixture/`pass` 以证明路径（注明**不是**新的 Gemini 生产小样）。
   - 证据写入 `/tmp/module-b-contract-e2e.log`。

4. **进度回写**
   - `progress.yaml`：`module_b_contract_status.B1=...`；`openapi_artifact` 路径；端测标记。
   - 不得把 ND-011 / `production_billing` 改成已放行。

### 端测（B1）

须全部出现在 `/tmp/module-b-contract-e2e.log`：

- `openapi_export_ok=true`（或等价 PASS）
- `business_key_issued_via_http=true`
- `no_session_upload_submit_query_download=PASS`（终态明确）
- `key_rejects_generation_or_prompt_or_import=PASS`
- `key_manage_rejected=true`（禁止 Key 自管）
- `zip_rejected=true`（若测到 pack）
- `B1_FR033_CONTRACT_PASS`
- `production_billing=false`；`s7_started=false`

---

## 任务 B2 · FR-010/011 生图尺寸合同（门闸 → 条件执行）

| 字段 | 内容 |
| --- | --- |
| 任务项 | 先取得生图供应商关于 **尺寸控制** 的合同/接口证据；确认 `gpt-image-2`（或当前启用 model）**支持**按请求 `width×height` 出图后，再执行代码与验收收口；不支持则登记缺口并停止，不得伪造成功 |
| 当前现状 | 请求体发送 `size="{w}x{h}"`；适配器不改写请求尺寸；供应商补测曾记 **requested=1024×768 actual=1536×1024**；合同 `capabilities.width/height=request-256-2048`，`gap_note` 称按请求原样发送；**尺寸是否被上游遵守尚未有正式合同结论** |
| 如何完成 | **两阶段**：B2-G 门闸探测 →（仅当「支持」）B2-X 收口实现与端测 |
| 预期结果 | 门闸结论书面化；若支持则实图尺寸与请求一致（在合同允许集合内）且端测 PASS；若不支持则 `B2_SIZE_UNSUPPORTED_RECORDED` 且本项不标完成 |

### 阶段 B2-G · 获取供应商合同并确认是否支持尺寸控制（必须先做）

1. **索取/读取证据（不编造）**
   - 从同级 `生产物料/`、aoju 中继文档、或管理员提供的接口说明中，找到当前生图入口（物料：`https://apis.aoju.ai/v1`，model 样例 `gpt-image-2`）关于：
     - 是否支持 `size` / `width`×`height`；
     - 允许的尺寸枚举或范围；
     - 不支持时的行为（忽略、报错、回落到固定档）。
   - 缺文件时在聊天向管理员索取；**禁止**把一次偶然成功当成合同。

2. **实测探测（开发机，记入证据）**
   - 对至少 2 组客户常用尺寸各生 ≥1 张（建议含曾失败组合 `1024x768`，以及合同声称支持的另一档如 `1024x1024` 若文档有）。
   - 记录：`requested_size`、解码后 `actual_width×actual_height`、HTTP 状态、model id、是否扣费。
   - 判定规则（写入日志，不得私自放宽）：
     - **SUPPORTS_SIZE_CONTROL=true**：合同写明支持，且探测样张 **实际像素尺寸 == 请求尺寸**（或合同明确的允许映射表内一一对应，须把映射表写入证据）。
     - **SUPPORTS_SIZE_CONTROL=false**：合同写明不支持，或探测出现请求≠实图且无批准映射表。
     - **INCONCLUSIVE**：缺合同且探测不稳定 → **停问管理员**，不得进入 B2-X。

3. **门闸出口**
   - `true` → 进入 B2-X。
   - `false` / `INCONCLUSIVE` → 更新 `generation` 合同 `capabilities` / `gap_note`（诚实缺口）；客户路径保持「按请求发送、实图如实展示、不静默改写」；日志 `B2_SIZE_UNSUPPORTED_RECORDED` 或 `B2_SIZE_INCONCLUSIVE_STOP`；**本工单 B2 不标完成**（B1 仍可单独合入，须在 PR 说明）。

### 阶段 B2-X · 仅当 SUPPORTS_SIZE_CONTROL=true 时执行

1. **合同行更新**
   - `capabilities` 写入已验证尺寸集合或范围、`sizeControl=enforced`（或等价键）。
   - `gap_note` 去掉「尺寸未验证」类模糊表述；保留种子 gap（AC-009 仍跳过）。

2. **实现收口（按合同，选一，禁止静默）**
   - **优先 A**：上游保证出图尺寸 = 请求 → 入库前校验 `actual == requested`，不符则该张失败、不扣成功费（或按 FR-016 生图失败口径），并记供应商偏差。
   - **备选 B**：合同仅允许枚举档 → 提交前校验客户尺寸∈枚举，非法直接拒；合法档必须 actual 匹配。
   - **禁止**：把实图 resize 成请求尺寸后当作「模型已按尺寸生成」交付；禁止改客户积分倒推。

3. **UI/详情**
   - 生图结果展示请求尺寸与实际尺寸；失败原因中文可操作（NFR-011），不泄密钥。

4. **端测（B2-X）**
   - 合同允许的尺寸：请求=实图，入库成功，计费符合生图按张。
   - 合同外尺寸：提交拒绝或按合同失败，不入库冒充成功。
   - 回归：不发送/不伪造 seed（AC-009）。
   - 标记：`B2_SIZE_CONTRACT_ENFORCED_PASS`。

### 端测（B2 总览，写入同一日志）

无论门闸结果，均须有：

- `B2_G_supplier_doc_checked=true|false`（false 时必须已向管理员索取并记录）
- `B2_G_probe_sizes=...`（列出 requested/actual）
- `SUPPORTS_SIZE_CONTROL=true|false|inconclusive`

然后二选一：

- 支持：`B2_SIZE_CONTRACT_ENFORCED_PASS`
- 不支持：`B2_SIZE_UNSUPPORTED_RECORDED`（更新 gap_note；不标 B2 完成）
- 不确定：`B2_SIZE_INCONCLUSIVE_STOP`（停问；不标 B2 完成）

---

## 总端测与退出

| 顺序 | 动作 |
| --- | --- |
| 1 | 分支 `cursor/module-b-contract-9973`（可自 `origin/main` 或已合入的 Module A 之后 tip，PR 注明依赖） |
| 2 | 先 B1，再 B2-G；仅门闸通过才 B2-X |
| 3 | `/tmp/module-b-contract-e2e.log` 须含：`B1_FR033_CONTRACT_PASS`；以及 B2 门闸三态之一的合法出口标记；`production_billing=false`；`s7_started=false`；OUT_* 排除项 |
| 4 | 回写 `progress.yaml`、`checkpoint.md`；摘要 `handoff.md`；约束台账如有冲突写入 `docs/mihuanyuantu-v2/input/` |
| 5 | 开 PR；**不得自评自合**；不得开 S7 |

### 总预期结果

- **B1 必达**：OpenAPI 对接工件与实现一致；无会话 Key 主路径端测复跑有证据。
- **B2 条件达**：仅当供应商合同+探测确认支持尺寸控制后，实现并端测「请求尺寸被遵守」；否则诚实登记缺口，不伪造成合同已收口。
- 不触碰 Gemini 刷分、生产收费、正式导入供应商、S7。

---

## 风险与禁止

| 项 | 说明 |
| --- | --- |
| 假合同 | 不得把联调偶然尺寸一致写成供应商合同已支持 |
| 假交付 | 不得用本地下采样/裁切冒充模型按尺寸生成 |
| 假上线 | 不得因本单 PASS 改 `production_billing=true` 或开 S7 |
| 密钥 | 不打印、不入库、不写入工单 |
| 合入 | Collaborator 推 PR；Owner 非作者 squash |
