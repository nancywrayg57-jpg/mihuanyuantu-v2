# FIVE-LAYER-LEGACY-ALIGN · 可行性门禁（主代理交叉裁定）

日期：2026-11-14  
交叉来源：
- [旧仓处理链深研](d5c7bd66-1b73-40b3-a88a-0d44cfff9721) → `...-subagent-legacy-report-2026-11-14.md`
- [现行五层缺口对照](d167f4fc-3c9f-4a3c-ab7b-0609819226ce) → `...-subagent-current-audit-2026-11-14.md`

## 裁定

| 项 | 裁定 | 依据 |
| --- | --- | --- |
| 编码门禁 | **OPEN**（本轮仅 C1+C4+C9） | 两报告均写与 `CONDITIONAL_YES` 无不可调和冲突；C1 为唯一合同内未测高杠杆 |
| Q1 可达 | **UNPROVEN**（不升级） | 旧仓不能证明 +10；既往最好 gain=3.83 |
| 模型 | 不换；仍 `gpt-image-2` `/images/edits` | C-LAYER0-API |
| 提示词 | 移植 phone/dslr/mirrorless；删桶形畸变；饱和度按裁决 A 中性改写；负向并入正向并日志声明 | C1；C-PROMPT-GEO-COLOR；裁决 A |
| 色差 | 删除 ×1.02；保留现行通道错位（本轮不改 shift 公式） | C4；不搬烂桩 |
| 测量 | e2e 保留胜出包五维；禁止空壳 `rerank_pick` 抹掉维度 | C9 |
| blend α | 端测设 `ALIGN_LAYER0_BLEND_ALPHA=1.0`（对齐旧整张替换语义；旧 strength 不进 API） | C-STRENGTH-DEAD；代码默认仍 0.12 可覆盖 |
| 不做 | 换 qwen、指纹几何/调色、平台/60%–80%、先频域、改 PASS_SCORE、抬暗角满表、port blur | 红线表 |

## 退出条件

- 端测 `ALIGN_W5_E2E_PASS`（n≥12，gain≥10，真 Gemini）→ 才允许对齐 CI / 开 PR（Q12）
- 否则 `ALIGN_W5_E2E_SHORTFALL` → **停止加码、不开 PR**，上报五维与瓶颈
