# 蜜獾原图 v2 · UX P2 验收记录（2026-11-18）

- 需求来源：`C:\Users\Administrator\Desktop\蜜獾原图文件\蜜獾原图-UX优化建议-2026-11-17.md`（桌面文档，不入库）
- 范围：P2-1 ～ P2-6
- 代码：PR #79（squash `ca5dcba`）+ PR #80（`9b985f1`，合同表宽度修正）
- 生产：`https://exif-demo.honeybadgersoft.com`，`current` 已指向 `9b985f1`
- 前端 BUILD_ID：`qwEgDCl-fNzI3U75NAlRx`
- 口径：`production_billing=false`；无后端/DB 变更

## 1. 落地内容

| 项 | 实现 | 关键落点 |
| --- | --- | --- |
| P2-1 移动端表格 | 新增 `RpTableScroll`：横向滚动 + 右侧渐变阴影 + 小屏「左右滑动查看完整列」提示，表格最小宽度 720px；图片资源、任务、消息、工单、用户、工作台、流水、生图、合同均已接入 | `rp-table.tsx` + 各列表页 |
| P2-2 空态文案 | 引导式文案 + 主行动按钮：图库去导入、任务去批量原图/去生图、消息去任务、用户/工单/流水/合同给出下一步说明 | 各列表页 |
| P2-3 模型合同表 | 表头中文化（职责/供应商/模型/版本/区域/能力/状态/缺口）；长文本截断 + hover 全名；能力收进「查看能力（N）」弹层；种子不支持/尺寸不保证/不轮询/非正式供应商标签；凭据引用移入弹层，8 列桌面宽度内完整展示 | `provider-contracts/page.tsx` |
| P2-4 弹窗可访问性 | `RpDialog` 支持 Esc、初始焦点、Tab 焦点陷阱、关闭后恢复焦点、`aria-modal`；渠道修改/新建模板/图片申诉/工单处理禁止遮罩误关；工单详情与图片申诉迁移到统一弹窗 | `rp-table.tsx`、`library`、`tech-desk`、`prompts`、`system-client` |
| P2-5 加载反馈 | 主要列表骨架屏；图库上传第 N/M 张、批量下载 N/M 张；任务批量下载 N/M；消息整组标记、工单刷新、生图刷新等按钮进行中禁用；分页按钮加载中禁用 | 各列表页 |
| P2-6 帮助入口 | 顶栏「帮助」菜单：快速上手 / 常见问题 / 联系客服 / 重看新手引导；FAQ 弹窗含三步流程、积分、检测未通过与下载保留期；工作台 `?guide=1` 重放首轮引导，可收起 | `help-menu.tsx`、`app-layout.tsx`、`workspace/page.tsx` |

## 2. 验证

本地：

- `pnpm typecheck`：通过
- `pnpm test`：16 passed
- `pnpm build`（含 eslint）：通过

CI（PR #79 / #80）：A secrets、C frontend、`CI gate` 全绿；B 后端按路径跳过。

生产走查（Playwright，13 项全 PASS）：

```text
PASS help_menu_items
PASS help_faq_dialog
PASS help_dialog_esc
PASS guide_replay
PASS guide_dismiss_button
PASS mobile_library_scroll_hint
PASS mobile_library_table_overflow
PASS mobile_workspace_scroll_hint
PASS contract_headers_zh
PASS contract_limit_tags
PASS contract_cap_button
PASS contract_cap_dialog
PASS contract_dialog_esc
```

截图（本机临时，不入库）：`%TEMP%\mhyt-ops\ux-p2\`
`help-faq.png`、`guide-replay.png`、`mobile-library.png`（390×844）、`mobile-workspace.png`、`provider-contracts.png`。

## 3. 生产状态

- `realphotos-api` / `realphotos-web`：active
- `/health`：200；公开 HTTPS 登录页：200
- 无数据库迁移；未触碰生产密钥

## 4. 回滚

- 代码回滚点：`d66a5d0`（P2 部署前 main）
- 前端从回滚点重新 `pnpm build` 后重启 `realphotos-web`；本轮后端无变更
- 无 DB 变更，不需要数据回滚

## 5. 未做 / 说明

- 用户管理的创建/删除/操作弹窗仍是页面内自定义遮罩，不在 P2-4 点名的任务详情/工单详情/申诉三类内；如需全站弹窗统一，可下一轮迁移。
- 本轮无后端改动，P2 完成后 UX 清单 18 项全部有落地或明确说明。
