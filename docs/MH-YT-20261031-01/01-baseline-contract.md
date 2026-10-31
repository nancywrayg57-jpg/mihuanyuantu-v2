# 检测契约基线卡（D1）

| 字段 | 内容 |
| --- | --- |
| 工单 | MH-YT-20261031-01 v1.1 |
| 产出日期 | 2026-10-31（Asia/Shanghai） |
| 状态 | **已用入库源文件二次核对** |

## 出处

| 契约项 | 出处 |
| --- | --- |
| 位置第 6 层 | `输入材料/蜜獾原图技术原理.md` §9 / 分层表 |
| 默认模型 `gemini-2.5-flash` | `exifVerifier.ts:390`；技术原理表 |
| 输入=成图+预设 EXIF 文本 | `exifVerifier.ts` 构建 prompt（品牌/型号/镜头/ISO/快门/光圈/软件） |
| 输出 passed/score/confidence/五维/conclusion/suggestions | `exifVerifier.ts` prompt JSON Schema（约 116–132 行） |
| 阈值 `score ≥ 75` 且 `passed = true` | `exifVerifier.ts:134`；PRD D-14 / FR-19 |
| 五维 | noise / depthOfField / lighting / colorRealism / overallRealism |
| 技术失败不得伪装低分 | PRD **LD-19 / RG-05**；**旧源码 catch 仍返回 score:0（缺陷，见差异清单）** |
| 方案层标签体系 | `基于 Gemini API 的全自动照片真实性验证解决方案.md`：`physical_device` / `ai_generated` / `uncertain` / `invalid_or_unverifiable` |

## 六项契约对照

| # | 契约项 | 基线 | 替代必须对齐 |
| --- | --- | --- | --- |
| 1 | 判定范式/位置 | 第 6 层独立后置（`exifVerifier.ts`） | 独立后置 |
| 2 | 输入 | 像素 + **预设 EXIF 文本** | 本评测默认 **仅像素**（变量固定）；与 Gemini 非同输入 |
| 3 | 输出 | passed/score/五维等 | 映射到 `physical_device`/`ai_generated`/`uncertain`/`tech_fail` |
| 4 | 阈值 | ≥75 且 passed=true | 可配阈值；记录所用阈值 |
| 5 | 可解释性 | 五维+文案 | 允许降级为概率 |
| 6 | 失败语义 | 技术失败≠业务低分（LD-19） | 适配器必须 `tech_fail` |

## 统一映射

见 `eval/schema.py`。默认阈值 P(AI)=0.5；uncertain_band 默认 0（主口径）。
