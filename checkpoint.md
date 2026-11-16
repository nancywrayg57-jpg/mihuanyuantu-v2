# 蜜獾原图 v2 · 检查点

> 职责：**可核实状态**。约束见 `anchor.md`；下一步见 `progress.yaml`。

## §0 最小集

| 字段 | 当前值 |
| --- | --- |
| updated | 2026-11-16 23:55 CST |
| origin/main | `3ed1088`（含预发端测 #65、API 型 URL 导入 #67） |
| 工作区分支 | `cursor/s7-prod-deploy-9973` |
| 工单 | `REALPHOTOS-S7-PROD-DEPLOY-E2E-2026-11-16` |
| T0 | PASS（S7 清单写入 `DEV_INSTRUCTIONS.md` §10.9） |
| T1 | PASS（同机 PG16 `realphotos_prod`、LocalDisk 三目录、TLS + certbot、运行时齐备） |
| T2 | PASS（`.env` 600；duty 四岗 `present=true`；仓库无密钥） |
| T3 | PASS（systemd 五单元 active；迁移 head；Next build；Nginx 切流） |
| T4 | PASS（上传→网关字节一致；challenges 200；health 200） |
| T5 | **PASS**：四角色 `fail_count=0`；预审 dashscope / 生图 aoju / 检测 Gemini 三岗均真实外呼 |
| T6 | **PASS**：§11 四项核对通过；收费保持 `false` |
| 汇总标记 | ✅ `REALPHOTOS_S7_PROD_E2E_PASS` |
| 证据 | `docs/mihuanyuantu-v2/input/REALPHOTOS-S7-PROD-DEPLOY-E2E-2026-11-16-e2e.txt`；`-blocker.md`；`/tmp/realphotos-s7-prod-e2e.log` |
| 生产入口 | **已切到应用**（非占位）；回滚 `08_rollback.sh` 可秒切占位 |
| 出口代理 | `gemini-egress-proxy.service`（Xray，本地 7890，出口 150.241.181.64）enabled+active |
| production_billing | false |
| PR | #68（CI 全绿，`MERGEABLE`，待非作者 Owner 审合） |
| 下一步 | Owner 审合 + 打 `v2.M.P`；2026-12-06 前替换第三方订阅代理（R7） |

## §1 生产机事实快照（2026-11-16）

| 项 | 值 |
| --- | --- |
| 主机 | `47.242.28.49`（`iZj6c5tqrza96o5w52qxpcZ`，内网 `172.17.54.212`） |
| OS / 规格 | Ubuntu 24.04.2 LTS；4 vCPU / 7270 MiB / 无 Swap；`/` 49G 用 ~27% |
| 运行时 | Python 3.12.3 + venv（SQLAlchemy 2.0.57）；Node v22.23.1；pnpm 10.13.1；exiftool 12.76 |
| 数据库 | 同机 PostgreSQL 16.15，`realphotos_prod` @ 127.0.0.1，`realphotos_app` 非超级用户 |
| 发布目录 | `/root/蜜獾原图-v2/releases/3ed1088`；`current` 符号链接；工作树对齐 `0f5fd1c` |
| 保密目录 | `/root/蜜獾原图-v2/shared`（0700，文件 0600）；脚本 `01_db.sh`…`11_xray_setup.sh` |
| 业务图 | `/root/蜜獾原图-v2/www/mhyt/{upload,phy-export,export}` |
| 应用单元 | `realphotos-api` / `-web` / `-process` / `-notify` / `-cleanup` |
| 出口单元 | `gemini-egress-proxy`（Xray 26.11.9 → vmess 节点，美国出口） |
| 已建账号 | `rp_merchant_a1/a2`、`rp_order_support`、`rp_tech_support`、`rp_admin`、`rp_merchant_b1`（种子口令，上线前须改） |
| 检测样本 | task 4：`gemini-3.1-pro-preview` 52 分未通过；输出 12,370,703 B 可下载；积分已释放 |
| 生成样本 | asset 4（`text_to_image`，1536×1024，2,585,364 B） |
