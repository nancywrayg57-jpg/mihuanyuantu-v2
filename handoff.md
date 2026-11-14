# 蜜獾原图 v2 · 新会话移交

> 职责：新会话**一分钟摘要与风险**。下一步权威以 `docs/mihuanyuantu-v2/progress.yaml` → `next_action` 为准。  
> 读序：`handoff.md` → `anchor.md` → `checkpoint.md` → `AGENTS.md` → `DEV_INSTRUCTIONS.md` → `progress.yaml`。

## 1. 一分钟接手

| 项 | 值 |
| --- | --- |
| 当前工单 | `REGISTER-FIX`（注册不可用） |
| 分支 | `cursor/register-fix-9973` |
| PR | [#58](https://github.com/nancywrayg57-jpg/mihuanyuantu-v2/pull/58) open |
| 根因 | 注册页走底座 `registration-config`，默认租户 `default` 不存在 → `enabled:false`；架构要求的 `POST /api/v1/realphotos/auth/register` 原缺失（404） |
| 修复 | 实现 realphotos 注册（验证码 + 新建商家租户/`rp_merchant`）；前端注册页改用该流 |
| 端测 | `/tmp/register-fix-e2e.log` 与 `docs/.../REGISTER-FIX-e2e-2026-11-14.txt` → `REGISTER_FIX_E2E_PASS=true` |
| 阶段红线 | **禁止开 S7**；禁止生产收费宣称 |

近期已合入（与本工单无关）：

- **#55** DET-SCORE 止血；**#56** NONLEGACY 不升默认；**#57** optical 0.24 升默认

## 2. 证据指针

- 约束账本：`docs/mihuanyuantu-v2/input/REGISTER-FIX-constraint-ledger.md`
- 端测：`docs/mihuanyuantu-v2/input/REGISTER-FIX-e2e-2026-11-14.txt`
- 单测：`aojuai-main/backend/tests/capabilities/realphotos/test_auth_register.py`

## 3. 风险 / 勿做

- 不得把本修复说成「改了租户默认开放策略」——根因是缺业务注册 API + 错误入口，不是故意 invite-only
- 不得恢复 CA / Layer0 img2img 默认；不得放宽 `PASS_SCORE`；不得开 S7
- 双账号：禁自评自合；Collaborator 禁打 Tag / 真部署
- 密钥只读同级 `生产物料/`，禁止入库

## 4. 下一步

等待非作者 Owner squash 合入 [#58](https://github.com/nancywrayg57-jpg/mihuanyuantu-v2/pull/58)。合入后可清本地旧分支 `cursor/five-layer-default-opt-9973`（内容已在 main）。
