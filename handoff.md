# 蜜獾原图 v2 · 新会话移交

> 职责：新会话**一分钟摘要与风险**。下一步权威以 `docs/mihuanyuantu-v2/progress.yaml` → `next_action` 为准。  
> 读序：`handoff.md` → `anchor.md` → `checkpoint.md` → `AGENTS.md` → `DEV_INSTRUCTIONS.md` → `progress.yaml`。

## 1. 一分钟接手

| 项 | 值 |
| --- | --- |
| 当前工单 | `REALPHOTOS-PROD-GAP-4PACK-2026-11-20` |
| 分支 | `cursor/prod-gap-4pack-9973` |
| 基线 | `origin/main` @ `d8870f1` |
| 生产 | `https://exif-demo.honeybadgersoft.com`（应用已在线） |
| 本包结果 | W1 生产启用 PASS；W2/W3-A/W4 代码 PASS；W3-B 未做 |
| 收费 | `production_billing=false` |

## 2. 证据指针

- 端测：`docs/mihuanyuantu-v2/input/REALPHOTOS-PROD-GAP-4PACK-e2e-2026-11-20.txt`
- 收口：`docs/mihuanyuantu-v2/input/REALPHOTOS-PROD-GAP-4PACK-closeout-2026-11-20.md`
- 工单：`docs/mihuanyuantu-v2/input/REALPHOTOS-PROD-GAP-4PACK-work-order-2026-11-20.md`

## 3. 风险 / 勿做

- W2/W3-A/W4 **前端/API 代码尚未发生产**；合入后须管理员确认再发版。
- 出口代理第三方订阅节点仍约 **2026-12-06** 到期（R7，本包不做）。
- 种子口令未改（R6，本包不做）。
- 禁自评自合；Collaborator 不打 Tag、不擅自生产发版。

## 4. 下一步

1. Collaborator 推分支开 PR；Owner **非作者** squash 合入。
2. 管理员确认后发前后端，使导入页提示 / 队列文案 / 策略摘要上线。
3. 未授权不启动 W3-B 多 worker。
