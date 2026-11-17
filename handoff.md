# 蜜獾原图 v2 · 新会话移交

> 职责：新会话**一分钟摘要与风险**。下一步权威以 `docs/mihuanyuantu-v2/progress.yaml` → `next_action` 为准。  
> 读序：`handoff.md` → `anchor.md` → `checkpoint.md` → `AGENTS.md` → `DEV_INSTRUCTIONS.md` → `progress.yaml`。

## 1. 一分钟接手

| 项 | 值 |
| --- | --- |
| 当前工单 | `REALPHOTOS-S7-PROD-DEPLOY-E2E-2026-11-16` |
| 分支 | `cursor/s7-prod-deploy-9973` |
| 基线 | `origin/main` @ `3ed1088`（含预发端测 #65、API 型 URL 导入 #67） |
| 生产目标 | `47.242.28.49` · `https://exif-demo.honeybadgersoft.com`（**已切到应用**） |
| T01 / T03 | B 同机 PostgreSQL（已接受单点） / 正式供应商 API 型导入 |
| 结果 | ✅ `T0–T7` 全绿、`REALPHOTOS_S7_PROD_E2E_PASS` |
| 收费 | `production_billing=false`（未开放） |

## 2. 证据指针

- 端测证据：`docs/mihuanyuantu-v2/input/REALPHOTOS-S7-PROD-DEPLOY-E2E-2026-11-16-e2e.txt`
- 收口与 T0–T7 状态：`docs/mihuanyuantu-v2/input/REALPHOTOS-S7-PROD-DEPLOY-E2E-2026-11-16.md`
- 阻塞复盘（已解除）：`docs/mihuanyuantu-v2/input/REALPHOTOS-S7-PROD-DEPLOY-E2E-2026-11-16-blocker.md`
- **生产运维手册**：[`S7-生产运维手册-2026-11-16.md`](docs/mihuanyuantu-v2/S7-生产运维手册-2026-11-16.md)
- 运行日志：`/tmp/realphotos-s7-prod-e2e.log`（生产机）；服务日志 `/var/log/realphotos/*.log`
- 生产机部署脚本：`/root/蜜獾原图-v2/shared/01_db.sh` … `11_xray_setup.sh`

## 3. 风险 / 勿做

- **出口代理是第三方订阅节点**（名称含到期日 **2026-12-06**）：到期前必须换成自有 SG/JP 代理，否则检测链路中断（R7）。
- 三条历史技术失败任务（1/2/3）各 10 积分仍 `held_until_tech_support` 冻结；task 4 为业务未通过，积分已按 PRD 释放。
- 验收账号仍是种子口令，上线前须改强口令（R6）。
- 无 Swap、无自动告警、无定时备份（R2/R5）。
- 双账号：禁自评自合；Collaborator 不打 Tag、不触发生产部署。

## 4. 下一步

1. Owner 以**非作者**账号审合 PR #68（作者为 `nancywrayg57-jpg`），通过后打 `v2.M.P`。
2. 2026-12-06 前完成 R7：自有 SG/JP 代理 → `09_proxy.sh apply` → 复跑检测抽样。
3. 上线前处理 R6（改口令）与 R5（备份/告警规程）。
4. 对外收费与「检测通过」话术仍须管理员另行确认（`production_billing` 保持 false）。
