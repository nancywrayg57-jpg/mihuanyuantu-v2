# 2026-10-28 用户管理原型上下文

范围：仅离线 HTML 原型。用户本轮要求优先于旧版菜单描述；未修改 PRD、生产架构或 aojuai 底座源码。

- 菜单路由：`#users` 为管理员一级用户管理，`#logs` 为管理员系统日志，`#settings` 显示为系统管理。管理员/技术客服隐藏积分与充值并拦截其直达路由；商家保留。
- 用户管理变更统一通过操作弹窗提交，目标由 `id + tenantId` 定位；权限管理替代行内“保存角色”。用户列表每页 10 条。
- 本地日志 schema：`id, module, time, actor, actorId, targetId, username, tenantId, action, before, after, reason, result`。记录创建、积分增减、权限、启停用、重置密码和删除的成功变更；系统更新和系统配置不进入此日志。每页 20 条。
- 积分额度、余额均为整数；本地使用 decimal.js 做精确计算并拒绝小数、负余额及超出原型整数安全范围的调整。密码仅用于输入校验，不进入快照或本地存储。
- 已参考 aojuai 用户重置密码接口及操作日志 schema 的目标账号/租户范围；原型字段不是新增后端契约，未实现或调用用户管理 API。
- 主脚本为 `prototype/prototype.js`；HTML 内嵌脚本与 `output/prototype-inline-check.js` 必须保持一致；运行需要同目录 `device-presets.js` 与 `vendor/decimal.js`。
- 生成历史默认全部来源，删除默认来源和右侧说明栏；任务详情删除原图/结果对比，保留结果预览、下载和逐张状态。
- 用户明确暂不生成 ZIP。浏览器证据和验证范围见 `蜜獾原图-v2-HTML原型验收记录-2026-10-25.md`。
