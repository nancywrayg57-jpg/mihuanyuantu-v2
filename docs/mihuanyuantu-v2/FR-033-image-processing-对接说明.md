# FR-033 客户业务 API 对接说明（image_processing）

> 本页支持对接联调与验收复跑；**不等于**生产已收费上线。`production_billing=false`；不得据此开 S7。

## 1. 鉴权

| 项 | 约定 |
| --- | --- |
| 请求头 | `X-API-Key: <明文>` |
| Scope 能力名 | 仅允许 `image_processing`（落库为能力名，鉴权映射为路径白名单） |
| 与 Web 会话 | 并列；无浏览器 Cookie/JWT 时仅用 Key |
| 明文 | 仅创建时返回一次；列表只见前缀/掩码 |

### 签发步骤（须 Web 登录）

1. 商家（或管理员代管授权租户）登录 Web。
2. `POST /api/v1/realphotos/business-api-keys`，body：`{"name":"...","scopes":["image_processing"],"expiresInDays":可选}`。
3. 保存返回的 `apiKey`；之后无法再取明文。
4. 吊销：同会话 `DELETE /api/v1/realphotos/business-api-keys/{id}`。

### 签发拒绝（须 400 `SCOPE_REJECTED`）

- 省略 `scopes`
- 空数组 `[]`
- 通配 `*`
- 培训路径前缀（如 `/api/v1/training`）

### 运行时拒绝（典型）

| 情况 | 表现 |
| --- | --- |
| 缺头 / 错 Key | 401 |
| 已吊销 / 过期 | 401 |
| scope 不覆盖该路径（生图、提示词、导入、Key 自管等） | 401/403 |
| 跨租户读他人任务 | 404 |

## 2. 允许路径（白名单）

OpenAPI 工件：`aojuai-main/backend/contracts/realphotos_image_processing.openapi.json`  
导出：`python -m scripts.export_image_processing_openapi`（`--check` 校验与实现一致）

前缀：

- `/api/v1/realphotos/assets`
- `/api/v1/realphotos/presets`
- `/api/v1/realphotos/processing-batches`
- `/api/v1/realphotos/processing-tasks`
- `/api/v1/realphotos/gateway/objects`

## 3. 主路径四步（无会话）

1. **上传供处理**：`POST /api/v1/realphotos/assets`（multipart 文件）
2. **提交处理**：`POST /api/v1/realphotos/processing-batches`（`assetIds`、`presetCode`、`idempotencyKey`；检测可用 `detectionMode=pass` 做路径证明，**不是** Gemini 生产小样）
3. **查询**：`GET /api/v1/realphotos/processing-tasks/{id}` 至终态（如 `DELIVERED`）
4. **下载**：`POST .../selected-downloads`（`pack=files`）+ `GET /api/v1/realphotos/gateway/objects/{objectKey}`；**禁止 ZIP**；不返回裸磁盘路径

Worker 须消费 `process_image` 任务后才有结果。

## 4. 明确不做（本 scope）

- 文生图 / 图生图、提示词优化、URL/JSON 导入
- 客服台、管理台、运营指标
- Key 自管（用 Key 再签发/吊销 Key）
- 客户自建上游模型 Key、外部电商代发、ZIP 交付包

## 5. 验收证据指针

- 端测日志：`/tmp/module-b-contract-e2e.log`（`B1_FR033_CONTRACT_PASS`）
- 规范与实现：`openapi_export_ok` / `openapi_diff=clean`
