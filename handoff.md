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
| 原型 | `prototype/index.html`；改 `prototype.js` 后跑 `node prototype/sync-inline.js` |
| 分支约定 | 见 `DEV_INSTRUCTIONS.md` |
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

- **当前冻结**：grill 收口 ADR 2026-11-05（Q1–Q5）已确认写回；**未收到管理员「授权开 S0」前禁止实现 S0 业务代码**（见 `progress.yaml` `s0_coding_authorized`）。
- 授权后：按 `DEV_INSTRUCTIONS.md` §10.1 完成 S0（任务 / 退出证据 / 禁止项），**端测通过**再进 §10.2 S1。
- **每个里程碑完成后须端测**；未通过或无证据不得开下一阶段。
- **开 S2+ 前**须先补齐该阶段「任务 / 退出证据 / 禁止项」；`02-delivery.yaml` 只同步 status。
- **协作**：Owner `@nancywrayg57-jpg` / Collaborator `@xtzhou247`；合入须过 Required **`CI gate`**；**禁自评自合须 Owner 网页确认后才算门禁齐**（grill Q5）。
- **客户业务 API**（PRD **2.10** / FR-033；架构 **1.7**：`api_keys.scopes`=能力名再映射路径；≠上游 Key）属第一版、S5/R3，**不进 S1**。
- **S7** 须管理员确认；缺密钥/SSH 时在聊天索取。

## 6. 风险提醒

- 原型里的检测替身 ≠ Gemini 真验收；文档齐全 ≠ 后端已交付。
- 租户共用积分是现行产品选择；账号隔离 ≠ 余额隔离。
- 首版 LocalDisk；不要按「必须先买 OSS」开工。
- 客户业务 API ≠ 上游模型 Key 自助 ≠ 外部平台代发；能力名 scope 外接口必须拒绝。
- `docs/architecture_decisions/`、`docs/archive/`、待决策清单正文不作为开发指令依据路径；ND-017 现行口径以 PRD **2.10** 为准。
