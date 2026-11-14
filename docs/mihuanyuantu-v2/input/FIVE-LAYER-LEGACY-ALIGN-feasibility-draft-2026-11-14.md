# FIVE-LAYER-LEGACY-ALIGN · 可行性草案（主代理 · 待子代理交叉）

状态：`crosscheck_legacy_done_awaiting_current_audit`  
日期：2026-11-14  
约束：不放宽 Q1≥10 / PASS_SCORE=75 / 禁几何与平台矩阵 / 层序 / Q12。  
旧仓交叉来源：[旧仓处理链深研](d5c7bd66-1b73-40b3-a88a-0d44cfff9721) → `FIVE-LAYER-LEGACY-ALIGN-subagent-legacy-report-2026-11-14.md`

## 1. 研究范围校验

| 步骤 | 内容 | 校验 |
| --- | --- | --- |
| S1 | 工单+账本+复裁锁定 | PASS：Q1–Q12 入账；冲突写入 `*-research-conflicts-2026-11-14.md` |
| S2 | clone 旧仓 | PASS：`4a3f2ade…`；六文件哈希=快照；**新增** `aiImageProcessor.ts` |
| S3 | 编排与禁项 | PASS：编排见 `routers.ts`；禁项见复用评估 RM-004～011 |
| S4 | 现行端测上限 | PASS：gain 最优 3.83（错误 Layer0 合同） |
| S5a | 旧仓子代理交叉 | PASS：与主代理草案同向；加细 CA@26mm 恒等、strength 死参数、唯一未测杠杆=中文提示 |
| S5b | 现行审计子代理 | **PENDING**：[现行五层缺口对照](d167f4fc-3c9f-4a3c-ab7b-0609819226ce) |

## 2. 旧→新差距（高置信，有行号）

### 2.1 Layer0（最大未测杠杆）

| 维度 | 旧版（clone） | 现行 v3 | 差距性质 |
| --- | --- | --- | --- |
| 提示词 | 分类中文长提示（噪点/紫边/暗角/景深/计算摄影痕迹）`aiImageProcessor.ts` 135–162 | 英文短句 + “Strength 0.12” `five_layer.py` ~228–231 | **实质内容缺口** |
| strength | 计算但不送 API（C-STRENGTH-DEAD） | blend α 或 prompt 数字 | 旧行为≠数值 strength |
| API | 默认 dashscope/qwen；亦支持 openai/gemini/custom | aoju `gpt-image-2` `/images/edits` | C-LAYER0-API：本轮不换模型除非另批 |
| 失败 | 失败退原图继续 | 返回 None 则跳过 Layer0 | 可接受（不静默标成功） |

### 2.2 L1–L3

| 维度 | 旧版 | 现行 | 备注 |
| --- | --- | --- | --- |
| 噪声 | `0.5√(ISO/100)`；暗部×1.5；iso&lt;200 可跳过 | 同公式×1.55 + floor400 + cap2.20；已有暗部×1.5 | 已偏强；非主缺口 |
| 暗角 | 表 0.35…0.04 | ×0.85 scale | 获准弱化 |
| 色差 | **烂桩**→饱和度1.02 | 真实 R/B 错位 + 仍留×1.02 | 修复向；应去掉饱和度尾巴 |
| 频域 | 入口内先 1D；phase≈0.004；隔行 | L2 在 L1 后；1D+2D+auto | 顺序正确禁止回迁 |
| 指纹 | 含调色/几何 | 仅稀疏+弱频谱 | 正确 |

### 2.3 L4–L5 / 禁项

EXIF/FocalPlane 已在 ALIGN W3 路径；upload/size 禁项不得回迁。

## 3. 候选补丁集（仅在交叉确认后编码）

| 补丁 | 动作 | 触及 | 预期机制 | 风险 | 依赖旧 AI 原文 |
| --- | --- | --- | --- | --- | --- |
| P1 | 移植 `DEFAULT_PROMPTS`（phone/dslr/mirrorless）；**剥离**桶形畸变等几何词；按 preset 类别选择 | Q8,Q7,C-LAYER0-GEO/COLOR | 对齐旧检测器针对的质感语义 | 供应商仍可能大改像素；MAD 仍高 | 是 |
| P2 | 删除 CA 末尾饱和度×1.02 | Q4,Q7,C-V2-CA-SAT | 避免可见调色；保留几何色差 | 略降 color 维分 | 否（反烂桩） |
| P3 | 中间 JPEG 对照旧 `chromaSubsampling 4:2:0` + quality≈88 档 | Q5 | 量化伪影更靠近相机直出 | 画质/字节 | 否 |
| P4 | 保持/收紧 blend：默认 α=1 仅当需要 raw edit；提示词对齐后重测 α | Q8,Q11 | 控制保真 | 扫档成本 | 否 |
| P5 | **不做**：换 qwen/DashScope、开几何指纹、平台矩阵、改 PASS_SCORE | 红线 | — | — | — |

## 4. 可行性判定（旧仓已交叉 · 待现行审计）

**编码可行性（收窄后的 P1′）**：`CONDITIONAL_YES`（仅提示词实验 + 删 CA×1.02）  
依据（旧仓报告 §9–§11）：  
- 唯一合同内未测高杠杆 = 分类中文提示（须裁畸变；饱和度按裁决 A 改写）  
- strength / α 再扫已降权（旧 strength 死；v2 α 已测 &lt;10）  
- 色差/暗角满表/无帽噪声 **不**作为 +10 杠杆；26mm 上旧色差恒等  
- P3（4:2:0）降为可选低优先级实验，**本轮默认不做**直至现行审计确认无隐性阻塞  

**明确不做（本轮）**：换 qwen 模型、取消尺寸拉回、取消 blend（除非另批）、抬暗角满表、port blur(0.3)、指纹几何/调色、平台/体积带。

**Q1 可达性**：仍为 **`UNPROVEN`**（旧仓报告原文：「不能支撑 Q1 已经可达」）。  
端测若 SHORTFALL → §4.4 停加码、不开 PR；并记录「对齐旧仓已无第二条同等未测杠杆」。

**执行门禁**：

1. 现行审计子代理完成且无阻断 P1′ 的新红线冲突  
2. 不引入未批模型（C-LAYER0-API）  
3. 提示词：删除桶形畸变；饱和度按裁决 A  
4. 同步删除 v2 CA 末尾 ×1.02（C-V2-CA-SAT / 旧报告裁决项 4C）  
5. 端测 n≥12 真 Gemini；仅 `ALIGN_W5_E2E_PASS` 后 CI/PR  

## 5. 显式非假设

- 未假设 qwen Key 可用  
- 未假设旧 Node 可在本机跑出对照分  
- 未假设 MAD 观察模式等于允许糊图刷分  
- 未假设改样本集或 PASS_SCORE  

## 6. 下一步

- 首轮子代理因额度失败：`e29da127…` / `f127ff19…`（Opus/Hydrogen 不可用）。
- 已用 Grok 重派：[`旧仓处理链深研`](d5c7bd66-1b73-40b3-a88a-0d44cfff9721)、[`现行五层缺口对照`](d167f4fc-3c9f-4a3c-ab7b-0609819226ce)。
- 合并交叉核验 → 若仍 `CONDITIONAL_YES` 则实施 P1–P4 → 端测。
