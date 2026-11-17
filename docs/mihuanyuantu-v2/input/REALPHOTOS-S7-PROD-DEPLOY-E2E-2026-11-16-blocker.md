# S7 生产部署 · 阻塞说明（Gemini 出口地区限制）

> **状态更新（2026-11-16 23:55）：已解除。** 管理员提供的代理订阅（vmess 节点，美国出口）已在生产机以 Xray 落地为 `gemini-egress-proxy.service`（本地 `127.0.0.1:7890`）；`09_proxy.sh apply` 注入后 Gemini `generateContent` 返回 200，task 4 取得真实报告 `gemini-3.1-pro-preview total_score=52 passed=false`，交付物 12,370,703 B 可下载，积分按 PRD 释放。`REALPHOTOS_S7_PROD_E2E_PASS` 已达成。**遗留**：该节点为第三方订阅（名称含到期日 2026-12-06），须在此前替换为自有 SG/JP 代理（见 closeout R7）。下文保留原始诊断与排除过程，供复盘。

工单：`REALPHOTOS-S7-PROD-DEPLOY-E2E-2026-11-16`  
日期：2026-11-16  
状态：**`T5_SUPPLIER_DETECTION_BLOCKED` / `REALPHOTOS_S7_PROD_E2E_FAIL`（failing_item=T5-SUP-FINAL_DETECTION）**

## 1. 结论（测试事实）

生产机 `47.242.28.49`（阿里云香港出口）对 **Google Gemini 原生 API** 的 `generateContent` 返回：

```
HTTP 400
{"error":{"code":400,"message":"User location is not supported for the API use.","status":"FAILED_PRECONDITION"}}
```

同一 Key、同一请求体，在**非受限出口**上返回 200（已复测），说明：

- **不是密钥失效**（Key 本身有效）；
- **不是代码缺陷**（同一 `detect_jpeg` 路径在允许地区可用）；
- **不是网络不可达**（`generativelanguage.googleapis.com` 可解析、可建连，`models` 列表可返回）；
- 是**服务端地区策略**：Gemini 对香港/中国大陆出口拒绝推理请求。

`models` 列表接口不校验地区，所以「连通性正常」不能证明「推理可用」。

## 2. 影响面

| 项 | 影响 |
| --- | --- |
| 最终检测（FR-018 / S3） | 全部图片处理任务在检测阶段失败 `GEMINI_TECHNICAL`，无检测报告、无交付图 |
| 自动重做 | 依赖检测结果，同样不可用 |
| 预审（dashscope） | **正常**（HTTP 200 已实测） |
| 生图（aoju gpt-image-2） | **正常**（已入库 asset 4，1536×1024） |
| 五层处理 + EXIF 写入 | **正常**（安装 exiftool 后任务推进到检测阶段才失败） |
| 四角色主路径与权限矩阵 | **正常**（生产 HTTPS 端测 fail_count=0） |
| 收费 | 保持 `production_billing=false`，未开放 |

## 3. 可选处置（需管理员决策，均为产品/合同级选择）

| 选项 | 做法 | 代价 / 风险 | 是否改 PRD |
| --- | --- | --- | --- |
| A 出站代理 | 为应用进程配置允许地区（新加坡/日本/美国）的 HTTPS 正向代理，`HTTPS_PROXY` 注入 systemd | 需采购或自建代理；需验证稳定时延；代理成为新单点 | 否 |
| B 迁移节点 | 应用迁到 Gemini 允许地区的云主机（如新加坡） | 迁移 + 重新 TLS/域名解析；大陆访问时延上升 | 否 |
| C 换检测供应商 | 最终检测改为可出口地区的合规中转或国内视觉模型 | 需供应商合同与接口证据；与「Gemini 为生产检测器」的现行合同冲突 | **是** |
| D 暂缓上线 | 保持占位页，等 A/B 落地 | 已部署能力闲置 | 否 |

> 本会话**不自行选择**以上任一项：A/B 涉及采购与网络变更，C 改 PRD 合同，均超出工单授权。

## 3.1 管理员已选定 A（2026-11-16）

管理员选择 **A 出站 HTTPS 代理**。应用侧已就绪：

- `/root/蜜獾原图-v2/shared/09_proxy.sh apply <proxy-url>`：为 `realphotos-api/process/notify/cleanup` 写入 systemd drop-in（`HTTPS_PROXY`/`NO_PROXY`），`NO_PROXY` 保留 dashscope、aoju、deepseek、本地库与内网直连，代理只承载 Gemini 流量；`revert` 一键撤除。
- 脚本已上传并通过 `sh -n` 语法检查，当前**未 apply**（尚无可用代理端点）。

**待办（管理员）**：提供一个允许地区（新加坡/日本/美国）的 HTTP 正向代理地址，例如 SG 小机型上的 `tinyproxy`/`squid`，仅放行 `generativelanguage.googleapis.com:443`。拿到地址后执行：

```sh
sh /root/蜜獾原图-v2/shared/09_proxy.sh apply http://<proxy-host>:<port>
sh /root/蜜獾原图-v2/shared/06_nginx.sh          # 切回应用
# 复跑检测抽样（商家提交一张 → 轮询到 DELIVERED 且 detector=gemini-*）
```

验证说明：本会话曾尝试用工作站反向隧道做就地验证，但工作站 WLAN 出口到 Google 443 时通时断，不能作为生产代理的可信证据，故未据此宣称检测可用。

### 3.2 已排除的绕行方案（2026-11-16 实测）

| 尝试 | 结果 | 结论 |
| --- | --- | --- |
| 生产机 IPv4 直连 `generativelanguage.googleapis.com` | `400 FAILED_PRECONDITION User location is not supported` | 地区策略拒绝 |
| 生产机 IPv6（AAAA `2001:4860:...`） | `curl -6` 无路由（`000`） | 该主机无 v6 出口 |
| 区域主机 `us-central1-` / `asia-southeast1-generativelanguage.googleapis.com` | `404`（非有效 API 主机） | 不存在按区域绕过的端点 |
| `models` 列表接口 | `200` | 连通性≠推理可用，不能作为证据 |
| aoju 中转原生 Gemini 路径 | `403 该令牌无权访问模型 gemini-3.1-pro-preview` | 该中转不承载 Gemini |

→ 在**不改检测供应商**（不改 PRD）的前提下，允许地区出站代理是唯一可行路径。

### 3.3 代理搭建配方（管理员侧，约 10 分钟）

在允许地区（新加坡/日本/美国）一台最小 VM 上：

```sh
apt-get install -y tinyproxy
cat >/etc/tinyproxy/tinyproxy.conf <<'EOF'
Port 8888
Listen 0.0.0.0
Allow 47.242.28.49          # 生产机出口 IP
ConnectPort 443
Filter "/etc/tinyproxy/filter"
FilterURLs On
FilterDefaultDeny Yes
EOF
echo '^generativelanguage\.googleapis\.com$' >/etc/tinyproxy/filter
systemctl enable --now tinyproxy
```

生产机侧（已内置于 `09_proxy.sh`，`NO_PROXY` 保留 dashscope / aoju / deepseek 直连）：

```sh
sh /root/蜜獾原图-v2/shared/09_proxy.sh apply http://<vm-ip>:8888
curl -s -o /dev/null -w '%{http_code}\n' -x http://<vm-ip>:8888 https://generativelanguage.googleapis.com/   # 期望 404（可达即可）
sh /root/蜜獾原图-v2/shared/06_nginx.sh
```

> 安全建议：代理只放行上述单域名、只允许生产机 IP、不开放匿名访问；上线前把该代理写入物料清单并登记为新的单点。

### 3.4 apply / revert 已在生产机空跑验证（2026-11-16）

用本地哑端口（`127.0.0.1:18999`，非真实代理）走了一遍真实运维路径，只验证管道、不验证出口：

| 步骤 | 结果 |
| --- | --- |
| `09_proxy.sh apply http://127.0.0.1:18999` | `realphotos-api/process/notify/cleanup` 全部 active；drop-in 生效 |
| `systemctl show realphotos-process -p Environment` | 注入 `HTTPS_PROXY`/`HTTP_PROXY`/`https_proxy`/`http_proxy` + `NO_PROXY`（dashscope、aoju、deepseek、`47.85.47.252`、内网直连） |
| `systemctl show realphotos-api -p Environment` | 同一组 6 项，API 进程同样感知 |
| `09_proxy.sh revert` | 环境变量归零（计数 0），五单元仍 active |

→ 真实代理地址一到，`apply` 即可生效，无需再改代码或单元文件。

### 3.5 无云主机时的替代：Cloudflare Worker 出口（代码已备好）

如果没有可用的 SG/JP 小机器，可用免费 Worker 承担同一职责，且**不需要改应用代码**：

- 代码：`scripts/ops/gemini-egress-worker.js`（只放行 `POST /v1beta/models/<model>:generateContent`；用 Gemini Key 的 SHA-256 白名单校验调用方；不转发任意 URL）。
- 部署：`wrangler secret put ALLOWED_KEY_SHA256`（填 Key 的 sha256 十六进制）→ `wrangler deploy`。
- 接线二选一：
  1. 管理端「模型 API」把 `final_detection` 合同 `base_url` 改成 `https://<worker>.workers.dev/v1beta`（无需重启）；或
  2. `.env` 设 `GEMINI_API_BASE=https://<worker>.workers.dev/v1beta` 并重启 API/worker。
- 验证：商家提交一张 → 轮询到 `DELIVERED` 且 `detector` 为 `gemini-*`。

> 需要管理员的 Cloudflare 账号授权（API Token，或由管理员执行 `wrangler deploy`）。Worker 出口地区由 Cloudflare 决定，必须先实测一次 `generateContent` 通过再切流。

### 3.6 为什么本会话不能"凭空"搭出一个可用代理

| 前提 | 现状 |
| --- | --- |
| 一台允许地区、有公网入口的主机 | 无（无云账号/采购权限；旧测试机 `47.239.81.27` 从生产机与本机两侧均不可达） |
| 把本机当出口 | 工作站无公网 IP，只能靠 SSH 反向隧道；且其 Clash Verge 为 `mode: direct`（无上游节点），本机自身也没有可用境外出口 |
| 免费隧道（ngrok/cloudflared 等） | 出口仍是本机网络，且会把代理暴露到公网，不宜承载模型 Key |
| 生产可用性 | 把付费产品的检测挂在个人工作站 + 个人机场订阅上不可接受 |

→ 代理**可以搭**，但必须落在**允许地区、独立于个人工作站**的载体上：云主机 / Cloudflare Worker / 管理员指定主机。

### 3.7 状态更新（2026-11-16 23:53 起已解除）

本阻塞已在后续会话中按 **Xray + 管理员提供的 vmess 节点** 变体解除：

- 生产机新增 `gemini-egress-proxy.service`（Xray 26.11.9 → vmess 节点，本地 `127.0.0.1:7890`），`09_proxy.sh` 把该本地代理注入四个应用单元；
- 检测真外呼恢复，`REALPHOTOS_S7_PROD_E2E_PASS` 已达成（task 4：`gemini-3.1-pro-preview` 52 分；2026-11-17 切 `gemini-2.5-flash` 后 task 5：60 分）；
- 公网入口已切到应用，不再回滚占位。

**遗留风险 R7**：该 vmess 节点来自第三方订阅，节点名标注到期 **2026-12-06**；到期前须替换为自有载体。替换时本文件 §3.3（tinyproxy）与 §3.5（Cloudflare Worker，代码已入库 `scripts/ops/gemini-egress-worker.js`）**仍然适用**，接线方式同为「`09_proxy.sh apply <local-proxy>`」或「改 `final_detection` 合同 `base_url`」。

> §3.6 的结论只针对"用个人工作站充当出口"这一种做法，不否定上述两条替换路径。

## 4. 已就绪、可随时续作

- 应用已部署并在 `current` 指向 `3ed1088`，五个 systemd 单元 enabled（当前 active，公网入口已回滚占位）。
- 生产库 `realphotos_prod` 可用，迁移到 head，六个 `rp_*` 验收账号已建。
- LocalDisk 三目录就绪，网关读通；duty secrets 四岗 `present=true`（0600）。
- 一旦出口问题解决，仅需：把 `final_detection` 的可达基址/代理注入 → `systemctl restart realphotos-api realphotos-process` → `sh /root/蜜獾原图-v2/shared/06_nginx.sh` 切回应用 → 复跑检测抽样。

## 5. 明确未做

- 未改 `PASS_SCORE`，未改检测供应商，未开放收费口径。
- 未宣称「检测通过」或「已上线可收费」。
- 未清空任何生产业务数据；三条失败任务的 10 积分仍为 `held_until_tech_support` 冻结，未擅自释放。
