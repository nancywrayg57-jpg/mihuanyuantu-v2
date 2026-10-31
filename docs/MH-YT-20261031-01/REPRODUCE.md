# 复现命令（MH-YT-20261031-01）

## 0. 解阻数据

将本地 Windows 目录同步到仓库：

```text
data/输入材料/          ← 四份文档（Gemini方案/技术原理/PRD/exifVerifier.ts）
data/测试用/测试图/
data/测试用/测试图_处理后/
data/测试用/测试图_二次处理后/
data/测试用/测试图_三次处理后/
```

不要放入 `校准图/`（Q6）。

## 1. 环境

```bash
cd /workspace
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements-eval.txt
# Top1
pip install "aidetector @ git+https://github.com/lynote-ai/ai-image-detector.git"
# Top2（可选官方包）
pip install "nonescape @ git+https://github.com/e3ntity/nonescape.git#subdirectory=python"
# Top3
pip install transformers timm pillow torch --index-url https://download.pytorch.org/whl/cpu
```

## 2. 构建 manifest

```bash
python -m eval.build_manifest
# 期望：g0/r1/r2/r3 各 ok=198；异常写入 docs/MH-YT-20261031-01/anomalies.md
```

## 3. 全量评测（每检测器 792 图次）

```bash
python -m eval.run_eval --detectors lynote_univfd,nonescape_onnx,community_forensics
python -m eval.metrics
```

断点续跑：重复 `run_eval` 即可（按 sha256 缓存）。

## 4. 单元自检（无测试图时也可跑）

```bash
python -m pytest tests/ -q
```

## 5. 归档哈希

```bash
find docs/MH-YT-20261031-01 data/manifest.csv results -type f | sort | xargs sha256sum > docs/MH-YT-20261031-01/ARCHIVE_HASHES.txt
```
