# 任务工单 · DET-SCORE-NONLEGACY-LIFT（非旧版联网方案 · 可判定后再执行）

| 项 | 值 |
| --- | --- |
| 工单 ID | `DET-SCORE-NONLEGACY-LIFT` |
| 日期 | 2026-11-14 |
| 执行方 | **主会话（Owner）** 调度 **主/子代理协作**；Collaborator 子会话仅按本单编码/测/推 PR |
| 继承 | `DET-SCORE-OPTIMIZE` → `FIVE-LAYER-LEGACY-ALIGN` |
| 分支建议 | 在止血合入后开新功能分支 `cursor/det-score-nonlegacy-lift-9973`（或主会话裁定续用现分支但**新里程碑名**） |
| 合入 | 仅 PR → `main`；**squash**；作者账号不得自评自合（`AGENTS.md` §7） |
| 生产/S7 | **禁止**；本单止于开发机真 Gemini 端测 + 可选 PR |

---

## 0. 管理员裁决（本单生效前提）

侧聊管理员已确认：**止血已完成**。主会话须按此执行，不得再卡在「是否推送止血」上。

| 裁决 | 含义 |
| --- | --- |
| 止血完成 | 白名单 **A+D+B** 视为交付完成：`ALIGN_LAYER0_IMG2IMG` 默认 `0`；`_CA_INTENSITY=0`；Layer0 它线程 `asyncio.run`+`join` 修复；失败日志含 `error_type` |
| 旧版对齐冲 Q1 | **关闭加码**：ALIGN/协议 C 已 `SHORTFALL`（gain≪10），**不得**再以旧仓杠杆复跑冒充达标 |
| 本单目标 | 在**不放宽 `PASS_SCORE=75`、不改合同 Q1 数字除非另裁**的前提下，**联网检索旧版以外方案 → 充分判定项目可用性 → 仅对判定可用者编码+端测** |
| 仍禁止 | 升 R4 测量值为默认；对抗式攻击管线入库；密钥入库；清空业务数据；S7/生产部署 |

---

## 1. 本地进度快照（侧聊核验 · 2026-11-14）

### 1.1 止血（代码事实 · 未必要已 push）

| 项 | 状态 |
| --- | --- |
| 分支 | `cursor/five-layer-legacy-align-9973`（相对 origin 有**未提交**改动） |
| `_CA_INTENSITY` | **`0.0`**（8mm/26mm 与输入恒等，无 saturation×1.02） |
| `ALIGN_LAYER0_IMG2IMG` | 默认 **`0`** |
| Layer0 async | 它线程 `asyncio.run(generate_images)` 后 `join`（已修） |
| `PASS_SCORE` | **75 未改** |
| `PIPELINE_VERSION` | 仍 `s2-five-layer-3` |
| 本地证据 | 协议 W：8mm mean_v3≈**62.17**（史≈49，色差 reason **0/12**）；pytest `test_s2_five_layer` **17 passed** |
| progress | `det_score_optimize_2026_11_14`；`coding_gate: OPEN_PARTIAL_IMPLEMENTED_LOCAL`；`pushed: false` |

**主会话 W0：** 将止血改动 **commit → push → 开/更新 PR**（若尚未合入），标题/正文写明「止血 A+D+B，不宣称 Q1 PASS」。合入前跑 CI 门禁。**不得**把后续非旧版试点塞进同一未审计大包而不写清。

### 1.2 旧版/ALIGN 冲分结论（不得再当作可加码路径）

| 臂 | 结果 |
| --- | --- |
| ALIGN W5 英短最优 | gain≈**3.83** ≪ 10 → `SHORTFALL` |
| C1 中文 | gain=**1.00** |
| 协议 C（止血默认 + score_fn + 26mm） | mean_v2=**65.75** mean_v3=**66.92** gain=**+1.17** → `ALIGN_W5_E2E_SHORTFALL`；过 75 仅 **2/12** |
| R4 光学/噪声降档测量 | Δ vs W ≈ **+0.83** → `P-V3-OVERDRIVE NOT_CONFIRMED`；**禁止**升为默认 |
| PR #54 | 已 **MERGED**（ALIGN 研究/UX；**未**宣称 W5 PASS） |

根因共识（证据级）：分差主要来自 **v3 处理伪影（曾 CA+Layer0）**，不是阈值；止血后分回升但仍相对 v2 冲 **+10 未证明** → 属 **架构/检测器响应天花板**，需**旧版外**新杠杆。

### 1.3 侧聊已备「非旧版」研究摘要（主会话须复核，不得直接当编码许可）

下列为侧聊 WebSearch / 文献摘要的**候选方向**与**项目适配初判**；主会话子代理须**再联网核实**并写入可行性门禁后，才可 OPEN 编码。

| 候选 | 文献/来源要点 | 项目初判 | 编码倾向 |
| --- | --- | --- | --- |
| **弱正向 ISP / Bayer 回投** | 真机 Bayer→demosaic→WB/tone 会留下 CFA 相关统计；检测侧常用 Bayer/像素方差（如 ICIPW 2025 Bayer one-class）；ISPCloak 类把「逆 ISP + Poisson–Gaussian + 正 ISP」用于**对抗逃逸** | **可用思路：弱、可解释、前馈的「相机物理仿真」子集**；**不可用：优化对抗、自适应 mask 攻击、以逃逸检测器为唯一目标的武器化管线** | 试点：轻量 mosaicing→加信号相关噪声→demosaic；强度可扫；对比止血基线 |
| **Poisson–Gaussian / 平坦区传感器噪声** | 真图平坦块有机噪声；生成图常「过干净」；简单 patch 噪声是常见判别 | **可用**：在现有 L 噪声层上做**更贴近光子噪声**的弱注入，避免再引入 CA 类色偏伪影 | 试点：ISO 相关、纹理自适应；**禁止**大强度毁画质 |
| **频域/JPEG 再编码温和化** | 检测看 mid/high 频与 JPEG 量化；重压 JPEG / 轻度模糊可降检测置信，但也伤「真相机」观感与五维语义分 | **谨慎可用**：与现有 encode 层对齐的 **Q 表/二次 JPEG** 微调；blur 仅极弱 | 先测五维分是否掉；掉则否决 |
| **可控语义 Layer0（非默认开）** | 旧 ALIGN Layer0 img2img 未兑现 +10；止血默认关正确 | **仅测量臂**：Key 可用时 `ALIGN_LAYER0_IMG2IMG=1` + **真实 strength** + 失败不静默；默认仍 0 | 不得把 Layer0 再设回默认开 |
| **对抗式 / 梯度 camouflage（ISPCloak 全套等）** | 明确「weaponize / adversarial」 | **项目禁用**（合规、可维护、PRD 真照片增强定位冲突） | 硬拒绝 |
| **放宽 PASS_SCORE / 改提示骗分** | — | **禁用** | 硬拒绝 |
| **仅堆 EXIF** | Gemini 侧对元数据依赖弱；本仓已有 EXIF 路径 | **辅助保留**，不单独当提分主杠杆 | 不单开 |

**侧聊结论一句话：** 优先 **弱 ISP/Bayer + 信号相关噪声** 的可解释物理仿真；保留 **可控 Layer0 测量臂**；禁止对抗管线与阈值放宽。

---

## 2. 目标与成功标准

### 2.1 用户价值

技术处理图在 **真 Gemini 五维检测** 下，相对止血后基线（及/或合同 v2）**可测量提升**；争取更多样本过 **75**；**不**通过降低门槛达标。

### 2.2 门禁标记（本单新标记，勿复用 SHORTFALL 冒充 PASS）

| 标记 | 条件 |
| --- | --- |
| `NONLEGACY_FEASIBILITY_PASS` | ≥1 个候选写清：机理、依赖、风险、与现 `five_layer` 落点、**为何适配本仓**；且无红线 |
| `NONLEGACY_PILOT_E2E_GAIN` | 开发机真 Gemini；合同 12 张（或主会话书面批准的同构集）；相对**止血基线** mean 提升，证据落盘 |
| `NONLEGACY_Q1_PROBE` | 若仍对标旧 Q1（相对 v2 gain≥10）：单独跑协议并标记 PASS/SHORTFALL；**SHORTFALL 不得宣称产品达标** |
| 失败退出 | 可行性全否 → 停止编码，仅交付研究报告 + 管理员选项（改裁目标 / 接受天花板） |

### 2.3 非目标

- 不重开旧版 ALIGN 加码循环  
- 不升 R4 为默认、不默认开 Layer0、不恢复 CA  
- 不 S7、不改分支保护、不碰生产 Secrets  

---

## 3. 主/子代理协作模型（强制）

```
主会话（Owner）
 ├─ 子代理 R1  联网检索（旧版以外 · 相机 ISP/Bayer/噪声/JPEG · 2024–2026）
 ├─ 子代理 R2  对抗文献红线过滤 + 合规/PRD 适配（否决 weaponize）
 ├─ 子代理 A   对照本仓 five_layer / 检测五维 / 现有噪声·encode 层，出「可落点映射表」
 ├─ 主会话     汇总结论 → 写可行性门禁 → 仅对 PASS 项 OPEN 编码
 ├─ 子代理 I   （Collaborator 或同会话实现臂）白名单编码 + 单测
 └─ 主会话     审计 diff → 开发机端测 → 更新 progress → 按 Q12 决定是否 PR
```

规则：

1. **先研究判定，后编码**；无 `NONLEGACY_FEASIBILITY_PASS` 不得改 `five_layer` 默认行为（测量覆写脚本除外）。  
2. 子代理配额失败时：主会话降模型重跑或主会话自研，**不得空过门禁**。  
3. 侧聊摘要（§1.3）可作种子，但 **R1 必须独立联网**，附 URL/题录；禁止只抄侧聊。  
4. 编码白名单须主会话书面列出文件级路径；越权改检测阈值 / PASS_SCORE → 审计 FAIL 回滚。

---

## 4. 工作包

### W0 · 止血入库（本单 Day-0，管理员已确认完成）

- [ ] `git status` 确认 A+D+B 相关 diff（`five_layer.py` / `config.py` / `test_s2_five_layer.py` + DET-SCORE 文档）  
- [ ] commit（信息点明止血，不宣称 Q1）→ push → PR（Collaborator）→ Owner 合并  
- [ ] 更新 `docs/mihuanyuantu-v2/progress.yaml`：`止血 pushed/merged`；`next` 指向本工单  
- [ ] **冻结止血基线**：协议 C 同类配置下 mean_v3 记为 `hemo_baseline`（可用已有 `DET-SCORE-OPTIMIZE-protocol-c-2026-11-14.txt`）

### W1 · 联网研究（子代理 R1+R2，主会话汇总）

产出路径建议：

- `docs/mihuanyuantu-v2/input/DET-SCORE-NONLEGACY-web-research-YYYY-MM-DD.md`  
- `docs/mihuanyuantu-v2/input/DET-SCORE-NONLEGACY-redline-filter-YYYY-MM-DD.md`

检索关键词（至少覆盖）：

- Bayer / CFA demosaic detection AI-generated  
- camera ISP pipeline simulation sensor noise Poisson-Gaussian  
- anti-forensics vs camera fingerprint（**用于否决清单**）  
- JPEG recompression frequency artifacts AI detection  
- **排除**：仅复述旧仓 `aiImageProcessor` 已否路径  

每条候选表列：`名称 | 机理 | 开源/可复现性 | 算力 | 视觉可感知风险 | 与 Gemini 五维可能关系 | 红线(是/否) | 初判(试/缓/禁)`

### W2 · 项目适配判定（子代理 A + 主会话）

产出：`docs/mihuanyuantu-v2/input/DET-SCORE-NONLEGACY-feasibility-gate-YYYY-MM-DD.md`

对每个「试」项回答：

1. 落点：新函数 / 插入层序（相对 L1–L5 / 可选 Layer0）  
2. 默认开还是 **仅 env 测量臂**（推荐测量臂先）  
3. 与止血不冲突（不得隐式恢复 CA / 默认 Layer0）  
4. 依赖：纯 numpy/Pillow/opencv 否？是否新模型权重？（新权重需管理员另批）  
5. 失败模式：异常时是否恒等回退  
6. **判定：OPEN_PILOT / DEFER / REJECT**

仅 `OPEN_PILOT` 进入 W3。若全部 REJECT/DEFER → 停止，向管理员交选项单。

### W3 · 试点编码（白名单 · 子代理 I）

原则：**测量臂优先**；默认路径保持止血行为，直到端测证明增益且主会话批准「默认开启」。

建议试点顺序（可按门禁调整）：

1. **弱 Bayer↔RGB 往返 + 微弱信号噪声**（无学习、前馈）  
2. **平坦区 Poisson–Gaussian 微调**（与现有噪声层参数解耦，可 A/B）  
3. **encode/JPEG 温和扫档**（已有层则只扫参，不新造对抗）  
4. **Layer0 测量臂**（默认仍 0；仅脚本 `ALIGN_LAYER0_IMG2IMG=1`）

禁改：`PASS_SCORE`、检测提示合约（除非另单）、计费、S7。

单测：恒等回退、强度=0 时输出=输入、焦距边界、无 Key 时 Layer0 跳过。

### W4 · 开发机真 Gemini 端测

- 环境：`hbs@192.168.19.128`（物料口令；Cloud 不可达则 self-hosted/VPN，**未通不得标完成**）  
- 样本：合同 12 张，seed 与 DET-SCORE 一致（`20261113`），除非主会话改裁并记 ledger  
- 臂：  
  - **H0** 止血基线（对照）  
  - **P1…Pk** 各 OPEN_PILOT（一次一变量）  
- 留证：`docs/mihuanyuantu-v2/input/DET-SCORE-NONLEGACY-e2e-*.txt` + `/tmp` 控制台日志  
- 报表：mean、过 75 比例、五维 reason 分布、相对 H0 的 Δ、相对 v2 的 gain（若跑 Q1 probe）

退出：

- 有稳健 Δ>0 且画质/五维无崩 → 可申请「默认开启」二次门禁（另裁）  
- 全臂无增益 → `SHORTFALL` 文档化，**停止加码**，交管理员改裁目标  

### W5 · 文档与 PR

- 更新 `progress.yaml` 本工单节、`checkpoint.md` / `handoff.md`（若项目惯例需要）  
- PR 正文必须含：可行性结论摘要、端测表、**明确是否宣称过 75 / Q1**  
- Owner 审计通过后合并；Collaborator 不合并自己的 PR  

---

## 5. 约束账本（新建）

路径：`docs/mihuanyuantu-v2/input/DET-SCORE-NONLEGACY-constraint-ledger.md`

继承硬约束：

| ID | 约束 |
| --- | --- |
| Q-PASS | `PASS_SCORE=75` 不放宽 |
| Q-HEMO | 止血 A+D+B 为默认底线；本单试点不得无门禁破坏 |
| Q-NO-ADV | 禁止对抗优化 / weaponized ISP 攻击管线入库 |
| Q-NO-LEGACY-LOOP | 禁止以旧 ALIGN 杠杆复跑代替本单研究 |
| Q-E2E | 里程碑完成 = 开发机真 Gemini 证据，非仅 Cloud pytest |
| Q-PR | 双账号；squash；秘密扫描；不提交 `.env` / `生产物料` |
| Q12 | SHORTFALL / 无增益 → 停止加码、不硬开 PR 冒充达标 |

---

## 6. 参考路径（只读种子）

| 用途 | 路径 |
| --- | --- |
| 进度 | `docs/mihuanyuantu-v2/progress.yaml` → `det_score_optimize_2026_11_14` |
| 止血/协议 C | `docs/mihuanyuantu-v2/input/DET-SCORE-OPTIMIZE-protocol-c-conclusion-2026-11-14.md` |
| 协议 W | `…/DET-SCORE-OPTIMIZE-ablation-w-conclusion-2026-11-14.md` |
| R4 | `…/DET-SCORE-OPTIMIZE-r4-measure-gate-2026-11-14.md` |
| 实现 | `aojuai-main/backend/app/capabilities/realphotos/services/five_layer.py` |
| 旧 ALIGN 账本 | `…/FIVE-LAYER-LEGACY-ALIGN-constraint-ledger.md` |
| 本工单文件 | `/home/hbs/Desktop/DET-SCORE-非旧版提分联网方案工单-2026-11-14.md` |

侧聊可引用关键词（非许可）：ISPCloak（**红线示例**）、Bayer pattern detection、Poisson–Gaussian sensor noise、simple-patch noise forensics、JPEG/frequency augmentation 对检测置信的影响。

---

## 7. 主会话开场指令（可直接粘贴）

```text
执行桌面工单 DET-SCORE-NONLEGACY-LIFT（DET-SCORE-非旧版提分联网方案工单-2026-11-14.md）。
管理员已确认止血完成：先 W0 把 A+D+B 入库/PR，再主子代理联网研究旧版以外方案，
结合侧聊 §1.3 摘要但必须独立核实，写出可行性门禁；仅对 OPEN_PILOT 编码。
禁止放宽 PASS_SCORE、禁止对抗管线、禁止默认恢复 CA/Layer0、禁止 S7。
端测必须开发机真 Gemini；无 NONLEGACY_FEASIBILITY_PASS 不得改默认管线。
按 AGENTS.md 双账号开 PR；SHORTFALL 不宣称达标。
```

---

## 8. 完成定义（DoD）

1. 止血已合入或等价可追溯提交；progress 已标本工单。  
2. 联网研究报告 + 红线过滤 + 可行性门禁三份落盘。  
3. 若有 OPEN_PILOT：代码 + 单测 + 开发机端测证据 + Δ 表。  
4. 对管理员的一句话结论：**可用并已测 / 仅研究无增益 / 需改裁目标**——三者必居其一，禁止含糊「基本好了」。
