# 蜜獾原图 v2 · 检查点

时区：Asia/Shanghai。本文件只记录**当前可核实状态**；不是发布说明，也不等同生产验收。

## 0. 每次会话必填（最小集）

| 字段 | 当前值 |
| --- | --- |
| updated | 2026-11-05 10:50 CST |
| branch | `cursor/arch-schema-flow-rbac-2d1c` |
| HEAD | `751d400`（短 SHA；以更新本文件时的 `git rev-parse --short HEAD` 为准） |
| 文档态 | PRD 2.9；架构 **1.6**（§5.4表裁剪/§5.5流转/§10.2–10.4 RBAC·双Token·支付图片）；01-design 已确认 |
| 代码态 | 业务闭环 **未实现**（`aojuai-main` 无 realphotos 可验收交付；底座已有通用 `api_keys` 表） |
| 验证态 | `validate_workspace` ok；开发机连通与真模型 **未在本检查点实测** |
| 当前阶段 | S0 **待自主推进**（以 `progress.yaml` 为准）；客户业务 API 不抢跑 |
| 下一步 | 按 `DEV_INSTRUCTIONS` §10.1 推进 S0；端测通过后再开 S1；FR-033 属 S5/R3 |

## 1. 仓库与文档基线

| 项目 | 值 |
| --- | --- |
| 仓库 | `https://github.com/nancywrayg57-jpg/mihuanyuantu-v2.git` |
| 文档工作区 | `docs/mihuanyuantu-v2/` |
| 现行 PRD | `docs/蜜獾原图-v2-PRD-v2.0.md`（document_version 2.9；AC-024=客户业务 API） |
| 项目架构 | `docs/蜜獾原图-v2-项目架构-v1.0.md`（version **1.6**；`implementation_status: NOT_IMPLEMENTED`） |
| Gemini 方案 | `docs/蜜獾原图-v2-Gemini-Vision检测与自动重做方案-v1.0.md` |
| 生产物料清单 | `docs/蜜獾原图-v2-生产物料清单-v1.0.md`（`production_readiness: NOT_READY`；`development_readiness: READY_FOR_R0_DOC_AND_BASE_CODING`） |
| Agent 开发指令 | `docs/mihuanyuantu-v2/DEV_INSTRUCTIONS.md` |
| 根目录职责文件 | `AGENTS.md`、`handoff.md`、`anchor.md`、`checkpoint.md` |
| AidevOps 校验 | `python3 aidevops/scripts/validate_workspace.py docs/mihuanyuantu-v2`（更新本文件时应重跑；结果写入验证态） |

## 2. 底座与原型（静态事实）

| 项目 | 值 |
| --- | --- |
| 底座目录 | `aojuai-main/` |
| 上游固定版本（文件登记） | `aojuai-main/UPSTREAM_PIN.txt`：`sha add4ddb28916a8745f1be200e15e5a504fb4b4b3` |
| 业务实现包 | 架构目标为 `realphotos`；**当前不等同已交付业务闭环** |
| HTML 原型入口 | `prototype/index.html`（离线交互；mock） |
| 设备预设源 | `输入材料/旧版可复用模块/02_设备参数/线上预设_脱敏原始.json`（`total` / `items` = 405） |
| 后端 env 模板（仓库内） | `aojuai-main/backend/.env.lite.template`、`aojuai-main/backend/.env.production.template` |
| 仓库内 `生产物料/` | **不存在**；密钥向管理员索取后仅存本机 |

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
| S0 基础 | 未开工；§10.1 清单已齐；完成后须端测通过才可开 S1 |
| S1 首期单张闭环 | 未开工；§10.2 清单已齐；依赖 S0 退出 + S0 端测通过 |
| S2–S6 | 未开工；S1 后可按依赖有限并行自主推进 |
| S7 生产部署 | **须管理员确认**；且 `production_readiness: NOT_READY` + 上线门槛证据 |

过程进度：`docs/mihuanyuantu-v2/progress.yaml`。

## 5. 验证分层（当前）

| 层级 | 状态 |
| --- | --- |
| 文档工作区结构 | AidevOps `validate_workspace` 可通过 |
| 原型交互演示 | 可本地打开；**不等于**后端验收 |
| 业务 API / worker / 整数积分流水 | **未实现为可验收产品** |
| 真实五层处理 / 真 Gemini 小样 | **未通过** |
| 生产收费服务 | **未就绪** |

## 6. 允许标「未测」但不可省略 §0

- 开发机/生产机实时进程、磁盘、证书实探。
- 模型 Key 可用性与费用。
- 业务 Alembic head（业务包未落地前可写「无」）。
- E2E 浏览器证据（无实现前可写「无」）。

有新的可核实提交或验收证据时，更新 §0 与 §4，并同步 `handoff.md` 摘要与 `progress.yaml`。
