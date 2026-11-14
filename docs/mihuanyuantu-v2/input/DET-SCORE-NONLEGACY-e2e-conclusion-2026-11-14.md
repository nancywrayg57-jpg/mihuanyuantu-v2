# DET-SCORE-NONLEGACY · 端测结论

日期：2026-11-14  
证据：`DET-SCORE-NONLEGACY-e2e-pilot-2026-11-14.txt`  
配置：n=12、26mm、Layer0=0、CA=0、**score_fn=None**（与协议 C 的 score_fn 臂不同）

## 结果

| 臂 | mean | Δ vs H0 | 裁决 |
| --- | --- | --- | --- |
| H0 止血（当次） | **62.33** | — | 对照（冻结协议 C 有 score_fn 的 66.92 **不可直接相减**） |
| P1 Bayer strength=0.35 | **52.50** | **−9.83** | **否决升默认**；伤分 |
| P2 PG scale=0.40 | **63.42** | **+1.08** | 微正；**不升默认**；未达产品达标 |

标记：`NONLEGACY_PILOT_E2E_GAIN` **partial**（仅 P2 微增）；**不**宣称过 75 / Q1。  
`NONLEGACY_Q1_PROBE`：**未跑**（本轮未对 v2 配对）。

## 一句话（DoD）

**仅研究有微增益**：平坦区 PG Δ≈+1；Bayer 往返明显掉分；**停止加码升默认**；需管理员改裁目标或接受天花板。

## 禁止

- 不把 P1/P2 写成生产默认  
- 不放宽 PASS_SCORE  
- 不恢复 CA / Layer0 默认  
- 不 S7  
