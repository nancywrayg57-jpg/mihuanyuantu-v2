---
name: aojuai-backend-migrations
description: Alembic workflow for AOJUAI backend (create/alter tables, review autogenerate, apply upgrade) while keeping multi-tenant conventions and safe upgrades/downgrades.
---

# AOJUAI 后端迁移（Alembic）

用于：新增表、修改字段、索引/约束调整、数据迁移。

> **先分清你在改哪条链**：
> - **core 链**（`backend/alembic/`）：内核与内置能力的表。下面整套流程讲的就是它。
> - **能力包链**（`app/capabilities/<code>/migrations/`）：包自带的独立链 +
>   独立 version table（`alembic_version_cap_<code>`），`down_revision` 从 `None` 起，
>   **不许挂到 core 链上**——挂上去就等于"不装也建表"。
>
> 生产完整升级命令是 `python -m scripts.capability db upgrade`
> （先 core 到 head，再逐个已安装的包升到各自的 head，并校验每条链恰好一个 head）。
> 裸 `alembic upgrade head` **只升 core**，是本地开发命令。

## 前置检查（否则 autogenerate 会漏）

- 新模型是否已导入到 `backend/app/domain/__init__.py`
- 本地 `backend/.env` 数据库连接是否正确

## 标准流程

1. 生成迁移（建议先只做结构变更）：
   - `cd backend`
   - `alembic revision --autogenerate -m "feat: <desc>"`
2. 审阅迁移脚本（`backend/alembic/versions/*.py`）：
   - 是否包含 `tenant_id` 索引（业务表通常需要）
   - 是否有正确的 `nullable/default/server_default`
   - 是否误生成/漏生成约束（unique/foreign key）
3. 执行：
   - `alembic upgrade head`
4. 回滚验证（可选但推荐）：
   - `alembic downgrade -1`
   - 再 `alembic upgrade head`
5. **过治理门禁**（会挡住几个反复踩的坑）：
   - `python scripts/check_governance.py`
   - 硬检查包括：迁移图恰好一个 head、`updated_at` 不许 NOT NULL、
     软删除表的业务唯一键必须是 `WHERE deleted_at IS NULL` 的 partial index
   - 能力包另跑 `python -m scripts.capability heads`（每条链都必须单 head）

## 数据迁移建议（需要时）

- 结构变更与数据回填尽量拆分到两次迁移
- 需要回填时，用 `op.execute()` 或批处理；注意写 `downgrade()` 的逆操作

## 参考

- 事务规范：`guide_docs/DATABASE_TRANSACTION_GUIDE.md`
- 公开版稳定基线：`docs/public/open-edition-base-hardening.md`
- 审阅清单：`docs/dev/skills/aojuai-backend-migrations/references/ALEMBIC_REVIEW_CHECKLIST.md`
