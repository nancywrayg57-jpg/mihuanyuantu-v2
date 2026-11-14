# 任务工单 · FIVE-LAYER-DEFAULT-OPT（技术处理默认路径专项优化）

| 项 | 值 |
| --- | --- |
| 工单 ID | `FIVE-LAYER-DEFAULT-OPT` |
| 日期 | 2026-11-14 |
| 来源 | 侧聊管理员确认：需要对**技术处理模块**做专项优化；接受改裁指标（不再绑死旧 Q1「相对 v2 +10」为唯一门禁） |
| 执行方 | **主会话（Owner）** 调度主/子代理；Collaborator 按白名单编码/测/推 PR |
| 继承 | `DET-SCORE-NONLEGACY-LIFT` → `DET-SCORE-OPTIMIZE` → `FIVE-LAYER-LEGACY-ALIGN` |
| 分支 | 从最新 `main` 开 `cursor/five-layer-default-opt-9973`（**禁止**在已合入的 NONLEGACY/ALIGN 分支上继续堆默认改动） |
| 合入 | 仅 PR → `main`；squash；作者不得自评自合（`AGENTS.md` §7） |
| 生产/S7 | **禁止** |

桌面副本：`/home/hbs/Desktop/五层技术处理默认路径专项优化工单-2026-11-14.md`  
仓库应同步：`docs/mihuanyuantu-v2/input/FIVE-LAYER-DEFAULT-OPT-work-order-2026-11-14.md`

---

## 0. 管理员裁决（本单生效）

| 裁决 | 含义 |
| --- | --- |
| 专项范围 | **仅**技术处理默认路径（`five_layer` v3/auto 工人路径仍开启的层） |
| 成功标准 **改裁** | 以 §2 新指标为准；**旧 Q1（相对 v2 gain≥10）降为可选 probe**，不得再当唯一达标门禁 |
| 前序合入 | 止血 PR #55、NONLEGACY PR #56 已 **MERGED**；本单不重复 Bayer/PG 升默认争论 |
| 仍禁止 | 放宽 `PASS_SCORE=75`；恢复 CA / Layer0 img2img **默认开**；Bayer **默认开**；对抗管线；S7；清空业务数据 |

---

## 1. 为何开本单（证据摘要）

| 事实 | 证据 |
| --- | --- |
| 历史最大伤分在技术处理 **CA**（已止血） | 协议 W：史≈49 → CA=0 后 8mm≈**62** |
| 止血后仍难过 75；相对 v2 冲 +10 **未证明** | 协议 C gain=**+1.17** SHORTFALL；过 75 仅 2/12 |
| R4 光学+噪声整包降档增益微弱 | Δ≈**+0.83** → `P-V3-OVERDRIVE NOT_CONFIRMED`（整包归因失败） |
| NONLEGACY：Bayer 测量臂伤分；PG 微正不升默认 | P1 **−9.83**；P2 **+1.08**；PR #56 不 promote |
| 当前默认仍开、可能影响分的层 | `_LAYER0_OPTICAL_STRENGTH=0.32`；`_NOISE_INTENSITY=1.55`；暗角；弱锐化；JPEG `_QUALITIES` 选档 |

**结论：** 剩余瓶颈在技术处理**默认路径整体**；须 **拆开单变量消融**，再决定是否改默认常量。

---

## 2. 改裁后的目标与门禁标记

### 2.1 用户价值

在 **真 Gemini 五维**、`PASS_SCORE=75` 不放宽的前提下，提升工人默认路径（止血底线）的检测表现与可解释性。

### 2.2 主成功标准（本单绑定 · 管理员改裁）

以开发机合同 12 张、seed=`20261113`、**26mm**、Layer0 img2img=0、CA=0、**与协议 C 同配置的 score_fn 开/关须在证据头写明（推荐先 `score_fn=None` 消融，达标候选再跑 score_fn 确认）** 为准。

| 标记 | 条件（满足其一即可申报「默认优化有效」） |
| --- | --- |
| `DEFAULT_OPT_MEAN_GAIN` | 相对 **本单 H0（当前 main 止血默认）** mean_total **Δ≥+3.0** 且无五维系统性崩盘（任维均 Δ≤−5 则否） |
| `DEFAULT_OPT_PASS75_LIFT` | 过 75 张数相对 H0 **至少 +2**（例如 2/12→≥4/12） |
| `DEFAULT_OPT_REASON_SHIFT` | 主会话书面认定：合成/噪点/光影类 reason 占比明显改善，且 mean 不下降（作辅助，**不可单独**升默认） |

### 2.3 可选 probe（不挡主门禁）

| 标记 | 条件 |
| --- | --- |
| `DEFAULT_OPT_Q1_PROBE` | 相对 v2 gain≥10 → PASS；否则 SHORTFALL **不得宣称产品 Q1 达标** |

### 2.4 升默认门槛（严于测量）

测量臂出现增益 **≠** 可写进代码默认。升默认须同时：

1. 满足 §2.2 至少一条；  
2. 单变量归因清楚（不是多旗标同时开）；  
3. 主会话审计 + 管理员口头/工单确认；  
4. 单测：新默认下关键路径不回归；关回旧常量可复现 H0（或留下 diff 说明）。

---

## 3. 范围

### 3.1 在范围内（默认路径 · 优先消融序）

| 序 | 杠杆 | 代码落点（约） | 测量方式 |
| --- | ---: | --- | --- |
| A1 | 光学 Layer0 强度 | `_LAYER0_OPTICAL_STRENGTH` / env `ALIGN_LAYER0_OPTICAL_STRENGTH` | 扫 0 / 0.16 / 0.24 / **0.32(H0)** |
| A2 | L1 噪声强度 | `_NOISE_INTENSITY` / `ALIGN_NOISE_INTENSITY` | 扫相对 H0：0.85× / 1.0× / **1.55** 邻域（主会话定 3 档） |
| A3 | 弱锐化开/关或强度 | `_weak_sharpen` 调用 | off vs on（H0） |
| A4 | 暗角缩放 | `_VIGNETTE_LEGACY_SCALE` | 1 档减弱 vs H0 |
| A5 | JPEG 候选网格 | `_QUALITIES` / 温和网格测量旗标 | **仅测量**；换掉偏爱的 98/100 看赢家与五维（曾 DEFER 的 P4） |
| A6 | PG 弱档（已有旗标） | `ALIGN_PG_*` | 仅测量；**默认仍关**，除非 §2.4 |

**一次只动一个杠杆**（相对 H0）。禁止 A1+A2 同时改默认却宣称归因。

### 3.2 明确不在范围（默认保持）

| 项 | 状态 |
| --- | --- |
| `_CA_INTENSITY` | **保持 0** |
| `ALIGN_LAYER0_IMG2IMG` 默认 | **保持 0** |
| `ALIGN_BAYER_ROUNDTRIP` 默认 | **保持关**（已伤分 −9.83） |
| 旧 ALIGN / 旧仓复刻加码 | **关闭** |
| 检测提示词、`PASS_SCORE`、计费、S7 | **不动** |
| 对抗 ISP / 武器化管线 | **禁** |

Bayer：本单**不修不升**；若管理员另批「弱 strength 一次性否决试」，须另开一行测量臂且默认仍关。

---

## 4. 主/子代理协作

```
主会话
 ├─ W0  确认 main 含 #55+#56；建分支；冻 H0 基线（真 Gemini）
 ├─ 子代理 M  消融计划矩阵 + 脚本（一次一变量）
 ├─ 主会话    跑/监开发机端测；写各臂结论
 ├─ 子代理 I  仅对「升默认候选」改常量 + 单测（白名单）
 └─ 主会话    审计 → PR → 更新 progress
```

规则：无 `DEFAULT_OPT_*` 达标证据，**禁止**改 `_LAYER0_OPTICAL_STRENGTH` / `_NOISE_INTENSITY` 等模块默认值入库。

---

## 5. 工作包

### W0 · 基线冻结

- [ ] `main` 含止血 + NONLEGACY（测量臂默认关）  
- [ ] 分支 `cursor/five-layer-default-opt-9973`  
- [ ] 账本：`docs/mihuanyuantu-v2/input/FIVE-LAYER-DEFAULT-OPT-constraint-ledger.md`  
- [ ] H0 端测落盘：`…/FIVE-LAYER-DEFAULT-OPT-e2e-h0-YYYY-MM-DD.txt`  
  - 记录 mean、过 75 数、五维均分、score_fn 开闭  
  - **不要**拿协议 C 的 66.92 与 `score_fn=None` 臂直接相减（NONLEGACY 已踩坑）

### W1 · 消融计划（子代理 M）

产出：`…/FIVE-LAYER-DEFAULT-OPT-ablation-plan-YYYY-MM-DD.md`  

矩阵至少含 A1–A5；每臂：env/覆写值、预期影响维、退出条件。

### W2 · 开发机真 Gemini 消融

- 主机：`hbs@192.168.19.128`（物料；未通不得标完成）  
- 脚本：可基于 `det_score_r4_measure_e2e.py` / `det_score_nonlegacy_pilot_e2e.py` 扩展为 `det_score_default_opt_e2e.py`  
- 每臂独立证据文件；汇总表：`…/FIVE-LAYER-DEFAULT-OPT-ablation-summary-YYYY-MM-DD.md`

退出：

- 有臂达 §2.2 → 进入 W3 升默认候选  
- 全臂 |Δ|<1 或伤分 → **停止改默认**；交付「天花板报告」+ 管理员选项（接受现状 / 再改裁指标 / 动检测侧另单）

### W3 · 升默认编码（仅候选）

白名单示例（主会话按实裁定裁剪）：

- `five_layer.py` 常量默认值  
- 必要单测更新  
- **禁止**顺手打开 Bayer/CA/Layer0 img2img  

### W4 · 确认端测 + PR

- 新默认 vs 旧 H0 再跑一轮合同集  
- PR 正文：消融表、是否达 §2.2、**明确不宣称旧 Q1**（除非 probe PASS）  
- 更新 `progress.yaml` / `checkpoint.md` / `handoff.md`

---

## 6. 约束账本（新建时抄入）

| ID | 约束 |
| --- | --- |
| Q-PASS | `PASS_SCORE=75` 不放宽 |
| Q-HEMO | CA=0、Layer0 img2img 默认 0、Bayer 默认关 |
| Q-RETARGET | 主门禁=§2.2；旧 Q1 仅 probe |
| Q-ONE-VAR | 消融与升默认归因必须单变量 |
| Q-NO-ADV | 禁止对抗/武器化 ISP |
| Q-E2E | 开发机真 Gemini；Cloud pytest ≠ 完成 |
| Q-PR | 双账号；squash；不提交密钥 |
| Q12 | 无增益不升默认、不硬开「达标」PR 文案 |

---

## 7. 参考路径

| 用途 | 路径 |
| --- | --- |
| 实现 | `aojuai-main/backend/app/capabilities/realphotos/services/five_layer.py` |
| 止血/协议 C | `docs/mihuanyuantu-v2/input/DET-SCORE-OPTIMIZE-protocol-c-conclusion-2026-11-14.md` |
| R4 | `…/DET-SCORE-OPTIMIZE-r4-measure-gate-2026-11-14.md` |
| NONLEGACY 结论 | `…/DET-SCORE-NONLEGACY-e2e-conclusion-2026-11-14.md` |
| 落点图 | `…/DET-SCORE-NONLEGACY-landing-map-2026-11-14.md` |
| progress | `docs/mihuanyuantu-v2/progress.yaml` |

---

## 8. 主会话开场指令（可粘贴）

```text
执行桌面工单 FIVE-LAYER-DEFAULT-OPT（五层技术处理默认路径专项优化工单-2026-11-14.md）。
从最新 main 开 cursor/five-layer-default-opt-9973。
先冻 H0（真 Gemini），再按 A1→A5 单变量消融光学 Layer0 / L1 噪声 / 锐化 / 暗角 / JPEG；
PG 仅测量；CA、Layer0 img2img、Bayer 默认保持关。
主成功标准用改裁的 DEFAULT_OPT_MEAN_GAIN / PASS75_LIFT，旧 Q1 仅可选 probe。
无达标证据不得改模块默认常量；禁止放宽 PASS_SCORE、对抗管线、S7。
按 AGENTS.md 双账号开 PR。
```

---

## 9. DoD

1. H0 + 消融汇总落盘，单变量表完整。  
2. 要么：有臂达 §2.2 且升默认经审计合入；要么：天花板报告 + 明确「不改默认」。  
3. 对管理员一句话：**默认已优化并达标 / 测完无增益保持止血 / 需再改裁**——三者居其一。
