# 蜜獾原图 v2 · 新会话移交

## 1. 一分钟接手

项目：蜜獾原图 v2（多租户图片资源 + 硬件化处理 + 积分）。

**开工入口（编码工具）**：`docs/mihuanyuantu-v2/DEV_INSTRUCTIONS.md`  
必读根目录职责文件：`AGENTS.md`、`handoff.md`（本文件）、`anchor.md`、`checkpoint.md`。  
过程续作权威：`docs/mihuanyuantu-v2/progress.yaml` 的 `next_action` / 切片状态（本文件与 `checkpoint.md` 只作同步摘要）。

再按需打开现行 PRD、项目架构、生产物料清单、Gemini 方案、`prototype/`。  
不要把离线 HTML 原型或文档齐全误当成后端已上线。

## 2. 权威顺序

1. 产品行为 → `docs/蜜獾原图-v2-PRD-v2.0.md`
2. 落地结构 → `docs/蜜獾原图-v2-项目架构-v1.0.md`
3. 切片与路径 → `docs/mihuanyuantu-v2/DEV_INSTRUCTIONS.md`

冲突则停并提问。过程技能见 `aidevops/SKILL.md`。

## 3. 位置与版本

| 项 | 路径 / 说明 |
| --- | --- |
| 仓库根 | `AGENTS.md`、`handoff.md`、`anchor.md`、`checkpoint.md`、`aojuai-main/`、`docs/`、`prototype/`、`输入材料/`、`aidevops/` |
| 特征工作区 | `docs/mihuanyuantu-v2/` |
| 编码指令 | `docs/mihuanyuantu-v2/DEV_INSTRUCTIONS.md` |
| 底座 | `aojuai-main/`（钉扎见 `aojuai-main/UPSTREAM_PIN.txt`） |
| 原型 | `prototype/index.html`；改 `prototype.js` 后跑 `node prototype/sync-inline.js` |
| 分支约定 | 见 `DEV_INSTRUCTIONS.md` |
| 密钥 | 仓库无 `生产物料/`；需要时在聊天向管理员索取，仅写本机环境 |

当前实现状态摘要见 `checkpoint.md`。

## 4. 关键导航

| 范围 | 打开 |
| --- | --- |
| 切片 S0–S7、门禁、验证环境 | `docs/mihuanyuantu-v2/DEV_INSTRUCTIONS.md` |
| 约束条目 | `anchor.md` |
| 就绪/未就绪事实表 | `checkpoint.md` |
| 协作纪律 | `AGENTS.md` |
| AidevOps 阶段 | `docs/mihuanyuantu-v2/` 下 `progress.yaml` 与阶段 yaml、`wiki.md` |
| 交互合同 | `prototype/README.md` |
| 旧算法/405 预设只读 | `输入材料/旧版可复用模块/` |
| 开发/生产主机与目录登记 | `docs/蜜獾原图-v2-生产物料清单-v1.0.md` |

## 5. 下一步（摘要；以 progress 为准）

- 编码工具按 `DEV_INSTRUCTIONS.md` **自主推进 S0–S6**（遵守切片依赖与有限并行）。
- **S7 生产部署**须管理员确认后再执行；缺密钥/SSH 时在聊天索取。
- 已在基线写明的技术栈/存储/账本/检测器等受保护决策，实现时不必反复索权；合同冲突或路径不存在时停止并提问。

## 6. 风险提醒

- 原型夹具 ≠ Gemini 真验收。
- 租户共用积分是现行产品选择；账号隔离 ≠ 余额隔离。
- 首版 LocalDisk；不要按「必须先买 OSS」开工。
- `docs/architecture_decisions/`、`docs/archive/`、待决策清单正文不作为开发指令依据路径（见 `DEV_INSTRUCTIONS.md`）。
