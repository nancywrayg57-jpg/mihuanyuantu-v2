---
version: '1.0'
date: 2026-11-02
timezone: Asia/Shanghai
decision: GEMINI_VISION_PRODUCTION_DETECTION_AND_AUTO_REDO
detector: Gemini Vision
production_detector: true
pass_rule: 'total_score >= 75 && passed=true'
auto_redo_default: false
auto_redo_threshold_default: 70
auto_redo_extra_rounds: '1-5'
related_prd: docs/蜜獾原图-v2-PRD-v2.0.md
related_adr: docs/architecture_decisions/蜜獾原图-v2-继续使用Gemini-Vision最终检测-2026-11-02.md
---

# 蜜獾原图 v2 · Gemini Vision 检测与自动重做方案

本文是**生产检测与自动重做合同**。最终检测由 Gemini Vision 输出五维分数、总分与 `passed`；自动重做按用户阈值与追加次数在同一图片处理链内重跑五层与检测。Check_Aimage、Synthbuster 等并行研究方案不替代本文。

## 1. 检测基线

| 项目 | 规则 |
|---|---|
| 检测器 | Gemini Vision（平台「最终检测」渠道，默认识别名 `gemini-2.5-pro`，以模型 API 实际配置为准） |
| 报告 | 五个维度（噪点颗粒、景深、光线曝光、色彩真实度、整体真实感；键名 `noise` / `depthOfField` / `lighting` / `colorRealism` / `overallRealism`）、总分、`passed`、未通过原因 |
| 通过标准 | `total_score >= 75` 且 `passed=true` |
| 语义边界 | 报告只表示 Gemini Vision 本次判定，不保证任何第三方平台审核通过 |
| 无效响应 | 缺失、HTML、超时、无法解析、分数非有限值：视为技术异常，不得伪造通过或未通过报告 |

检测结果写入任务/图片详情，不设独立「检测结果」页。历史任务保留当时报告，不按新模型回算。

## 2. 自动重做

设置由服务端持久保存；提交图片处理任务时生成不可变快照，之后改设置只影响新任务。

| 项目 | 规则 |
|---|---|
| 开关 | 用户自选；默认关闭 |
| 追加次数 | 1—5 次（不含首次处理），默认 1 |
| 阈值 | 0—100 整数，默认 70 |
| 适用来源 | 本地上传、URL 导入、文生图、图生图进入**图片处理任务**后的链路 |
| 输入 | 上一轮有效处理结果；只重跑五层与最终检测；不重生图；不覆盖既有图片、报告或尝试记录 |
| 触发 | 上一轮有可解析总分，且 `total_score < chain.score_threshold`，且未达该链追加次数 |
| 等于阈值 | 不触发 |
| 与 75 基线 | 相互独立。阈值 > 75 时，已过基线但低于用户阈值的结果仍继续重做 |
| 不触发 | 技术异常、缺分、无有效结果、前置校验失败、质量/保真失败、用户未开启、次数用尽 |

关闭浏览器不影响已提交链的自动轮次。迟到回调、重复调度不得创建重复轮次、重复消费或重复释放。

## 3. 交付与计费

- 通过：该张结算 10 积分（提交时已按拟处理张数冻结）。
- 未通过但检测正常返回：保留真实报告与有效结果，允许预览/下载，该张不收费并释放对应预留（ND-019）。
- 任一轮通过且有有效结果：该张幂等只消费一次 10 积分；自动轮次不叠加。
- 该张全部轮次未通过：该张消费为 0。
- 技术异常：不进入自动循环；冻结待客服审计后释放（ND-009）；手动检测重试最多 2 次，不增加处理轮次、不另计费。
- 主动重新处理创建关联新任务，独立报价，不属于自动重做，也不占用技术重试次数。

## 4. 状态

客户可见处理进度：输入校验 → 预审 → 技术处理 → 结果检测 → 结果交付。

| 终态 / 中间态 | 含义 |
|---|---|
| `DELIVERED` | 检测通过（≥75 且 `passed=true`） |
| `FAILED` | 检测正常返回但未通过，且不再自动重做 |
| `AUTO_REPROCESS_PENDING` | 已触发自动重做，正在执行下一轮 |
| `TECH_FAILED` | 检测无有效分数 |
| `QUALITY_FAILED` | 文件或保真检查失败 |
| `RETRY_PENDING` | 等待手动重试检测 |

旧 Check 研究任务若仍停留在风险复核/文件就绪等夹具状态，视为历史研究记录，不按本文回算、不自动续跑。

## 5. 模型渠道

平台管理员在系统管理 → 模型 API 配置「最终检测」用途的 Gemini 渠道（提供商、模型、Base URL、API Key）。客户不可见 Key。预审、生图、提示词优化与最终检测按用途隔离，互不覆盖。

禁止把 Check_Aimage 或 Synthbuster 登记为生产最终检测渠道。

## 6. 研究方案边界

Check_Aimage、Synthbuster 及其他开源/本地检测试验已于 2026-11-02 清出仓库（含研究文档、克隆、对照表与处理后图）。不得把既有风险分、`P(fake)` 或其他候选分数映射为 Gemini 五维总分或 `passed`。再次评估替代检测器须另开决策并修订 PRD。

## 7. 原型与实现边界

HTML 原型用固定五维夹具演示报告、阈值触发与账务，不调用真实 Gemini。规则模块为 `prototype/check-policy.js`（`GeminiRedoPolicy`）。

生产后端须按 FR-018 / FR-026 实现真实调用、快照、幂等与账本；真实检测质量、成本与上线证据为 PENDING，不能用原型夹具代替验收。
