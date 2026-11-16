# 蜜獾原图 v2 · 检查点

> 职责：**可核实状态**。约束见 `anchor.md`；下一步见 `progress.yaml`。

## §0 最小集

| 字段 | 当前值 |
| --- | --- |
| updated | 2026-11-16 CST |
| origin/main | `3ed1088`（含预发端测 #65、API 型 URL 导入 #67） |
| 工作区分支 | `cursor/s7-prod-deploy-9973` |
| 工单 | `REALPHOTOS-S7-PROD-DEPLOY-E2E-2026-11-16` |
| T0 | PASS（S7 清单写入 `DEV_INSTRUCTIONS.md` §10.9） |
| T1 | PASS（同机 PG16 `realphotos_prod`、LocalDisk 三目录、TLS + certbot、运行时齐备） |
| T2 | PASS（`.env` 600；duty 四岗 `present=true`；仓库无密钥） |
| T3 | PASS（systemd 五单元 active；迁移 head；Next build 成功；Nginx 切流） |
| T4 | PASS（上传→网关字节一致；challenges 200；health 200） |
| T5 | **PARTIAL**：四角色矩阵 `fail_count=0`；**最终检测被 Gemini 地区策略拒绝** → `T5_SUPPLIER_DETECTION_BLOCKED` |
| T6 | BLOCKED（§11 检测证据缺失；收费仍 false） |
| 汇总标记 | ❌ `REALPHOTOS_S7_PROD_E2E_FAIL`（failing_item=`T5-SUP-FINAL_DETECTION`） |
| 证据 | `docs/mihuanyuantu-v2/input/REALPHOTOS-S7-PROD-DEPLOY-E2E-2026-11-16-e2e.txt`；`-blocker.md`；`/tmp/realphotos-s7-prod-e2e.log` |
| 生产入口 | 已按失败协议**回滚占位页**；应用单元 enabled+active；`current` → `releases/3ed1088` |
| production_billing | false |
| S7 | 已开工、未完成（等管理员对出口/检测供应商做决策） |
| 下一步 | 管理员决策出口代理/迁节点/换检测供应商；续作只用一条命令切回应用并复跑检测抽样 |

## §1 生产机事实快照（2026-11-16）

| 项 | 值 |
| --- | --- |
| 主机 | `47.242.28.49`（`iZj6c5tqrza96o5w52qxpcZ`，内网 `172.17.54.212`） |
| OS / 规格 | Ubuntu 24.04.2 LTS；4 vCPU / 7270 MiB / 无 Swap；`/` 49G 用 23% |
| 运行时 | Python 3.12.3 + venv（SQLAlchemy 2.0.57）；Node v22.23.1；pnpm 10.13.1；exiftool 12.76 |
| 数据库 | 同机 PostgreSQL 16.15，`realphotos_prod` @ 127.0.0.1，`realphotos_app` 非超级用户 |
| 发布目录 | `/root/蜜獾原图-v2/releases/3ed1088`；`current` 符号链接 |
| 保密目录 | `/root/蜜獾原图-v2/shared`（0700，文件 0600）；部署脚本 `01_db.sh`…`08_rollback.sh` |
| 业务图 | `/root/蜜獾原图-v2/www/mhyt/{upload,phy-export,export}` |
| 单元 | `realphotos-api` / `-web` / `-process` / `-notify` / `-cleanup` |
| 已建账号 | `rp_merchant_a1/a2`、`rp_order_support`、`rp_tech_support`、`rp_admin`、`rp_merchant_b1`（种子口令，上线前须改） |
| 生成资产 | `asset 4`（`text_to_image`，1536×1024，2,585,364 B） |
