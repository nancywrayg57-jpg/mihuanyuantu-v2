# guide_docs（代码级落地手册）

> 这里是 nextjs-base 的代码级规范库：告诉你“怎么写代码才符合约束”。
>
> 你在 `docs/dev/flows/NEW_MODULE.md` 里看到的每一步，都应该能在这里找到“落地写法”。
>
> **两条路径先分清**（见 `NEW_MODULE.md` §0.1 的分层判据）：
> - **内置底座能力**（assistant/speech/cms 这类）：`app/domain/<module>/`，
>   在 `backend/app/api/v1/__init__.py` 用 `register_builtin_capability_router()` **条件挂载**
>   （未安装就不 import、不挂载），并在 `app/core/module_manifest.py` 登记物理边界
> - **可选能力包**（部署时选装）：`app/capabilities/<code>/` 自注册，
>   用 `python -m scripts.new_module` 生成骨架，装配与迁移走 `backend/scripts/capability.py`
>
> 本手册的写法（Service/权限/响应/事务）两条路径通用；差别只在**注册与迁移方式**。
> 两条路径的动态加载流程见 `docs/dev/flows/DYNAMIC_MODULE_LOADING.md`。

## P0 推荐阅读顺序

1. `docs/dev/guide_docs/API_ENDPOINT_GUIDE.md`：端点层（依赖注入、权限、响应）
2. `docs/dev/guide_docs/SERVICE_LAYER_GUIDE.md`：Service 层（事务、Repository 约束、边界）
3. `docs/dev/guide_docs/DATABASE_TRANSACTION_GUIDE.md`：事务与提交策略（避免乱 commit）
4. `docs/dev/guide_docs/PERMISSION_CHECKER_GUIDE.md`：功能权限与 perms 约定
5. `docs/dev/guide_docs/DATA_PERMISSION_GUIDE.md`：数据权限（DataScopeCtx：团队/范围过滤）
6. `docs/dev/guide_docs/MENU_SEED_MIGRATION_GUIDE.md`：菜单/权限三写（seed + Alembic 数据迁移 + 建租户 reconciler）
7. `docs/dev/guide_docs/FRONTEND_PAGE_SCAFFOLD_GUIDE.md`：前端页面脚手架标准（移动端首屏预算、字号下限、HintTip、质感基线）
8. `docs/dev/guide_docs/FRONTEND_PERMISSION_OPTION_LOADING.md`：前端受保护选项接口的权限对齐与预加载约束
9. 可选能力包的装配：`backend/app/capabilities/sample_items/README.md`（官方样例）
   + `python -m scripts.capability --help`（list / heads / sync / db upgrade）

## 其他参考

- `docs/dev/guide_docs/RESPONSE_USAGE_GUIDE.md`：统一响应封装
- `docs/dev/guide_docs/LOGGING_GUIDE.md`：日志规范
- `docs/dev/guide_docs/ENUM_USAGE_GUIDE.md`：枚举规范
- `docs/dev/guide_docs/SCHEDULER_GUIDE.md`：定时任务（如有）
- `CREDITS_BILLING_GUIDE.md`：积分计费接入指南（计量 / 计价 / 结算三层；对话类与任务类接入；回流自 nextjs-plugins）
