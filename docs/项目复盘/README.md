# 蜜獾原图 v2 · 项目复盘文档索引

公网入口：[https://exif-demo.honeybadgersoft.com](https://exif-demo.honeybadgersoft.com)  
证据采集见 `evidence_metrics.json` · `origin/main`：`b99d5af` · 提交数：**86** · 已合入 PR：**80** · Tag：`v2.0.1` · `production_billing`：**false**

## 文档清单

| 文档 | Markdown | HTML |
| --- | --- | --- |
| 开发过程复盘与成败经验 | [01_开发会话复盘与成败经验.md](./01_开发会话复盘与成败经验.md) | [01_开发会话复盘与成败经验.html](./01_开发会话复盘与成败经验.html) |
| 项目架构与开发路线图 | [02_项目架构与开发路线图.md](./02_项目架构与开发路线图.md) | [02_项目架构与开发路线图.html](./02_项目架构与开发路线图.html) |
| 后续优化与演进建议 | [03_后续优化与演进建议.md](./03_后续优化与演进建议.md) | [03_后续优化与演进建议.html](./03_后续优化与演进建议.html) |
| 总览门户 | 本文件 | [index.html](./index.html) |
| 本轮系统指令（蜜獾原图版） | 见本目录以 `[系统指令] 蜜獾原图v2…` 开头的 `.md` | — |

## 关键事实摘要（禁止口头改数）

| 指标 | 值 |
| --- | ---: |
| `origin/main` 提交数 | 86 |
| 已合入 PR | 80 |
| Tag | v2.0.1 |
| 公网入口 | 已切应用 |
| 生产收费 | false |

返工热点文件 Top（`git log --name-only` 触碰次数）：`progress.yaml`、`wiki.md`、`checkpoint.md`、`handoff.md`、`s1_processing.py`、`s6_ops.py`、任务/图库/工作台前端页等——详见 `evidence_metrics.json`。

## 证据与映射

- `evidence_metrics.json` — Git/PR/热点/产品锚点  
- `pr_stage_map.json` — 阶段（章）↔ PR 列表  
- 系统指令 — 本目录「蜜獾原图版」提示词（自金专 OA 版改写）

## 阅读建议

1. 先扫本 README 数字与范围。  
2. 工程成败与避坑 → `01_*`。  
3. 架构与已走路线 → `02_*`。  
4. 下一步只做合同内事项 → `03_*`。

## 口径备忘

- 只写已合入 `main` 的事实。  
- 《01》含 2026-11-20 管理员边问边证结论。  
- HTML：离线自包含，风格贴近蜜獾原图运营工具气质；可用 `python scripts/build_html_reports.py` 从 Markdown 重新生成。
