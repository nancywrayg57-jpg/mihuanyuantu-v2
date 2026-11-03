# `support` 工单能力包

默认**不安装、不开启**的官方可选能力包。装上之后提供一条完整的工单链路：
分类 / 状态 / 优先级、回复线程（公开回复 + 内部备注 + 状态事件）、首次响应 SLA、
客服台，以及一个匿名公开提单入口。

来源：从下游业务分支的工单实现泛化回流，去掉了全部业务词汇与业务耦合。

## 装 / 卸

```bash
# 安装（与既有值合并）
AOJ_ENABLED_MODULES=support python -m scripts.capability db upgrade
AOJ_ENABLED_MODULES=support python -m scripts.capability sync     # 菜单/权限对账
AOJ_ENABLED_MODULES=support python -m scripts.capability heads     # 单头校验

# 卸载（先从 AOJ_ENABLED_MODULES 移除，再显式销毁）
python -m scripts.capability db purge support --purge
```

未安装时：包不被 import、路由不进 route table（请求得到 404 而不是 403）、
表不存在、目录里没有它的开关项。

## 边界

- **不 import 任何业务域**，尤其不 import CMS/公开站。留言→工单的联动方向是
  `cms_public → support.bridge`，由调用方用 `is_module_installed("support")` +
  `is_module_enabled_for_tenant(...)` 守卫后**延迟 import**。反向依赖由
  `tests/capabilities/support/test_support_module_boundaries.py` 用 AST 钉住。
- `related_type` / `related_id` 是**不透明**的泛化关联：取值与生命周期归调用方，
  本模块不认识任何具体业务实体。
- 匿名入口 `POST /api/v1/support/public/tickets` 走内核的
  `resolve_public_tenant_for_module(module_code="support")`——与公开站同一套主机解析，
  但不要求 CMS 已部署，校验的是 support 自己的租户开关。
  蜜罐命中静默接受；限流用 `incr_with_ttl_strict`，Redis 不可用时**拒绝**（fail closed）。

## 复制成新模块时必须改

包名与 `CAPABILITY.code`、显示名与 `label_key`/`description_key`、前后端 route、
`cap_` 表名、独立 `version_table`、migration revision、权限前缀、access 的
key/path/component、前端类型与语言包。优先用 `python -m scripts.new_module`。

## 不要修改

`TenantBaseModel`、所有查询的 tenant / 软删除条件、软删除业务唯一键的 partial index、
`updated_at nullable=True`、迁移 `down_revision=None`、独立 version table、
"迁移只建表、菜单只走 reconciler" 的分工、薄路由与 `PermissionChecker` 的一一对应。
