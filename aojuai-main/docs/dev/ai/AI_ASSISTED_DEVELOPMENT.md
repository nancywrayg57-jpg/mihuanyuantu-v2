# AI 辅助开发作业流（nextjs-base）

> 目的：把 AI 变成“可控的加速器”，而不是引入新的不确定性。本文定义 **AI 应该如何在 nextjs-base 上协作开发**：输入格式、产出物、验收方式、以及必须避免的误区。

## 1. AI 开发的最小闭环（敏捷）

每次需求都按同一闭环推进，避免“写一堆代码但不可验收”：

1. **需求与边界**：目标、用户角色、验收标准、Out of scope
2. **方案与拆分**：数据模型、权限码、菜单结构、API 契约、前端页面结构
3. **实现**：后端（Domain/Service/Endpoint）→ 迁移/seed → 前端（路由/页面）
4. **验证**：冒烟（关键链路）+ 权限可见性 + 数据隔离 + 日志可定位
5. **复盘沉淀**：把“本次踩坑/纠错”写回 `docs/dev/issues/DEVBASE_PITFALLS.md`

建议每次只做 **1 个可验收增量**（例如：先把列表页闭环，再做新增/编辑/删除）。

## 2. 输入格式（给 AI 的最小必需信息）

当你让 AI 开发一个模块/功能时，按下面格式提供信息（越完整越少返工）：

**A. 功能描述**
- 这是什么功能？（一句话）
- 涉及哪些角色？（普通用户/租户管理员/超级管理员）
- 主要页面/入口是什么？（path）

**B. 数据模型**
- 表名/实体名
- 字段（类型、是否必填、默认值、索引/唯一约束）
- 是否需要 `tenant_id`（绝大多数都需要）
- 是否需要 DataScopeCtx（按团队/范围过滤才需要）

**C. 权限与菜单（必须）**
- 权限码：`resource:action`（例如 `module:settings`、`project:create`）
- 菜单层级：目录(0)→页面(1)→按钮(2)
- 是否存在“模块设置页”（租户级配置）
  - 有的话：必须放在 `/system/<module>-settings` 且只给租户管理员

**D. API 契约**
- 列表分页字段（`currentPage/pageSize/total/list`）
- 错误码/错误信息格式要求
- 排序/过滤参数（`sortBy/sortOrder`）

**E. 验收标准**
- 至少 3 条可执行验收（例如：无权限按钮不可见；老租户升级后可见菜单；新租户初始化也可见）

## 3. AI 的输出物（你应该期待它交付什么）

对一个完整模块，AI 输出应包含（按顺序）：

1. **变更清单**：要改哪些文件/新增哪些文件
2. **权限清单**：权限码列表 + 归属页面/按钮
3. **菜单结构**：path、component、icon、排序、授权角色
4. **迁移与 seed 方案**（关键）：如何同时覆盖
   - 新装/新租户：`seed_data.py` / 租户初始化钩子
   - 已有租户升级：Alembic 数据迁移（幂等、无租户时安全 no-op）
5. **验证步骤**：具体命令/接口/页面验证点

## 4. 必须避免的误区（来自历史分支纠错）

- **误区 1：假设存在 `permissions` 表**
  - 当前 nextjs-base 权限码在 `menus.perms`，角色授权在 `role_menus`
- **误区 2：把模块设置入口放到业务菜单**
  - 模块的租户级配置必须挂系统配置：`/system/<module>-settings`，且只给租户管理员
- **误区 3：只做迁移或只做 seed**
  - 菜单/权限新增必须 **三写**：seed（全新部署/全库对账）+ Alembic 数据迁移（老租户升级）+ 建租户后调 reconciler（运行时新建租户）

## 5. 推荐的“指令模板”（可直接复制给 AI）

```
你是 nextjs-base 项目的 AI 助手。请按 nextjs-base 规范完成开发闭环。

目标：
- <一句话功能目标>

约束（必须遵守）：
- 多租户：业务表必须 tenant_id；查询过滤 deleted_at IS NULL
- 权限：无 permissions 表；menus.perms + role_menus
- 如果有模块设置页：必须 /system/<module>-settings，仅租户管理员可见
- 菜单/权限必须三写：seed_data + Alembic 数据迁移 + 建租户 reconciler（都幂等，允许无租户时 no-op）

请输出：
1) 变更清单（文件级）
2) 权限码清单
3) 菜单树（含 path/component/perms/menu_type）
4) 迁移 + seed 的具体方案与执行顺序
5) 验证步骤（至少 5 条）
```

## 6. 关联文档

- `docs/dev/checklists/DEV_CHECKLIST.md`（开发自检：菜单/权限三写、路由顺序等）
- `docs/dev/flows/DEVELOPMENT_WORKFLOW.md`（端到端闭环）
- `docs/public/open-edition-base-hardening.md`（公开版稳定基线）
- `docs/dev/guide_docs/*`（代码级落地手册）
- `docs/dev/skills/skills.md`（可复用的任务剧本）

## 7. 委派外部编码代理（codex）执行大规模机械改造（2026-06 实战）

当任务是"成千上万处同构机械替换"（如全前端文案外置 i18n），可委派外部编码代理（本机 `codex exec`）批量执行。以下是实战中验证有效的做法与必须设的护栏：

### 7.1 任务简报（写成文件交给代理）
- 写一份 `<TASK>.md`：目标、**必须复用的既有架构**（点名文件与函数，禁止它发明新机制）、**分批顺序**（每批=一个目录）、命名规则、**每批后跑 tsc 并独立小步 commit**、最后的验收命令。
- 简报文件本身不要入库：`git add -A` 会把它和 `.agents/` 沙箱目录一起扫进提交——执行前后都要 `rm` 或加 `.gitignore`。

### 7.2 沙箱
- `codex exec` 的 bwrap 沙箱要在工作区建 `.agents/`，权限不足会直接报 `bwrap: Can't mkdir .../.agents: Permission denied` 且**任何命令都起不来**。
- 预建并放权：`mkdir -p <repo>/.agents && chmod 777 <repo>/.agents`；或用 `--sandbox danger-full-access`（信任的本机工作区可用）。

### 7.3 监控
- 用 Monitor 盯进度时，过滤器只匹配**真实提交行**（`^\[<branch> <hash>\]`）和退出标记，**不要**匹配 `i18n(|失败|error` 之类宽词——代理会大量 grep/读取文件，文件内容里的"失败/error"会把监控刷爆。

### 7.4 验证（核心：不信任，要复核）
代理报"tsc 通过"是**必要非充分**条件。本次它通过了 tsc，但：
- 在服务端组件模块顶层调用了 client-only 函数 → `pnpm build` 预渲染崩溃（见 `docs/dev/issues/FRONTEND_I18N_PITFALLS.md` #1）。
- 整文件重排时静默丢了既有功能（defaultLocale 管线、分支语言包 import、Shopify 参数转发）。
所以代理交付后**必须由主控独立**跑：完整 `pnpm build` + eslint + 非注释中文审计 + 关键功能定向回归，再部署。

### 7.5 分批小步提交的价值
每批一个 commit 让失败可定位、可回滚、可断点续跑；一次性全改后才验证 = 出错时无法二分。

### 7.6 适用与不适用
- 适用：同构、规则清晰、可机械化的大体量改造（文案外置、批量重命名、API 形状统一）。
- 不适用：需要业务判断或架构取舍的改动——那些仍由主控亲自做或用带审查的子代理。

