# S7 生产部署 · 阻塞说明（Gemini 出口地区限制）

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

## 4. 已就绪、可随时续作

- 应用已部署并在 `current` 指向 `3ed1088`，五个 systemd 单元 enabled（当前 active，公网入口已回滚占位）。
- 生产库 `realphotos_prod` 可用，迁移到 head，六个 `rp_*` 验收账号已建。
- LocalDisk 三目录就绪，网关读通；duty secrets 四岗 `present=true`（0600）。
- 一旦出口问题解决，仅需：把 `final_detection` 的可达基址/代理注入 → `systemctl restart realphotos-api realphotos-process` → `sh /root/蜜獾原图-v2/shared/06_nginx.sh` 切回应用 → 复跑检测抽样。

## 5. 明确未做

- 未改 `PASS_SCORE`，未改检测供应商，未开放收费口径。
- 未宣称「检测通过」或「已上线可收费」。
- 未清空任何生产业务数据；三条失败任务的 10 积分仍为 `held_until_tech_support` 冻结，未擅自释放。
