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

1. 以管理员当前明确任务为范围；未授权不扩展到未点名切片、未点名环境或未点名系统改造。
2. 「先看」「给建议」「先审计」「整理文档」不等于授权改业务代码或部署生产；明确要求实现/修改/部署后才做对应动作。
3. 切片编排与依据路径以 `docs/mihuanyuantu-v2/DEV_INSTRUCTIONS.md` 为准；产品行为以现行 PRD 为准；落地结构以项目架构为准。三者冲突时停止并提问，禁止发明新需求。
4. 未经要求不新增外部发布、客户 API、OSS 必选、ZIP 交付、独立 GPS 页、生图自动硬件化等 PRD 已禁止或未纳入当前切片的能力。

## 2. 证据纪律

- 区分：用户要求、现行合同正文、代码事实、测试事实、待验证推断。
- 编号、积分、角色、权限、状态机必须以 PRD/架构/可运行证据为来源；原型演示常量不是生产政策。
- 文档完成、代码完成、验证通过分别陈述；单元/夹具通过不等于端到端或生产验收。
- 不编造密钥已配置、模型已实测、生产已就绪、检测已通过等未证实结论。

## 3. 数据与密钥

- 不提交真实 `.env`、API Key、口令、私钥；仓库内当前无 `生产物料/` 时，缺密钥在聊天中向管理员索取。
- 不清空用户或租户业务数据来「修好」演示；不把源码内种子数据包装成真实客户数据。
- 积分账本、冻结、消费、释放分路径处理；禁止用单一模糊状态替代。
- 图片经受控网关访问；不暴露 LocalDisk 裸路径。

## 4. UI 规则

- 信息架构、角色菜单、主流程对齐 `prototype/`；与 PRD 冲突时听 PRD。
- 沿用原型既有产品密度与中文运营工具风格；不为每个字段堆卡片；列表优先表格。
- 商家 / 订单客服 / 管理员菜单按角色裁剪；管理员工作台不套商家四卡。

## 5. 实现与验证

1. 开工前核对分支、工作树与目标切片（S0–S7），功能分支使用 `cursor/<功能简述>-9973`。
2. 业务落在 aojuai `realphotos`（或架构指定等价包）；旧版材料只读参考，不整包迁入伪队列/用户/Key。
3. 主验证以物料清单登记的开发机为准；Cloud 环境可改代码，不能替代的项须在开发机补验。
4. 生产部署仅在开发指令门禁满足后协助执行；缺 SSH/密钥则询问管理员。
5. 每完成切片更新 AidevOps：`docs/mihuanyuantu-v2/progress.yaml`、阶段文件、`wiki.md`。

## 6. 范围外

只有明确获准时才开展范围外审计、重设计或生产发布。
