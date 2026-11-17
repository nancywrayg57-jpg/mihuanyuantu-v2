# 全量端测报告 · 2026-11-17

环境：`https://exif-demo.honeybadgersoft.com`（生产，`47.242.28.49`），发布目录 `c00f707`（前端 `BUILD_ID=3p7JzRLdhiDOyrQSFQA_7`）
测试素材：`C:\Users\Administrator\Desktop\图片`（51 个文件，140.1 MB）

## 0. HTTP 413 定位与修复

**原因**：图片资源「本地上传」把**整批文件放进一个 multipart 请求**；nginx 站点原为 `client_max_body_size 25m`。实测 nginx 错误日志：

```
client intended to send too large body: 40528899 bytes  POST /api/v1/realphotos/assets/batch
client intended to send too large body: 45375578 bytes  POST /api/v1/realphotos/assets/batch
client intended to send too large body: 49061271 bytes  POST /api/v1/realphotos/assets/batch
```

413 由 nginx 直接返回 HTML 错误页，前端无法解析，只能显示 `请求失败（HTTP 413）`。

**修复**
1. 前端改为**每 5 张一批**上传，弱网失败自动重试一次；
2. nginx `client_max_body_size` 提升到 `200m`（原值已备份 `*.bak-20261117`）；
3. 新增 413 专属提示：「上传内容过大：单次请求超过服务器体积限制，请减少张数或压缩图片后重试」。

**验证**：51 张测试图分 10 批上传，**50/50 成功**（`product_*.jpg/png`，最大单张 3.43 MB）。

## 1. 账号与用户管理（rp_admin 执行）

| 用例 | 结果 | 证据 |
| --- | --- | --- |
| 账号注册（公开注册 + 验证码） | PASS | 新建 `e2e_reg_*`，自动建租户 5，角色 `rp_merchant`，可登录 |
| 管理员创建账号 | PASS | 租户 2 下创建 `e2e_um_*` |
| 停用账号 | PASS | 停用后登录返回 401 |
| 启用账号 | PASS | 启用后可正常登录 |
| 修改角色 | PASS | `rp_merchant + rp_order_support` 生效 |
| 重置密码 | PASS | 新密码可登录 |
| 删除账号 | PASS | 删除成功 |

> 测试创建的注册账号与租户已在收尾阶段删除。

## 2. 积分充值（商家下单 + 订单客服确认）

| 用例 | 结果 | 证据 |
| --- | --- | --- |
| 商家提交充值单 | PASS | ¥100 → 1000 积分，order #5 |
| 订单客服确认 | PASS | 状态 confirmed |
| 余额到账 | PASS | 699 → 1699 |

## 3. 四种图片入库

| 方式 | 结果 | 证据 |
| --- | --- | --- |
| 本地上传 | PASS | 50/50 张（分批 5 张） |
| URL 导入（每行一条） | PASS | `imported=1`，asset 123 |
| JSON 数组（粘贴） | PASS | `imported=1`，asset 126（**JSON 条目必须带 `name`**） |
| JSON 文件上传 | PASS | `imported=1`，asset 127 |
| 文生图 | PASS | task 4，`items[0].status=stored`，asset 124，扣 10 积分 |
| 图生图 | PASS | task 5（参考已有资产） |

> 临时导入渠道指向生产机本地静态源 `http://127.0.0.1:18999`，测完已停服并**恢复为停用 + 原 Base URL**。

## 4. 提示词与模板

| 用例 | 结果 | 证据 |
| --- | --- | --- |
| 提示词优化 | PASS | id=2，返回优化文，状态 succeeded |
| 确认优化文 | PASS | confirmed=true |
| 创建 AI 提示词模板 | PASS | id=1，scope=tenant |
| 模板用于生图 | PASS | 文生图请求带 `templateId` 成功 |

## 5. 批量图片处理（≥50 张）

提交 50 条任务（同一预设，素材为 50 张本地上传图），由 process worker 顺序消费。实测结果（15:28 之后创建的任务，含后续重试/重处理共 51 条）：

| 结果 | 数量 | 占比 |
| --- | --- | --- |
| 已交付 DELIVERED | 44 | 86.3% |
| 检测未通过 detection_not_passed | 3 | 5.9% |
| 预审失败 pre_review | 4 | 7.8% |
| **合计** | **51** | 100% |

- 单任务耗时约 1.5–3 分钟（含 5 层处理 + Gemini 检测），50 张总耗时约 70 分钟；
- 全部任务最终进入终态，无残留 `SUBMITTED`。

## 6. 图片申诉（商家 → 技术客服）

| 用例 | 结果 | 证据 |
| --- | --- | --- |
| 商家提交申诉 | PASS | ticket #1，类型 image_appeal |
| 技术客服可见 | PASS | 工单列表可见 |
| 技术客服处理 | PASS | resolve outcome=rejected |

## 7. 积分冻结与解冻

| 用例 | 结果 | 证据 |
| --- | --- | --- |
| 冻结明细可见 | PASS | `/held-credits`：3 笔、合计 30 分 |
| 技术客服释放冻结 | PASS | task 3 → `released_tech_audit` |
| 流水可见 | PASS | `/wallet/ledger` 有条目 |

## 8. 自动重做

| 用例 | 结果 | 证据 |
| --- | --- | --- |
| 技术失败 → 重试 | PASS | task 2（GEMINI_TECHNICAL）重试成功，状态回到 SUBMITTED |
| 检测未通过 → 重处理 | PASS | task 30 → 新任务 76 |
| 非技术失败不允许重试 | PASS | `RETRY_REJECTED`：只有技术失败可沿用原任务重试 |
| 重做设置读写 | PASS | enabled/threshold/extraRounds 修改后已还原为 `false/70/1` |

## 9. 已登记模型 API 编辑（rp_admin）

| 用例 | 结果 | 证据 |
| --- | --- | --- |
| 修改最终检测模型 | PASS | `gemini-2.5-flash` → `gemini-2.5-pro`，configVersion 递增 |
| 全站同步 | PASS | 列表接口、能力接口立即反映新模型 |
| 复原 | PASS | 改回 `gemini-2.5-flash` |

## 10. 业务 API（X-API-Key · image_processing）

| 用例 | 结果 | 证据 |
| --- | --- | --- |
| 创建业务 Key | PASS | `aoju_sk_5e7eed…`，scope=image_processing |
| 调用 `/presets` | PASS | 200 |
| 调用 `/assets` | PASS | 200 |
| 越权访问 `/wallet/ledger`、`/support-tickets`、`/workspace` | PASS | 均 401（scope 拦截） |
| 删除 Key | PASS | revoked=true |

## 11. 收尾：恢复测试前状态

| 项 | 状态 |
| --- | --- |
| 导入渠道 | 停用，Base URL 恢复 `http://47.85.47.252` |
| 最终检测模型 | `gemini-2.5-flash` |
| 生图 / 提示词优化 / 预审 | 未改动 |
| 端测注册账号 + 租户 | 已删除 |
| 端测充值 1000 分 | 已用管理员调整单回滚（原因「E2E 端测充值回滚」） |
| 端测本地静态源 | 已停服 |

## 12. 发现的问题（建议另开单）

1. **JSON 导入必填 `name`**：只给 `url` 会报「缺少 name」，但页面提示未说明，容易误用。
2. **上传耗时受网络影响大**：单张 ~3 MB 时约 6–9 秒/张；51 张需 ~7 分钟（分批后不会失败，但慢）。
3. **任务处理吞吐**：单 worker 顺序处理，50 张约需 60–90 分钟；批量场景建议评估并发度。
4. **（缺陷）自动重做遇到资源缺失会卡死**：对一条技术失败任务执行 `retry` 后，若其 asset 已被清理，worker 认领时报 `NotFoundError: 资源不存在`，日志出现 `task_failed`，但**任务状态仍停留在 SUBMITTED、执行 job 停留在 running**（attempts=0，未被回收），只能人工修数。建议：重试前校验 asset 是否存在；worker 异常路径确保 task → FAILED、job → failed 并提交事务。本次端测已把该测试任务恢复为 FAILED（原 failure_class=GEMINI_TECHNICAL）并终结其 job。
