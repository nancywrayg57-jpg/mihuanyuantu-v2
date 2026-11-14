# 蜜獾原图 v2 · 检查点

> 职责：**可核实状态**（分支 / SHA / 端测数字 / 合入事实）。不等于 PRD；约束见 `anchor.md`；下一步见 `progress.yaml`。

## §0 最小集

| 字段 | 当前值 |
| --- | --- |
| updated | 2026-11-14 CST |
| origin/main | `e7a93c5`（合入前基线） |
| 工作区分支 | `cursor/register-fix-9973` |
| 工单 | REGISTER-FIX |
| 根因 | 底座 registration-config 默认租户缺失 → enabled=false；realphotos `/auth/register` 原 404 |
| 修复 | `POST /api/v1/realphotos/auth/register` + 前端验证码注册页 |
| 单测 | `test_auth_register.py` 3 passed |
| 端测 | `REGISTER_FIX_E2E_PASS=true`（`docs/mihuanyuantu-v2/input/REGISTER-FIX-e2e-2026-11-14.txt`） |
| production_billing | false |
| S7 | blocked |
| 下一步 | 推分支开 PR；禁自评自合 |

## 同日已合入 main（无关本工单）

| PR | 工单 | 结果 |
| --- | --- | --- |
| #55 | DET-SCORE hemostasis | Layer0/CA 默认关 |
| #56 | DET-SCORE-NONLEGACY-LIFT | 不升默认 |
| #57 | FIVE-LAYER-DEFAULT-OPT | optical 0.32→0.24 |

## 关键证据路径

- `docs/mihuanyuantu-v2/input/REGISTER-FIX-constraint-ledger.md`
- `docs/mihuanyuantu-v2/input/REGISTER-FIX-e2e-2026-11-14.txt`
