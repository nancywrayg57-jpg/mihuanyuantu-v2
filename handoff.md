# 蜜獾原图 v2 · 新会话移交

## 1. 一分钟接手

项目：蜜獾原图 v2（多租户图片资源 + 相机参数处理 + 积分）。

**开工入口（编码工具）**：`docs/mihuanyuantu-v2/DEV_INSTRUCTIONS.md`  
必读根目录职责文件：`AGENTS.md`、`handoff.md`（本文件）、`anchor.md`、`checkpoint.md`。  
过程续作权威：`docs/mihuanyuantu-v2/progress.yaml` 的 `next_action` / 阶段状态（本文件与 `checkpoint.md` 只作同步摘要）。

再按需打开现行 PRD、项目架构、生产物料清单、Gemini 方案、`prototype/`。  
不要把离线 HTML 原型或文档齐全误当成后端已上线。

## 2. 权威顺序

1. 产品行为 → `docs/蜜獾原图-v2-PRD-v2.0.md`
2. 落地结构 → `docs/蜜獾原图-v2-项目架构-v1.0.md`
3. 阶段划分与路径 → `docs/mihuanyuantu-v2/DEV_INSTRUCTIONS.md`

冲突则停并提问。过程技能见 `aidevops/SKILL.md`。

## 3. 位置与版本

| 项 | 路径 / 说明 |
| --- | --- |
| 仓库根 | `AGENTS.md`、`handoff.md`、`anchor.md`、`checkpoint.md`、`aojuai-main/`、`docs/`、`prototype/`、`输入材料/`、`aidevops/` |
| 本功能文档区 | `docs/mihuanyuantu-v2/` |
| 编码指令 | `docs/mihuanyuantu-v2/DEV_INSTRUCTIONS.md` |
| 底座 | `aojuai-main/`（上游固定版本见 `aojuai-main/UPSTREAM_PIN.txt`） |
| S0 业务包 | `aojuai-main/backend/app/capabilities/realphotos/` |
| 原型 | `prototype/index.html`；改 `prototype.js` 后跑 `node prototype/sync-inline.js` |
| 分支约定 | 见 `DEV_INSTRUCTIONS.md` / `AGENTS.md` §7；收口分支 `cursor/s0-devhost-e2e-closeout-6c0b`（与 `-9973` 后缀冲突已记录） |
| 密钥 | 仓库无 `生产物料/`；需要时在聊天向管理员索取，仅写本机环境 |

当前实现状态摘要见 `checkpoint.md`。

## 4. 关键导航

| 范围 | 打开 |
| --- | --- |
| 阶段 S0–S7、上线门槛、验证环境 | `docs/mihuanyuantu-v2/DEV_INSTRUCTIONS.md` |
| 约束条目 | `anchor.md` |
| 就绪/未就绪事实表 | `checkpoint.md` |
| 协作纪律 | `AGENTS.md` |
| AidevOps 阶段 | `docs/mihuanyuantu-v2/` 下 `progress.yaml` 与阶段 yaml、`wiki.md` |
| 界面约定 | `prototype/README.md` |
| 旧算法/405 预设只读 | `输入材料/旧版可复用模块/` |
| 开发/生产主机与目录登记 | `docs/蜜獾原图-v2-生产物料清单-v1.0.md` |

## 5. 下一步（摘要；以 progress 为准）

- **当前**：**S0 开发机端测已通过并暂停**。开发机本机 `pg_isready` 通过；`scripts.s0_pg_claim_one_smoke` 日志 `/tmp/s0-pg-claim-one-smoke.log` 含 `S0_PG_CLAIM_ONE_PASS`。
- **不得开 S1**，直到管理员授权。
- 端测自治：每里程碑后 Agent 自行在开发机补验（`DEV_INSTRUCTIONS` §6.1）；口令只在同级 `生产物料/` 或本机 `.env`，禁止入库。
- Cloud 证据：`s0-pytest.txt`、`s0-e2e-service.log`。开发机证据：`/tmp/s0-pg-claim-one-smoke.log`。
- **协作**：见 `AGENTS.md` §7。**S7** 须管理员确认。

## 6. 风险提醒

- 原型里的检测替身 ≠ Gemini 真验收；文档齐全 ≠ 后端已交付。
- Cloud 服务端测 ≠ 开发机 PostgreSQL 验收；本机 `claim_one` 已通过，仍须管理员授权后才开 S1。
- 租户共用积分是现行产品选择；账号隔离 ≠ 余额隔离。
- 首版 LocalDisk；不要按「必须先买 OSS」开工。
- 客户业务 API ≠ 上游模型 Key 自助 ≠ 外部平台代发；能力名 scope 外接口必须拒绝。
- `docs/architecture_decisions/`、`docs/archive/`、待决策清单正文不作为开发指令依据路径；ND-017 现行口径以 PRD **2.10** 为准。
