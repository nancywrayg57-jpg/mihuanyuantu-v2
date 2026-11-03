---
name: aojuai-db-setup
description: Set up PostgreSQL + backend .env + migrations/seed for AOJUAI nextjs-base. Use when bootstrapping a new environment, resetting DB, or troubleshooting DB connectivity/migrations/seed.
---

# nextjs-base 数据库与初始化（PostgreSQL / Alembic / seed）

用于：新环境快速拉起后端、重建数据库、排查“迁移/seed/权限菜单缺失”。

## 你需要先确认的 5 件事

1. PostgreSQL 版本（建议 `>= 15`）
2. 目标数据库名、用户名、密码
3. 后端 `.env` 文件位置（通常 `backend/.env`）
4. 是否要保留旧数据（如果要保留，避免 drop database）
5. 是否需要“迁移 + seed”都执行（大多数情况下都需要）

## 标准流程（新装环境）

> 下列命令为示意，请按你的机器调整（系统包管理器 / 服务名 / 权限）。

1) 创建数据库与用户（示意 SQL）：

```sql
CREATE USER aoju WITH PASSWORD '<DB_PASSWORD>';
CREATE DATABASE aoju OWNER aoju;
GRANT ALL PRIVILEGES ON DATABASE aoju TO aoju;
```

2) 配置后端环境变量（示例，按项目模板拷贝并填写）：

```bash
cd backend
cp .env.production.template .env
```

3) 执行迁移（结构升级）：

```bash
cd backend
alembic upgrade head          # 本地开发：只升 core 链
# 装了可选能力包时用编排命令（core + 每个已安装包各自的链）：
# python scripts/capability.py db upgrade
```

4) 执行 seed（初始化租户/角色/菜单等）：

```bash
cd backend
python -m scripts.seed_data
```

5) 启动后端并验证：

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 38000
```

- Swagger：`http://localhost:38000/api/v1/docs`
- 验证菜单路由：登录后 `GET /api/v1/menus/routes` 应返回非空

## 关键注意事项（避免踩坑）

- **迁移在前，seed 在后**：新装环境通常先 `alembic upgrade head` 再 `seed_data`
  - 因此 Alembic 的“数据迁移”必须允许无租户时安全 no-op
- **菜单/权限不是代码生成的**：它是 DB 数据，新增时必须三写：seed + 迁移 + 建租户 reconciler
- **asyncpg JSONB**：raw SQL 里不要写 `:param::jsonb`，用 `cast(:param as jsonb)`

## 自检清单

详见：`docs/dev/skills/aojuai-db-setup/references/DB_SETUP_CHECKLIST.md`

## 关联文档

- 本地环境模板：`.claude/LOCAL_ENV.md`
- 常见坑复盘：`docs/dev/issues/DEVBASE_PITFALLS.md`
- 菜单/权限三写：`docs/dev/guide_docs/MENU_SEED_MIGRATION_GUIDE.md`
