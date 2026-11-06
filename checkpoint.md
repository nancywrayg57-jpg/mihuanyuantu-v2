# 蜜獾原图 v2 · 检查点

时区：Asia/Shanghai。本文件只记录**当前可核实状态**；不是发布说明，也不等同生产验收。

## 0. 每次会话必填（最小集）

| 字段 | 当前值 |
| --- | --- |
| updated | 2026-11-06 CST（Asia/Shanghai） |
| branch | `cursor/s3-gemini-redo-9973`（本地提交，未 push；基线 `cbb68b4`；`origin/main` 仍是 `25fafd6`；PR #21 未合并） |
| HEAD | 本文件随 S3 提交写入。提交后不 push，不合并 |
| 文档态 | PRD **2.10**；架构 **1.7**；物料清单 **1.32**；端测自治见 `DEV_INSTRUCTIONS` §6.1 / `AGENTS.md` §5 |
| 代码态 | S0 已在 `main`。S1 与 S2 在未合并的 PR #21。S3 在 `cursor/s3-gemini-redo-9973`。不是生产收费已开放 |
| 验证态 | 真实小样只认 `/tmp/s3-pg-e2e.log` 的 `S3_PG_SAMPLE_READONLY task_id=29 detector=gemini-3.1-pro-preview noise=45 depthOfField=40 lighting=35 colorRealism=50 overallRealism=35 total_score=38 passed=false has_jpeg=true output_bytes=30982 reservation=released total_is_not_dimension_average=true dimension_average=41.0`。`S3_PG_E2E_PASS` 是同一次调用记录，字段以只读行为准。`/tmp/s3-pg-e2e-controls.log` 的 `S3_PG_CONTROLS_PASS` 使用 `gemini-control`，只证明自动重做、无效响应冻结、主动重处理和技术重试，不代替任务 29。工作台用 `realphotos.s1.taskId=29` 打开后，检测报告为 `detector=gemini-3.1-pro-preview total_score=38 passed=false`，积分处置 `released_detection_not_passed`，下载 30982 字节且 JPEG 头通过。pytest `tests/capabilities/realphotos` 19 passed，含超时、非整数分和技术失败冻结，以及 reprocess 的 `REPROCESS_REJECTED` |
| 当前阶段 | S3 开发机证据已分开。这不是对外「检测通过」，也不是生产收费已开放 |
| 下一步 | 不得开 S4。不得 push，不得合并 PR #21 |

## 1. 仓库与文档基线

| 项目 | 值 |
| --- | --- |
| 仓库 | `https://github.com/nancywrayg57-jpg/mihuanyuantu-v2.git` |
| 文档工作区 | `docs/mihuanyuantu-v2/` |
| 现行 PRD | `docs/蜜獾原图-v2-PRD-v2.0.md`（document_version **2.10**；§7 含订单客服 A；AC-024=客户业务 API） |
| 项目架构 | `docs/蜜獾原图-v2-项目架构-v1.0.md`（version **1.7**） |
| grill 收口 ADR | `docs/architecture_decisions/蜜獾原图-v2-grill-me文档基线收口-2026-11-05.md` |
| Gemini 方案 | `docs/蜜獾原图-v2-Gemini-Vision检测与自动重做方案-v1.0.md` |
| 生产物料清单 | `docs/蜜獾原图-v2-生产物料清单-v1.0.md`（`production_readiness: NOT_READY`） |
| Agent 开发指令 | `docs/mihuanyuantu-v2/DEV_INSTRUCTIONS.md` |
| 根目录职责文件 | `AGENTS.md`、`handoff.md`、`anchor.md`、`checkpoint.md` |
| AidevOps 校验 | `python3 aidevops/scripts/validate_workspace.py docs/mihuanyuantu-v2` |

## 2. 底座与原型（静态事实）

| 项目 | 值 |
| --- | --- |
| 底座目录 | `aojuai-main/` |
| 上游固定版本（文件登记） | `aojuai-main/UPSTREAM_PIN.txt`：`sha add4ddb28916a8745f1be200e15e5a504fb4b4b3` |
| 业务实现包 | `aojuai-main/backend/app/capabilities/realphotos/`（S0 切片已落地；非整包业务闭环） |
| HTML 原型入口 | `prototype/index.html`（离线交互；mock） |
| 设备预设源 | `输入材料/旧版可复用模块/02_设备参数/线上预设_脱敏原始.json` |
| 仓库内 `生产物料/` | **不入库**；同级目录已建 `../生产物料/蜜獾原图v2-生产物料.md`（含 SSH 口令） |

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
| 文档收口 | 已合入 |
| S0 基础 | **代码已实现 + CI 绿**；Cloud 服务端测通过；**开发机 PG `claim_one` 已通过** |
| S1 首期单张闭环 | 开发机 PG 与浏览器主路径已有证据；技术失败积分按决定保持冻结 |
| S2 真实五层 | 开发机 `/tmp/s2-pg-e2e.log` 含 `S2_PG_E2E_PASS`。成功样本字节数不少于源文件；达不到下限的任务失败且无下载对象。检测仍为规则替身 |
| S3–S6 | 未开工。清单未写，禁止开工 |
| S7 生产部署 | **须管理员确认** |

过程进度：`docs/mihuanyuantu-v2/progress.yaml`。

## 5. 验证分层（当前）

| 层级 | 状态 |
| --- | --- |
| 文档工作区结构 | AidevOps 工作区存在 |
| 原型交互演示 | 可本地打开；**不等于**后端验收 |
| S0 业务基础（登录/积分/网关/worker） | Cloud 服务层证据已有；开发机 PG `claim_one` 已通过 |
| 真实五层处理 | 开发机小样已通过：`/tmp/s2-pg-e2e.log`。不是生产收费验收 |
| 真 Gemini 小样 | **未做**（属 S3） |
| 生产收费服务 | **未就绪** |
| CI Required | **`CI gate`** 已在 `main` 开启 |

### Cloud 证据路径（2026-11-05）

- `/opt/cursor/artifacts/s0-pytest.txt` — 8 passed
- `/opt/cursor/artifacts/s0-e2e-service.log` — `S0_E2E_PASS`
- `/opt/cursor/artifacts/s0-ruff.txt` — All checks passed
- `/opt/cursor/artifacts/s0-secret-scan.txt` — passed

### 开发机证据（2026-11-05 22:49 CST）

- 主机：`hbs-VMware-Virtual-Platform`（本机）
- `pg_isready -h 127.0.0.1 -p 5432`：accepting connections（客户端在 `/usr/local/pgsql-16/bin`）
- 命令：`DB_DRIVER=postgresql AOJ_ENABLED_MODULES=realphotos .venv/bin/python -m scripts.s0_pg_claim_one_smoke`
- 日志：`/tmp/s0-pg-claim-one-smoke.log` 含 `S0_PG_CLAIM_ONE_PASS job_id=1 status=succeeded dialect=postgresql`
- 库：`realphotos_dev` @ `127.0.0.1:5432`（口令未入库）

### 开发机 S1 证据（2026-11-06）

- 命令：`DB_DRIVER=postgresql AOJ_ENABLED_MODULES=realphotos .venv/bin/python -m scripts.s1_pg_e2e_smoke`
- 日志：`/tmp/s1-pg-e2e.log` 含 `S1_PG_E2E_PASS task_id=11 peer_task_id=12 dialect=postgresql claimed_by=s1-pg-e2e#15c717aaf1eb9123 presets=3 wallet_delta_two_passes=-20`
- 该次脚本在认领前删除运行中资源，得到 `ASSET_IN_USE`，然后才 `claim_one` 并执行到终态；过期下载返回 410；第二租户读取任务被拒绝。
- 同租户两会话并发冻结（各 10，不同 event_key）：两次都返回 ok，可用 −20、冻结 +20。早前一次无重试的探测出现 `VERSION_CONFLICT`，不能当作通过；当前账本路径会重试版本冲突。
- 浏览器：`/tmp/s1-browser-e2e.txt`。商家工作台拒绝 GIF、接受 1024×768 JPEG、提交后状态为 SUBMITTED，离开页面后 worker 把任务做到 DELIVERED，五维键与 `total_score=90` 可见，下载 JPEG 头通过，站内消息可见。订单客服确认充值单 4、拒单 5 并记下原因。
- 未做：把 `realphotos_0002` 在这台已有 `create_all` 表的库上重放。`alembic_version_cap_realphotos` 当时不存在。
- 已决定：技术失败保持冻结，标记 `held_until_tech_support`，等到技术客服阶段再处理。充值按待决策清单档位入账。

### 开发机 S2 证据（2026-11-06）

- 命令：`DB_DRIVER=postgresql AOJ_ENABLED_MODULES=realphotos .venv/bin/python -m scripts.s1_pg_e2e_smoke`
- 日志：`/tmp/s2-pg-e2e.log` 含 `S2_PG_E2E_PASS task_id=24 peer_task_id=25 constraint_task_id=27 dialect=postgresql claimed_by=s1-pg-e2e#5d0b8414e0d659f3 pipeline=s2-five-layer-1 wallet_delta_two_passes=-20 byte_floor=held dimensions=match colorspace=sRGB exif=read_back gps=none makernote=absent detector=fixture`
- 成功样本在最终编码并恢复 EXIF 之后检查：宽高等于源图，`ColorSpace=sRGB`，字节数不少于源文件。品牌/型号、APEX 快门与光圈可回读。`gpsMode=none` 无 GPS。无 MakerNote。阶段 L1–L5 状态为 completed。检测 `detector=fixture`。
- 源文件尾部带 2MB 无关字节、最终文件仍达不到下限时，任务 `FAILED` / `OUTPUT_CONSTRAINT_UNSATISFIED`，积分保持冻结，没有可下载对象，也没有检测报告。

## 6. 允许标「未测」但不可省略 §0

- 开发机/生产机实时进程、磁盘、证书实探。
- 模型 Key 可用性与费用。
- 业务 Alembic head 在开发机 PostgreSQL 上的真实 upgrade。
- E2E 浏览器证据（S0 以 API/服务层为主；浏览器 UI 非本里程碑必选项）。

有新的可核实提交或验收证据时，更新 §0 与 §4，并同步 `handoff.md` 摘要与 `progress.yaml`。
