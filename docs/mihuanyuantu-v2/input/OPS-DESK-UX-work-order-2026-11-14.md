# OPS-DESK-UX · 工单（2026-11-14）

分支：`cursor/ops-desk-ux-9973`  
基线：`origin/main` @ `2d807e8`（含 REGISTER-FIX #58）  
工作区：`/home/hbs/hbs-projects/mihuanyuantu-v2/.worktrees/ops-desk-ux`  
禁：S7、改五层默认 / PASS_SCORE 合同、清空业务数据、自评自合。

## T1 工单管理（`tech-desk/page.tsx` + 必要 API）

1. 将客服侧两块表单拆成标签页：**账号申诉** / **积分冻结**。
2. **账号申诉**：列表「操作」列按钮「处理」→ **弹窗**办结（原详情面板内办结迁入弹窗）；租户/账号列展示具体名称（租户名、用户名），不只数字 ID。
3. **积分冻结**：按**租户**聚合展示该租户全部 held 冻结积分合计；行内可填「本次释放积分」并处理；租户/账号信息可读；不必逐任务一行。
4. 后端：为 tickets / held-credits 补 `tenantName`/`username`（及聚合/按量释放若前端无法仅靠现有单任务 release 完成）。

## T2 用户管理（`users/page.tsx` + 必要 API）

1. 主表改为**租户列表**；每行「查看账号」可查看该租户下全部账号。
2. 账号级操作（加减分、重置密码、角色、启停、删除等）收拢到租户行 **「操作」** → 弹窗：先选操作再选账号。
3. 若有**租户级**操作（如创建账号到该租户），独立按钮留在租户行，不塞进「操作」弹窗。

## T3 检测基线文案（`detection-pass-score-card.tsx`）

删除说明注释/文案，含：

- 「通过标准为总分 ≥ … 且模型 passed=true。代码默认 75。新检测任务…」
- 「平台通过分为 total_score ≥ …」（`promptLine` 展示）

保留及格线编辑控件本身；**不改**后端 `PASS_SCORE` 默认值。

## 验收

- 前端页面可操作路径符合上述 IA；表格优先、弹窗承载处理。
- 相关后端若有变更：补最小单测；ruff 干净。
- 证据写入 `/tmp/ops-desk-ux-e2e.log` 或 `docs/mihuanyuantu-v2/input/OPS-DESK-UX-e2e-*.txt`。
