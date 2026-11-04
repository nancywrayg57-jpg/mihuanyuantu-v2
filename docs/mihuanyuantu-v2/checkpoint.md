# 蜜獾原图 v2 · 检查点

时区标注：Asia/Shanghai。本文件只记录**当前可核实状态**；不是发布说明，也不等同生产验收。

## 1. 仓库与文档基线

| 项目 | 值 |
| --- | --- |
| 仓库 | `https://github.com/nancywrayg57-jpg/mihuanyuantu-v2.git` |
| 文档工作区 | `docs/mihuanyuantu-v2/` |
| 现行 PRD | `docs/蜜獾原图-v2-PRD-v2.0.md`（document_version 以文件头为准） |
| 项目架构 | `docs/蜜獾原图-v2-项目架构-v1.0.md`（`implementation_status: NOT_IMPLEMENTED`） |
| Gemini 方案 | `docs/蜜獾原图-v2-Gemini-Vision检测与自动重做方案-v1.0.md` |
| 生产物料清单 | `docs/蜜獾原图-v2-生产物料清单-v1.0.md`（清单头：`production_readiness: NOT_READY`；`development_readiness: READY_FOR_R0_DOC_AND_BASE_CODING`） |
| Agent 开发指令 | `docs/mihuanyuantu-v2/DEV_INSTRUCTIONS.md` |
| AidevOps 校验 | `python3 aidevops/scripts/validate_workspace.py docs/mihuanyuantu-v2` → 曾报 `ok`（以最新运行为准） |

## 2. 底座与原型（静态事实）

| 项目 | 值 |
| --- | --- |
| 底座目录 | `aojuai-main/` |
| 上游钉扎（文件登记） | `aojuai-main/UPSTREAM_PIN.txt`：`sha add4ddb28916a8745f1be200e15e5a504fb4b4b3` |
| 业务实现包 | 架构目标为 `realphotos`；**当前不等同已交付业务闭环** |
| HTML 原型入口 | `prototype/index.html`（离线交互；mock，不接真实 OSS/模型/支付） |
| 设备预设源 | `输入材料/旧版可复用模块/02_设备参数/线上预设_脱敏原始.json`（`total` / `items` = 405） |
| 仓库内 `生产物料/` | **不存在**；密钥须向管理员索取后仅存本机 |

## 3. 环境登记（摘自物料清单，非本机实测）

| 项目 | 登记值 |
| --- | --- |
| 开发主机 | `192.168.19.128`（物料） |
| 生产应用主机 | `47.242.28.49`（物料） |
| 生产域名 | `exif-demo.honeybadgersoft.com`（物料） |
| 图片盘约定 | 开发/生产 `www/mhyt/` 分子目录（物料） |
| 首版存储策略 | 不开 OSS，LocalDisk（物料 + 架构现行口径） |

> 上表为文档登记；Cloud Agent 环境未代替开发机做连通性验收。

## 4. 切片状态（编排）

| 切片 | 状态 |
| --- | --- |
| S0 基础 | 未开工（编码未授权或未开始） |
| S1 第一刀闭环 | 未开工 |
| S2–S7 | 未开工 |
| 生产部署 | 阻塞：`production_readiness: NOT_READY` + 门禁证据未齐 |

过程账本：`docs/mihuanyuantu-v2/progress.yaml`（以该文件 `next_action` / `phase_gates` 为准）。

## 5. 验证分层（当前）

| 层级 | 状态 |
| --- | --- |
| 文档工作区结构 | AidevOps `validate_workspace` 可通过 |
| 原型交互演示 | 可本地打开；**不等于**后端验收 |
| 业务 API / worker / 整数账本 | **未实现为可验收产品** |
| 真五层 / 真 Gemini 小样 | **未作为本检查点通过项** |
| 生产收费服务 | **未就绪** |

## 6. 本次跳过（信息不足，不编造）

- 开发机/生产机实时进程、磁盘占用、证书到期实探（需在目标主机执行）。
- 具体模型 Key 是否可用、调用延迟与费用。
- 业务迁移版本号 / Alembic head（业务包尚未落地时无可报 heads）。
- 端到端浏览器走查录像（无已授权实现可测）。

有新的可核实提交或验收证据时，更新本节与第 4 节，并同步 `handoff.md`。
