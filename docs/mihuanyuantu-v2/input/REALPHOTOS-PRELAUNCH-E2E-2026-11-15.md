# 蜜獾原图 v2 · 任务工单

| 字段 | 内容 |
| --- | --- |
| 工单编号 | `REALPHOTOS-PRELAUNCH-E2E-2026-11-15` |
| 创建日期 | 2026-11-15 |
| 提出人 | 管理员（侧会话规划） |
| 执行角色 | **主代理**拆单、派发、审计、缺陷分级；**Collaborator 子代理**执行端测与返修；**Owner**审合（**不得自评自合**） |
| 建议分支 | `cursor/prelaunch-e2e-9973`（小写；若从未合入 polish 续作，可先合 #64 再开本分支，或在干净 `origin/main` tip 上新建） |
| 建议 worktree | `/home/hbs/hbs-projects/mihuanyuantu-v2/.worktrees/prelaunch-e2e`（禁止在脏主树或未点名实验分支上混改） |
| 基线 | 开干前 `git fetch`；以当时 `origin/main` tip 为基；若 #64 等 polish 未合入且影响端测，先列依赖再开工 |
| 验证环境 | 开发机本机（`hbs@192.168.19.128` 或同机）FE `:3000` / API `:38000` + PostgreSQL + `realphotos_heartbeat` worker；`scripts/restart-local-preview.sh`（须带共享 `REALPHOTOS_STORAGE_ROOT` 与 duty secrets 可读） |
| 账号策略 | **仅用已有账号**（演示/物料中的商家、订单客服、技术客服、平台管理员）；禁止新建生产式客户账号做「造数表演」；禁止清空业务数据「修好」演示 |
| 不做 | **S7 真实生产部署**（须另开管理员确认）；生产收费；对外宣称「检测通过」服务承诺；改 PRD 信息架构/菜单；改默认 `PASS_SCORE`；发明新业务能力；自评自合；密钥入库；ZIP / OSS 必选 / 独立 GPS 页 |
| 证据总日志 | `/tmp/realphotos-prelaunch-e2e.log`（须含分角色标记与汇总 `REALPHOTOS_PRELAUNCH_E2E_PASS`） |
| 红线 | 端测证据可复查；区分「代码事实 / 测试事实 / 待验证推断」；单元测试 ≠ 端测；Cloud 环境通过 ≠ 开发机验收 |

---

## 0. 背景与目标

### 0.1 现状

- S0–S6 主体能力与多轮专项工单（UI 正式化、OPS-DESK、模型 API、GPS 文案、资源网关等）已合入或在 PR 中；近期本地曾暴露 **worktree 空 LocalDisk**、**duty secrets 路径漏读 → 预审 `missing_credential`**、资源缩略图/批量「对象不存在」等环境+路径类缺陷。
- `DEV_INSTRUCTIONS.md`：**S7 清单仍未写齐，且须管理员确认**；本单做的是**上线前收尾（验收向）**，不是执行生产发布。
- 需要一次**多角色全量端测**，确认主路径功能与资源加载，把潜在 bug 修到可合入，并留下证据，再本地对齐 CI 后推 PR。

### 0.2 目标（管理员确认）

1. **主代理 + 子代理协同**：主代理拆单/审计/门禁；子代理并行或串行执行端测矩阵与缺陷修复。
2. 用**已有账号**跑全量端测：功能是否正常、图片/网关/预设/密钥等资源是否正确加载。
3. 排查并修复端测中发现的潜在 bug（范围限于复现缺陷与上线前阻塞项）。
4. 完成**上线前收尾**文档与进度回写（清单核对、残余风险登记）；**不擅自开 S7**。
5. 端测通过且本地对齐 CI 后，Collaborator **推分支并开/更新 PR**；Owner 审合。

### 0.3 成功标准

- 四角色（商家 / 订单客服 / 技术客服 / 平台管理员）主路径端测均有 PASS 标记与日志片段。
- 图片资源缩略图、网关下载、批量带入、任务结果缩略图（若已合入）在共享存储 + 可读 secrets 下可加载。
- 预审/检测不再因 `missing_credential` 或空 LocalDisk 误失败（真供应商业务拒绝仍按 PRD 记，不算本单基础设施失败）。
- 发现的 P0/P1 bug 已修并有回归证据；P2 可登记延后但须写入残余风险。
- 本地 `secret_scan` + 相关 `ruff`/`pytest` + 前端 `tsc` 对齐 CI 后 PR 已开；未自评自合。

---

## 1. 约束账本（摘要）

| ID | 类型 | 内容 |
| --- | --- | --- |
| C1 | 硬约束 | 仅用已有账号；不清空租户业务数据；不提交真实 `.env` / Key |
| C2 | 硬约束 | 端测在开发机（或同机等价栈）执行；PostgreSQL `claim_one` 等不可用 Cloud 冒充 |
| C3 | 硬约束 | worktree 必须共享主仓 LocalDisk（`REALPHOTOS_STORAGE_ROOT`）且能读到 `生产物料/realphotos-duty-secrets.json` |
| C4 | 硬约束 | 本单**不上生产、不开 S7**；上线门槛未齐且未管理员确认前禁止生产收费话术 |
| C5 | 硬约束 | 双账号：Collaborator 推 PR；Owner 审合；作者不得自合 |
| C6 | 硬约束 | 不改默认 `PASS_SCORE`、不改积分状态机语义、不发明 PRD 未有能力 |
| C7 | 建议 | 缺陷分级：P0 阻塞端测 / P1 主路径错误 / P2 文案与非阻塞体验 |
| C8 | 禁止 | 用 fixture/替身冒充「供应商已接通」或「生产检测通过」 |

---

## 2. 协作模型（主代理 / 子代理）

| 角色 | 职责 |
| --- | --- |
| 主代理 | 读本工单与 `progress.yaml`；环境自检；拆 T1–T5；派发子代理；合并缺陷列表；审计 diff；确认 CI/证据齐全后指令推 PR |
| 子代理 A · 端测 | 按角色矩阵执行浏览器/API 端测，写 `/tmp/realphotos-prelaunch-e2e.log` |
| 子代理 B · 返修 | 对 P0/P1 开最小修复；每修一项补回归片段；不扩 scope |
| Owner（人/主会话） | 审 PR、squash 合入；决定是否另开 S7 |

并行建议：T1 环境自检完成后，T2 角色端测可与「已知回归项」并行；T3 修复依赖 T2 缺陷清单；T4/T5 串行收尾。

---

## 3. 任务拆分

### T1 · 环境与物料自检（阻断）

| 项 | 内容 |
| --- | --- |
| 范围 | `scripts/restart-local-preview.sh`；LocalDisk；duty secrets；FE/API/worker |
| 做法 | 1）`git fetch` + 干净 worktree/分支。<br>2）重启预览，确认日志打印共享 `REALPHOTOS_STORAGE_ROOT`。<br>3）确认 `secret_store_paths` 能命中主仓 `生产物料/realphotos-duty-secrets.json`（`pre_review` / `final_detection` / `generation` / `prompt_opt` 均 `present=true`，**不打印明文**）。<br>4）抽样 `storage.exists(已知 object_key)` 为 true。<br>5）登录页验证码/挑战接口可用（无 `PROXY_BASE_URL_MISSING`）。 |
| 验收 | 四项资源可读；FE `:3000` / API `:38000` / worker 存活 |
| 端测标记 | `T1_ENV_PASS` |

### T2 · 多角色全量端测（已有账号）

按角色裁剪菜单与主路径；每角色至少覆盖下列条目，失败记缺陷 ID。

#### T2-M 商家

- 登录 → 工作台可见性符合角色
- 图片资源：列表分页、缩略图加载、上传（≤20）、勾选 → 去处理
- 批量原图：带入资源预览、预设选择、GPS 跳过中文提示（无 `fixed 无坐标…` 英文泄漏）、提交批次
- 任务详情：列表状态刷新、详情分区、处理完成后缩略图可点放大；未完成行为空白
- 生图（若账号有权）：提交与结果入库；失败路径可读
- 积分与充值：余额/流水类型中文；提交充值单（不要求客服当场确认入账，除非本账号流程需要）
- 消息中心：可读；冻结账号时不能新建任务（若测到冻结态）

#### T2-O 订单客服

- 仅见授权菜单；充值确认主路径
- **无**解冻 / 用户管理 / 系统日志 / 405 预设运营 / 模型 API（按 PRD/S6）

#### T2-T 技术客服

- 工单管理：账号申诉 **20 条/页**；积分冻结列表翻页
- 用户管理（授权范围）：列表可用；操作弹窗；**无**越权改 `rp_admin` 保护项
- 系统日志：**20 条/页**
- 系统管理：可见「自动重做」；**不可见**「模型 API」「检测基线」（非管理员）

#### T2-A 平台管理员

- 系统管理：模型 API / 检测基线入口可见且可打开（不改 `PASS_SCORE` 默认除非管理员另令）
- 预设运营：启停对商家列表生效抽样
- 运营指标：真实数或空态；无商家四卡
- 供应商合同只读核对：不把未配置写成已接通

| 验收 | 各角色 `T2_<ROLE>_PASS`；缺陷写入清单 |
| 端测标记 | `T2_E2E_PASS`（四角色全过才可汇总） |

### T3 · 缺陷修复与已知回归

| 项 | 内容 |
| --- | --- |
| 范围 | T2 新发现 P0/P1；下列**已知回归**必须复测 |
| 已知回归 | ① worktree 空存储 → 缩略图/处理「对象不存在」<br>② worktree 读不到 duty secrets → 预审「预审请求失败」/`missing_credential`<br>③ 批量页仅拉默认 20 条资源导致带入图丢失<br>④ 登录页未配 `API_BASE_URL`/`BACKEND_PORT`<br>⑤ GPS / 页头冗余文案、工单/日志分页（若已合入则回归，未合入则记依赖） |
| 做法 | 最小修复；每项补 `/tmp` 日志片段；禁止借机改 PRD 外能力 |
| 验收 | P0/P1 清零或有管理员书面接受 |
| 端测标记 | `T3_FIX_PASS` |

### T4 · 上线前收尾（非 S7）

| 项 | 内容 |
| --- | --- |
| 范围 | 文档与进度；上线门槛**核对**而非执行部署 |
| 做法 | 1）对照 `DEV_INSTRUCTIONS.md` §11 上线门槛列清单：已具备 / 缺失 / 残余风险。<br>2）回写 `docs/mihuanyuantu-v2/progress.yaml`、`checkpoint.md` §0、`handoff.md` 摘要；入库证据指针 `docs/mihuanyuantu-v2/input/REALPHOTOS-PRELAUNCH-E2E-*.md/txt`。<br>3）明确：**本 PR 不含生产部署、不含 Tag `v2.M.P`、不含改分支保护**。<br>4）若发现须开 S7，单独向管理员请示，不在本单执行。 |
| 验收 | 收尾文档齐全；`production_billing=false` 不误改为 true |
| 端测标记 | `T4_CLOSEOUT_PASS` |

### T5 · 本地 CI 对齐并推 PR

| 项 | 内容 |
| --- | --- |
| 范围 | `.github/workflows/ci.yml` 对应本地门禁 |
| 做法 | 1）`scripts/ci/secret_scan.sh`<br>2）后端：改动相关 `ruff check` + `DB_DRIVER=sqlite pytest`（涉及路径用 worktree `PYTHONPATH`）<br>3）前端：`tsc --noEmit`<br>4）证据汇总写入 `/tmp/realphotos-prelaunch-e2e.log`，含 `REALPHOTOS_PRELAUNCH_E2E_PASS`<br>5）Collaborator push + `gh pr create/update`；标题注明 prelaunch e2e；**不合并** |
| 验收 | CI 本地绿；PR URL 回报管理员 |
| 端测标记 | `T5_PR_PASS` |

---

## 4. 建议实施顺序

1. **T1** 环境自检（阻断）
2. **T2** 四角色端测（可派子代理）
3. **T3** 修 P0/P1 + 已知回归
4. **T4** 上线前收尾文档
5. **T5** 本地 CI → 推 PR → Owner 审合

---

## 5. 协作纪律

1. 仅在指定 worktree / 分支改代码；不碰未点名脏工作区。
2. 合入目标 `main`，仅 PR + squash；作者不得自合。
3. 密钥只读同级 `生产物料/`；聊天可确认「已配置」**不得**贴明文 Key。
4. 证据：`/tmp/realphotos-prelaunch-e2e.log` + `docs/mihuanyuantu-v2/input/REALPHOTOS-PRELAUNCH-E2E-*`。
5. 进度回写 `progress.yaml`（`current_loop` / `next_action`）。
6. 桌面本稿为管理员规划件；执行会话入库副本时保持编号 `REALPHOTOS-PRELAUNCH-E2E-2026-11-15` 一致。

---

## 6. 验收清单（管理员）

- [ ] T1：共享存储 + duty secrets + 预览栈就绪
- [ ] T2：商家 / 订单客服 / 技术客服 / 管理员主路径端测 PASS
- [ ] 资源：库内图、网关、批量带入、任务结果缩略图（适用时）正确加载
- [ ] T3：P0/P1 已修；已知回归已复测
- [ ] T4：上线门槛核对表与残余风险已写；**未执行 S7**
- [ ] T5：本地 CI 绿；PR 已开；未自评自合
- [ ] 日志含 `REALPHOTOS_PRELAUNCH_E2E_PASS`

---

## 7. 参考路径

| 用途 | 路径 |
| --- | --- |
| 开发指令 / 上线门槛 | `docs/mihuanyuantu-v2/DEV_INSTRUCTIONS.md` §6.1、§11、§12 |
| 进度权威 | `docs/mihuanyuantu-v2/progress.yaml` |
| 协作宪法 | 仓库根 `AGENTS.md` §5–§7 |
| 预览重启 | `scripts/restart-local-preview.sh` |
| 密钥解析 | `aojuai-main/backend/app/capabilities/realphotos/services/supplier_secrets.py` |
| 任务详情 | `aojuai-main/frontend/src/app/(app)/realphotos/tasks/page.tsx` |
| 图片资源 / 批量 | `…/library/page.tsx`、`…/batch/batch-client.tsx` |
| 既有 UI 工单 | `/home/hbs/Desktop/蜜獾原图-v2-UI正式化样式工单-2026-11-15.md` |
| 开放 PR（若仍开着） | https://github.com/nancywrayg57-jpg/mihuanyuantu-v2/pull/64 |

---

## 8. 汇总端测标记（写入日志）

```
T1_ENV_PASS
T2_E2E_PASS
T3_FIX_PASS
T4_CLOSEOUT_PASS
T5_PR_PASS
REALPHOTOS_PRELAUNCH_E2E_PASS
```

任一项失败：日志写 `REALPHOTOS_PRELAUNCH_E2E_FAIL` + 失败项 ID，**不得**推「已完成」口径的 PR 描述。

---

**桌面文件路径：** `/home/hbs/Desktop/蜜獾原图-v2-上线前收尾全量端测工单-2026-11-15.md`
