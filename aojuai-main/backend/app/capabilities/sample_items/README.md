# `sample_items` 官方样例模块

这个模块演示一个默认不安装、默认不开启的业务能力如何贯穿完整技术栈：包内
`CAPABILITY` 自动进入 catalog；FastAPI 只在部署显式安装时挂载路由；模型和服务
始终带 `tenant_id` 并排除软删除；四个 endpoint 权限与菜单按钮一一对应；菜单、
默认角色授权由声明式 reconciler 收敛；表结构由包内独立 Alembic 链管理；前端按
登录态权限显示操作按钮。

复制为新模块时必须修改：包名和 `CAPABILITY.code`、显示名称、前后端 route、
`cap_` 表名、独立 `version_table`、migration revision、实体字段、权限前缀、access
key/path/component、前端类型和文案。优先使用 `python -m scripts.new_module`，避免
漏改隐含契约。

不要修改：`TenantBaseModel`、所有查询的 tenant/soft-delete 条件、软删除业务唯一键
的 partial index、`updated_at nullable=True`、迁移 `down_revision=None`、独立
version table、迁移/seed 分工、薄路由与 `PermissionChecker` 的一一对应。迁移只
建表；不得 seed 菜单、打开模块开关或 `create_all()`。模块目录也不得依赖其他业务包。

`layer="sample"` 和 `production_blocked=True` 是发布阻断标记。样例即使在部署变量
留空（普通模块的 legacy “all” 语义）也不会安装；只能通过显式
`AOJ_ENABLED_MODULES=sample_items` 用于开发、验收和教学。
