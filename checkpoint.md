# 蜜獾原图 v2 · 检查点

时区：Asia/Shanghai。本文件只记录**当前可核实状态**；不是发布说明，也不等同生产验收。

## 0. 每次会话必填（最小集）

| 字段 | 当前值 |
| --- | --- |
| updated | 2026-11-05 17:15 CST |
| branch | `cursor/arch-paths-materials-sibling-9973` |
| HEAD | 以本分支 tip 为准（`git rev-parse --short HEAD`） |
| 文档态 | PRD **2.10**；架构 **1.7**（§1.1 底座/旧版路径已改仓内；密钥=同级 `生产物料/`）；CI/CD=`AGENTS.md` §7 |
| 代码态 | 业务闭环 **未实现**；已有 CI workflows + Tag stub；底座 `api_keys` 仍为路径前缀语义（FR-033 能力名映射待 S5 改造） |
| 验证态 | `main` Required **`CI gate`** 已开；仓 public；同级 `生产物料/蜜獾原图v2-生产物料.md` 已就位（未入库）；开发机/真模型未实测 |
| 当前阶段 | 文档收口已合入；**S0 编码冻结** |
| 下一步 | 明确「授权开 S0」后再按 DEV §10.1 |

## 1. 仓库与文档基线

| 项目 | 值 |
| --- | --- |
| 仓库 | `https://github.com/nancywrayg57-jpg/mihuanyuantu-v2.git` |
| 文档工作区 | `docs/mihuanyuantu-v2/` |
| 现行 PRD | `docs/蜜獾原图-v2-PRD-v2.0.md`（document_version **2.10**；§7 含订单客服 A；AC-024=客户业务 API） |
| 项目架构 | `docs/蜜獾原图-v2-项目架构-v1.0.md`（version **1.7**；`implementation_status: NOT_IMPLEMENTED`） |
| grill 收口 ADR | `docs/architecture_decisions/蜜獾原图-v2-grill-me文档基线收口-2026-11-05.md` |
| Gemini 方案 | `docs/蜜獾原图-v2-Gemini-Vision检测与自动重做方案-v1.0.md` |
| 生产物料清单 | `docs/蜜獾原图-v2-生产物料清单-v1.0.md`（`production_readiness: NOT_READY`） |
| Agent 开发指令 | `docs/mihuanyuantu-v2/DEV_INSTRUCTIONS.md` |
| 根目录职责文件 | `AGENTS.md`、`handoff.md`、`anchor.md`、`checkpoint.md` |
| AidevOps 校验 | `python3 aidevops/scripts/validate_workspace.py docs/mihuanyuantu-v2`（缺 `prototypes/` 目录时结构校验会报错；非 S0 编码阻塞） |

## 2. 底座与原型（静态事实）

| 项目 | 值 |
| --- | --- |
| 底座目录 | `aojuai-main/` |
| 上游固定版本（文件登记） | `aojuai-main/UPSTREAM_PIN.txt`：`sha add4ddb28916a8745f1be200e15e5a504fb4b4b3` |
| 业务实现包 | 架构目标为 `realphotos`；**当前不等同已交付业务闭环** |
| HTML 原型入口 | `prototype/index.html`（离线交互；mock） |
| 设备预设源 | `输入材料/旧版可复用模块/02_设备参数/线上预设_脱敏原始.json` |
| 密钥目录 | 与仓库**同级** `生产物料/`（本机已有 `蜜獾原图v2-生产物料.md`）；**禁止入库** |

## 3. 环境登记（摘自物料清单，非本机实测）

| 项目 | 登记值 |
| --- | --- |
| 开发主机 | `192.168.19.128`（物料） |
| 生产应用主机 | `47.242.28.49`（物料） |
| 生产域名 | `exif-demo.honeybadgersoft.com`（物料） |
| 图片盘约定 | 开发/生产 `www/mhyt/` 分子目录（物料） |
| 首版存储策略 | 不开 OSS，LocalDisk（物料 + 架构现行口径） |

## 4. 阶段状态（编排；细节以 progress 为准）

| 阶段 | 状态 |
| --- | --- |
| 文档收口 | Q1–Q5 已确认；待合入本分支文档 |
| S0 基础 | **冻结**；须管理员「授权开 S0」 |
| S1 首期单张闭环 | 未开工；依赖 S0 退出 + 端测 |
| S2–S6 | 未开工 |
| S7 生产部署 | **须管理员确认** |

过程进度：`docs/mihuanyuantu-v2/progress.yaml`。

## 5. 验证分层（当前）

| 层级 | 状态 |
| --- | --- |
| 文档工作区结构 | AidevOps 缺 `prototypes/` 时 validate 失败；CI D 门仅查关键文件存在 |
| 原型交互演示 | 可本地打开；**不等于**后端验收 |
| 业务 API / worker / 整数积分流水 | **未实现为可验收产品** |
| 真实五层处理 / 真 Gemini 小样 | **未通过** |
| 生产收费服务 | **未就绪** |
| CI Required | **`CI gate`** 已在 `main` 开启 |

## 6. 允许标「未测」但不可省略 §0

- 开发机/生产机实时进程、磁盘、证书实探。
- 模型 Key 可用性与费用。
- 业务 Alembic head（业务包未落地前可写「无」）。
- E2E 浏览器证据（无实现前可写「无」）。

有新的可核实提交或验收证据时，更新 §0 与 §4，并同步 `handoff.md` 摘要与 `progress.yaml`。
