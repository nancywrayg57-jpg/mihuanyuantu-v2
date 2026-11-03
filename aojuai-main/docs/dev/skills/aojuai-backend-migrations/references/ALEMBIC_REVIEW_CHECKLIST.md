# Alembic 迁移审阅清单（AOJUAI）


> 适用范围：**core 链**。能力包有自己的独立链与 version table，
> 完整升级走 `python -m scripts.capability db upgrade`，单 head 校验走 `capability heads`。

## 机器会替你查的（别只靠人眼）

`python scripts/check_governance.py` 已经强制：

- 迁移图**恰好一个 head**
- 迁移里不许把 `updated_at` 建成 `nullable=False`（扫的是**迁移文件本身**，不是 ORM）
- 软删除模型的业务唯一键必须是 `postgresql_where=deleted_at IS NULL` 的 partial index
- 运行时配置不许直接读 `os.environ` / `os.getenv`

人工审阅重点放在这些查不了的地方：语义是否正确、数据迁移是否幂等、是否允许无租户时 no-op。
> 目标：避免 autogenerate “看起来能跑，但会埋雷”的迁移脚本。

## 生成前（避免漏表/漏字段）

- 新模型是否已导入：`backend/app/domain/__init__.py`
- 本地 `backend/.env` 的 `DATABASE_URL` 是否指向正确库

## 生成后（逐行审阅）

- 表/字段：
  - `nullable` 是否正确
  - `default` vs `server_default` 是否合理（尤其 JSONB）
- 索引：
  - `tenant_id` 是否有索引（业务表通常需要）
  - 外键字段是否有索引
- 约束：
  - unique/foreign key 是否误生成/漏生成
- 数据迁移：
  - 结构变更与数据回填尽量拆分
  - `downgrade()` 是否可逆（至少不报错）

## 常用命令

```bash
cd backend
alembic revision --autogenerate -m "feat: <desc>"
alembic upgrade head
```

