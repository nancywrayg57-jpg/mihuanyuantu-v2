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

- 不提交真实 `.env`、API Key、口令、私钥；仓库内当前无 `生产物料/` 时，缺密钥在聊天中向管理员索取。
- 不清空用户或租户业务数据来「修好」演示；不把源码内种子数据包装成真实客户数据。
- 积分流水的冻结、消费、释放分路径处理；禁止用单一模糊状态替代。
- 图片经受控网关访问；不暴露 LocalDisk 裸路径。

## 4. UI 规则

- 信息架构、角色菜单、主流程对齐 `prototype/`；与 PRD 冲突时听 PRD。
- 沿用原型既有产品密度与中文运营工具风格；不为每个字段堆卡片；列表优先表格。
- 商家 / 订单客服 / 管理员菜单按角色裁剪；管理员工作台不套商家四卡。

## 5. 实现与验证

阶段划分、验证环境、Git 分支、代码落点、上线门槛与里程碑端测以 `docs/mihuanyuantu-v2/DEV_INSTRUCTIONS.md` 为准；每阶段完成后先端测并更新 AidevOps 进度文件（`docs/mihuanyuantu-v2/progress.yaml`、阶段文件、`wiki.md`）及该指令要求维护的根目录状态文件，再进入下一阶段。

## 6. 范围外

只有明确获准时才开展与当前阶段无关的审计重设计，或跳过上线门槛的发布。
