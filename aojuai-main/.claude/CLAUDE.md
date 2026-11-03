# nextjs-base AI 开发入口

本文件是 AI/维护者在 `nextjs-base` 上工作的启动入口。`nextjs-base` 是公开底座版本，只承载租户配置、系统管理、个人设置、AI 助手基础、语音配置、Message Channel、RBAC、菜单和数据权限等可复用能力。

不要把历史分支治理文档、业务分支文档或旧资料当作当前事实来源。

## 启动顺序

1. 根目录文档地图：@[DOCS_MAP.md](../DOCS_MAP.md)
2. 公开版说明：@[README.md](../README.md)
3. 公开文档入口：@[docs/README.md](../docs/README.md)
4. 文档路由设计：@[docs/DOCUMENTATION_ROUTING.md](../docs/DOCUMENTATION_ROUTING.md)
5. 维护者文档入口：@[docs/dev/README.md](../docs/dev/README.md)
6. 安全与代理边界：@[docs/dev/reference/AUTH_SECURITY_BASELINE.md](../docs/dev/reference/AUTH_SECURITY_BASELINE.md)

## 当前底座事实

- 菜单必须由后端 `GET /api/v1/menus/routes` 输出并按权限过滤，前端不维护硬编码菜单树。
- 权限码承载在 `menus.perms`，角色授权通过 `role_menus`，后端接口使用 `PermissionChecker(...)`。
- 数据权限使用 `DataScopeCtx`，租户配置类数据通常只按 `tenant_id` 隔离。
- 个人设置、租户设置、系统设置属于 base 能力；垂直业务页面、业务 prompt、业务 action executor 不属于 base。
- 生产部署以 Nginx 为唯一受信边界，`/api/v1/*` 直达 FastAPI 并注入 `x-aoju-proxy-key`；`NEXT_ENABLE_BACKEND_REWRITES=0`。
- Next App Route proxy 只作为本地直连、无 Nginx 或特殊服务端代理场景的兜底。

## 常用任务入口

- 新模块或扩展接入：@[docs/dev/flows/NEW_MODULE.md](../docs/dev/flows/NEW_MODULE.md)
- 菜单/权限双写：@[docs/dev/flows/MENUS_PERMS_DUALWRITE.md](../docs/dev/flows/MENUS_PERMS_DUALWRITE.md)
- 开发检查清单：@[docs/dev/checklists/DEV_CHECKLIST.md](../docs/dev/checklists/DEV_CHECKLIST.md)
- 代码级指南：@[docs/dev/guide_docs/README.md](../docs/dev/guide_docs/README.md)
- 部署文档入口：@[docs/deploy/README.md](../docs/deploy/README.md)
- 部署代理事故库：@[docs/dev/issues/DEPLOYMENT_PROXY_PITFALLS.md](../docs/dev/issues/DEPLOYMENT_PROXY_PITFALLS.md)

## 交付要求

每次变更至少说明：

1. 变更范围和文件。
2. 是否触及权限、菜单、租户配置或代理边界。
3. 是否需要迁移、seed 或环境变量调整。
4. 已执行的验证命令。
5. 新踩坑是否已沉淀到 `docs/dev/issues/` 或检查清单。
