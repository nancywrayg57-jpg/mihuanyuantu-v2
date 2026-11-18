# 蜜獾原图 v2 · UX P1 迭代 2 验收记录（2026-11-18）

- 需求来源：`C:\Users\Administrator\Desktop\蜜獾原图文件\蜜獾原图-UX优化建议-2026-11-17.md`（桌面文档，不入库）
- 范围：P1-1 ～ P1-7（P2 留待管理员确认）
- 代码：PR #74（squash `b93f295`）+ PR #75（`60a8038`，消息资源清理回退）
- 生产：`https://exif-demo.honeybadgersoft.com`，`current` 已指向 `60a8038`
- 前端 BUILD_ID：`2EG6HqaZ9p6c0dqtZkk3Q`
- 口径：`production_billing=false`；无数据库迁移

## 1. 落地内容

| 项 | 实现 | 关键落点 |
| --- | --- | --- |
| P1-1 图片资源 | 全站统一 10 条/页；资源列表新增最近/最早/最大/最小排序与「最近上传」快捷键；缩略图 56px 且悬停放大；长文件名中段省略 + hover 全名；表格横向滚动容器 | `library/page.tsx`、`s5.py`、`s5_growth.py` |
| P1-2 任务详情 | 「复制（免冻）」→「复制参数（不扣分）」并加 tooltip；技术重试仅技术客服/管理员可见；移除页内消息入口，保留顶栏铃铛 | `tasks/page.tsx` |
| P1-3 工单管理 | 10 条/页；新增创建时间/等待时长列与等待最久优先排序；已办结按钮改「查看」；`openTotal` 全量待处理数 + 刷新按钮 + 30 秒自动刷新 | `tech-desk/page.tsx`、`s6.py`、`s6_ops.py` |
| P1-4 用户管理 | 租户列表补状态/创建时间/最近活跃/负责人；租户名可点开详情（账号/任务/余额汇总）；删除收进「更多」 | `users/page.tsx`、`s6.py`、`s6_ops.py` |
| P1-5 消息中心 | 消息带任务号 + 图片名，任务号可点击直达详情；处理任务/充值/系统标签页 + 7/30 天筛选；同批同文案合并为「本批 N 张」；整组已读/未读；保留期说明移到页脚 | `messages/page.tsx`、`s1.py` |
| P1-6 生图页 | 新增「最近生成」（缩略图/任务号/尺寸/时间/去处理），生成成功后自动刷新 | `generate-client.tsx`、`s5.py` |
| P1-7 工作台 | 最近历史补缩略图、预设名、失败原因；整行可点击进详情；失败任务给「重处理」、锁定任务给「申诉」；「保留 30 天」移出卡片 | `workspace/page.tsx`、`me.py` |

配套：任务详情页支持 `?taskId=` 深链，消息中心与工作台可直接打开任务详情。

## 2. 验证

本地：

- `ruff check app tests/capabilities/realphotos/test_ux_p1.py`：通过
- `pytest test_ux_p0.py test_ux_p1.py test_s5_growth.py test_s6_ops.py`：25 passed
- `pnpm typecheck`：通过
- `pnpm test`：16 passed
- `pnpm build`：通过

CI（PR #74 / #75）：A secrets、B backend、C frontend、`CI gate` 全绿。

生产走查（API + Playwright DOM，30 项全 PASS）：

```text
PASS api_assets_sorted_largest | n=10
PASS api_tickets_page_and_open_total | pageSize=10
PASS api_tickets_created_at
PASS api_tenants_enriched | n=6
PASS api_tenant_detail | tenant=1
PASS api_inbox_kind_and_task_no | n=90 tasks=89
PASS api_inbox_asset_name
PASS api_workspace_history_enriched | n=10
PASS ui_library_sort_and_recent
PASS ui_library_56_thumb
PASS ui_library_filename_title
PASS ui_tasks_copy_label
PASS ui_tasks_no_message_entry
PASS ui_tasks_merchant_no_tech_retry
PASS ui_messages_tabs
PASS ui_messages_range
PASS ui_messages_footer
PASS ui_messages_task_link
PASS ui_generate_recent
PASS ui_workspace_columns
PASS ui_workspace_retention_moved
PASS ui_workspace_thumbs
PASS ui_tickets_time_columns
PASS ui_tickets_refresh
PASS ui_tickets_sort
PASS ui_users_columns
PASS ui_users_tenant_link
PASS ui_users_tenant_detail
PASS ui_tasks_admin_tech_retry
```

截图（本机临时，不入库）：`%TEMP%\mhyt-ops\ux-p1\`
`library.png`、`tasks-merchant.png`、`tasks-admin.png`、`messages.png`、`generate-recent.png`、`workspace.png`、`tech-desk.png`、`users-detail.png`。

## 3. 生产状态

- `realphotos-api` / `realphotos-web`：active
- `/health`：200；公开 HTTPS 登录页：200
- 无数据库迁移；未触碰生产密钥
- 历史消息中 1 条源图已被清理，已回退显示「资源 #id（已清理）」，不影响任务定位

## 4. 回滚

- 代码回滚点：`8521879`（P1 部署前 main）
- 前端需从回滚点重新 `pnpm build` 后重启 `realphotos-web`；后端重启 `realphotos-api`
- 本轮无 DB 变更，不需要数据回滚

## 5. 未做 / 下一轮

- P2 六项（移动端表格、空态文案、模型合同表、弹窗可访问性、加载反馈、帮助入口）未实施，待管理员确认。

## 6. 追加修正（2026-11-18 任务操作按钮）

管理员询问「复制参数（不扣分）」是否与「主动重处理」相同。核对代码后确认**不相同**，因此保留复制能力，并按事实修正文案：

| 能力 | 适用对象 | 预审 | 冻结 | 计费 | 代码 |
| --- | --- | --- | --- | --- | --- |
| 按原参数复制（原「复制参数（不扣分）」） | 任意处理任务 | 跳过实时预审（`pre_review_mode=pass`） | 不冻结 | 成功交付后从可用余额扣 10 积分/张；失败不扣 | `copy_processing_task` / `billing_mode=copy_no_reserve` |
| 重新处理（原「主动重处理」） | 仅真实检测未通过且有结果文件的任务 | 走正常提交流程 | 正常冻结 10 积分 | 按正常任务结算 | `reprocess` / `policy.origin=reprocess` |

结论：两者在适用条件、预审、冻结与计费路径上不同；复制是 FR-013 / ND-025 的既有能力，不能按「重复功能」直接删除。本轮将按钮改为「按原参数复制」，tooltip 与成功提示明确「免预审、免冻结；成功交付后扣 10 积分/张」；「主动重处理」统一改名为「重新处理」（任务详情与工作台）。

- 代码：PR #77（squash `8d4b583`）
- 生产：main `8d4b583`，前端 BUILD_ID `d3vjlWd4J14M-wLf081d5`
- 生产 DOM 校验：`按原参数复制` 存在、`复制参数（不扣分）` 不存在、`重新处理` 存在、`主动重处理` 不存在、商家侧无「技术重试」（5/5 PASS）

