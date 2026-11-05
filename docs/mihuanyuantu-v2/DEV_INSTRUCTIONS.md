# 蜜獾原图 v2 · Agent 开发指令

面向 Cursor / 编码 Agent。本文是**开工入口**：只做切片编排与依据路径索引；不发明产品需求，不替代现行合同正文。  
默认**自主推进 S0–S6**（遵守依赖）；**S7 生产部署须管理员确认**。

## 1. 权威顺序

1. **产品行为** → `docs/蜜獾原图-v2-PRD-v2.0.md`（最高）
2. **落地结构 / 模块 / 数据 / 部署形态** → `docs/蜜獾原图-v2-项目架构-v1.0.md`
3. **切片编排与路径** → 本文件  

冲突时：红线与用户可见行为听 PRD；目录、表、适配器、进程与部署结构听架构；本文件不得新增 PRD/架构未有之需求。若发现三者无法同时满足，**停止实现并在聊天中提问**，禁止自行定夺。

根目录约束快查：`anchor.md`（冲突仍听 PRD）。续作队列权威：`docs/mihuanyuantu-v2/progress.yaml`（`handoff.md` / `checkpoint.md` 为同步摘要）。

## 2. 执行身份与过程账本

- 主执行者：编码 Agent（自主推动开发，不必等待「开始编码」口令）。
- 必须同时遵循：`aidevops/SKILL.md`。
- 仓库根职责文件（每次会话必读，变更后维护）：
  - `AGENTS.md` — 协作宪法与工作纪律
  - `handoff.md` — 新会话摘要与风险
  - `anchor.md` — 现行约束锚点（含节级适用范围）
  - `checkpoint.md` — 可核实状态（含 §0 最小集）
- 新会话顺序：`handoff.md` → `anchor.md` → `checkpoint.md` → `AGENTS.md` → 本文件 → `progress.yaml`。
- 每完成一切片或关键闸口，更新：
  - `progress.yaml`（**下一步以这里为准**）
  - 阶段文件：`00-discovery.yaml` / `01-design.yaml` / `02-delivery.yaml` / `03-acceptance.yaml`
  - `wiki.md`（可复用规则/命令/风险，不写流水账）
  - 根目录 `checkpoint.md` §0；摘要同步 `handoff.md`；约束变更时改 `anchor.md`
- 已在基线写明的技术栈、LocalDisk、整数租户账本、Gemini 为生产检测器等，**不必反复索权**；仅合同冲突、路径不存在、缺密钥、或进入 S7 时停问。
- 仓库级路由：`.aidevops-active.yaml`。

## 3. 硬性禁止

- 禁止把 HTML 原型的 mock / localStorage 当作后端已验收证据。
- 禁止在未满足生产门禁且未经管理员确认 S7 时，对公网生产开放收费或对外宣称「检测通过」。
- 禁止生成 ZIP 交付包；禁止独立 GPS 选择页；禁止生图自动进入硬件化交付——细则见 PRD。
- 禁止提交密钥、口令、真实 `.env`、私钥；禁止把密钥写入本指令、PRD、架构、wiki 或提交记录。
- 禁止将 `docs/architecture_decisions/`、`docs/archive/`、`docs/蜜獾原图-v2-待决策清单-v1.0.md` 列为开发依据或从其正文拷贝规则到实现说明。
- 禁止整包迁入旧版伪队列、假页面、用户数据、积分与 Key。
- 禁止在 `main` 上直接开发。
- 禁止未进入对应切片却实现 `anchor.md` 中标注为后续切片的能力（见节级适用范围）。

## 4. 依据文件路径（开发中应打开）

只列仓库中**真实存在**的路径；缺失项写明索取方式。

### 4.1 合同与设计

| 用途 | 路径 |
|---|---|
| 产品需求与验收行为 | `docs/蜜獾原图-v2-PRD-v2.0.md` |
| 系统实现结构 | `docs/蜜獾原图-v2-项目架构-v1.0.md` |
| Gemini 检测与自动重做生产合同 | `docs/蜜獾原图-v2-Gemini-Vision检测与自动重做方案-v1.0.md` |
| 文档入口索引 | `docs/README.md` |
| 仓库总览 | `README.md` |

### 4.2 环境与物料

| 用途 | 路径 |
|---|---|
| 开发机 / 生产机登记、目录约定、就绪结论 | `docs/蜜獾原图-v2-生产物料清单-v1.0.md` |
| 本地密钥目录 | **当前不存在** `生产物料/`；密钥在聊天向管理员索取，本机保存且永不入库 |
| 后端环境模板（占位） | `aojuai-main/backend/.env.lite.template`、`aojuai-main/backend/.env.production.template` |
| 前端说明 | `aojuai-main/frontend/README.md` |
| 后端说明 | `aojuai-main/backend/README.md` |
| 底座总览 | `aojuai-main/README.md` |
| 底座上游钉扎信息 | `aojuai-main/UPSTREAM_PIN.txt` |

### 4.3 交互与参考实现材料

| 用途 | 路径 |
|---|---|
| HTML 交互合同 | `prototype/README.md`、`prototype/index.html`、`prototype/prototype.js`、`prototype/check-policy.js`、`prototype/device-presets.js` |
| 原型同步脚本 | `prototype/sync-inline.js`（`node prototype/sync-inline.js`） |
| 旧版可复用只读参考 | `输入材料/旧版可复用模块/` |
| 设备预设源数据（405） | `输入材料/旧版可复用模块/02_设备参数/线上预设_脱敏原始.json` |
| AidevOps 本特征工作区 | `docs/mihuanyuantu-v2/` |
| 协作宪法 | `AGENTS.md` |
| 新会话移交 | `handoff.md` |
| 约束锚点 | `anchor.md` |
| 状态检查点 | `checkpoint.md` |
| 本指令 | `docs/mihuanyuantu-v2/DEV_INSTRUCTIONS.md` |

### 4.4 代码落点（实现时）

| 用途 | 路径 |
|---|---|
| 指定底座 | `aojuai-main/` |
| 业务能力包目标（按架构） | `aojuai-main/backend/app/capabilities/` 下 `realphotos`（或架构指定之等价包名） |
| 前端应用 | `aojuai-main/frontend/` |

## 5. 密钥与管理员协作

- 清单级主机、路径、拓扑：只使用 `docs/蜜獾原图-v2-生产物料清单-v1.0.md`。
- 需要 API Key、数据库口令、SSH 等时：**在聊天中通知管理员提供**；写入本机环境变量或本机保密目录，**不得**提交到 Git。
- 配置模板只保留占位符。

## 6. 环境与验证位置

- **主验证环境**：物料清单登记的开发机。
- **Cloud Agent 环境**：可改代码与文档；不能等价替代开发机的验收项，须在开发机补验并留下证据说明。
- **生产服务器**：S7 且门禁通过、管理员确认后部署。

## 7. Git 约定

- 功能分支：`cursor/<功能简述>-9973`（小写）。
- 合入目标：`main`（经 Pull Request）。
- 提交前确认未跟踪密钥与本地保密目录。
- 忽略规则见 `.gitignore`；行尾约定见 `.gitattributes`。

## 8. 交互合同（原型）

- UI 信息架构、角色可见菜单、主操作路径以 `prototype/` 为准。
- 与 PRD 冲突时听 PRD；不得擅自另起一套导航或角色模型。
- 实现后端时，状态、计费、隔离必须满足 PRD，不得用原型夹具冒充生产检测。

## 9. 旧版参考规则

- 允许只读：`输入材料/旧版可复用模块/` 及架构指向的算法/预设原理。
- 新实现写入 aojuai 业务包；参数与保真按 PRD 重新验证。
- 不迁入旧用户、旧 Key、旧积分、旧图片资产。

## 10. 切片编排

原则：

- **基础能力先就绪**，再开启可并行切片。
- **允许有限并行**：在不破坏 PRD 行为与架构边界的前提下，真五层、真 Gemini、生图等可并行推进。
- **有依赖则不可抢跑**。
- **S0–S6 自主推进**；**S7 须管理员确认**。
- 每切片退出必须有可重复验证证据，并回写 AidevOps 与 `checkpoint.md` §0。
- **三件套硬规则**：每个切片开工前，本文件须已写明该切片的 `tasks` / `exit_evidence` / `forbidden`。当前仅 **S0、S1** 已齐；**开 S2–S7 任一切片前必须先补齐该切片三件套，缺一禁止开工**。清单正文以本文件为准；`progress.yaml` / `02-delivery.yaml` 只镜像完成状态与 `next_action`。条目只写 ID 与短句，行为冲突仍听 PRD。

| ID | 切片 | 内容要点 | 依赖 | 可并行对象 |
|---|---|---|---|---|
| S0 | 基础 | 真会话登录；租户/账号；RBAC（商家、订单客服 A 档、管理员）；`rp_credit_*` 整数账本；LocalDisk 存储适配器 + 受控访问网关；PostgreSQL 持久任务队列；同机 worker | 无 | — |
| S1 | 第一刀闭环 | 本地上传硬校验；≤3 启用预设；单张处理；预审桩；假五层（仍输出 sRGB JPEG + 预设快照字段）；Gemini 规则夹具；站内消息；下载 / `expires_at` 拒绝；空闲资源软删；同租户双账号共用积分 + 第二租户隔离 | S0 | — |
| S2 | 算法证据 | 真五层替换假桩；完成保真与字节下限小样并归档 | S1 | 可与 S4 文档/接口准备并行 |
| S3 | 检测门禁 | 真 Gemini 调用；自动重做与主动重处理按 PRD/方案；真实小样与供应商证据归档 | S1 | 可与 S2 并行；生产收费前 S2+S3 证据均需具备 |
| S4 | 批次与账本增强 | 1–10 张部分成功、按张结算、并发与释放 | S1 | 可与 S2/S3/S5 部分并行 |
| S5 | 增长能力 | 文生图/图生图只入库；提示词优化；URL 导入（无供应商证据前不得真呼）；**客户业务 API**（`X-API-Key` + scope=`image_processing` + OpenAPI/Swagger，FR-033） | S1 | 可与 S2/S3/S4 并行 |
| S6 | 运营完备 | 真预审与冻号规则；技术客服；用户管理；系统日志；设备预设 405 运营；运营指标 | S1 | 可与 S2–S5 并行 |
| S7 | 上线与生产部署 | 按物料与架构完成 TLS/发布/回滚/监控等；部署到生产服务器 | S0–S6 相关项 + 第 11 节门禁 + **管理员确认** | — |

### 10.1 S0 · 基础

**tasks**

| ID | 任务 | 验证要点 |
|---|---|---|
| T-S0-001 | 真会话登录（开发验证码可）+ 租户/账号模型落库 | 合法会话可进；无会话拒绝 |
| T-001 | RBAC 种子：merchant×2、order_support、admin、第二租户 | 三角色可登录；跨租户拒绝 |
| T-002 | `rp_credit_*` 整数账本与旧 Decimal 入口隔离 | 整数余额；旧 Decimal 对 realphotos 不可用 |
| T-003 | LocalDisk `StorageAdapter` + 受控访问网关 | 无裸路径；鉴权可读 |
| T-S0-002 | PostgreSQL 持久任务队列 + 同机 worker 骨架（可消费 no-op/心跳任务） | 入队后 worker 可取到并达终态；关 API 进程后队列仍在库 |

**exit_evidence**（全部勾选才可标 S0 完成并开 S1）

- 商家 / 订单客服 A 档 / 管理员均可登录；第二租户账号无法读第一租户对象。
- `rp_credit_*` 整数户可手工加减并出流水；旧 Decimal 入口对 realphotos 不可用。
- LocalDisk 读写只经鉴权网关；响应中无裸磁盘路径。
- PG 队列至少跑通一条可重复的 worker 消费证据（命令输出或开发机日志路径记入 artifacts / `checkpoint.md`）。
- 上述证据已回写 `progress.yaml` 与 `checkpoint.md` §0。

**forbidden**

- 未勾满本切片 `exit_evidence` 不得标 S0 完成，不得开 S1。
- 禁止把 OSS 当首版必选；禁止提交真实 `.env` / 密钥。
- 禁止整包迁入旧用户、旧积分、旧 Key、旧图片资产。
- 禁止提前实现 `anchor.md` 中 `from:S2+` / `from:S5` / `from:S6` / 节 G 能力，并宣称属 S0。
- 禁止用 HTML 原型 mock / localStorage 冒充本切片退出证据。

### 10.2 S1 · 第一刀闭环

**实现边界**

- 账本 / 任务状态机 / 落库 worker / LocalDisk 网关下载：真实实现。
- 预审：桩（默认通过；管理员可强制拒绝）；文件硬校验必须真。
- 五层：假桩，但交付物合同字段必须真。
- 最终检测：规则夹具，键名与通过规则对齐 Gemini 方案文件。
- 不做：见 `anchor.md` 节 G（与下方 `forbidden`）。

**tasks**（依赖 S0 退出；与 `02-delivery.yaml` ID 对齐）

| ID | 任务 | 验证要点 |
|---|---|---|
| T-004 | 上传硬校验与资源表 | AC-K1-001 |
| T-005 | 处理任务表 + PG 队列 worker（单张状态机到终态） | AC-K1-002 |
| T-006 | StubFiveLayer + FixtureDetector + 管理员注入 | JPG + 五维键；管理员可注入未通过/技术异常 |
| T-007 | 单张冻结/结算/释放与站内消息 outbox | AC-K1-003；双账号并发冒烟 |
| T-008 | 订单客服最小确认/拒单 | 确认到账；拒单记原因 |
| T-009 | 过期拒绝下载 + 资源软删 | 过期拒绝；运行中禁删 |
| T-010 | 第一刀退出证据清单走查 | 下列 `exit_evidence` 全勾 |

**exit_evidence**（对照 `00-discovery` AC-K1；全部勾选才可标 S1 完成）

- AC-K1-001：非法格式/超限被前后端拒绝且不建资产。
- AC-K1-002：请求返回后关闭页面，任务仍可达终态（worker 关页后续跑）。
- AC-K1-003：同租户账号 B 可消耗账号 A 入账积分；流水记操作账号；双账号并发冒烟通过。
- AC-K1-004：第二租户令牌读第一租户资源/任务/余额/下载一律拒绝。
- 过期后下载拒绝；运行中任务占用资源禁止删除。
- 订单客服可对种子充值订单确认到账或拒单并记原因。
- ≤3 启用预设可选；单张路径产出 sRGB JPEG + 预设快照字段；夹具报告含五维键。
- 证据已回写 `progress.yaml`、`02-delivery.yaml` 任务状态与 `checkpoint.md` §0（含 artifacts 路径）。

**forbidden**

- 未勾满本切片 `exit_evidence` 不得标 S1 完成，不得开 S2+。
- 禁止实现或验收宣称 `anchor.md` 节 G（`not:S1`）：文生图/图生图、提示词优化、URL 真导入、405 运营台、真预审/冻号台、真五层、真 Gemini、自动重做/主动重处理、2–10 混合批次、技术客服台、ZIP、OSS 必选、扫码支付、客户业务 API（FR-033，属第一版/S5，不进 S1 退出）、运营大盘。
- 禁止把 StubFiveLayer / FixtureDetector 标为生产已验收或「检测通过」对外承诺。
- 禁止用原型 mock / localStorage 冒充后端验收证据。
- 禁止生产收费与公网开放收费检测（属 S7 + 门禁）。

### 10.3 资金与角色（编排级）

- 积分：租户共用整数户；扣费/冻结记操作账号；账号预审冻结不冻结整户余额。
- 订单客服 A 档：确认/拒单与查看订单凭证；不解冻、不看业务原图、不改系统模型/预设。
- 技术客服：归入 S6。

## 11. 生产门禁与部署（S7）

同时满足且**管理员确认 S7** 前，禁止生产收费与对外「检测通过」服务承诺：

- PRD 要求的真实模型/算法小样与归档证据已具备。
- 物料清单中生产就绪阻塞项已关闭或由管理员明确接受残余风险。
- 部署目标、域名、TLS、回滚与监控按架构与物料执行。

缺密钥或 SSH 时在聊天中向管理员索取。不得绕过门禁强行发布。

## 12. 切片完成定义（通用）

1. 代码在功能分支上可审查；
2. 对照 PRD 相关 FR/AC（及本切片范围）的验证记录或命令输出；
3. `progress.yaml` 与相关阶段文件已更新；
4. `checkpoint.md` §0 已更新（含 SHA/分支）；
5. 无密钥泄漏；
6. 未把夹具/桩误标为生产已验收。

## 13. 开工检查清单（每次会话）

1. 读根目录 `handoff.md`、`anchor.md`、`checkpoint.md`、`AGENTS.md`，再读本文件与 `aidevops/SKILL.md`。  
2. 读 `progress.yaml`，按 `next_action` 续作（权威）。  
3. 读本切片相关的 PRD/架构/物料/Gemini 章节；UI 对照 `prototype/`。  
4. 在 `cursor/<功能简述>-9973` 分支工作。  
5. 缺密钥则问管理员，再写本机配置。  
6. 实现并验证后更新 AidevOps、`checkpoint.md` §0，摘要同步 `handoff.md`。  

## 14. 语言与标识

- 对人说明、阶段说明、产品文案：默认中文。  
- 代码标识、API、模型名、环境变量、文件路径、命令：英文或仓库既有形式。
