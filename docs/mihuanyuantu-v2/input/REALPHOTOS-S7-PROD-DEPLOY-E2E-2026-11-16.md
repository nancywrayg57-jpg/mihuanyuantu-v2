# 工单副本 · S7 生产部署与全量端测（2026-11-16）

> 来源：管理员桌面工单 `REALPHOTOS-S7-PROD-DEPLOY-E2E-2026-11-16`（桌面文件即 S7 授权载体）。
> 本文件为**执行记录 + 收口结论**；原始工单字段以桌面文件为准，本文不改写其决策栏。

| 字段 | 值 |
| --- | --- |
| 工单 | `REALPHOTOS-S7-PROD-DEPLOY-E2E-2026-11-16` |
| 分支 | `cursor/s7-prod-deploy-9973` |
| 基线 | `origin/main` @ `3ed1088`（含 #65 预发端测、#67 API 型 URL 导入） |
| 生产目标 | `47.242.28.49` · `https://exif-demo.honeybadgersoft.com` |
| T01 决策 | **B** 同机自建 PostgreSQL（管理员已接受单点残余风险） |
| T03 决策 | **正式供应商**：API 型 URL 导入（基址可配；本次未做外呼探测） |
| 收费 | **`production_billing=false`**（保持关闭） |
| 结果 | **未达成** `REALPHOTOS_S7_PROD_E2E_PASS`；阻塞项 `T5-SUP-FINAL_DETECTION` |

## T0–T7 执行状态

| 项 | 状态 | 证据 |
| --- | --- | --- |
| T0 补齐 S7 清单 | ✅ `T0_S7_CHECKLIST_PASS` | `DEV_INSTRUCTIONS.md` §10.9（tasks / exit_evidence / forbidden） |
| T1 生产基建 | ✅ `T1_INFRA_PASS` | 同机 PG16 集群 online；`realphotos_prod` 可连；`listen=localhost`；LocalDisk 三目录；TLS 200；certbot.timer active |
| T2 配置与密钥 | ✅ `T2_SECRETS_PASS` | `.env` 600；duty 四岗 `present=true`；admin 合同页 `contracts_with_secret` 四项 |
| T3 发布切流 | ✅ `T3_DEPLOY_PASS` | systemd 五单元 active；迁移 head；Next build 成功（BUILD_ID 生成）；Nginx 切流后 `https_login=200` |
| T4 发布后冒烟 | ✅ `T4_SMOKE_PASS` | 上传 10.9MB JPEG → 网关读回字节一致；`/auth/challenges` 200；`/health` 200 |
| T5 生产四角色端测 | ⚠️ 角色矩阵 ✅ / **供应商检测 ❌** | `T5_PROD_E2E_ROLES_PASS`；`T5_SUPPLIER_DETECTION_BLOCKED` |
| T6 门槛终核 | ⛔ `T6_GATE_BLOCKED` | 见下 §11 核对；收费未开 |
| T7 文档 / CI / PR | ✅ 文档与 PR（Tag 待 Owner） | 证据入库；本地 CI 见 §CI |

## T5 明细

角色矩阵在生产域名上 `fail_count=0`：登录四角色、商家工作台/资源/上传/网关/预设/任务提交/生图、订单客服充值确认与越权拒绝、技术客服工单 20 条/页与用户管理/日志、管理员模型 API/检测基线/预设运营/运营指标。

供应商抽样：

- **预审** dashscope `qwen3-vl-plus` → HTTP 200（真实调用）
- **生图** aoju `gpt-image-2` → HTTP 200，结果入库 `asset 4`（`text_to_image`，1536×1024，2,585,364 B）
- **最终检测** Gemini → **被地区策略拒绝**：`User location is not supported for the API use.`

详见 `REALPHOTOS-S7-PROD-DEPLOY-E2E-2026-11-16-blocker.md`。

## §11 上线门槛核对

| §11 项 | 结论 |
| --- | --- |
| PRD 真实模型/算法小样与归档证据 | 部分具备：预审/生图有生产实测；**检测无生产证据** |
| 物料生产就绪阻塞项关闭或书面接受残余风险 | T01 已按 B 接受；T02 未闭（检测链路）；T03 决策为正式供应商但**未做基址探测** |
| 部署目标、域名、TLS、回滚与监控 | 部署/TLS/回滚已执行；监控仍为手工规程 |
| 收费开关 | 保持 `production_billing=false` |

→ 门槛未通过，**不得**宣称「检测通过」或「已上线可收费」。

## 本轮修复的阻断缺陷

| ID | 类型 | 内容 | 验证 |
| --- | --- | --- | --- |
| D1 | 前端构建 P0 | `rp-table.tsx` 未使用的 `TdHTMLAttributes` 触发 eslint `no-unused-vars`，`next build` 失败 | 修复后 build 通过 |
| D2 | 前端构建 P0 | `(app)/schedule/page.tsx` 在条件 return 之后调用 hooks，`react-hooks/rules-of-hooks` | 修复后 build 通过 |
| D3 | 基础设施 P0 | 生产机缺 `exiftool` → 任务 `EXIF_WRITE_FAILED` | 安装 `libimage-exiftool-perl` 12.76 后任务推进至检测阶段 |
| D4 | 运行时兼容 P0 | 未钉版本的 SQLAlchemy 2.1 把 `postgresql://` 默认 DBAPI 换成 psycopg3，迁移报 `No module named 'psycopg'` / `AmbiguousParameter` | 按 `pyproject.toml` 契约钉 `>=2.0.36,<2.1`，迁移通过 |
| D5 | 配置 P0 | 物料 Markdown 解析把服务器口令块误当 Gemini Key（`GEMINI_API_KEY=root`） | 修正解析；Key 在允许出口实测 200 |

## 回滚与续作

```sh
# 回滚公网到占位站（本次已执行）
sh /root/蜜獾原图-v2/shared/08_rollback.sh
# 出口问题解决后切回应用
sh /root/蜜獾原图-v2/shared/06_nginx.sh
```

五个 systemd 单元保持 `enabled` 且 `active`；`current` 仍指向 `releases/3ed1088`。

## 残余风险

| ID | 风险 | 处置 |
| --- | --- | --- |
| R1 | 生产库与应用同机单点（T01-B） | 管理员已接受；建议后续独立备份 + 恢复演练 |
| R2 | 无 Swap、磁盘 23% 已用 | 已登记；建议加磁盘/内存告警 |
| R3 | 真供应商出口地域差异 | **已实证阻塞**（Gemini 地区拒绝），见 blocker |
| R4 | 外部导入未探测 | T03 定为正式供应商，但本次未做基址连通探测 |
| R5 | 监控/备份仅手工规程 | 未建自动告警 |
| R6 | 验收账号使用种子默认口令 | 仅演示租户；上线前须改强口令 |

## CI

本地执行：`scripts/ci/secret_scan.sh`、`ruff check`（realphotos）、`pytest`（realphotos 相关）、前端 `tsc --noEmit`。结果见 PR 描述。

`production_billing=false` · `REALPHOTOS_S7_PROD_E2E_PASS: NOT ACHIEVED`
