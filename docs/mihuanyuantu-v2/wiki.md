# Local LLM Wiki: mihuanyuantu-v2

## Project Snapshot
- Goal: 电商商家将商品图/生成图整理为可追溯、可下载、带设备成像参数的图片资产；积分可审计。不承诺外部平台原创/实拍认定。
- MVP slice（第一刀）: 真会话 → 本地上传 → 单张处理 → 预审桩 → 假五层（仍交 sRGB JPG）→ Gemini 规则夹具 → 整数账本按张 10 → LocalDisk 网关下载；同租户双账号 + 跨租户隔离。
- Current phase: design（架构合同已按 grill 修订）；delivery 待用户授权编码。
- Protected decisions: 已确认——栈=aojuai(Next/FastAPI/PG)；认证=用户名密码+验证码；部署=经济起步/开发机；数据=LocalDisk+整数租户账本；AI 边界=第一刀夹具，真模型受 Q5 门禁。
- Vibe coding mode: 开启；一次一个可见切片。

## Decision Ledger
| Date | Phase | Decision | Status | Source |
| --- | --- | --- | --- | --- |
| 2026-11-04 | discovery | LocalDisk 默认 / OSS 适配器预留 | confirmed | grill Q1 |
| 2026-11-04 | discovery | 租户共用积分；改 PRD 措辞 | confirmed | grill Q2 |
| 2026-11-04 | discovery | 第一刀薄切片；生图/运营后置 | confirmed | grill Q3 |
| 2026-11-04 | discovery | 订单客服 A 档进正式开发前 | confirmed | grill Q4/Q6 |
| 2026-11-04 | discovery | ND-011/020/021 无证据禁生产收费 | confirmed | grill Q5 |
| 2026-11-04 | design | 第一刀五层假、Gemini 夹具；真五层独立切片 | confirmed | grill Q7→改回假 / Q11′A / Q12 |
| 2026-11-04 | design | ≤3 预设；单张；无自动重做；持久 worker | confirmed | grill Q13–Q18 |
| 2026-11-04 | design | 双账号+第二租户；技术客服延后 | confirmed | grill Q19–Q21/Q20 |
| 2026-11-04 | design | 真登录；桩交付合同；消息；冻结范围列表 | confirmed | grill Q22–Q25 |
| 2026-11-04 | design | 整数 rp_credit；过期拒绝；软删；预审桩；仅开发机 | confirmed | grill Q26–Q30 |
| 2026-11-04 | discovery | 微决策：管理员注入夹具；双账号并发冒烟；开发验证码 | confirmed | user A+微决策 |

## Phase Knowledge
### Discovery
- Outcomes: 审计指出 OSS 合同分叉、共享钱包措辞冲突、MVP 过胖；grill 闭合根决策。
- Lessons: RESOLVED ND ≠ 上线证据；物料与架构日期冲突要以明确 ADR 收口。
- Reusable rules: 每轮 ≤5 前沿题；事实自查仓库；决策等用户。
- Open questions: 无根级开放项；编码授权待用户。

### Design
- Outcomes: 架构 1.4 LocalDisk；第一刀适配器边界写入 01-design。
- Lessons: 假五层也必须遵守交付字段合同，否则换真时二次返工。
- Reusable rules: 存储经 `StorageAdapter`；检测经 `DetectorAdapter`（fixture|gemini）。
- Prompt notes: 无本轮 PNG 原型请求。

### Delivery
- Outcomes: 待授权。
- Commands: 待 02-delivery 填写。
- Implementation rules: 禁止第一刀未过门禁部署到 exif-demo 收费。
- Deploy/rollback notes: 见生产物料；production_readiness NOT_READY。

### Acceptance
- Evidence: 无实现证据。
- Defects: n/a
- Accepted risks: 租户共用积分店内误花；ND-016 无版权声明；假→真五层字段漂移残余风险。
- Next sprint knowledge: 算法证据切片 → 检测门禁切片 → 混合批次。

## Reusable Prompts and Commands
- Agent entry: `DEV_INSTRUCTIONS.md`（必读根目录四职责文件）
- Autonomous: S0–S6；S7 须管理员确认；next_action 以 `progress.yaml` 为准
- Slice triad: 每切片 `tasks` / `exit_evidence` / `forbidden` 正文在 `DEV_INSTRUCTIONS` §10；`02-delivery.yaml` 只镜像 status
- Hard rule: 开 S2+ 前须先在指令补齐该切片三件套
- Root pack: `AGENTS.md` · `handoff.md` · `anchor.md` · `checkpoint.md`
- Constraints: `anchor.md`（节级适用范围；冲突听 PRD）
- Status: `checkpoint.md` §0 最小集
- Command: `python3 aidevops/scripts/validate_workspace.py docs/mihuanyuantu-v2`
- Command: `node prototype/sync-inline.js`（改原型后）

## Vibe Coding Loops
| Loop | Visible Output | Verify | Result | Next |
| --- | --- | --- | --- | --- |
| 0-grill | 共享理解草案 | 用户确认 A | done | 合同修订 |
| 1-s0-s1-triad | DEV_INSTRUCTIONS §10.1/10.2 三件套 | 用户「按此修改并推送」 | done | 自主实现 S0 |
| 2-first-knife | 单张闭环 UI+API | §10.2 exit_evidence / AC-K1 | pending | 按 §10.1 开工 S0 |

## Risks and Watchpoints
- Risk: 文档自称 RESOLVED 掩盖 PENDING 证据 → 上线误放行。
- Mitigation: Q5 + 物料 NOT_READY + 本 wiki 红线。
- Risk: 实现范围回潮塞进第一刀。
- Mitigation: §10.2 forbidden + `anchor.md` 节 G；改列表须改 DEV_INSTRUCTIONS + progress。

## Backlog Knowledge
- Next: 按 DEV_INSTRUCTIONS §10.1 自主推进 S0；勾满 exit_evidence 后开 S1。
- Deferred: 见 00-discovery mvp_scope.deferred 与 §10.2 forbidden。
