# DET-SCORE-OPTIMIZE · Constraint Ledger

工单：管理员 2026-11-14 正式分析（检测分低根因 → 旧仓对照 → 可行方案 → 子代理实施 → 端测/CI → 主代理审计）  
承接：`FIVE-LAYER-LEGACY-ALIGN-SCORE-2026-11-13`  
宪法：`AGENTS.md`（AidevOps 激活；证据纪律；双账号 PR；不改 PASS_SCORE）

## 0. 本轮硬锁（无权放宽）

| ID | 硬锁 | 追溯 |
| --- | --- | --- |
| H-Q1 | 相对 `s2-five-layer-2` 同样本均分 `total_score` 提升 **≥10**（ALIGN 合同仍有效，除非管理员书面改裁） | ALIGN 账本 Q1；本轮用户「不可随意放宽」 |
| H-PASS | **禁止**改 `PASS_SCORE=75` / 检测门闩 | ALIGN Q10；AGENTS §2 |
| H-NODE | 不整包迁 Node；不跑旧 Node 后端 | ALIGN 红线 |
| H-FP | 禁几何指纹（rotate/crop）与可见全局调色刷分 | ALIGN Q7；冲突账本 C 节 |
| H-SIZE | 禁 60%–80% 体积带；禁平台 resize 矩阵 | ALIGN / 架构 |
| H-ORDER | 层序 Layer0→L1→L2→L3→L4→L5；**禁止**回迁 physicalizer「先频域」 | ALIGN |
| H-KEY | 密钥只读同级 `生产物料/`；禁止入库 | AGENTS §3 |
| H-IMPL | **可行性门禁 OPEN 之前禁止编码改像素/提示**（本轮用户明确：确认可行后再由子代理执行） | 本轮用户指令 |
| H-S7 | 不得开 S7 / 生产部署 | AGENTS §6–7；既有闸门 |
| H-PUSH | 端测未 `ALIGN_W5_E2E_PASS` 不得宣称达标；推送/PR 仍受 Q12 + 双账号约束 | ALIGN Q12 |

## 1. 已锁定事实（本轮核验，可追溯）

| ID | 事实 | 证据类型 | 依据 |
| --- | --- | --- | --- |
| F-BRANCH | 当前分支 `cursor/five-layer-legacy-align-9973`；HEAD 含 PR#54 CI/冲突消解提交 | 代码事实 | `git branch` / `git log` |
| F-PIPE | 预览失败任务使用 `pipeline_version=s2-five-layer-3` | 测试事实 | `cap_realphotos_image_tasks` |
| F-SCORE-V3 | 近批 v3 真 Gemini：`total_score` 例 273=55, 272=35, 271=42, 269=48, 268=71, 267=45；**均未过 75** | 测试事实 | `cap_realphotos_detection_results` |
| F-SCORE-DROP | 同库对照：`s2-five-layer-2` 均分≈**65.5**（n=29）→ `s2-five-layer-3` 均分≈**49.3**（n=6）；色彩/整体真实感同步塌陷 | 测试事实 | 子代理库统计 + 主代理复读库表 |
| F-REASON-CA | Gemini reason 点名「严重色差滤镜 / 边缘红蓝伪影」 | 测试事实 | task 271/272 `reason` |
| F-REASON-AI | Gemini reason 点名「生成瑕疵 / 文字扭曲 / 结构不对」 | 测试事实 | task 267/269/273 `reason` |
| F-CA-8MM | 预览预设 `legacy-legacy-online-1073`：`focalLength=8mm` → `focal_length_to_ca_strength=2.0`；`_CA_INTENSITY=1.15` → `shift=ceil(2.3*0.55)=2` px | 代码事实 | `five_layer.py` + 任务 `preset_snapshot` |
| F-CA-LEGACY-GATE | 旧仓有效色差：默认 intensity 下仅焦距 **≤14mm** 才进饱和度×1.02；**composite 被丢弃**；24/35/50mm **像素恒等** | 代码事实（旧仓） | 冲突账本 `C-CA-BUG-GATE`；`imagePhysicalizer.ts` |
| F-L0-ASYNC | Worker 内已有 running loop 时 `_maybe_layer0_img2img` 的 `asyncio.run(generate_images(...))` **失败并 `return None`**；同步路径可成功 | 测试事实 | `/tmp/local-preview-worker.log` ×11 `never awaited`；本机复现 sync len>0 / async None |
| F-L0-E2E | C1 中文提示端测 Layer0 12/12 ok，但 **gain=1.00&lt;10** → SHORTFALL | 测试事实 | `FIVE-LAYER-LEGACY-ALIGN-e2e-c1-zh-2026-11-14.txt` |
| F-BEST-GAIN | 合同内已测最好相对 gain≈**3.83**（英短提示整图 edits）；仍 &lt; Q1 | 测试事实 | ALIGN 账本 |
| F-EXIF-LOCAL | MeteringMode 数字写入 vs PrintConv 回读不一致已本地修复（`Tag#` 回读 + 别名）；**未推送** | 代码事实 | 本会话 EXIF 修复；用户「暂不推送」 |
| F-SCHEMA-LOCAL | 本机缺 `cap_realphotos_platform_settings.deleted_at/tenant_id` 致检测写回前炸；已本地 DDL 补齐 | 测试事实 | worker `ProgrammingError`；本会话 ALTER |
| F-LEGACY-CLONE | 旧仓本地：`/home/hbs/hbs-projects/_refs/mihuanyuantu` @ 既有 SHA；`aiImageProcessor.ts` sha256=`37ca598b…af5b9fb` | 代码事实 | `sha256sum` |
| F-GATE-CLOSED | C1 轮后编码门禁曾标 **CLOSED_after_c1_shortfall**；本轮用户重新授权「研究→可行→再实施」 | 用户要求 + 文档 | `progress.yaml` + 本轮指令 |

## 2. 矛盾 / 歧义 / 前置缺失（先记录，不私自调和）

| ID | 类型 | 描述 | 处置 |
| --- | --- | --- | --- |
| C-Q1-VS-DROP | 目标冲突 | Q1 要相对 v2 **+10**；本地 v3 相对 v2 **均分下降 ≈16** | 先止血再谈冲 Q1；不得改 PASS_SCORE 伪装达标 |
| C-CA-ALIGN | 对齐歧义 | Q4「允许色差」被实现为 **真实通道错位**；旧仓同焦距有效行为接近 **不改像素 / 仅 sat×1.02（已禁）** | **[NEEDS CLARIFICATION]** 是否将 CA 降到「旧有效近零」或保留可见 CA 扫档？ |
| C-L0-INTENT | 行为歧义 | 设计默认开启 Layer0 img2img；worker 路径静默跳过 → 生产与 e2e **不一致** | 必须修 async；修完后分数可能再变（升或降） |
| C-L0-BLAME | 归因歧义 | Gemini「生成瑕疵」可能来自 Layer0 **或** 强光学扰动；worker 上 Layer0 常失败时，归因不得默认 Layer0 | 分路径消融：optical-only / img2img-fixed / CA-off |
| C-IMPL-GATE | 流程 | 用户要求「确认可行后再子代理更新」；ALIGN 曾「SHORTFALL 停止加码」 | 本轮：仅当可行性稿写明 **OPEN 范围** 才编码；OPEN≠已证明 Q1 |
| C-LAYER0-API | 模型边界 | 旧默认 DashScope/qwen；v2=`gpt-image-2` edits **无 strength** | 未批换模型前禁止换供应商模型提分 |
| C-HANDOFF-STALE | 文档 | 根目录 `handoff.md`/`checkpoint.md` 仍停在 AUDIT-REMAIN-CLOSEOUT（2026-11-11） | 本轮研究完成后必须改写为 ALIGN/DET-SCORE 现状 |
| C-EXIF-UNPUSHED | 交付 | EXIF 修复与 schema DDL 仅本地 | 与「检测分」正交；合入策略待管理员/ Q12 |

## 3. 根因工作假说（待消融证伪；非已证明唯一因）

1. **P-CA-PHONE**：手机短焦（如 8mm）触发最大 CA 档 → Gemini 判「色差滤镜」→ `color_realism`/`overall` 塌陷。  
2. **P-V3-OVERDRIVE**：v3 相对 v2 加强噪声/频域/光学 Layer0 → 总分从 ~65 掉到 ~50。  
3. **P-L0-ASYNC**：worker Layer0 未真正执行 → 与 e2e（Layer0 ok）不可比；修 async 后需重测。  
4. **P-ARCH-CEILING**：即使 Layer0+中文提示全开，ALIGN 端测 gain 上限已测 &lt;10 → **单靠对齐旧仓不足以承诺 Q1**。

## 4. 禁止方案（即使提分）

同 ALIGN 冲突账本 §C：指纹 hue/sat + 几何；uploadSimulator；60%–80%；先频域；旧 CA 烂桩原样；失败退原图当成功；改 PASS_SCORE；糊图刷分。

## 5. 本轮阶段闸门

| 阶段 | 状态 | 退出条件 |
| --- | --- | --- |
| R0 账本 | **DONE** | 本文 |
| R1 低分事实 | **DONE**（库表+日志+async 复现） | F-* 行可审计 |
| R2 旧仓对照 | **IN_PROGRESS**（派子代理） | 书面杠杆清单 + 红线映射 |
| R3 可行性 | **PENDING** | 主代理交叉 → `OPEN`/`CLOSED` + 允许改动白名单 |
| R4 子代理编码 | **BLOCKED until OPEN** | 仅白名单 |
| R5 端测+本地 CI | **BLOCKED until R4** | 真 Gemini；不宣称 PASS 除非 gain≥10 |
| R6 主代理审计 | **BLOCKED until R5** | 审计子代理 diff/证据 |

## 6. [ASSUMPTION] 本轮显式假设

| ID | 假设 | 理由 |
| --- | --- | --- |
| A-SAME-CONTRACT | 管理员未改裁 Q1/Q10 时，仍沿用 ALIGN Q1≥10 与 PASS_SCORE=75 | 用户「不可随意放宽」+ 未给新数值 |
| A-LOCAL-EVIDENCE | 本机 Meta/开发库真 Gemini 结果可作为根因证据；正式里程碑标记仍受 `DEV_INSTRUCTIONS` 开发机条款约束 | AGENTS §5 / C-DEVHOST |

## 7. 待管理员澄清（最多保留；不阻塞 R2 研究）

1. **[NEEDS CLARIFICATION: CA 政策]** 手机短焦是否允许「真实通道错位」？或改为对齐旧有效近零？  
2. **[NEEDS CLARIFICATION: Q1 目标]** 若消融后仍无法 +10，是否改裁 Q1、批准换 Layer0 模型，或接受「对齐旧仓不足以承诺 +10」？  
3. **[NEEDS CLARIFICATION: 推送]** EXIF/schema/后续像素修复是否允许在 SHORTFALL 下仍推 PR（此前有 admin PR override 先例）？
