# 测试报告（指标汇总）

> **声明**：本报告仅为模型判定结果，**不构成**任何平台上传验收承诺。  
> Gemini 定量对比按 Q8 **未执行**；见调研报告定性差异。

## 状态：全量未跑通（硬阻塞 B-02）

本机源路径已确认：`D:\workspace\蜜獾原图v2\测试用`。  
Cloud 侧 `data/测试用/` 仍为空，**禁止**用其他样图冒充 198 分母。

解阻方式：`scripts/sync_test_assets.md`。

### 已完成的管道自检（不计 O3/O4）

| 项 | 结果 |
| --- | --- |
| `pytest tests/` | 6 passed（标签规则 + 附录 B 公式） |
| lynote 适配器字段 | 已修正为读取 `probability_ai` |
| lynote 公开样图冒烟 | 可出概率；**不得**计入工单指标 |

解阻后自动续跑：

```bash
python -m eval.build_manifest
python -m eval.run_eval --detectors lynote_univfd,nonescape_onnx,community_forensics
python -m eval.metrics
```
