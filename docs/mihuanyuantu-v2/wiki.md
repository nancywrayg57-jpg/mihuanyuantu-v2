# Local LLM Wiki: mihuanyuantu-v2

## Project Snapshot
- Goal: 电商商家将商品图/生成图整理为可追溯、可下载、带设备成像参数的图片资产；积分可审计。不承诺外部平台原创/实拍认定。
- 首期（S1）: 真会话 → 本地上传 → 单张处理 → 预审占位 → 五层占位实现（仍交 sRGB JPG）→ Gemini 规则替身 → 整数积分流水按张 10 → LocalDisk 网关下载；同租户双账号 + 跨租户隔离。
- Current phase: delivery（**S0 编码冻结**至管理员授权；文档基线 PRD 2.10 / 架构 1.7）。
- Protected decisions: 栈=aojuai；认证=用户名密码+验证码；部署=经济起步；数据=LocalDisk+整数租户积分；AI=首期规则替身；FR-033 scopes=能力名映射。
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
| 2026-11-05 | design | 架构 1.5→1.6：api_keys 复用；表裁剪；先冻后队；RBAC；双 Token | confirmed | 审计补缺口 |
| 2026-11-05 | delivery | CI/CD：§7 禁自评自合；**CI gate** Required 已开；Tag stub；仓 public | confirmed | 用户配置 + #9 |
| 2026-11-05 | design | **能力名 scopes** + 映射层；PRD §7 订单客服 A；§8.3 LocalDisk；**冻结 S0**；禁自评自合须 Owner 确认 | confirmed | grill round-2 Q1–Q5 |
| 2026-11-05 | delivery | S0 网关可用开发种子文件取证；禁自评自合在开 S0 前开启 | confirmed | grill Q6 / Q7 |
| 2026-11-05 | delivery | Owner 确认禁自评自合已开；S0 暂不启动；子会话须 xtzhou247 本人连 Cursor↔GitHub | confirmed | user |

## Phase Knowledge
### Discovery
- Outcomes: OSS/共享钱包/MVP 过胖分叉已闭合；FR-033 纳入第一版但不进 S1。
- Lessons: RESOLVED ND ≠ 上线证据；历史 ADR 头版本可能滞后，以收口 ADR 为准。
- Reusable rules: 每轮 ≤5 前沿题；事实自查仓库；决策等用户。
- Open questions: 文档合入后 Owner 按 Q7 开启禁自评自合并登记；管理员「授权开 S0」。

### Design
- Outcomes: 架构 **1.7** = 1.6 包 + LocalDisk 网关措辞消歧 + scopes **能力名→路径白名单** 映射合同；PRD **2.10** §7 与矩阵对齐。
- Lessons: 底座 `api_keys` 现为路径前缀/培训白名单，直接存 `image_processing` 会失败——须 S5 前改造，不可假装已兼容。
- Reusable rules: 存储经 `StorageAdapter`；检测经 `DetectorAdapter`；客户业务 Key ≠ 上游模型 Key。
- Prompt notes: 原型尚无「业务 API 凭证」页；S5 前补。

### Delivery
- Outcomes: S0/S1 三件套在 DEV_INSTRUCTIONS；CI A–D + **CI gate**；S0 编码按 Q4 冻结。
- Commands: DEV_INSTRUCTIONS §7/§10；`bash scripts/ci/secret_scan.sh`。
- Implementation rules: 禁自评自合；合入须 CI gate；未授权不开 S0。
- Deploy/rollback notes: production_readiness NOT_READY；真 Secrets 仅 Owner 录入。

### Acceptance
- Evidence: 无业务实现证据。
- Defects: n/a
- Accepted risks: 租户共用积分店内误花；ND-016 无版权声明；假→真五层字段漂移残余风险。
- Next sprint knowledge: 授权后 S0 → 端测 → S1。

## Reusable Prompts and Commands
- Agent entry: `DEV_INSTRUCTIONS.md`（必读根目录四职责文件）
- Gate: `s0_coding_authorized` 在 `progress.yaml`；默认 false 直至用户授权
- Stage checklist: DEV_INSTRUCTIONS §10；`02-delivery.yaml` 只镜像 status
- Hard rule: 每个里程碑完成后须端到端测试
- Root pack: `AGENTS.md` · `handoff.md` · `anchor.md` · `checkpoint.md`
- Command: `python3 aidevops/scripts/validate_workspace.py docs/mihuanyuantu-v2`
- Command: `node prototype/sync-inline.js`（改原型后）

## Vibe Coding Loops
| Loop | Visible Output | Verify | Result | Next |
| --- | --- | --- | --- | --- |
| 0-grill | 共享理解草案 | 用户确认 A | done | 合同修订 |
| 1-s0-s1-triad | DEV_INSTRUCTIONS §10.1/10.2 | 用户「按此修改并推送」 | done | 曾指向自主 S0 |
| 2-cicd-public | CI + public + CI gate Required | 保护规则可强制 | done（CI gate） | 禁自评自合待 Owner |
| 3-grill-round2 | PRD 2.10 / 架构 1.7 / 收口 ADR / §10.1 Q6 | Q1–Q6 确认；Q7=合入后开 S0 前 | docs_close_ready_for_merge | 合入→开禁自评自合→授权 S0 |
| 4-s0-loop | S0 基础可登录/积分/网关/worker | §10.1 exit_evidence + 端测 | pending | 须授权 |

## Risks and Watchpoints
- Risk: 把文档齐全或 CI 绿当成后端已交付。
- Mitigation: checkpoint 代码态 + progress `s0_coding_authorized`。
- Risk: 实现时直接复用底座路径前缀 scopes。
- Mitigation: 架构 1.7 §9.2.1 改造义务；S5 验收 AC-024。
- Risk: 禁自评自合未开仍宣称门禁齐。
- Mitigation: grill Q5 + DEV §7.5 待办。

## Backlog Knowledge
- Next: 用户授权开 S0 后按 §10.1 实现；FR-033 → S5/R3。
- Deferred: CI Python/pnpm 版本与架构推荐对齐（非 S0 阻塞）。
