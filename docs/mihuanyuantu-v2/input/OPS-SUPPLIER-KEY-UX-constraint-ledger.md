# OPS-SUPPLIER-KEY-UX-2026-11-13 · 约束台账

依据：本工单、PRD FR-012/FR-030/PG-011、架构 AD-008、MODEL-API-CONFIG 台账、`prototype/`、AGENTS.md。

## 冲突 / 歧义

| ID | 类型 | 原文 | 处理 |
| --- | --- | --- | --- |
| C1 | 覆盖旧裁决 | MODEL-API-CONFIG C1「禁止多 Key / 单槽」 | **本单管理员裁决**：多 Key **共存存储**；同时只启用一套；**禁止权重轮询** |
| C2 | 硬约束 | 密钥明文 | 仅 gitignored `生产物料/` 或 `.secrets/`；响应掩码；禁止 commit/日志全文 |
| C3 | 硬约束 | Base URL 切换 | 提供商切换后必须写入已知默认 URL，禁止留空 |
| C4 | 硬约束 | 种子 | `gpt-image-2` 不支持；UI 灰显；API `SEED_UNSUPPORTED` 保留 |
| C5 | 硬约束 | PASS_SCORE | 默认可仍为 75；管理员可改；非管理员不可写；不得借机擅自永久降到更低默认 |
| C6 | 范围 | 另一会话五层对齐 | 不触碰 `mihuanyuantu-v2` worktree 脏文件 |
| C7 | 合入 | 双账号 | 不得自评自合；不开 S7；`production_billing=false` |

## 声明假设

- `[DECLARED]` 多 Key 实现可优先「秘密库多条目 + 合同行仍每 duty 一行指向当前启用」；若必须多合同行则迁移解除 `uq_duty` 或加 version 表，须在端测注明方案。
- `[DECLARED]` 模型探活失败时允许静态目录兜底，但日志/证据须标明 `probe=fallback_static`。
- `[DECLARED]` T5 样式以 realphotos 应用区为主；不强行重做整个 aojuai 底座主题。

## 证据

- 工单：`docs/mihuanyuantu-v2/input/OPS-SUPPLIER-KEY-UX-2026-11-13.md`
- 端测：`/tmp/ops-supplier-key-ux-e2e.log`
