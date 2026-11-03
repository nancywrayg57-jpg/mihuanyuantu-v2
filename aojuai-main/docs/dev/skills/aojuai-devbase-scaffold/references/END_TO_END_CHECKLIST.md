# 端到端新增模块 Checklist（AOJUAI nextjs-base）

1. 明确模块规格（字段/权限码/菜单 component/分页参数）
2. 找 3+ 参考模块（users/roles/menus）
3. 后端 Domain + Service + Endpoint（按 `guide_docs`）
4. Alembic 迁移（autogenerate + 审阅 + upgrade）
5. Seed（可选）：菜单/按钮 perms/默认授权
6. 前端页面 + API 对接（先列表再表单）
7. 演示模式自检（读可用、写被拦截；必要时更新 allowlist）
8. 构建验证：`python -m compileall backend/app` + `pnpm -C frontend build`

