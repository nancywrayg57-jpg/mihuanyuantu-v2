# Top3 修订说明（2026-10-31 实测前）

原 Top3 第 3 名 `buildborderless/CommunityForensics-DeepfakeDet-ViT` 在入库权重核验时失败：

- `num_labels=1`，`id2label={0: LABEL_0}`
- softmax 对单 logit 恒为 1.0，无法形成有效二分类
- 不宜进入主口径

**替补（同一调研池、同许可、可跑）**：`lynote-ai/ai-image-detector` 的 **`hybrid`** 后端（UnivFD + HF 轻量分类器集成，MIT）。

本轮正式跑批 Top3：

| # | detector_id | 后端 |
| --- | --- | --- |
| 1 | `lynote_univfd` | UnivFD |
| 2 | `nonescape_mini` | lynote 封装的 nonescape-mini（官方 CDN 权重由 lynote 拉取；独立 CDN 直链曾 403） |
| 3 | `lynote_hybrid` | hybrid |

评分卡权重**未改**；仅因第 3 名权重不可用做等权替补，并登记本修订。
