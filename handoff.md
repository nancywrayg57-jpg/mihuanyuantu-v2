# 蜜獾原图 v2 · 新会话移交

> 职责：新会话**一分钟摘要与风险**。下一步权威以 `docs/mihuanyuantu-v2/progress.yaml` → `next_action` 为准。  
> 读序：`handoff.md` → `anchor.md` → `checkpoint.md` → `AGENTS.md` → `DEV_INSTRUCTIONS.md` → `progress.yaml`。

## 1. 一分钟接手

| 项 | 值 |
| --- | --- |
| 当前工单 | `REALPHOTOS-PRELAUNCH-E2E-2026-11-15` |
| 分支 | `cursor/prelaunch-e2e-9973`（worktree `.worktrees/prelaunch-e2e`） |
| 基线 | `origin/main` @ `6bb498a`（含 #64 polish） |
| 交付 | 上线前四角色全量端测 + 已知回归复测 + §11 门槛核对（非部署） |
| 验证 | `/tmp/realphotos-prelaunch-e2e.log` 含 `T1`–`T3` PASS；证据入库见 input/ |
| 阶段红线 | **禁止开 S7**；禁止生产收费宣称；不改 PASS_SCORE；作者不得自合 |

## 2. 证据指针

- 工单副本：`docs/mihuanyuantu-v2/input/REALPHOTOS-PRELAUNCH-E2E-2026-11-15.md`
- 端测摘要：`docs/mihuanyuantu-v2/input/REALPHOTOS-PRELAUNCH-E2E-2026-11-15-e2e.txt`
- 门槛核对：`docs/mihuanyuantu-v2/input/REALPHOTOS-PRELAUNCH-E2E-2026-11-15-closeout.md`
- 运行日志：`/tmp/realphotos-prelaunch-e2e.log`

## 3. 风险 / 勿做

- S7 清单未齐；本 PR 不含 Tag / 真部署 / 改分支保护
- FE 冷启动偶发短超时；复测用更长超时
- 双账号：禁自评自合；禁打 Tag / 真部署

## 4. 下一步

Collaborator 推分支并开/更新 PR；Owner（非作者）审合。禁 S7。
