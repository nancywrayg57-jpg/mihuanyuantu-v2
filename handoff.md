# 蜜獾原图 v2 · 新会话移交

## 1. 一分钟接手

项目：蜜獾原图 v2（多租户图片资源 + 硬件化处理 + 积分）。  
仓库根职责文件与编码指令：

1. `handoff.md`（本文件，仓库根）
2. `anchor.md`（现行约束，仓库根）
3. `checkpoint.md`（可核实状态，仓库根）
4. `AGENTS.md`（协作宪法，仓库根）
5. `docs/mihuanyuantu-v2/DEV_INSTRUCTIONS.md`（编码工具切片编排与依据路径）
6. `docs/mihuanyuantu-v2/progress.yaml`（当前阶段与下一步）

再按需打开现行 PRD、项目架构、生产物料清单、Gemini 方案、`prototype/`。  
**不要**把离线 HTML 原型或文档齐全误当成后端已上线。  
**不要**在未明确授权时改业务代码或部署生产。

## 2. 权威顺序

1. 产品行为 → `docs/蜜獾原图-v2-PRD-v2.0.md`
2. 落地结构 → `docs/蜜獾原图-v2-项目架构-v1.0.md`
3. 切片与路径 → `docs/mihuanyuantu-v2/DEV_INSTRUCTIONS.md`

冲突则停并提问。过程技能见 `aidevops/SKILL.md`。

## 3. 位置与版本

| 项 | 路径 / 说明 |
| --- | --- |
| 仓库根 | 含 `AGENTS.md`、`handoff.md`、`anchor.md`、`checkpoint.md`、`aojuai-main/`、`docs/`、`prototype/`、`输入材料/`、`aidevops/` |
| 特征工作区 | `docs/mihuanyuantu-v2/` |
| 编码指令 | `docs/mihuanyuantu-v2/DEV_INSTRUCTIONS.md` |
| 底座 | `aojuai-main/`（钉扎见 `aojuai-main/UPSTREAM_PIN.txt`） |
| 原型 | `prototype/index.html`；改 `prototype.js` 后跑 `node prototype/sync-inline.js` |
| 分支约定 | `cursor/<功能简述>-9973` → PR → `main` |
| 密钥 | 仓库无 `生产物料/`；需要时在聊天向管理员索取，仅写本机环境 |

当前实现状态摘要见 `checkpoint.md`（架构仍为未实现业务闭环；生产未就绪）。

## 4. 关键导航

| 范围 | 打开 |
| --- | --- |
| 切片 S0–S7、门禁、验证环境 | `docs/mihuanyuantu-v2/DEV_INSTRUCTIONS.md` |
| 约束条目 | `anchor.md` |
| 就绪/未就绪事实表 | `checkpoint.md` |
| 协作纪律 | `AGENTS.md` |
| AidevOps 阶段 | `docs/mihuanyuantu-v2/00-discovery.yaml` … `03-acceptance.yaml`、`progress.yaml`、`wiki.md` |
| 交互合同 | `prototype/README.md` |
| 旧算法/405 预设只读 | `输入材料/旧版可复用模块/` |
| 开发/生产主机与目录登记 | `docs/蜜獾原图-v2-生产物料清单-v1.0.md` |

## 5. 下一步应等待的指令

- 默认阻塞：用户**明确授权**按 `DEV_INSTRUCTIONS.md` 从 **S0/S1** 开始编码。
- 授权后：在功能分支实现；主验证跟物料开发机；更新 `progress.yaml` 与本检查点/移交。
- 生产部署：仅在开发指令生产门禁满足后协助；缺 SSH/密钥先问管理员。
- 未授权：可继续文档澄清；不部署、不宣称检测/收费已通。

## 6. 风险提醒（接手必知）

- 原型夹具 ≠ Gemini 真验收。
- 租户共用积分是现行产品选择；账号隔离 ≠ 余额隔离。
- 首版 LocalDisk；不要按「必须先买 OSS」开工。
- `docs/architecture_decisions/`、`docs/archive/`、待决策清单正文**不作为**开发指令依据路径（见 `DEV_INSTRUCTIONS.md`）。
