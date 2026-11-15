# OPS-DESK-UX · 约束账本

| ID | 约束 | 说明 |
| --- | --- | --- |
| C1 | 听 PRD / 架构 | UI 密度对齐运营工具：列表表格、弹窗承载处理；不发明新收费能力 |
| C2 | 禁 S7 / 生产收费宣称 | production_billing=false |
| C3 | 不改五层默认、不放宽 PASS_SCORE 合同 | T3 只删展示文案，不改 `PASS_SCORE=75` 代码默认 |
| C4 | 积分冻结/释放分路径 | 租户聚合展示；释放仍须原因审计；按量释放须诚实对应 held 预留 |
| C5 | 账号信息可读 | 租户名 + 用户名；ID 可辅显，不得只显示数字 |
| C6 | 双账号合入 | 分支 `cursor/ops-desk-ux-9973`；PR + squash；禁自评自合 |
| C7 | 不碰主树 DOF 脏工作 | 只改本 worktree |
