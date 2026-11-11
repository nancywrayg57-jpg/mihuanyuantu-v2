# 蜜獾原图 v2 · 任务工单

| 字段 | 内容 |
| --- | --- |
| 工单编号 | FIVE-LAYER-PHYS-TUNE-2026-11-11 |
| 创建日期 | 2026-11-11 |
| 范围 | 在 ND-020 保真红线内，**适度加强**五层 L1「像素物理化」（及必要时 L2 细微频域），使交付图更接近细微真实机成像噪声/颗粒；用同图前后 live Gemini 对照验证是否抬分；不改检测门闩 |
| 不做 | S7；生产收费（`production_billing=false`）；改 `PASS_SCORE=75`；刷分（改 `passed`/后处理改分/fixture 冒充 live）；照搬旧版色差 composite、色调/饱和度替代、可见暗角；旋转/裁切/缩放；可见改色/改构图/改文字商标；自评自合 PR；清空业务库 |
| 依据 | PRD FR-009 / ND-020 / ND-021；架构 §8.2 L1–L5；`five_layer.py`（`s2-five-layer-1`）；旧 `imagePhysicalizer.ts` **仅作细微噪声/成像参数参考**；AGENTS.md；SCORE-ROOTCAUSE 基线 `/tmp/score-lift-rootcause-e2e.log` |
| 管理员裁决（本工单） | ① **允许适当加强物理化**；② 必须守 ND-020「肉眼无可见变化」；③ **主会话完成后须端测**并留证据；④ 不降通过线、不刷分 |
| 验证环境 | 开发机本机（`192.168.19.128`）FE `3000` / API `38000` + PostgreSQL + worker + live Gemini；证据 `/tmp/five-layer-phys-tune-e2e.log` |
| 分支约定 | `cursor/five-layer-phys-tune-9973`（Collaborator）；合入仅非作者 Owner squash |

---

## 0. 开干前硬约束

1. 权威顺序：PRD → 架构 → 本工单；冲突停问。
2. **ND-020**：商品主体、颜色、文字、商标、构图、边框无肉眼可见变化；像素宽高不变；仅允许细微噪声、频域扰动、编码调整、设备元数据重写。
3. 架构禁照搬：旧色差 composite 结果丢弃逻辑、色调替代逻辑 **不得**作为完成能力合入。
4. `PASS_SCORE` 保持 **75**；检测 prompt / `accepted()` 门闩不得为抬分而改松。
5. 新算法必须升 `pipeline_version`（建议 `s2-five-layer-2`）；旧任务报告不改写。
6. 密钥只读同级 `生产物料/` / 本机 `.env`；禁止入库。
7. **主会话全部任务项编码完成后，必须跑本工单端测**；未出现总标记前不得宣称完成、不得开 S7。
8. 预期诚实：物理化加强**不保证**达到 90%≥75；若对照无显著增益，证据写明并停止堆参数，改由管理员另批样张/策略工单。

---

## 1. 现状（实现前核实）

| 项 | 现状 |
| --- | --- |
| 代码 | `aojuai-main/backend/app/capabilities/realphotos/services/five_layer.py`：`PIPELINE_VERSION=s2-five-layer-1` |
| L1 | `rng.normal(0, 0.8)` 全图像素噪声 |
| L2 | 高频半径 `>0.35` 处幅度扰动 `σ=0.02` |
| L3 | 最多 512 点 ±1 稀疏扰动 |
| L4/L5 | EXIF 回读 + JPEG 质量阶梯 + 字节下限（不变本工单主目标） |
| 根因基线 | SCORE-ROOTCAUSE：10×2 live；有分 40–72；`NOT_DEFECT_SAMPLE_OR_MODEL`；detector=`gemini-3.1-pro-preview` |
| 旧版参考 | `输入材料/.../imagePhysicalizer.ts`：CMOS 噪声、暗角、色差、JPEG 重压——**本单只允许抽取「细微噪声/成像参数」思路，禁止可见光学特效** |

---

## 2. 对照集（端测固定）

优先复用 SCORE-ROOTCAUSE 已有分资产（`rp_merchant_a1`），固定预设与可复现 `seed`：

| 优先级 | assetId（基线） | 备注 |
| --- | --- | --- |
| 必测 | 159, 160, 140, 109, 83 | 基线曾出分；含偏真机与 AI 源 |
| 可选 | 139, 108 | 若预审/超时允许进入检测 |
| 排除对照 | 119, 27, 112 | 基线多为预审拒绝，不作为物理化抬分主证据 |

记录字段：`assetId`、`pipelineVersion`、`seed`、`totalScore`、五维、`reason`、`detector`。

---

## 任务 P0 · 保真红线清单与对照基线冻结

| 字段 | 内容 |
| --- | --- |
| 任务项 | 开改前冻结对照分 + 书面确认允许/禁止的物理化手段 |
| 当前现状 | 有 SCORE-ROOTCAUSE 分表；尚无本工单专用对照日志 |
| 如何完成 | 见步骤 |
| 预期结果 | `/tmp/five-layer-phys-tune-e2e.log` 含 `P0_BASELINE_FROZEN`；禁止项列表写入日志 |

### 完成步骤

1. 在开发机确认 FE/API/PG/worker + Gemini Key 可用；`production_billing=false`。
2. 对对照集跑一轮 **当前** `s2-five-layer-1` live 检测（或从 `/tmp/score-lift-rootcause-e2e.log` 摘录同资产最近有效分，并在日志注明来源）。
3. 日志写明本单 **允许**：细微 CMOS/高斯类噪声强度与形态微调、与 ISO/预设相关的噪声幅度映射（若有）、L2 高频扰动在「肉眼不可见」范围内的小幅加强。  
   **禁止**：色差通道错位、可见暗角、饱和度/色调整体偏移、锐化导致边缘光晕、模糊造景深、任何改宽高。
4. 标记：`P0_BASELINE_FROZEN`

---

## 任务 P1 · 实现 `s2-five-layer-2` 适度物理化

| 字段 | 内容 |
| --- | --- |
| 任务项 | 在 `five_layer.py` 加强 L1（必要时微调 L2），保持 L3–L5 合同行为；升级 `PIPELINE_VERSION` |
| 当前现状 | L1 σ=0.8 过弱，观感几乎不变 |
| 如何完成 | 见步骤 |
| 预期结果 | 新任务 `pipeline_version=s2-five-layer-2`；单测绿；端测 `P1_PIPELINE_BUMP_PASS` |

### 完成步骤

1. **参数策略（建议一次只动一类，避免无法归因）**
   - 首选：L1 噪声由固定 σ 改为「细微、可复现」的强度曲线（例如与预设 ISO 弱相关，或略提高 σ，但仍须人工不可见）。
   - 可选：L2 高频扰动 σ 小幅上调；禁止改成可见纹理或块状伪影。
   - L3 保持稀疏微扰；不借 L3 做大面积改图。
2. **从旧版可借鉴、不可照搬**
   - 可参考：噪声与传感器/ISO 的定性关系、可复现 RNG。
   - 不可移植：`applyChromaticAberration` / composite 色调桩、为「像相机」而做的可见暗角与饱和度。
3. 代码：`PIPELINE_VERSION = "s2-five-layer-2"`；所有新处理任务写入该版本；宽高断言与字节下限逻辑保留。
4. 单测：扩展 `test_s2_five_layer.py`——宽高不变、JPEG 头、字节下限、EXIF 回读仍过；可增加「相对原图像素平均绝对差在细微上限内」的回归阈值（阈值须在日志写明，防止日后静默放大）。
5. 标记：`P1_PIPELINE_BUMP_PASS`

---

## 任务 P2 · 人工保真抽检

| 字段 | 内容 |
| --- | --- |
| 任务项 | 对对照集输出做人工并排：原图 / v1 输出 / v2 输出 |
| 当前现状 | 无本轮保真记录 |
| 如何完成 | 见步骤 |
| 预期结果 | 日志含抽检结论；任一张「肉眼可见改色/改主体」→ **整单失败回退参数**，不得硬推 |

### 完成步骤

1. 导出或经网关下载对照集 v2 结果 JPEG。
2. 检查点：商标/文字是否变糊或变色；肤色/商品色是否偏移；是否出现色边、暗角、异常颗粒团。
3. 日志逐张：`fidelity=pass|fail` + 一句话原因。
4. 标记：`P2_FIDELITY_PASS`（全部 pass 才可）。

---

## 任务 P3 · 同图前后 live Gemini 对照端测

| 字段 | 内容 |
| --- | --- |
| 任务项 | 同一批资产、同一预设、同一检测模型、`PASS_SCORE=75`，对比 v1 vs v2 分数 |
| 当前现状 | 仅有 v1 基线 |
| 如何完成 | 见步骤 |
| 预期结果 | 证据表完整；总标记见 §3；脚本可复跑 |

### 完成步骤

1. 对对照集提交处理：`detectionMode=gemini`，live 预审（若预审挡路，日志单独记，不把预审失败算物理化失败）。
2. 每张至少 **2 轮**（模型有波动；基线资产 160 曾 68→40）。
3. 汇总表字段：`assetId, round, pipelineVersion, totalScore, dims, reason, status, failureClass`。
4. 统计：v2 相对 v1 的 `total_score` 中位数差、≥75 张数变化；**禁止**为冲指标改门闩。
5. 结论三选一写入日志：
   - `PHYS_TUNE_GAIN`：保真通过且分数中位数明显上移或 ≥75 增加；
   - `PHYS_TUNE_NEUTRAL`：保真通过但分数无稳定增益；
   - `PHYS_TUNE_REGRESS`：保真失败或分数稳定变差 → 回退/关 PR。
6. 标记：`P3_GEMINI_COMPARE_PASS`（指流程跑完且表完整；**不等于**必须涨分）。

---

## 任务 P4 · 进度与 PR

| 字段 | 内容 |
| --- | --- |
| 任务项 | 回写进度；开证据/实现 PR |
| 如何完成 | 更新 `checkpoint.md`、`docs/mihuanyuantu-v2/progress.yaml`；分支推送；Collaborator 开 PR；**非作者 Owner squash** |
| 预期结果 | PR 链接入进度；`production_billing=false`；`s7_started=false` |

---

## 3. 主会话完成后的端测总闸（必做）

主会话在 P1–P2 编码与保真通过后，**必须**在本机执行完整端测并追加同一证据文件：

```text
/tmp/five-layer-phys-tune-e2e.log
```

**总通过标记（同时满足才可宣称本工单技术完成）：**

```text
FIVE_LAYER_PHYS_TUNE_E2E_PASS
```

前置子标记均须出现：`P0_BASELINE_FROZEN`、`P1_PIPELINE_BUMP_PASS`、`P2_FIDELITY_PASS`、`P3_GEMINI_COMPARE_PASS`。

若结论为 `PHYS_TUNE_NEUTRAL` / `PHYS_TUNE_REGRESS`：仍可保留诚实证据 PR，但 **不得**在文案中宣称「已解决低分」；Owner 决定是否合入或回退。

附加固定行：

```text
production_billing=false
pass_score=75
s7_started=false
pipeline_version=s2-five-layer-2
```

---

## 4. 风险与停损

| 风险 | 停损 |
| --- | --- |
| 为涨分引入可见特效 | 立即停；保真失败不合并 |
| 同图 Gemini 波动掩盖结论 | 至少 2 轮；看中位数与区间，不看单次峰值 |
| 样张本身 AI/闪光/水印 | 物理化无效时记 `NEUTRAL`，另开工单换样或策略，不无限加大 σ |
| 40MP 性能 | 至少 1 张大图冒烟；超时/OOM 记失败 |

---

## 5. 回写清单

- [ ] `/tmp/five-layer-phys-tune-e2e.log` 含总标记与对照表
- [ ] `checkpoint.md` §0 更新
- [ ] `docs/mihuanyuantu-v2/progress.yaml` 本环 goal/verify/pr
- [ ] PR 已开且等待非作者 Owner squash
- [ ] 未开 S7；未改 `PASS_SCORE`
