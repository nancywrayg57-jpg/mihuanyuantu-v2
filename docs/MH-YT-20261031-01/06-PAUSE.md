# 暂停点（2026-10-31 Asia/Shanghai）

**状态**：开发暂停，等待测试图入库后唤醒继续。

## 已完成

- 阶段 A：基线卡 / 差异清单 / 阻塞登记
- 阶段 B：调研报告 + Top3
- 阶段 C：评测脚手架 + 单元测试；全量 792 **未跑**
- PR：`cursor/mh-yt-detector-alt-eval-88c4` → #1

## 唤醒条件

四组目录出现在仓库（或 Cloud 工作区）`data/测试用/`：

1. `测试图/`
2. `测试图_处理后/`
3. `测试图_二次处理后/`
4. `测试图_三次处理后/`

不要含 `校准图/`。本机源：`D:\workspace\蜜獾原图v2\测试用`。同步说明：`scripts/sync_test_assets.md`。

## 唤醒后立即执行

```bash
git pull
python -m eval.build_manifest   # 期望 g0/r1/r2/r3 各 ok=198
python -m eval.run_eval --detectors lynote_univfd,nonescape_onnx,community_forensics
python -m eval.metrics
# 然后补全 04-test-report / 05 终局勾选 / ARCHIVE_HASHES
```

## 不得做

- 用其他样图冒充 198 分母
- 放宽门禁或伪造 O3/O4
