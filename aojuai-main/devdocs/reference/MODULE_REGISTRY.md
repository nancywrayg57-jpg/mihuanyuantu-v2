# 模块登记表（nextjs-base）

本文件登记 base 上**可选能力包**（`app/capabilities/<code>/`）的对外契约：
模块编码、层级、路由与权限前缀、独立迁移链、以及"装/卸"的命令。

分层判据见 `docs/dev/reference/BASE_ARCHITECTURE.md`，新增模块的完整作业流见
`docs/dev/flows/NEW_MODULE.md`。内核与内置能力（assistant / speech / public_site）
的物理边界登记在 `backend/app/core/module_manifest.py`，由 GOV-18 守卫；
能力包不在那张表里——它们靠目录扫描发现，删目录就整条消失。

## 登记项

| code | layer | 默认 | 路由前缀 | API 前缀 | 权限前缀 | 迁移链 / version table | 表前缀 |
|---|---|---|---|---|---|---|---|
| `sample_items` | sample | 不进生产 | `/sample-items` | `/api/v1/sample-items` | `sample_items` | `sample_items_0001` / `alembic_version_cap_sample_items` | `cap_sample_items` |
| `support` | pack | 默认不开 | `/support` | `/api/v1/support` | `support` | `support_0001` / `alembic_version_cap_support` | `cap_support_*` |

## `support` 工单中心

**是什么**：默认关闭的可选工单能力。工单带分类 / 状态 / 优先级，回复线程区分公开回复、
内部备注与状态事件，带首次响应 SLA；另有一个匿名公开提单入口，以及一个**可选**的
"公开站留言 → 工单"桥。

**来源**：从下游业务分支的工单实现泛化回流。

**权限码**（三个，与菜单按钮一一对应）：

| 权限码 | 谁用 | 覆盖的接口 |
|---|---|---|
| `support:read` | 提单人 | `/options`、`GET /tickets`、`GET /tickets/{id}` |
| `support:create` | 提单人 | `POST /tickets`、`POST /tickets/{id}/messages` |
| `support:manage` | 客服 | `/admin/**`（列表、详情、改状态/指派、公开回复与内部备注） |

`POST /support/public/tickets` 是唯一的匿名接口：租户由内核的
`resolve_public_tenant_for_module(module_code="support")` 按公开主机解析（与公开站同一套
可信代理与精确域判定），蜜罐命中静默接受，限流用 `incr_with_ttl_strict`——Redis 不可用时
**拒绝**而不是放行。

**菜单**（`backend/app/capabilities/support/access.py`，三条链路共用同一个 reconciler）：
`/support`（目录）→ `/support/tickets`（我的工单）、`/support/admin/tickets`（工单管理）。
默认授权：`admin` / `tenant_admin` 全量，`user` 只拿"我的工单 + 提交工单"。

**与公开站/CMS 的关系**：单向且可选。`app/api/v1/endpoints/cms_public.py` 在
`is_module_installed("support")` + `is_module_enabled_for_tenant(...)` 都成立时**延迟 import**
`app.capabilities.support.bridge`；support 自己不 import 任何 CMS 代码，也不把 `public_site`
写进 `dependencies`。方向由 `backend/tests/capabilities/support/test_support_module_boundaries.py`
用 AST 钉住。

**装 / 卸**：

```bash
AOJ_ENABLED_MODULES=support python -m scripts.capability db upgrade   # 建表
AOJ_ENABLED_MODULES=support python -m scripts.capability sync         # 菜单/权限对账
AOJ_ENABLED_MODULES=support python -m scripts.capability heads        # 单头校验
python -m scripts.capability db purge support --purge                 # 卸载（先移出 AOJ_ENABLED_MODULES）
```

**前端**：`frontend/src/app/(app)/support/**`、`frontend/src/lib/support-api.ts`、
`frontend/src/lib/i18n/locales/support.ts`。菜单标题的 `menu.<中文原文>` 译文在
`frontend/src/lib/i18n/locales/en-US.ts` / `es-ES.ts`（GOV-19 只认这两份）。

## 新增一个包时要同步更新的清单

1. `python -m scripts.new_module <code> --layer pack --route /<kebab> --entity <entity> --permissions read,create`
2. 填实体、权限、`access.py` 声明与前端页面；表名保持 `cap_<code>_*`
   （`module_manifest.CAPABILITY_TABLE_PREFIX`，换前缀会让核心链 autogenerate 生成 DROP TABLE）
3. `python -m scripts.export_module_catalog`、`python -m scripts.export_locale_index`
4. 菜单标题补 `menu.<中文原文>` 到两份核心语言包
5. 在本文件登记一行 + 一节
