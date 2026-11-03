# 巨型 Service 安全拆分管线（实例：nextjs-plugins ppt-master service.py）

> 回流说明（2026-08-27）：方法通用——按职责分片、late-binding 依赖、逐片零回归、E2E 闸门、以及"真实进程是否加载了新代码"的验证；实例与测试基线数字是 nextjs-plugins ppt-master 的，base 无该模块。

更新：2026-08-08

## 巨型 Service 安全拆分管线（已验证 6 片零回归）

service.py 12,223 行 → 11,084 行，拆出 6 个模块（image_stage / image_geometry /
design_rules / generation_watchdog / progress_reporting / generation_finalize），
全部零行为变化。可复用流程：

1. **纯函数片**（模块级 def/常量）：按行号提取源码 → 差集脚本找出片内未定义的外部名
   （注意同时扫下划线开头与公共常量两类）→ 逐字迁移到新模块 → service 以 import 重导出
   片外仍引用的名字。校验：源片段每一非空行必须原样出现在新模块中（missing=0）。
2. **闭包片**（编排方法内的嵌套函数）：提取为类/函数 + 显式依赖传参。方法内后续会被
   重新赋值的外层变量（target_count、prompt_structure 等）必须以 `lambda: var` getter
   传入保持 late-binding，构造点之后不再变的变量才能按值传。接线处保留同名局部别名，
   调用点零改动。
3. 每片必须：ppt_master 测试全绿 → 全量套件与基线完全比对（错误数一致才算干净）→
   E2E 生成冒烟（scratchpad ppt_bp_check.py 模式）→ 单独 commit。
4. **E2E 前必须确认执行进程加载了目标代码**：ppt-master 生成由独立的
   `app.tasks.ppt_master_worker` 进程执行（非 uvicorn --reload，不热加载）。改完代码只看
   uvicorn 会得到假阳性——2026-08-08 六片重构的首轮 E2E 全部跑在未重启的老 worker 上，
   "全部通过"验证的其实是旧代码。正确做法：确认队列无 running/pending 任务后
   `kill <worker_pid>` 并以原命令原目录重启（`python -m app.tasks.ppt_master_worker --concurrency 1`，
   cwd=backend），再跑 E2E；必要时在改动里埋一个可观测标记（如新日志字段）以确认新代码生效。
4. 触模板 preset 注册簇（`_ppt_master_template_presets`/`PptMasterRuntime`）的函数
   不要迁出；确需迁出时用函数内延迟 `from ...service import`（见 design_rules._project_design_rules）。

剩余高风险片（R1-4 蓝图准备阶段、R1-5 页面生成主干）涉及 Blueprint Compiler 核心
路径与异常恢复分支，需先建 mock 页面生成的 golden 测试再动，勿在无 golden 基建时搬移。

## 全量测试基线的 17 个既有 error（非回归）

`pytest tests/` 全量跑时 `test_training_claim_activity_service.py` 的 17 例在 setup
阶段报 `AttributeError: module 'app.core' has no attribute 'provider_secrets'`——
fixture 用字符串路径 monkeypatch `app.core.provider_secrets.*`，依赖其他测试先
import 该子模块，全量跑的收集顺序下未加载。单独跑 `-k claim` 全过。
判定回归时以"1775+ passed, 17 errors"为基线；修复方向是在该测试文件顶部显式
`import app.core.provider_secrets`。
