# 阶段 B 检索方案（B1）

## 纳入标准

1. 能对**整图**给出 AI vs 真实（或等价概率）信号；
2. 有可打开核实的 GitHub / HuggingFace / 官方 API 文档链接；
3. 许可证明确且允许本 POC 使用（商业不明或仅 NC 的候选不得进 Top3 主路径）；
4. 有可获取权重或可调用的免费/低价推理入口；
5. 单张边际成本目标：免费或 ≤ 0.01 元（Q9）。

## 排除标准

1. 许可证不明（工单：直接剔除，不得写入正式对比表主列）；
2. 仓库归档且无权重；
3. 仅做人脸 deepfake、不做通用 AIGC 检测；
4. 仅元数据/EXIF 规则引擎作为**唯一**判据（可作辅助信号，不进 Top3）；
5. 链接无法打开核实。

## 检索式（已执行）

```text
site:github.com AI generated image detector          2025..2026
site:github.com "AI-generated image detection" stars:>200
site:github.com diffusion model detection frequency fingerprint
"AI image detector" huggingface model card free
"AI-generated image detection" benchmark 2025 arxiv
free / cheap AI image detection API pricing
```

## 评分卡权重（事先固定，禁止事后调整）

| 维度 | 权重 |
| --- | --- |
| 检测有效性（原图误判率 / 判别力） | 30% |
| 成本 | 30% |
| 部署与集成难度 | 10% |
| 延迟 | 10% |
| 可解释性 | 10% |
| 维护活跃度 | 5% |
| 合规与许可 | 5% |

评分尺度 1–5；加权总分 = Σ(分×权重)。有效性在全量实测前用「公开基准/跨生成器证据」作**先验分**，实测后用指标 A 覆写（不得改权重）。
