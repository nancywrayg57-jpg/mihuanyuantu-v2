# 蜜獾原图 v2 · 新会话移交

> 职责：新会话**一分钟摘要与风险**。下一步权威以 `docs/mihuanyuantu-v2/progress.yaml` → `next_action` 为准。  
> 读序：`handoff.md` → `anchor.md` → `checkpoint.md` → `AGENTS.md` → `DEV_INSTRUCTIONS.md` → `progress.yaml`。

## 1. 一分钟接手

| 项 | 值 |
| --- | --- |
| 当前工单 | `REALPHOTOS-S7-PROD-DEPLOY-E2E-2026-11-16` |
| 分支 | `cursor/s7-prod-deploy-9973` |
| 基线 | `origin/main` @ `3ed1088`（含预发端测 #65、API 型 URL 导入 #67） |
| 生产目标 | `47.242.28.49` · `https://exif-demo.honeybadgersoft.com` |
| T01 / T03 | B 同机 PostgreSQL（已接受单点） / 正式供应商 API 型导入 |
| 已达成 | T0–T4 PASS；T5 四角色矩阵 `fail_count=0`；生成/预审真供应商抽样 PASS |
| **阻塞** | **最终检测被 Gemini 地区策略拒绝**：`User location is not supported for the API use.` |
| 生产入口 | 已按失败协议回滚占位页；五个 systemd 单元 enabled+active |
| 收费 | `production_billing=false` |

## 2. 证据指针

- 端测证据：`docs/mihuanyuantu-v2/input/REALPHOTOS-S7-PROD-DEPLOY-E2E-2026-11-16-e2e.txt`
- 收口与 T0–T7 状态：`docs/mihuanyuantu-v2/input/REALPHOTOS-S7-PROD-DEPLOY-E2E-2026-11-16.md`
- 阻塞说明与处置选项：`docs/mihuanyuantu-v2/input/REALPHOTOS-S7-PROD-DEPLOY-E2E-2026-11-16-blocker.md`
- 运行日志：`/tmp/realphotos-s7-prod-e2e.log`（生产机）；服务日志 `/var/log/realphotos/*.log`
- **生产运维手册**：[`S7-生产运维手册-2026-11-16.md`](docs/mihuanyuantu-v2/S7-生产运维手册-2026-11-16.md)（启停 / 切流 / 回滚 / 代理 / 密钥 / 故障 / 备份）
- 生产机部署脚本：`/root/蜜獾原图-v2/shared/01_db.sh` … `08_rollback.sh`

## 3. 风险 / 勿做

- **检测未通**：Gemini 拒绝香港/大陆出口；解决前不得宣称「检测通过」或开收费。
- 三条历史任务（1/2/3）均为技术失败，各 10 积分 `held_until_tech_support` 冻结，未擅自释放。
- 验收账号仍是种子口令，上线前须改强口令。
- 无 Swap、无自动告警；备份仅手工规程。
- 双账号：禁自评自合；Collaborator 不打 Tag、不触发生产部署。

## 4. 下一步

1. 管理员已选 **A 出站代理**；应用侧 `09_proxy.sh` 已就绪（drop-in + NO_PROXY 保留国内供应商直连）。
2. 拿到允许地区代理地址后：`09_proxy.sh apply http://<host>:<port>` → `06_nginx.sh` 切回 → 复跑检测抽样 → 再走 T5/T6。
3. 通过后 Owner（非作者）审合 PR #68 并打 `v2.M.P`。
