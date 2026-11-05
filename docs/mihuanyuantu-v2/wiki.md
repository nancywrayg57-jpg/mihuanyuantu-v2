# Local LLM Wiki: mihuanyuantu-v2

## Project Snapshot
- Goal: 电商商家将商品图/生成图整理为可追溯、可下载、带设备成像参数的图片资产；积分可审计。不承诺外部平台原创/实拍认定。
- 首期（S1）: 真会话 → 本地上传 → 单张处理 → 预审占位 → 五层占位实现（仍交 sRGB JPG）→ Gemini 规则替身 → 整数积分流水按张 10 → LocalDisk 网关下载；同租户双账号 + 跨租户隔离。
- Current phase: delivery（可按 DEV_INSTRUCTIONS 自主推进 S0–S6；S7 须管理员确认）。
- Protected decisions: 已确认——栈=aojuai(Next/FastAPI/PG)；认证=用户名密码+验证码；部署=经济起步/开发机；数据=LocalDisk+整数租户积分流水；AI 边界=首期规则替身，真模型受 Q5 上线门槛。
- Vibe coding mode: 开启；一次一个可见阶段。

## Decision Ledger
| Date | Phase | Decision | Status | Source |
| --- | --- | --- | --- | --- |
| 2026-11-04 | discovery | LocalDisk 默认 / OSS 适配器预留 | confirmed | grill Q1 |
| 2026-11-04 | discovery | 租户共用积分；改 PRD 措辞 | confirmed | grill Q2 |
| 2026-11-04 | discovery | 首期薄范围；生图/运营后置 | confirmed | grill Q3 |
| 2026-11-04 | discovery | 订单客服 A 档进正式开发前 | confirmed | grill Q4/Q6 |
| 2026-11-04 | discovery | ND-011/020/021 无证据禁止生产收费 | confirmed | grill Q5 |
| 2026-11-04 | design | 首期五层占位、Gemini 规则替身；真实五层独立阶段 | confirmed | grill Q7→改回占位 / Q11′A / Q12 |
| 2026-11-04 | design | ≤3 预设；单张；无自动重做；持久 worker | confirmed | grill Q13–Q18 |
| 2026-11-04 | design | 双账号+第二租户；技术客服延后 | confirmed | grill Q19–Q21/Q20 |
| 2026-11-04 | design | 真登录；占位交付合同；消息；冻结范围列表 | confirmed | grill Q22–Q25 |
| 2026-11-04 | design | 整数 rp_credit；过期拒绝；软删；预审占位；仅开发机 | confirmed | grill Q26–Q30 |
| 2026-11-04 | discovery | 微决策：管理员注入替身结果；双账号并发快速联通测试；开发验证码 | confirmed | user A+微决策 |
| 2026-11-05 | prd | 第一版纳入客户业务 API：X-API-Key + image_processing + OpenAPI/Swagger（FR-033 / AC-024）；不进首期 S1 | confirmed | user 改第一版范围 |
| 2026-11-05 | design | 架构 1.5：复用 api_keys；§9.2.1 处理子集路由；scope 映射禁止空=不限制；澄清≠上游模型 Key | confirmed | 审计补缺口 |

## Phase Knowledge
### Discovery
- Outcomes: 审计指出 OSS 合同分叉、共享钱包措辞冲突、MVP 过胖；grill 闭合根决策。
- Lessons: RESOLVED ND ≠ 上线证据；物料与架构日期冲突要以明确 ADR 收口。
- Reusable rules: 每轮 ≤5 前沿题；事实自查仓库；决策等用户。
- Open questions: 无根级开放项；实现按 DEV_INSTRUCTIONS 自主推进。

### Design
- Outcomes: 架构 1.5 LocalDisk + FR-033 客户业务 API（复用 `api_keys`、处理子集路由）；首期适配器边界写入 01-design。
- Lessons: 五层占位实现也必须遵守交付字段合同，否则换真时二次返工；业务 API scope 不得沿用底座空列表不限制。
- Reusable rules: 存储经 `StorageAdapter`；检测经 `DetectorAdapter`（fixture|gemini）；客户业务 Key ≠ 上游模型 Key。
- Prompt notes: 无本轮 PNG 原型请求；S5 前须补商家「业务 API 凭证」页（原型现仅有上游模型 Key）。

### Delivery
- Outcomes: S0/S1 任务·退出证据·禁止项已写入 DEV_INSTRUCTIONS；gate ready。
- Commands: 见 DEV_INSTRUCTIONS §10 与 02-delivery 任务镜像。
- Implementation rules: 禁止首期未过上线门槛部署到 exif-demo 收费。
- Deploy/rollback notes: 见生产物料；production_readiness NOT_READY。

### Acceptance
- Evidence: 无实现证据。
- Defects: n/a
- Accepted risks: 租户共用积分店内误花；ND-016 无版权声明；假→真五层字段漂移残余风险。
- Next sprint knowledge: 算法证据阶段 → 检测上线门槛阶段 → 混合批次。

## Reusable Prompts and Commands
- Agent entry: `DEV_INSTRUCTIONS.md`（必读根目录四职责文件）
- Autonomous: S0–S6；S7 须管理员确认；next_action 以 `progress.yaml` 为准
- Stage checklist: 每阶段 `tasks` / `exit_evidence` / `forbidden` 正文在 `DEV_INSTRUCTIONS` §10；`02-delivery.yaml` 只镜像 status
- Hard rule: 开 S2+ 前须先在指令补齐该阶段清单（任务·退出证据·禁止项）
- Hard rule: 每个里程碑完成后须端到端测试；确认无误并留证据后，才可进入下一阶段
- Root pack: `AGENTS.md` · `handoff.md` · `anchor.md` · `checkpoint.md`
- Constraints: `anchor.md`（节级适用范围；冲突听 PRD）
- Status: `checkpoint.md` §0 最小集
- Command: `python3 aidevops/scripts/validate_workspace.py docs/mihuanyuantu-v2`
- Command: `node prototype/sync-inline.js`（改原型后）

## Vibe Coding Loops
| Loop | Visible Output | Verify | Result | Next |
| --- | --- | --- | --- | --- |
| 0-grill | 共享理解草案 | 用户确认 A | done | 合同修订 |
| 1-s0-s1-triad | DEV_INSTRUCTIONS §10.1/10.2 任务·退出证据·禁止项 | 用户「按此修改并推送」 | done | 自主实现 S0 |
| 2-s1-loop | 单张闭环 UI+API | §10.2 exit_evidence / AC-K1 | pending | 按 §10.1 开工 S0 |

## Risks and Watchpoints
- Risk: 文档自称 RESOLVED 掩盖 PENDING 证据 → 上线误放行。
- Mitigation: Q5 + 物料 NOT_READY + 本 wiki 红线。
- Risk: 实现范围回潮塞进首期（S1）。
- Mitigation: §10.2 forbidden + `anchor.md` 节 G；改列表须改 DEV_INSTRUCTIONS + progress。

## Backlog Knowledge
- Next: 按 DEV_INSTRUCTIONS §10.1 自主推进 S0；勾满 exit_evidence → 端测通过 → 再开 S1。
- Deferred: 见 00-discovery mvp_scope.deferred 与 §10.2 forbidden。
