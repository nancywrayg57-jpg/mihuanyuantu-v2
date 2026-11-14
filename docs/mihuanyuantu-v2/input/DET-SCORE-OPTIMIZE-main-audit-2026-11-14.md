# DET-SCORE-OPTIMIZE · 主代理审计（编码子代理交付）

日期：2026-11-14  
被审：[OPEN_PARTIAL 白名单实施](c23e6e3c-bca6-4743-9769-c4ca5b9bc7f5)  
门禁：`DET-SCORE-OPTIMIZE-feasibility-gate-2026-11-14.md`

## 审计结论

| 项 | 结果 |
| --- | --- |
| 白名单符合 | **PASS** |
| 红线未破 | **PASS**（未改 PASS_SCORE / PIPELINE_VERSION / 光学·噪声常量 / 焦距表） |
| 单测 | **PASS** `test_s2_five_layer` 17 |
| 本地 CI 切片 | **PASS** secret_scan + ruff(改动文件) + 同上 pytest |
| Q1 | **仍 UNPROVEN**（本审计不宣称提分达标） |
| 推送 | **未授权**（保持本地） |

## 核对要点

1. **A**：`_generate_images_off_loop` 它线程 `asyncio.run` + join；失败 `_layer0_img2img_fail` 打 `error_type`；未改 `s1_processing` 调用链（符合「它线程」选项）。  
2. **D**：`Settings.ALIGN_LAYER0_IMG2IMG` 默认 `"0"`；flag 关跳过不记失败。  
3. **B**：`_CA_INTENSITY=0.0`；8mm/26mm 恒等单测；无 sat×1.02。  
4. **未越界**：`_LAYER0_OPTICAL_STRENGTH=0.32`、`_NOISE_INTENSITY=1.55`、`PIPELINE_VERSION=s2-five-layer-3` 仍在。  
5. **可接受重构**：抽出 `_blend_layer0_jpeg`；向 `generate_images` 显式传 `api_key`（该形参本已存在）。

## 下一步（R5 续）

- 重启本地 worker 加载新代码后，协议 W：R1（现行语义已变 CA=0 + Layer0 默认关）vs 历史对照。  
- 真 Gemini 消融留证；合同集协议 C 冲 Q1 另排。  
- SHORTFALL → 停止加码；`L-OPTICAL-BACKOFF` 等不自动入库。
