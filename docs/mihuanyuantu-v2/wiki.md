# Local LLM Wiki: mihuanyuantu-v2

## Project Snapshot
- Goal: 电商商家将商品图/生成图整理为可追溯、可下载、带设备成像参数的图片资产；积分可审计。不承诺外部平台原创/实拍认定。
- 首期（S1）: 真会话 → 本地上传 → 单张处理 → 预审占位 → 五层占位实现（仍交 sRGB JPG）→ Gemini 规则替身 → 整数积分流水按张 10 → LocalDisk 网关下载；同租户双账号 + 跨租户隔离。
- Current phase: delivery（FIX-FAILURE-RATE-TECH R1–R5 本地 PASS、R6 开发机证据缺失；#36 已合；不是生产收费就绪；不得开 S7。文档基线 PRD 2.10 / 架构 1.7）。
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
| 2026-11-05 | delivery | CI/CD：**CI gate** Required；Tag stub；仓 public；全局约定迁入 `AGENTS.md` §7 | confirmed | 用户配置 + #9 / 后续迁址 |
| 2026-11-05 | design | **能力名 scopes** + 映射层；PRD §7 订单客服 A；§8.3 LocalDisk；**冻结 S0** | confirmed | grill round-2 Q1–Q5 |
| 2026-11-05 | delivery | S0 网关可用开发种子文件取证 | confirmed | grill Q6 |
| 2026-11-05 | delivery | S0 暂不启动 | superseded | user（随后授权） |
| 2026-11-05 | delivery | 去掉 GitHub 审批开关与 Collaborator OAuth 绑定类文档跟踪 | confirmed | user |
| 2026-11-05 | delivery | 授权开 S0；实现 realphotos S0；第一个里程碑后暂停 | confirmed | user |
| 2026-11-05 | delivery | 分支后缀冲突：Cloud `-6c0b` vs AGENTS `-9973` | recorded | cloud session vs AGENTS |
| 2026-11-05 | delivery | 开发机 PG `claim_one` 通过；关闭 `S0_E2E_ENV` | confirmed | `/tmp/s0-pg-claim-one-smoke.log` |
| 2026-11-06 | delivery | 五项冲突按管理员决定落地：技术失败保持冻结至技术客服；正方形按横图下限；充值用清单档位；字节下限与分支后缀不变 | decided | 管理员当次回复 |

## Phase Knowledge
### Discovery
- Outcomes: OSS/共享钱包/MVP 过胖分叉已闭合；FR-033 纳入第一版但不进 S1。
- Lessons: RESOLVED ND ≠ 上线证据；历史 ADR 头版本可能滞后，以收口 ADR 为准。
- Reusable rules: 每轮 ≤5 前沿题；事实自查仓库；决策等用户。
- Open questions: 无上述五项。技术客服阶段再处理已冻结的技术失败积分。

### Design
- Outcomes: 架构 **1.7** = 1.6 包 + LocalDisk 网关措辞消歧 + scopes **能力名→路径白名单** 映射合同；PRD **2.10** §7 与矩阵对齐。
- Lessons: 底座 `api_keys` 现为路径前缀/培训白名单，直接存 `image_processing` 会失败——须 S5 前改造，不可假装已兼容。
- Reusable rules: 存储经 `StorageAdapter`；检测经 `DetectorAdapter`；客户业务 Key ≠ 上游模型 Key。
- Prompt notes: 原型尚无「业务 API 凭证」页；S5 前补。

### Delivery
- Outcomes: S0 realphotos 包落地；Cloud pytest + CI 绿；开发机 `S0_PG_CLAIM_ONE_PASS`；S1 单张闭环有开发机证据；S2 五层开发机 `S2_PG_E2E_PASS`；S3 真实小样 `S3_PG_E2E_PASS` 与控制路径 `S3_PG_CONTROLS_PASS`；S4 批次 `/tmp/s4-pg-e2e.log` 的 `S4_PG_E2E_PASS`。
- Commands: `AOJ_ENABLED_MODULES=realphotos .venv/bin/python -m pytest tests/capabilities/realphotos -q`；开发机 `DB_DRIVER=postgresql AOJ_ENABLED_MODULES=realphotos .venv/bin/python -m scripts.s0_pg_claim_one_smoke`（日志 `/tmp/s0-pg-claim-one-smoke.log`）；`bash scripts/ci/secret_scan.sh`。
- Implementation rules: 整数账本禁止桥接 Decimal；网关不回裸路径；SQLite 条件更新认领，PG 用 `claim_one`。
- Deploy/rollback notes: production_readiness NOT_READY；SSH 方法在清单 §2.1，口令只在同级 `生产物料/`。
- Autonomy: 每里程碑后 Agent 自行 SSH 开发机端测（`DEV_INSTRUCTIONS` §6.1）；Cloud 不可达 LAN 时走 self-hosted worker。

### Acceptance
- Evidence: `/tmp/s4-pg-e2e.log` = `S4_PG_E2E_PASS`；`/tmp/s3-pg-e2e.log` = `S3_PG_E2E_PASS`；`/tmp/s3-pg-e2e-controls.log` = `S3_PG_CONTROLS_PASS`；`/tmp/s2-pg-e2e.log` = `S2_PG_E2E_PASS`；S1 与 S0 日志仍有效。
- Defects: 开发机 `alembic_version_cap_realphotos` 当时不存在，`realphotos_0002` 未在该库重放。技术失败积分按决定保持冻结。
- Accepted risks: 开发库已被端测与并发探测写入，不清空。
- Next sprint knowledge: 技术失败冻结留到技术客服阶段。S5 PR #23 未合并，未标完成。S6 已由管理员结束，不重跑。供应商证据在 `/tmp/supplier-live-e2e.log`，导入未接通。不得开 S7。

## Reusable Prompts and Commands
- Agent entry: `DEV_INSTRUCTIONS.md`（必读根目录四职责文件）
- Gate: `origin/main`=`922ef06`（#27/#28）；`s5_exited=true`；`s6_exited` 未靠重跑改写；导入未接通；`production_billing=false`；PRODUCT-GAP-A 证据 `/tmp/product-gap-a-e2e.log` + `/tmp/product-gap-a-browser.txt`
- Stage checklist: DEV_INSTRUCTIONS §10；`02-delivery.yaml` 只镜像 status
- Hard rule: 每个里程碑完成后须端到端测试；Cloud ≠ 开发机
- Root pack: `AGENTS.md` · `handoff.md` · `anchor.md` · `checkpoint.md`
- Command: `python3 aidevops/scripts/validate_workspace.py docs/mihuanyuantu-v2`
- Command: `AOJ_ENABLED_MODULES=realphotos .venv/bin/python -m pytest tests/capabilities/realphotos -q`
- Command: `node prototype/sync-inline.js`（改原型后）

## Vibe Coding Loops
| Loop | Visible Output | Verify | Result | Next |
| --- | --- | --- | --- | --- |
| 0-grill | 共享理解草案 | 用户确认 A | done | 合同修订 |
| 1-s0-s1-triad | DEV_INSTRUCTIONS §10.1/10.2 | 用户「按此修改并推送」 | done | 曾指向自主 S0 |
| 2-cicd-public | CI + public + CI gate Required | 保护规则可强制 | done（CI gate） | — |
| 3-grill-round2 | PRD 2.10 / 架构 1.7 / 收口 ADR / §10.1 Q6 | 收口合入 | done（#10/#11/#12） | 授权开 S0 |
| 4-s0-loop | S0 基础可登录/积分/网关/worker | §10.1 + Cloud 端测 + 开发机 claim_one | devhost_passed | S1 已授权 |
| 5-s1-loop | 单张上传/处理/下载/充值确认拒单 | `/tmp/s1-pg-e2e.log` + `/tmp/s1-browser-e2e.txt` | evidenced | S2 |
| 6-s2-loop | 有序五层、字节下限、预设 EXIF | `/tmp/s2-pg-e2e.log` | devhost_passed | S3 |
| 7-s3-loop | 真实 Gemini、自动重做、主动重处理、技术重试 | `/tmp/s3-pg-e2e.log` + `/tmp/s3-pg-e2e-controls.log` | devhost_passed | S4 |
| 8-s4-loop | 1–10 张按张冻结、部分成功、勾选下载 | `/tmp/s4-pg-e2e.log` | devhost_passed | S5 已授权，退出未齐 |
| 9-s5-loop | 生图只入库、未配置导入、image_processing Key | `/tmp/s5-pg-e2e.log` | pr_23_open | 未标 S5 完成；未合并 |
| 10-s6-list | 运营完备 | `/tmp/s6-pg-e2e.log` | admin_closed_not_rerun | 随 ia-page 分支待合入；不重跑；不开 S7 |
| 11-supplier-live | 生图、提示词优化、预审真实请求；导入未配置 | `/tmp/supplier-live-e2e.log` | recorded_not_production | 不是生产节点；不开 S7 |
| 12-ia-page | 分角色工作台、侧栏、铃铛、任务双 Tab 等 | `/tmp/ia-page-smoke-c2c3c7.txt` | merged_#25 | — |
| 13-blocking-partial | 阻断级 A–G + 部分对齐 A–F | `/tmp/blocking-fix-e2e.log` `/tmp/partial-align-e2e.log` | merged_#27_#28 | product-gap-a |
| 14-product-gap-a | 种子诚实/AI提示词/设备枚举/消息清理/旧预设MakerNote/客服浏览器 | `/tmp/product-gap-a-e2e.log` `/tmp/product-gap-a-browser.txt` | coded_pr_pending | Owner 审 #29；A5 延后 |
| 15-preset-bulk | 清占位 + 405 全量导入 + 55 键快照 | `/tmp/preset-bulk-import-e2e.log` | coded_pr_pending | Owner 审 PR；依赖 #29；不开 S7 |
| 16-browser-e2e-fix | F1–F8：深链/工单/用户/held/率%/藏演示/系统裁剪/generation 网关 | `/tmp/browser-e2e-fix-e2e.log` | merged_#32 | — |
| 17-ux-cn-preset | U1–U7 中文标签 + 预设分页/详情/新增弹窗；C1 撤批量 UI | `/tmp/ux-cn-preset-e2e.log` | merged_#35 | — |
| 18-fix-task-failure-ux | F1–F6 失败原因映射/详情分数门槛/GPS 提示/替身区分/预审请求可重试 | `/tmp/fix-task-failure-ux-e2e.log` | merged_#36 | — |
| 19-fix-failure-rate-remain | R1–R6 失败率剩余项；本机即开发机补 R6 | `/tmp/fix-failure-rate-remain-e2e.log` | local_pass_pr_pending | Owner squash #37；PASS_SCORE=75；不开 S7 |

## Risks and Watchpoints
- Risk: 把文档齐全或 CI 绿当成后端已交付。
- Mitigation: checkpoint 代码态 + progress `s0_coding_authorized`。
- Risk: 实现时直接复用底座路径前缀 scopes。
- Mitigation: 架构 1.7 §9.2.1 改造义务；S5 验收 AC-024。
- Risk: 生图已入库但缩略图恒「图」被误判为模型未接入。
- Mitigation: F8 网关放行 `generation/*`（资产表校验）；「(降级)」仅文件名元数据回退。

## Backlog Knowledge
- Next: Owner 非自评自合 PR #37；不得开 S7。
- Closed this loop: FIX-FAILURE-RATE-TECH R1–R6（`MERGE_READY=True`；R6 证据 task=158 `gpsMode=none` DELIVERED on 本机开发机）。
- Deferred: A5 运营成本真实聚合；CI 升 3.12/pnpm10；替身改库码 `fixture_technical` 须 Owner 批准。
