# 蜜獾原图 v2 · 任务工单

| 字段 | 内容 |
| --- | --- |
| 工单编号 | REMAIN-GAP-PLAN-2026-11-11 |
| 创建日期 | 2026-11-11 |
| 修订 | 2026-11-11：① 管理员确认 **PR #46 已合入**；本单从最新 `main` 开分支。② 增补 **推送前本地对齐 CI 门禁**；**改配置读取方式须同步改测试** |
| 范围 | 侧聊二次审计「A. 建议继续跟进的缺口」九项：底座登录旁路、资源库服务端分页、复制门闩合同形、Alembic 迁移、进程拓扑、OpenAPI→SDK、OSS 适配器预留、架构 front-matter、S7/ND-011（仅规划闸门） |
| 前置 | **PRODUCT-GAP-FIX（G1–G5）已合入**：PR [#46](https://github.com/nancywrayg57-jpg/mihuanyuantu-v2/pull/46)。开干前：`git fetch origin && git checkout main && git pull`，确认 `main` 含缺口修复后再切 `cursor/remain-gap-9973` |
| 不做 | **未经管理员确认不开真 S7 / 不宣称生产收费**；OSS 真切换上云；正式 ND-012 供应商冒充；ZIP；Key 轮询；改 `PASS_SCORE`；重做 FR-025 计量；自评自合；清空业务库 |
| 依据 | PRD 2.10：FR-001 / ND-001 / FR-028；架构 1.7：AD-001 / AD-005 / §6.2 / AD-007 / AD-009 / AD-011 / S7·ND-011；`AGENTS.md` §7.3 CI；侧聊审计 2026-11-11 |
| 管理员裁决（本工单草案） | ① 按下方波次推进，每波先端测再合入；② **R9（S7）默认 BLOCKED**，仅当管理员书面「授权 S7」后另开执行单；③ 合同形冲突（复制门闩字段）以架构为准，若承认现实现则**书面改合同**二选一，禁止静默双轨；④ **推送前必须本地对齐 CI 门禁**（见 §0 / §5） |
| 验证环境 | 开发机（`hbs@192.168.19.128`）FE `3000` / API `38000` + PostgreSQL + worker；证据建议 `/tmp/remain-gap-e2e.log` |
| 分支约定 | `cursor/remain-gap-9973`（Collaborator）；合入仅非作者 Owner squash |

---

## 0. 开干前硬约束

1. 权威顺序：PRD → 架构 → 本工单 → `DEV_INSTRUCTIONS.md`；冲突停问。
2. 密钥只读同级 `生产物料/`；禁止入库。
3. 每开发项须有：**缺口说明 / 如何修复 / 预期结果 / 端测标记**；文档项可无运行时端测，但须 diff 可审。
4. 不得在未授权时启动 S7 真部署或改 `production_billing=true`。
5. 改动落在 `aojuai-main` 与 `docs/`；不扩未点名系统。
6. **推送前本地对齐 CI 门禁（必做）**  
   - 对照 `.github/workflows/ci.yml` 与 `AGENTS.md` §7.3：至少在本地跑通本 PR 会触发的检查，再 `git push`。  
   - 后端改动：`cd aojuai-main/backend && ruff check`（改动范围）+ `DB_DRIVER=sqlite pytest`（相关用例，勿只跑端测脚本）。  
   - 前端改动：`cd aojuai-main/frontend && pnpm typecheck` + `pnpm test`（相关包）。  
   - 文档/流程改动：确认门控文件仍在。  
   - 未本地对齐就推送，**极易**在 Required **`CI gate`** 红灯返工。
7. **改配置读取方式时，测试必须一起改**  
   - 凡把 `os.environ` / 散落 getenv 收口到 `settings`、改 Settings 字段名、改 feature flag 读取路径：同步改所有依赖旧读法的单测与 fixture（含 `monkeypatch`、`env` 夹具）。  
   - 历史教训：只改生产代码、测试仍直读环境变量 → 本地/CI 表现不一致，**CI 易失败**（参见既有 GOV-10 / Module 类 PR 返修）。  
   - 自检：全局搜旧键名与旧读取点；PR 中「配置改动」与「测试改动」同提交或同 PR，禁止拆成「先合代码、后补测试」。

---

## 1. 波次总览（建议顺序）

| 波次 | ID | 类型 | 缺口 | 优先级 | 建议端测标记 |
| --- | --- | --- | --- | --- | --- |
| W1 | R1 | 开发 | FR-001 关闭底座无验证码登录旁路 | P0 | `R1_AUTH_BYPASS_CLOSED_PASS` |
| W1 | R2 | 开发 | FR-028 资源库服务端分页 | P0 | `R2_ASSET_SERVER_PAGE_PASS` |
| W2 | R3 | 开发 | AD-011 Alembic 补齐 outbox/门闩等列 | P0 | `R3_ALEMBIC_SCHEMA_PASS` |
| W2 | R4 | 开发 | AD-005 / §6.2 复制门闩合同形对齐 | P1 | `R4_COPY_GUARD_CONTRACT_PASS` |
| W3 | R5 | 开发 | AD-001 进程拓扑收口（处理/消息/清理） | P1 | `R5_WORKER_TOPOLOGY_PASS` |
| W4 | R6 | 开发 | AD-009 OpenAPI → 前端 generated SDK | P2 | `R6_FE_SDK_GENERATED_PASS` |
| W4 | R7 | 开发 | AD-007 OSS StorageAdapter 预留类 | P2 | `R7_OSS_ADAPTER_STUB_PASS` |
| W4 | R8 | 文档 | 架构 front-matter 实现状态对齐 | P2 | `R8_ARCH_STATUS_DOC_PASS` |
| — | R9 | **闸门** | S7 / ND-011 生产收费与上线包 | 阻塞 | `R9_S7_BLOCKED=true`（未授权） |

建议合并策略：W1 可同一 PR；W2 的 R3 宜在 R4 前或同 PR（门闩表结构）；W3/W4 可拆 PR。总闸（不含 R9）：

```text
REMAIN_GAP_W1_PASS / W2 / W3 / W4
R9_S7_BLOCKED=true
production_billing=false
```

---

## 2. 任务明细

### R1 · FR-001 关闭底座无验证码登录旁路

| 字段 | 内容 |
| --- | --- |
| 缺口说明 | 产品页已走 realphotos 验证码；底座 `POST /api/v1/auth/login` 仍可无 captcha 拿会话 |
| 如何修复 | 1）业务租户/商家入口禁止使用无验证码底座登录：返回 403/引导走 `/api/v1/realphotos/auth/*`，或底座 login 强制 challenge。2）单测：无 captcha 调底座 login 对业务角色失败；realphotos 路径仍通。3）文档写明唯一合法 Web 登录入口。 |
| 预期结果 | 无法再用无验证码底座登录进入商家/业务会话；端测 `R1_AUTH_BYPASS_CLOSED_PASS` |
| 依赖 | PRODUCT-GAP-FIX G1 已合入或同分支可用 |

---

### R2 · FR-028 资源库服务端分页

| 字段 | 内容 |
| --- | --- |
| 缺口说明 | 列表偏全量拉取 + 前端 `PAGE_SIZE` 本地切片，不符合「服务端约 20/页」 |
| 如何修复 | 1）`GET` 资源列表增加 `page`/`pageSize`（默认 20），返回 `items`+`total`。2）前端资源库改为请求分页；跨页勾选状态保留（PRD）。3）来源筛选与分页可组合。 |
| 预期结果 | 网络层每页约 20 条；大数据量下不再一次拉全库；`R2_ASSET_SERVER_PAGE_PASS` |
| 依赖 | 无强依赖；勿破坏 G3 批量上传 |

---

### R3 · AD-011 Alembic 迁移补齐

| 字段 | 内容 |
| --- | --- |
| 缺口说明 | outbox 投递列、`copy_latch_*` 等靠脚本/ORM，干净库/上线不可复现 |
| 如何修复 | 1）盘点 `product_gap_fix_schema.py` 与模型相对 Alembic 的差集。2）新增迁移：outbox `attempt_count`/`next_attempt_at`/`recipient_user_id`/`last_error`；复制门闩相关列/表。3）端测：空库 migrate → 应用可启动 → outbox/copy 冒烟。4）逐步淘汰「仅脚本 ALTER」作为唯一路径。 |
| 预期结果 | `alembic upgrade head` 后具备完整列；`R3_ALEMBIC_SCHEMA_PASS` |
| 依赖 | 宜与 R4 同波，避免门闩表二次改 |

---

### R4 · AD-005 / §6.2 复制门闩合同形

| 字段 | 内容 |
| --- | --- |
| 缺口说明 | 现有 `copy_latch_*` / `COPY_LATCH_ACTIVE` 与架构 `guard_epoch` / `ACCOUNT_SPEND_BUSY` 不一致 |
| 如何修复 | **路径 A（对齐架构）**：引入/改名 guard 字段与错误码，复制期间减额/冻结返回约定码，UI 提示「复制进行中」。**路径 B（改合同）**：管理员书面承认现实现，更新架构 §6.2 后本项关闭。禁止长期双轨。 |
| 预期结果 | 合同与代码同一套名字/错误码；并发复制只一份生效；`R4_COPY_GUARD_CONTRACT_PASS` |
| 依赖 | R3 迁移；需管理员选 A 或 B |

---

### R5 · AD-001 进程拓扑收口

| 字段 | 内容 |
| --- | --- |
| 缺口说明 | notify 已可独立；图片处理与清理仍可能挤在同一 heartbeat |
| 如何修复 | 1）明确三个入口：`process` / `notify` / `cleanup`（或等价 CLI）。2）systemd/开发启动脚本示例（**不**等于 S7 生产部署）。3）端测：分别启动后认领对应 job kind，互不抢错队列。 |
| 预期结果 | 文档+脚本可分进程跑；`R5_WORKER_TOPOLOGY_PASS` |
| 依赖 | G4 outbox 已存在 |

---

### R6 · AD-009 OpenAPI → 前端 SDK

| 字段 | 内容 |
| --- | --- |
| 缺口说明 | 有 OpenAPI 制品，无 `generated` 客户端，前端易漂移 |
| 如何修复 | 1）固定生成器版本；从 `contracts/realphotos_image_processing.openapi.json`（及/或全量 realphotos OpenAPI）生成 `frontend/src/generated/realphotos/`。2）CI `--check` 防手改。3）逐步替换手写调用（可先业务 API + 资源列表）。 |
| 预期结果 | 生成目录入库或构建产物可复现；`R6_FE_SDK_GENERATED_PASS` |
| 依赖 | G5 制品稳定 |

---

### R7 · AD-007 OSS StorageAdapter 预留

| 字段 | 内容 |
| --- | --- |
| 缺口说明 | 仅 LocalDisk；无 OSS 适配器类 |
| 如何修复 | 1）新增 `OssStorageAdapter`（或等价）实现同一接口；默认配置仍 LocalDisk。2）未配 OSS 凭证时不得启用；单测用 mock。3）**禁止**本工单接真桶上线。 |
| 预期结果 | 代码可切换适配器；默认仍本地盘；`R7_OSS_ADAPTER_STUB_PASS` |
| 依赖 | 无 |

---

### R8 · 架构 front-matter 状态对齐

| 字段 | 内容 |
| --- | --- |
| 缺口说明 | 架构仍标 `implementation_status: NOT_IMPLEMENTED`，与 S0–S6 实码不符 |
| 如何修复 | 更新 `docs/蜜獾原图-v2-项目架构-v1.0.md` front-matter / 实现状态说明，按真实阶段（如 `partial`/`s0_s6_coded`）书写；注明 S7/生产未就绪。 |
| 预期结果 | 新人不会误读「完全未实现」；`R8_ARCH_STATUS_DOC_PASS`（文档 diff 即可） |
| 依赖 | 无；可与任意波次同 PR |

---

### R9 · S7 / ND-011（默认阻塞）

| 字段 | 内容 |
| --- | --- |
| 缺口说明 | 部署清单、上线证据、生产收费门未开 |
| 本工单动作 | **仅登记**；输出「S7 开工检查清单」草稿到 `docs/mihuanyuantu-v2/`（可选），**不执行**真部署、不改 Secrets、不打生产 Tag |
| 解锁条件 | 管理员明确「授权 S7」+ ND-011 证据路径齐 |
| 证据 | 日志强制 `R9_S7_BLOCKED=true`、`production_billing=false` |

---

## 3. 明确排除 / 延期（写入证据）

| ID | 项 | 裁决 |
| --- | --- | --- |
| OUT-S7-EXEC | 真 S7 部署与生产收费 | 未授权前禁止；`R9_S7_BLOCKED=true` |
| OUT-ND012 | 正式导入供应商 | 保持 staging；不冒充正式 |
| OUT-ZIP | ZIP 交付 | 继续拒绝 |
| OUT-POLL | Key 轮询 | 第一版关闭 |
| OUT-PHYS | 五层抬分 / PASS_SCORE | 另单；本单不改 75 |

---

## 4. 端测与证据

证据文件建议：`/tmp/remain-gap-e2e.log`（可按波次分段）。

最低：

1. **R1**：无 captcha 底座 login 拒；realphotos 登录通。  
2. **R2**：page=1/2 条数与 total 正确；超大页参数被钳制或 422。  
3. **R3**：migrate 空库后 outbox 列存在；notify 认领成功。  
4. **R4**：双复制并发一只成功；忙时错误码符合所选合同。  
5. **R5**：分进程启动后 kind 隔离冒烟。  
6. **R6**：生成物存在且 typecheck 过。  
7. **R7**：未配 OSS 时仍 LocalDisk；适配器可实例化。  
8. **R8**：架构 front-matter 已改。  
9. **R9**：打印 `R9_S7_BLOCKED=true`。

---

## 5. 交付与合入

1. 从已含 #46 的最新 `main` 开分支：`cursor/remain-gap-9973`（或按波次 `cursor/remain-gap-w1-9973` 等）。  
2. PR 标题示例：`fix(realphotos): remain-gap W1 auth bypass + asset pagination`。  
3. **推送检查清单（Collaborator 推分支前）**  
   - [ ] 本地已跑本 PR 路径对应的 CI 等价命令（ruff / pytest·sqlite / pnpm typecheck+test 等）  
   - [ ] 若改了 Settings / 环境变量读取：相关测试与 monkeypatch **已同改**并通过  
   - [ ] 无密钥入库；`CI gate` 预期可绿（存量基线问题须在 PR 说明，勿假装不知）  
4. 合入：仅非作者 Owner squash；Collaborator 不合并、不打 Tag、不部署。  
5. 完成后回写 `progress.yaml` / `wiki.md`；**不**自动开 S7。

---

## 6. 完成定义（DoD）

- [ ] W1–W4 按裁决完成或书面降级  
- [ ] 每波推送前完成本地 CI 对齐；配置读取变更均有测试同改  
- [ ] 证据含 `production_billing=false`、`R9_S7_BLOCKED=true`  
- [ ] 未宣称生产收费 / S7 完成  
- [ ] R4 路径 A/B 有管理员确认记录  

---

## 7. 与上一工单关系

| 工单 | 关系 |
| --- | --- |
| PRODUCT-GAP-FIX-2026-11-11 | **PR #46 已合入**；G1–G5 已进 `main`；本单**不重复** captcha/锁图/batch20/outbox/OpenAPI 可达 |
| MODULE-A / B | 成本计量、staging 导入、尺寸诚实缺口保持；本单不重开；其 CI 返修经验（配置→settings、测试同改）适用本单 |
