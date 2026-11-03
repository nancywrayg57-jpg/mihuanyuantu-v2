# 2026-10-29 生成历史账号隔离与技术客服用户管理

范围：仅离线 HTML 原型。用户本轮要求优先于交接表中“用户管理/系统日志仅管理员”的旧描述；未修改 PRD、生产架构或 aojuai 底座源码。

## 决策

1. **生成历史按账号隔离**：列表、工作台最近历史、详情、结果弹窗、下载/删除/复制/重处理/检测重试，均以任务上的 `messageRecipient.recipientId + tenantId` 与当前登录账号比对；管理员也不再跨账号查看他人历史。旧无归属历史仅迁移给示例商家 `USR-001 / DEMO-01`，空列表不重灌。
2. **技术客服开放用户管理与系统日志**：侧栏与直达路由对 `admin` 与 `support` 可见可操作；模型 API、设备预设等平台配置仍仅管理员。`recordUserAction` 写入真实操作人 `actorId = role().userId`（客服为 `USR-002`，管理员为 `USR-003`），成功变更继续进入 `system.userLogs`。
3. 客服默认权限补齐 `user.manage`；已持久化的客服账号在加载时若缺少该权限则追加。系统日志表头由“管理员”改为“操作人”。

## 实现定位

- 主脚本：`prototype/prototype.js`；必须同步 `prototype/index.html` 内嵌脚本与 `output/prototype-inline-check.js`。
- 检索：`visibleHistory`、`ownsHistory`、`findOwnedHistory`、`canManageUsers`、`recordUserAction`、`initializeMessages`。
- 不生成 ZIP；不清空用户本地状态；不开启 Check 自动重做。
