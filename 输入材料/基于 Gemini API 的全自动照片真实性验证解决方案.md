# 基于 Gemini API 的全自动照片真实性验证解决方案

> 本方案不设置人工复核环节。所有图像判定、低置信度处理和冲突裁决均由 AI 自动完成，包括主分析、多次采样一致性判断、自动二次 AI 仲裁和确定性规则后处理。规则后处理仅做格式校验、投票聚合和策略路由，不引入人工判断。最终仍无法确定时，系统自动输出 `uncertain` 并采取自动拒识/要求重新上传等系统动作。

---

## 1. 目标与范围

构建一个全自动照片验证系统，判断上传图像是否由真实物理设备（相机/智能手机）拍摄，或是否为 AI 生成图像。

判定标签：

- `physical_device`：物理设备拍摄
- `ai_generated`：AI 生成
- `uncertain`：证据不足或存在冲突
- `invalid_or_unverifiable`：图像不可用或无法验证

系统原则：

1. Gemini 作为严格数字取证图像分析器，而不是通用聊天机器人。
2. 使用 Few-Shot Prompting 覆盖真实照片、AI 生成图和边界案例。
3. 要求模型内部执行 Chain-of-Thought 取证检查，但只输出证据摘要和结构化结论。
4. 使用严格 JSON Schema 和固定枚举值，降低 LLM 数值输出方差。
5. 低温度、多采样投票、自动二次 AI 仲裁和确定性规则后处理结合。
6. 全自动决策，不设置人工复核。
7. 提示词、Few-Shot、Schema、模型版本、采样结果和最终决策全链路可追溯。

---

## 2. 总体架构

```text
图像上传
  → 预处理（格式、尺寸、损坏检测，可选读取 EXIF）
  → 主分析：Gemini 多模态取证分析
  → JSON Schema 校验与有限重试
  → 多采样（建议 3 次）
  → 一致性投票与冲突检测
  → 自动二次 AI 仲裁（必要时）
  → 确定性规则引擎生成最终决策
  → 结果输出与审计日志
```

核心组件：

- API 服务层：接收图像、鉴权、限流、任务队列。
- 预处理层：格式转换、尺寸限制、损坏检测、可选元数据读取。
- 提示管理层：System Prompt、Few-Shot 示例、仲裁提示、Schema 版本管理。
- 模型调用层：Gemini 多模态调用，低温度，结构化输出。
- 校验层：JSON 合法性、枚举值、必填字段、证据一致性校验。
- 自动决策层：多采样投票、冲突检测、二次 AI 仲裁、最终规则路由。
- 审计层：保存请求 ID、图像哈希、模型版本、提示版本、Schema 版本、采样输出、仲裁输出和最终决策。

---

## 3. System Prompt 构建

主分析系统提示词建议如下：

```text
你是一个专业的数字取证与图像认证 AI 系统。
你的唯一任务是分析上传的图像，判断它是由真实物理世界设备（相机/智能手机）拍摄，还是由 AI 生成的图像。

你必须：
1. 作为严格的取证图像分析师工作，而不是通用聊天机器人。
2. 仅基于图像可见证据和明确提供的元数据作出判断；不得臆造不可见信息。
3. 在内部按以下维度进行 Chain-of-Thought 检查：
   - 光照一致性与阴影方向
   - 纹理细节与皮肤/物体表面连续性
   - 边缘、轮廓和压缩伪影
   - 反射、阴影与几何一致性
   - 背景文字、线条、重复图案异常
   - 传感器噪声、镜头伪影、景深和光学特征
   - 是否存在典型生成痕迹，如过度平滑、结构错位、文字乱码、局部不合理融合
4. 只输出证据摘要和结论，不输出完整内部思维链。
5. 如果证据不足、图像质量差或存在冲突，必须输出 uncertain，不得强行二分类。
6. 必须严格遵循给定 JSON Schema 输出，不得添加 Schema 之外的字段。

判定标签：
- physical_device：有较强证据表明来自真实物理设备拍摄
- ai_generated：有较强证据表明为 AI 生成
- uncertain：证据不足或冲突
- invalid_or_unverifiable：图像不可用或无法验证

不要声称读取了未提供的 EXIF 或外部信息。
```

英文角色开头可保留：

```text
You are an expert digital forensics and image authentication AI system.
Your sole task is to analyze the uploaded image to determine if it was captured by a physical real-world device (camera/smartphone) or if it is an AI-generated image.
```

---

## 4. Few-Shot Prompting 与 CoT 设计

建议提供 2–4 个 Few-Shot 示例，覆盖：

1. 明确物理设备拍摄图；
2. 明确 AI 生成图；
3. 边界案例，例如强滤镜、低质量压缩、截图、二次编辑图；
4. 不确定案例，展示模型应输出 `uncertain`。

每个示例采用“图像 + 期望 JSON 输出”的形式。示例中展示证据摘要到结论的映射，不展示冗长思维链。

示例一：物理设备拍摄

```json
{
  "verdict": "physical_device",
  "confidence_level": "high",
  "evidence": [
    "光照与阴影方向一致",
    "皮肤纹理和毛发细节连续",
    "存在自然传感器噪声和镜头伪影"
  ],
  "risk_flags": [],
  "uncertainty_reasons": []
}
```

示例二：AI 生成图像

```json
{
  "verdict": "ai_generated",
  "confidence_level": "high",
  "evidence": [
    "背景文字存在乱码和结构错位",
    "局部纹理过度平滑",
    "边缘融合和反射存在不合理之处"
  ],
  "risk_flags": [
    "text_artifact",
    "over_smoothing",
    "structural_inconsistency"
  ],
  "uncertainty_reasons": []
}
```

示例三：边界或不确定案例

```json
{
  "verdict": "uncertain",
  "confidence_level": "low",
  "evidence": [
    "图像经过强压缩和滤镜处理",
    "部分区域存在生成痕迹，但不足以形成高置信结论"
  ],
  "risk_flags": [
    "heavy_compression",
    "strong_filter"
  ],
  "uncertainty_reasons": [
    "压缩伪影掩盖传感器噪声特征",
    "证据存在冲突"
  ]
}
```

CoT 要求：

- 模型内部先检查光照、纹理、边缘、反射、背景文字、噪声模式、生成痕迹；
- 最终只输出证据摘要、风险标记、不确定原因和结论；
- 对冲突证据要求输出 `uncertain`；
- 不要求模型输出完整推理链，降低提示注入和冗长输出风险。

---

## 5. 主分析 Structured JSON Output Schema

使用严格 Schema，置信度使用分档枚举，减少数值方差。

```json
{
  "type": "object",
  "properties": {
    "verdict": {
      "type": "string",
      "enum": ["physical_device", "ai_generated", "uncertain", "invalid_or_unverifiable"]
    },
    "confidence_level": {
      "type": "string",
      "enum": ["low", "medium", "high"]
    },
    "evidence": {
      "type": "array",
      "items": {"type": "string"},
      "minItems": 1,
      "maxItems": 8
    },
    "risk_flags": {
      "type": "array",
      "items": {"type": "string"},
      "maxItems": 8
    },
    "uncertainty_reasons": {
      "type": "array",
      "items": {"type": "string"},
      "maxItems": 6
    }
  },
  "required": [
    "verdict",
    "confidence_level",
    "evidence",
    "risk_flags",
    "uncertainty_reasons"
  ],
  "additionalProperties": false
}
```

说明：

- 不要求模型输出自由浮点置信度，避免数值方差。
- 若 Gemini API 支持 `response_schema`，直接启用结构化输出。
- 若不支持，使用 JSON 模式，并在服务端进行严格校验和有限重试。
- 校验失败时最多重试 1–2 次；仍失败则进入自动二次 AI 仲裁或输出系统级 `uncertain`。

---

## 6. 全自动调用与决策流程

### 6.1 主分析调用

建议参数：

- `temperature`：0–0.2；
- `response_mime_type`：`application/json`；
- 启用 `response_schema`（若模型/API 支持）；
- 对同一图像进行 3 次独立采样。

伪代码：

```python
samples = []
for i in range(3):
    response = gemini.generate_content(
        contents=[system_prompt, few_shot_examples, user_image],
        generation_config={
            "temperature": 0.1,
            "response_mime_type": "application/json",
            "response_schema": schema
        }
    )
    result = validate_json(response.text, schema)
    if result.valid:
        samples.append(result.data)
```

### 6.2 多采样一致性判断

自动决策规则：

1. 三次采样结果中，`verdict` 多数一致且 `confidence_level` 为 `medium` 或 `high`：进入最终规则路由。
2. 三次采样结果不一致：触发自动二次 AI 仲裁。
3. 多数结果为 `uncertain` 或 `confidence_level` 为 `low`：触发自动二次 AI 仲裁。
4. 任一结果为 `invalid_or_unverifiable` 且图像预处理也判定不可用：直接输出 `invalid_or_unverifiable`。
5. 结论与证据明显矛盾：降级为 `uncertain` 并触发自动二次 AI 仲裁。

### 6.3 自动二次 AI 仲裁

仲裁仍由 Gemini 完成，不引入人工。将主分析采样结果、证据摘要和冲突点提供给仲裁提示词，要求输出最终 JSON。

仲裁提示词建议：

```text
你是数字取证图像认证的自动仲裁器。
你将收到同一张图像的多次主分析结果。请基于图像本身和这些结构化结果，裁决最终判定。
你必须独立检查图像证据，不得仅依赖多数投票。
如果证据仍不足或冲突无法解决，输出 uncertain 和 low 置信度。
只输出给定 JSON Schema，不输出完整思维链。

判定标签：physical_device、ai_generated、uncertain、invalid_or_unverifiable。
置信度：low、medium、high。
```

仲裁调用同样使用严格 JSON Schema 和低温度。仲裁结果作为最终 AI 判定输入规则引擎。

### 6.4 最终自动决策矩阵

| 主采样情况            | 仲裁情况             | 最终结果                  | 自动动作                                          |
| --------------------- | -------------------- | ------------------------- | ------------------------------------------------- |
| 多数一致，medium/high | 不需要               | 采用多数结果              | `accept_physical_device` 或 `accept_ai_generated` |
| 不一致或低置信度      | 仲裁为 medium/high   | 采用仲裁结果              | 对应接受或标记                                    |
| 不一致或低置信度      | 仲裁为 uncertain/low | `uncertain`               | `reject_auto_accept` 或 `request_reupload`        |
| 图像损坏/不可用       | 可选                 | `invalid_or_unverifiable` | `reject_invalid_image`                            |
| AI 生成且高风险标记   | 仲裁确认             | `ai_generated`            | `flag_ai_generated_risk`                          |

最终输出由确定性规则引擎生成，规则引擎只做聚合、校验和路由，不判断图像内容。

---

## 7. 最终系统结果 Schema

建议系统最终输出以下结构：

```json
{
  "type": "object",
  "properties": {
    "final_verdict": {
      "type": "string",
      "enum": ["physical_device", "ai_generated", "uncertain", "invalid_or_unverifiable"]
    },
    "final_confidence_level": {
      "type": "string",
      "enum": ["low", "medium", "high"]
    },
    "decision_action": {
      "type": "string",
      "enum": [
        "accept_physical_device",
        "accept_ai_generated",
        "flag_ai_generated_risk",
        "reject_auto_accept",
        "request_reupload",
        "reject_invalid_image",
        "system_error"
      ]
    },
    "sample_consistency": {
      "type": "string",
      "enum": ["consistent", "inconsistent", "single_sample", "failed"]
    },
    "arbitration_used": {"type": "boolean"},
    "evidence": {
      "type": "array",
      "items": {"type": "string"}
    },
    "risk_flags": {
      "type": "array",
      "items": {"type": "string"}
    },
    "uncertainty_reasons": {
      "type": "array",
      "items": {"type": "string"}
    },
    "request_id": {"type": "string"},
    "model_version": {"type": "string"},
    "prompt_version": {"type": "string"},
    "schema_version": {"type": "string"}
  },
  "required": [
    "final_verdict",
    "final_confidence_level",
    "decision_action",
    "sample_consistency",
    "arbitration_used",
    "evidence",
    "risk_flags",
    "uncertainty_reasons",
    "request_id",
    "model_version",
    "prompt_version",
    "schema_version"
  ],
  "additionalProperties": false
}
```

---

## 8. 稳定性与一致性策略

针对 LLM 数值输出方差，采用：

1. 固定枚举标签，不依赖自由文本结论。
2. 置信度分档，避免模型输出不稳定小数。
3. 低温度调用。
4. 三次采样多数投票。
5. 证据一致性检查：结论与证据矛盾时降级为 `uncertain`。
6. 严格 JSON 校验和有限重试。
7. 低置信度或冲突时自动触发二次 AI 仲裁。
8. 仲裁仍不确定时自动输出 `uncertain`，并执行 `reject_auto_accept` 或 `request_reupload`。
9. 提示词、Few-Shot、Schema、模型版本全部版本化。
10. 模型不可用时返回 `system_error`，不自动判真或判假。

---

## 9. 异常处理与降级策略

- JSON 解析失败：重试 1–2 次；仍失败则触发仲裁或输出 `system_error`。
- 图像损坏：输出 `invalid_or_unverifiable` 和 `reject_invalid_image`。
- 图像过大或格式不支持：预处理阶段拒绝或转换。
- Gemini 超时/限流：指数退避重试；超过阈值返回 `system_error`。
- 多采样结果冲突：自动二次 AI 仲裁。
- 仲裁失败：输出 `uncertain`，动作 `reject_auto_accept` 或 `request_reupload`。
- 高风险 AI 生成标记：输出 `ai_generated` 并附带 `flag_ai_generated_risk`。

---

## 10. 评估与迭代

建立测试集，覆盖：

- 真实相机/手机照片；
- 主流 AI 生成图；
- 压缩、截图、滤镜、二次编辑图；
- 低光照、模糊、遮挡图；
- 边界和对抗样本；
- 提示注入图像文字样本。

核心指标：

- 准确率、精确率、召回率；
- AI 生成图召回率；
- 真实照片误报率；
- `uncertain` 比例；
- 多采样一致性率；
- 二次 AI 仲裁触发率；
- JSON Schema 合法率；
- 最终自动决策准确率；
- 平均延迟和成本。

迭代机制：

- 定期更新 Few-Shot 示例；
- 监控 Gemini 模型升级导致的输出漂移；
- 对提示词和 Schema 做 A/B 测试；
- 保留失败案例库；
- 根据评估结果调整多采样次数、仲裁触发阈值和最终动作策略。

---

## 11. 安全、合规与审计

- 图像可能含隐私信息，需明确授权、加密存储和保留期限。
- 系统输出不应作为唯一法律或执法依据；对外使用时应保留置信度和风险标记。
- 防止提示注入：用户图像中的文字不得改变系统指令。
- 保存审计日志：请求 ID、图像哈希、模型版本、提示版本、Schema 版本、采样结果、仲裁结果、最终决策和系统动作。
- 对高风险场景通过 `flag_ai_generated_risk` 自动标记，供下游自动风控使用。
- 所有模型调用和规则路由均需可追溯、可回放。

---

## 12. 实施步骤

1. 定义判定标签、主分析 Schema 和最终结果 Schema；
2. 编写 System Prompt 和自动仲裁 Prompt；
3. 准备 2–4 个 Few-Shot 示例；
4. 建立小规模评估集；
5. 接入 Gemini API，启用低温度和结构化输出；
6. 实现三次采样、JSON 校验、重试、一致性投票和自动二次 AI 仲裁；
7. 实现确定性规则引擎生成最终决策和动作；
8. 灰度上线，监控一致性、误报率、不确定率、延迟和成本；
9. 根据评估反馈迭代提示词、示例和阈值。

---

## 13. 交付物清单

- System Prompt 模板；
- 自动仲裁 Prompt 模板；
- Few-Shot 示例集；
- 主分析 JSON Schema 与最终结果 Schema；
- JSON 校验器与重试逻辑；
- Gemini 多模态调用服务；
- 多采样投票与自动二次 AI 仲裁模块；
- 确定性规则引擎；
- 评估集与指标看板；
- 审计日志与版本管理方案。