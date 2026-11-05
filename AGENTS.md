# Agent Instructions · 蜜獾原图 v2

<!-- AIDEVOPS-ACTIVE:START -->
This workspace has AidevOps activated.

For PRD, user story, design, visual prototype, gpt-image-2 image prototype, architecture, sprint, implementation, review, acceptance, deployment, rollback, or beginner vibe-coding work:

1. Read `aidevops/SKILL.md` before acting, even if the user does not repeat the skill name.
2. Continue from `docs/<feature>/progress.yaml` and the phase files when they exist.
3. Keep Chinese guidance by default for domestic beginner users; keep code/API/env/model identifiers in English.
4. Do not treat this activation as permission to skip clarification, Git checks, protected decisions, or quality gates.

For unrelated small coding questions, answer normally without forcing the full AidevOps workflow.
<!-- AIDEVOPS-ACTIVE:END -->

## 1. 工作范围

1. 以管理员当前明确任务为范围；未授权不扩展到未点名的其他公司项目或未点名系统。
2. 「先看」「给建议」「先审计」「整理文档」不等于授权改无关系统或清空业务数据；实现与部署按编码指令推进。
3. 产品行为以现行 PRD 为准；落地结构以项目架构为准；阶段划分与依据路径以 `docs/mihuanyuantu-v2/DEV_INSTRUCTIONS.md` 为准。三者冲突时停止并提问，禁止发明新需求。
4. 未经要求不新增外部发布、客户自建上游模型 Key、OSS 必选、ZIP 交付、独立 GPS 页、生图成功后自动进入相机参数处理等 PRD 已禁止的能力。本平台业务 API（`X-API-Key` + `image_processing`）已纳入第一版（FR-033），按阶段推进，不在 S1 抢跑。

## 2. 证据纪律

- 区分：用户要求、现行合同正文、代码事实、测试事实、待验证推断。
- 编号、积分、角色、权限、状态机必须以 PRD/架构/可运行证据为来源；原型演示常量不是生产政策。
- 文档完成、代码完成、验证通过分别陈述；单元测试或检测替身通过，不等于端到端或生产验收。
- 每个里程碑完成后必须做端到端测试；确认无误并留下证据后，才可进入下一阶段开发（细则见 `DEV_INSTRUCTIONS.md`）。
- 不编造密钥已配置、模型已实测、生产已就绪、检测已通过、端测已通过等未证实结论。

## 3. 数据与密钥

- 不提交真实 `.env`、API Key、口令、私钥；密钥与生产凭据只读**与仓库同级**的 `生产物料/`（例：`../生产物料/`），**禁止入库**；缺文件时在聊天向管理员索取。
- 不清空用户或租户业务数据来「修好」演示；不把源码内种子数据包装成真实客户数据。
- 积分流水的冻结、消费、释放分路径处理；禁止用单一模糊状态替代。
- 图片经受控网关访问；不暴露 LocalDisk 裸路径。

## 4. UI 规则

- 信息架构、角色菜单、主流程对齐 `prototype/`；与 PRD 冲突时听 PRD。
- 沿用原型既有产品密度与中文运营工具风格；不为每个字段堆卡片；列表优先表格。
- 商家 / 订单客服 / 管理员菜单按角色裁剪；管理员工作台不套商家四卡。

## 5. 实现与验证

阶段划分、验证环境、代码落点、上线门槛与里程碑端测以 `docs/mihuanyuantu-v2/DEV_INSTRUCTIONS.md` 为准；**Git / CI/CD 双账号与合入纪律以本文件第 7 节为准**。每阶段完成后先端测并更新 AidevOps 进度文件（`docs/mihuanyuantu-v2/progress.yaml`、阶段文件、`wiki.md`）及该指令要求维护的根目录状态文件，再进入下一阶段。

**开发机端测自治（管理员已授权）：** 每完成一个里程碑，Agent 须自行按物料 SSH 连接开发机（`hbs@192.168.19.128`；口令在同级 `生产物料/`）执行该阶段端测（含 PostgreSQL `claim_one` 等 Cloud 不可替代项），**无需等待人工代跑**。Cloud 若无法路由 LAN，改走开发机 self-hosted worker 或 VPN/跳板；未连通前不得标阶段完成、不得开下一阶段。细则见 `DEV_INSTRUCTIONS.md` §6.1。

## 6. 范围外

只有明确获准时才开展与当前阶段无关的审计重设计，或跳过上线门槛的发布。

## 7. CI/CD 协作（双账号 · 全局约定）

本节是仓库级协作宪法；`DEV_INSTRUCTIONS.md` 只索引阶段与路径，不重复改写本约定。

### 7.1 分支与合入

- 功能分支：`cursor/<功能简述>-9973`（小写）。
- 合入目标：`main`（**仅经 Pull Request**；禁止直接 push `main`；禁止在 `main` 上直接开发）。
- 合并方式：**仅 squash merge**。
- 提交前确认未跟踪密钥与本地保密目录；忽略规则见 `.gitignore`；行尾约定见 `.gitattributes`。
- `main` 分支保护期望：必须 PR；Required status checks 勾选汇总门禁 job 名 **`CI gate`**；禁止直接 push / force push。

### 7.2 角色与账号

| 角色 | GitHub | Cursor 会话 | 职责 |
|------|--------|-------------|------|
| Owner | `@nancywrayg57-jpg`（Admin） | 主会话 | 研究、拆解、派发、代码审计、合并 PR、打 `v2.M.P` Tag、触发部署、改分支保护与 Actions Secrets |
| Collaborator | `@xtzhou247`（Write） | 子会话 | 具体开发、返修、单测、推分支、开/更新 PR |

- **不得自评自合**：PR 作者账号不能审批或合并自己的 PR；合并仅 Owner 主会话（或 Owner 人工）在**非本人作者**的 PR 上执行。
- Collaborator **禁止**：合并 `main`、打发布 Tag、触发/执行生产部署、修改分支保护与 Actions Secrets。
- 模型不定死：正式开发时由 Owner 主会话选定主/子会话模型及推理强度。

### 7.3 PR 必过检查（首版）

工作流：`.github/workflows/ci.yml`（按改动路径过滤 job；汇总门禁 job 名 **`CI gate`**，应设为 Required）。

| 门 | 范围 | 内容 |
|----|------|------|
| A 安全/红线 | 所有 PR | 拒提交疑似密钥与明文保密文件（`scripts/ci/secret_scan.sh`） |
| B 后端 | `aojuai-main/backend/**` 等 | `ruff check` + `pytest`（`DB_DRIVER=sqlite`） |
| C 前端 | `aojuai-main/frontend/**` 等 | `pnpm typecheck` + `pnpm test` |
| D 文档/流程 | `AGENTS.md`、`DEV_INSTRUCTIONS.md`、`docs/mihuanyuantu-v2/**` 等 | 关键门控文件仍存在 |

- `mypy`、前端 `eslint`/`build`：**暂不阻断**；稳定后由 Owner 决定升为必过。
- **基线注意**：`aojuai-main/backend` 全量 `ruff`/`pytest` 在初始化时点仍可能有存量失败；改动后端前须先修绿，或由 Owner 临时放宽 Required checks。勿在未修绿时把「B 后端」设为唯一合入门槛却无人修基线。
- Cloud Agent 环境通过不等于开发机验收；端测证据规则见 `DEV_INSTRUCTIONS.md`。

### 7.4 Tag 与部署

- 里程碑 Tag：`v2.M.P`（例 `v2.0.1`），**仅 Owner** 在审计通过并合入 `main` 后打。
- Tag 推送触发 `.github/workflows/deploy-stub.yml`（首版 **stub**：校验 Tag、打印部署意图，**不连生产**）。
- **真实生产部署**仍须：`DEV_INSTRUCTIONS.md` S7、上线门槛、**管理员确认**。
- 生产/部署 Secrets：首版可不配；真部署时由 Owner 录入 GitHub Actions Secrets；聊天附件仅可作本机临时配置，**不得入库**。
