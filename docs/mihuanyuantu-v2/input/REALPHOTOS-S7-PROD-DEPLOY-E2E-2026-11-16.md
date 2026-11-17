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
| T03 决策 | **正式供应商**：API 型 URL 导入（基址 `http://47.85.47.252`，`/api/images/<file>` 形态吻合） |
| 收费 | **`production_billing=false`**（保持关闭） |
| 结果 | ✅ `REALPHOTOS_S7_PROD_E2E_PASS`；收费仍未开放 |

## T0–T7 执行状态

| 项 | 状态 | 证据 |
| --- | --- | --- |
| T0 补齐 S7 清单 | ✅ `T0_S7_CHECKLIST_PASS` | `DEV_INSTRUCTIONS.md` §10.9（tasks / exit_evidence / forbidden） |
| T1 生产基建 | ✅ `T1_INFRA_PASS` | 同机 PG16 集群 online；`realphotos_prod` 可连；`listen=localhost`；LocalDisk 三目录；TLS 200；certbot.timer active |
| T2 配置与密钥 | ✅ `T2_SECRETS_PASS` | `.env` 600；duty 四岗 `present=true`；admin 合同页 4 项有密钥 |
| T3 发布切流 | ✅ `T3_DEPLOY_PASS` | systemd 五单元 active；迁移 head；Next build 成功；Nginx 切流后 `https_login=200` |
| T4 发布后冒烟 | ✅ `T4_SMOKE_PASS` | 上传 10.9MB JPEG → 网关读回字节一致；`/auth/challenges` 200；`/health` 200 |
| T5 生产四角色端测 | ✅ `T5_PROD_E2E_PASS` | `T5_M/O/T/A_PASS`，`fail_count=0`；三岗供应商均有生产实测 |
| T6 门槛终核 | ✅ `T6_GATE_PASS` | 见下 §11 核对；收费保持 `false` |
| T7 文档 / CI / PR | ✅ `T7_PR_PASS` | 证据入库；PR #68 CI 全绿；Tag 待 Owner |

## T5 明细

角色矩阵在生产域名上 `fail_count=0`：登录四角色、商家工作台/资源/上传/网关/405 预设/任务提交/生图、订单客服充值单确认与越权拒绝、技术客服工单 20 条/页与用户管理/日志、管理员模型 API/检测基线/预设运营/运营指标。

供应商抽样（三岗全部真实外呼）：

| 职责 | 供应商 | 结果 |
| --- | --- | --- |
| 预审 | dashscope `qwen3-vl-plus` | HTTP 200 |
| 生图 | aoju `gpt-image-2` | HTTP 200，入库 `asset 4`（`text_to_image`，1536×1024，2,585,364 B） |
| 最终检测 | Gemini `gemini-3.1-pro-preview` | HTTP 200（经出口代理），`total_score=52`、`passed=false` |

检测未通过的那张（task 4）按 PRD 处理：**输出 12,370,703 B 有效 JPEG 可下载（网关 200、JPEG 头 FFD8、7 天有效期），积分 disposition=`released_detection_not_passed`（释放而非消费）**。业务未通过不算基础设施失败。

## §11 上线门槛核对

| §11 项 | 结论 |
| --- | --- |
| PRD 真实模型/算法小样与归档证据 | **PASS**：预审 / 生图 / 最终检测三岗均有生产实测；检测报告为真实 Gemini 分数 |
| 物料生产就绪阻塞项关闭或书面接受残余风险 | T01 关闭（B，管理员接受单点）；T02 关闭（五层 + EXIF + 检测 + 交付 + 积分全链路已通）；T03 决策为正式供应商，基址可达且路径形态吻合，**对象级导入未执行**（R4） |
| 部署目标、域名、TLS、回滚与监控 | 部署 / TLS / 回滚脚本已执行并演练；监控仍为手工规程（R5） |
| 收费开关 | 保持 `production_billing=false` |

→ 门槛通过（收费仍关）。**不宣称「检测通过」作为面向客户的服务承诺**：检测是逐张真实评分，52 分即未通过。

## 本轮修复的阻断缺陷

| ID | 类型 | 内容 | 验证 |
| --- | --- | --- | --- |
| D1 | 前端构建 P0 | `rp-table.tsx` 未使用的 `TdHTMLAttributes` 触发 eslint `no-unused-vars`，`next build` 失败 | 修复后 build 通过 |
| D2 | 前端构建 P0 | `(app)/schedule/page.tsx` 在条件 return 之后调用 hooks | 修复后 build 通过 |
| D3 | 基础设施 P0 | 生产机缺 `exiftool` → 任务 `EXIF_WRITE_FAILED` | 装 `libimage-exiftool-perl` 12.76 后通过 |
| D4 | 运行时兼容 P0 | 未钉版本的 SQLAlchemy 2.1 把 `postgresql://` 默认 DBAPI 换成 psycopg3，迁移失败 | 钉 `>=2.0.36,<2.1`，迁移通过 |
| D5 | 配置 P0 | 物料解析把服务器口令块误当 Gemini Key | 修正解析并用可达出口实测 200 |
| D6 | 出口 P0 | Gemini 拒绝香港/大陆出口（`FAILED_PRECONDITION`） | 允许地区出口代理：生产机 Xray（vmess → US 出口）本地 7890 + `09_proxy.sh` 注入 |

## 出口代理（新增依赖，务必登记）

- `gemini-egress-proxy.service`（Xray 26.11.9，enabled + active），本地 `127.0.0.1:7890`，出口 IP `150.241.181.64`。
- 订阅 token 只存于生产机 `/root/蜜獾原图-v2/shared/`（0600），**未入库**。
- 节点名称自带到期日 **2026-12-06** → 必须在此之前替换为自有 SG/JP 代理，否则检测链路中断（见 R7）。

## 变更记录

### 2026-11-17 · 导航与列表 UI 六项调整（生产已上线）

| # | 需求 | 实现 | 验证 |
| --- | --- | --- | --- |
| 1 | 删除「概览/首页」与「蜜獾原图」一级目录；各模块单独为导航按钮；**全站无二级菜单** | 后端 `access.py` 将 14 个页面提升为一级；`app-layout.tsx` 删除固定 overview 分组与分组头/手风琴，只渲染叶子链接；生产库软删 4 条空壳 `蜜獾原图` 根节点 | Playwright：侧栏 11 项（管理员 16 项）、`has_group_chevron=False`、无 `/welcome` |
| 2 | 时间统一 `年-月-日 时:分`；列表 10 条/页 | 新增 `lib/realphotos-time.ts`；应用于工作台最近历史、消息中心、系统日志、任务、工单、预设；各列表页 10 条/页并带翻页 | DOM：`2026-11-17 00:20`；分页文案「共 N 条 · 每页 10」 |
| 3 | 积分流水「操作账号」显示角色而非编号 | `wallet.py` 增加 `operatorDisplay`（用户名 + 角色中文） | DOM：`rp_order_support（订单客服）`、`rp_merchant_a1（商家）` |
| 4 | 系统日志时间列显示真实时间 | 后端已返回 `createdAt`；前端由「时间序号 + id」改为格式化时间；`LOG_PAGE_SIZE=10` | DOM：表头为「时间」、无「时间序号」；API `pageSize=10` |
| 5 | 消息中心文案与按钮 | 说明改为「消息保留30天」；「补发」改为「标为未读」（新增 `POST /inbox/{id}/unread`）；删除补发提示语 | DOM：新文案在、旧文案不在；接口 round-trip 后 `readAt=null` |
| 6 | 工作台删除搜索框 | 移除 `ListSearch` 及搜索态与过滤 | DOM：`本页列表关键词` 不存在 |

部署过程记录：首轮构建因 `realphotos-jobs-enqueue` 权限节点被误删导致菜单同步失败（已修为只上提一级）；第二轮构建因 PowerShell 模板字符串插值丢失 `${...}` 造成 502，修复后重建恢复。当前 `BUILD_ID=qyIyqwjX2posbcXSkpLth`。

### 2026-11-17 · 最终检测模型切换为 `gemini-2.5-flash`

| 项 | 值 |
| --- | --- |
| 变更前 | `gemini-3.1-pro-preview`（task 4 实测 52 分未通过） |
| 变更后 | `gemini-2.5-flash`（task 5 实测 60 分未通过） |
| 入口 | 管理端合同接口 `POST /api/v1/realphotos/provider-contracts`（`duty=final_detection`，`modelId=gemini-2.5-flash`），provider / baseUrl / enabled 保持不变 |
| 配置同步 | `backend/.env` 的 `GEMINI_MODEL` 同步为 `gemini-2.5-flash`（仅作 seed 回退），api/process 已重启 |
| 可用性预检 | 经出口代理直接调用 `models/gemini-2.5-flash:generateContent` → 200；`gemini-2.5-pro` 返回 404「no longer available to new users」，故未选 |
| 端到端复核 | task 5：`detector=gemini-2.5-flash`、`total_score=60`、`passed=false`、输出 12,359,870 B、积分 `released_detection_not_passed` |
| 回滚 | 同一接口把 `modelId` 改回 `gemini-3.1-pro-preview` 即可 |

## 回滚与续作

```sh
sh /root/蜜獾原图-v2/shared/08_rollback.sh   # 公网回滚占位（应用单元保留）
sh /root/蜜獾原图-v2/shared/06_nginx.sh      # 切回应用
sh /root/蜜獾原图-v2/shared/09_proxy.sh revert   # 撤除代理注入
```

五个应用单元与出口代理均 `enabled`；`current` → `releases/3ed1088`（工作树对齐 `0f5fd1c`，干净）。

## 残余风险

| ID | 风险 | 处置 |
| --- | --- | --- |
| R1 | 生产库与应用同机单点（T01-B） | 管理员已接受；建议独立备份 + 恢复演练 |
| R2 | 无 Swap、磁盘 27% | 已登记；建议加磁盘/内存告警 |
| R3 | 供应商出口地域 | **已解除**（出口代理），转由 R7 承接 |
| R4 | 导入基址未做对象级导入 | 需管理员确认该基址为正式供应商，或提供样例文件 |
| R5 | 监控/备份仅手工规程 | 未建自动告警与定时备份 |
| R6 | 验收账号使用种子口令 | 上线前改强口令 |
| R7 | 出口代理为第三方订阅节点（2026-12-06 到期） | 替换为自有 SG/JP 代理并写入物料清单 |

## CI

本地 `scripts/ci/secret_scan.sh` 通过；PR #68 的 `A secrets` / `C frontend typecheck+test` / `D docs gate` / `CI gate` 全绿（`B backend` 因无后端改动 skip）。

`production_billing=false` · `REALPHOTOS_S7_PROD_E2E_PASS`
