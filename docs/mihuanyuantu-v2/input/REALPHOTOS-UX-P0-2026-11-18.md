# 蜜獾原图 v2 · UX P0 迭代 1 验收记录（2026-11-18）

- 需求来源：`C:\Users\Administrator\Desktop\蜜獾原图文件\蜜獾原图-UX优化建议-2026-11-17.md`（桌面文档，不入库）
- 范围：P0-1 ～ P0-5（P1/P2 留待管理员确认后进入下一轮）
- 代码：PR #70（squash `5abdffe`）+ PR #71（`b72f8dc`，链式流水补任务号）+ PR #72（`3f2e1fb`，本记录）
- 生产：`https://exif-demo.honeybadgersoft.com` / `/root/蜜獾原图-v2/releases`（`current` 已指向 `3f2e1fb`；运行时后端代码为 `b72f8dc`）
- 前端 BUILD_ID：`jt29D1SjD50Z04iLb2iw1`（PR #71 仅后端，前端构建沿用）
- 口径：`production_billing=false`；本轮不改变计费政策，只改展示与操作反馈

## 1. 落地内容

| 项 | 实现 | 关键落点 |
| --- | --- | --- |
| P0-1 设备预设死页 | 非管理员不再显示「设备预设」菜单；直接访问时改为只读「平台提供」页，展示类型/品牌/型号/ISO/快门/光圈/焦距/GPS，不出现裸权限串，无新增/编辑/启停/版本按钮 | `useMenuRoutes.ts`、`realphotos/presets/page.tsx` |
| P0-2 业务 API 凭证 | 新增凭证列表（名称/前缀/创建/最近调用/状态）、重新生成、吊销；明文只在创建或重新生成时显示一次并可复制；补最小调用示例与 OpenAPI 下载 | `api/s5.py`、`realphotos/api-keys/page.tsx` |
| P0-3 批量原图摘要 | 首屏固定展示 ISO/快门/光圈/焦距/GPS；「开始处理」前弹确认：张数 × 10 积分 = 预计冻结，并列出预设与曝光参数 | `realphotos/batch/batch-client.tsx` |
| P0-4 积分流水对账 | 增加冻结变动、变动后可用/冻结、关联任务（处理 #N / 生图 #N）；链式消费/释放按 chainId 回溯任务号；支持按任务号搜索并导出 CSV | `api/wallet.py`、`services/task_numbering.py`、`realphotos/wallet/page.tsx` |
| P0-5 任务编号 | 处理/生图均使用租户内编号（各租户从 1 开始）；工作台、任务详情统一「处理 #96 / 生图 #11」 | `services/task_numbering.py`、`api/me.py`、`api/s5.py`、workspace/tasks 页面 |

## 2. 自动验证

本地：

- `ruff check app tests/capabilities/realphotos/test_ux_p0.py`：通过
- `pytest tests/capabilities/realphotos/test_ux_p0.py`：3 passed（凭证列表/轮换、流水冻结与链式任务号、租户内处理/生图编号）
- `pnpm typecheck`：通过
- `pnpm test`：16 passed
- `pnpm build`：通过

CI（PR #70 / #71）：A secrets、B backend（ruff + pytest）、C frontend、`CI gate` 全绿。

生产走查（API + Playwright DOM，27 项全 PASS）：

```text
PASS merchant_menu_no_presets | n=11
PASS merchant_device_presets_denied | http=403
PASS merchant_enabled_presets_ok | http=200
PASS admin_device_presets_ok | http=200
PASS business_keys_list_http | http=200
PASS business_key_create_http | http=200
PASS business_key_plaintext_once | id=5
PASS business_key_appears_in_list | names=['UX-P0-VERIFY']
PASS business_key_rotate_http | http=200
PASS business_key_revoke_http | http=200
PASS ledger_http_rows | http=200 rows=20
PASS ledger_reserved_delta | consume=13
PASS ledger_balance_after
PASS ledger_task_number | sample=[('processing', 89), ('processing', 89), ('processing', 88), ('processing', 88)]
PASS workspace_history_task_no | n=10
PASS generation_task_no | http=200 n=7
PASS ui_workspace_no_presets_menu
PASS ui_workspace_prefix
PASS ui_presets_readonly_copy
PASS ui_presets_no_raw_permission
PASS ui_presets_exposure_headers
PASS ui_presets_no_create_button
PASS ui_wallet_headers
PASS ui_api_keys_management
PASS ui_api_keys_no_raw_name_search
PASS ui_batch_exposure_summary
PASS ui_admin_presets_editable
```

截图（本机临时，不入库）：`%TEMP%\mhyt-ops\ux-p0\`
`merchant-workspace.png`、`merchant-presets-readonly.png`、`merchant-wallet.png`、`merchant-api-keys.png`、`merchant-batch.png`、`admin-presets.png`。

## 3. 生产状态

- `realphotos-api` / `realphotos-web`：active
- `GET http://127.0.0.1:38000/health`：200
- 公开入口 HTTPS：登录页与商家/管理员页面均正常
- 未新增/修改数据库迁移；未触碰生产密钥；测试用业务 Key 已在验收结束时吊销

## 4. 回滚

- 代码回滚点：`5c20940`（部署前生产 HEAD）
- 前端需从回滚点重新 `pnpm build` 后重启 `realphotos-web`；后端重启 `realphotos-api`
- 本轮无 DB 变更，不需要数据回滚

## 5. 未做 / 下一轮

- P1 七项与 P2 六项未在本轮实施，待管理员确认后进入迭代 2。
- P0-4 的「按时间范围导出」目前以任务号搜索 + 全量 CSV 导出覆盖；时间区间筛选留待下一轮与列表统一排序一起做。
