# 蜜獾原图 v2 · 新会话移交

> 职责：新会话**一分钟摘要与风险**。下一步权威以 `docs/mihuanyuantu-v2/progress.yaml` → `next_action` 为准。  
> 读序：`handoff.md` → `anchor.md` → `checkpoint.md` → `AGENTS.md` → `DEV_INSTRUCTIONS.md` → `progress.yaml`。

## 1. 一分钟接手

| 项 | 值 |
| --- | --- |
| 当前工单 | `OPS-DESK-UX` |
| 分支 | `cursor/ops-desk-ux-9973`（worktree `.worktrees/ops-desk-ux`） |
| 基线 | `origin/main` @ `2d807e8`（含 REGISTER-FIX #58） |
| 交付 | T1 工单双标签+申诉弹窗+租户聚合冻结释放；T2 租户列表/查看账号/操作弹窗；T3 删检测基线说明文案 |
| 验证 | pytest 3 项 + ruff；证据 `OPS-DESK-UX-e2e-2026-11-15.txt` |
| 阶段红线 | **禁止开 S7**；禁止生产收费宣称；不改 PASS_SCORE 合同默认 |

## 2. 证据指针

- 工单 / 账本：`docs/mihuanyuantu-v2/input/OPS-DESK-UX-work-order-2026-11-14.md`、`OPS-DESK-UX-constraint-ledger.md`
- 端测：`docs/mihuanyuantu-v2/input/OPS-DESK-UX-e2e-2026-11-15.txt`

## 3. 风险 / 勿做

- `GET /held-credits` 的 `items` 现为租户聚合；逐任务明细在 `tasks`（旧脚本勿再读 `items[].taskId`）
- 主树 `gemini-dof-light-opt` 脏工作勿与本 worktree 混用
- 双账号：禁自评自合；禁打 Tag / 真部署

## 4. 下一步

推分支并开 PR；非作者 Owner squash。禁 S7。
