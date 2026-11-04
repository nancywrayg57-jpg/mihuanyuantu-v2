---
title: 蜜獾原图 v2 继续使用 Gemini Vision 承担最终检测
date: 2026-11-02
timezone: Asia/Shanghai
status: CONFIRMED_PRODUCTION
decision: RETAIN_GEMINI_VISION_AS_PRODUCTION_DETECTOR
production_detector: Gemini Vision
production_auto_redo: FR-026
check_aimage_production: false
synthbuster_production: false
formal_provider_change: NONE
---

# 继续使用 Gemini Vision 承担最终检测

## 决定

2026-11-02 最终确认：**生产环境图片最终检测继续由 Gemini Vision 承担**。Check_Aimage、Synthbuster 及其他开源/本地检测路线停留在研究材料，不写入正式需求，不替代五维报告、`passed` 判定或计费通过标准。

正式合同：

- 检测通过：`total_score >= 75 && passed=true`（PRD FR-018）
- 五维名称/键：噪点颗粒 `noise`、景深 `depthOfField`、光线曝光 `lighting`、色彩真实度 `colorRealism`、整体真实感 `overallRealism`（沿用旧版 exifVerifier；不得改用「真实感/材质/设备/平台适配」）
- 自动重做：用户开关默认关闭；追加 1—5 次（默认 1）；阈值 0—100（默认 70）；`total_score < chain.score_threshold` 触发，等于阈值不触发；该条件独立于 75 基线（PRD FR-026）
- 计费：每张成功图片 10 积分；自动轮次不叠加；未通过不收费

方案正文见 [`蜜獾原图-v2-Gemini-Vision检测与自动重做方案-v1.0.md`](../蜜獾原图-v2-Gemini-Vision检测与自动重做方案-v1.0.md)。PRD v2.2 将 FR-018 / FR-026 从「冻结沿用」改为生产确认。

## 研究材料如何看待

Check_Aimage、Synthbuster 及其他开源/本地检测试验材料已于 2026-11-02 清出仓库，**不得当作生产基线或上线门禁**。再次切换检测器必须另开决策并修订 PRD。

## 原型

HTML 原型恢复 Gemini 五维报告、FR-026 可编辑自动重做，以及模型 API 中的「最终检测」Gemini 渠道。此前 Check 门禁、风险分报告、最终检测 Key 强制停用，仅视为研究夹具，不再代表产品合同。

真实 Gemini 调用、画质验收与上线证据仍须另行完成，不因本决定视为已通过。
