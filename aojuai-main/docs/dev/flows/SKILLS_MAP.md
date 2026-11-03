# Skills 使用地图（按开发链路）

> 目的：在 `nextjs-base` 开发过程中，让团队与 AI 在每个阶段都能“点名正确 skill”，减少反复沟通与漏项。

## 1) 端到端开发链路 → 推荐 skills

| 阶段 | 你在做什么 | 推荐 Skill | 主要产出 |
|------|------------|------------|----------|
| 需求/拆分 | 明确边界、验收、权限/菜单草图 | `aojuai-development-workflow` | 需求模板、任务拆分、API契约草案 |
| 后端模块 | Domain/Service/Endpoint 落地 | `aojuai-backend-module` | 端点 + Service + schema/repo 结构 |
| 迁移 | 表/字段/索引/约束 | `aojuai-backend-migrations` | Alembic revision + 审阅清单 |
| seed/初始化 | 新装/新租户默认数据 | `aojuai-backend-seed` | seed_data / seed_<module>.py（幂等） |
| 菜单/权限 | perms、按钮级权限、赋权 | `aojuai-rbac-menu-perms` | perms 规划与排错方法 |
| 菜单三写闭环 | seed + 迁移 + 建租户，共用 reconciler | `aojuai-menu-perms-dualwrite` | 新装/升级/新建租户三条链路终态一致 |
| SQLAlchemy 异步 | 事务、预加载、JSONB | `aojuai-sqlalchemy-async` | async ORM 规范与坑位修复 |
| 前端页面 | 页面/接口对接/组件 | `aojuai-nextjs-shadcn-frontend` | app routes + apiFetch + 组件复用 |
| 路由/布局 | Next.js App Router / 导航与布局 | `aojuai-nextjs-shadcn-frontend` | 路由结构、布局、权限与对接清单 |
| 测试 | pytest/异步测试 | `aojuai-backend-testing` | 单元/集成测试模板与策略 |
| 演示模式 | DemoMode 拦截与 allowlist | `aojuai-demo-mode` | 只读模式兼容策略 |

## 2) 高频场景速查

- “要新增一个租户级配置页面/模块设置” → `aojuai-menu-perms-dualwrite` + `aojuai-rbac-menu-perms`
- “老租户看不到新菜单，但新租户能看到” → 优先检查 Alembic 数据迁移是否补齐（见 `docs/dev/flows/MENUS_PERMS_DUALWRITE.md`）
- “页面出现了但打不开/白屏” → 检查 Next.js 路由文件是否存在（`frontend/src/app/**/page.tsx`）+ `RequireAuth` 跳转逻辑 + `NEXT_PUBLIC_API_BASE_URL`
- “要新增组件但怕重复造轮子/风格不一致” → 优先复用 `frontend/src/components/ui/**` 与现有页面组件，再补齐/封装
