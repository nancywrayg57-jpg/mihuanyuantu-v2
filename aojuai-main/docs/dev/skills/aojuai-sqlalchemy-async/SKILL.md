---
name: aojuai-sqlalchemy-async
description: SQLAlchemy 2.0 async usage in AOJUAI (AsyncSession, transaction rules, raw SQL JSONB casting with asyncpg). Use when writing services, scripts, or debugging DB behavior.
---

# SQLAlchemy Async（AOJUAI 版）

用于：写 Service/脚本时的异步 SQLAlchemy 2.0 实践与坑位规避。

## 会话与事务（本仓库约定）

- API 端点通过 `get_db()` 注入 `AsyncSession`
  - 成功：自动 `commit`
  - 异常：自动 `rollback`
  - Service 层：**只 `flush()`，不 `commit()`**
- 脚本/后台任务使用 `get_db_context()`（context manager）

相关实现：
- `backend/app/infrastructure/database/session.py`
- `guide_docs/DATABASE_TRANSACTION_GUIDE.md`

## raw SQL + JSONB（asyncpg）

在 Python 脚本里执行 `text()` 时，JSONB 需要：

- ✅ `cast(:param as jsonb)`
- ❌ `:param::jsonb`

更多说明见：`docs/dev/skills/aojuai-sqlalchemy-async/references/JSONB_ASYNCPG.md`

## 小工具

- 只读连通性检查：`docs/dev/skills/aojuai-sqlalchemy-async/scripts/db_smoke_test.py`

