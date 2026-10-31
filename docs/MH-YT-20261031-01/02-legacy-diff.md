# 旧版 `exifVerifier.ts` vs v2 要求差异清单（A2）

| 字段 | 内容 |
| --- | --- |
| 状态 | **已对照源文件** |
| 源文件 | `输入材料/旧版可复用模块/01_源码参考/原样快照/server/exifVerifier.ts` |
| PRD | `输入材料/蜜獾原图-SaaS-PRD-v2.0.md`（FR-19/20、RG-05、LD-19） |

## 必须保留

| ID | 能力 | 出处 |
| --- | --- | --- |
| M1 | 独立后置检测 | 技术原理第 6 层 |
| M2 | 结构化 passed + score + 五维 | `exifVerifier.ts` prompt |
| M3 | 通过口径 ≥75 且布尔 true | FR-19 / D-14 / `:134` |
| M4 | 模型版本可锁定记录 | `GEMINI_MODEL` / `usedModel` |
| M5 | 技术失败与业务低分分离 | LD-19 / RG-05 |

## 旧版缺陷（不宜照搬）

| ID | 问题 | 出处 | 处理 |
| --- | --- | --- | --- |
| D1 | `catch` 返回 `score:0, passed:false`，把 API 失败伪装成低分 | `exifVerifier.ts:431-444`；LD-19 | 替代适配器用 `tech_fail` |
| D2 | 预设 EXIF 文本喂模型（RK-12） | prompt 构建 | 本评测默认仅像素 |
| D3 | 主观五维 ≠ 来源鉴定 | 方案/PRD 声明 | 报告首页声明 |
| D4 | 单供应商 + 调用费线性 | 工单背景 | Top3 优先本地零成本 |

## 方案文档 vs 旧源码

| 点 | 方案 MD | 旧 `exifVerifier.ts` |
| --- | --- | --- |
| 标签 | physical/ai/uncertain/invalid | passed 布尔 + score |
| 仲裁 | 多样本投票+二次仲裁 | 单次调用 |
| 失败 | 方案要求 uncertain/系统动作 | 实现成 0 分 |

替代 POC 对齐**产品验收口径**（映射后的物理/AI + 技术失败分离），不复刻单次 Gemini 五维分数。
