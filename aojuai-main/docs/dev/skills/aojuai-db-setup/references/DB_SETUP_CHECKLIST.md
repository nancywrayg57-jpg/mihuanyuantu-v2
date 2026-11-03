# DB Setup Checklist（nextjs-base）

## 连接与权限

- [ ] PostgreSQL 已启动，可本机连接
- [ ] 用户已创建且可登录：`psql -U <user> -d <db>`
- [ ] 数据库属于该用户或已授权（能建表/建索引）

## 后端配置

- [ ] `backend/.env` 已正确配置数据库 DSN（async + sync / 或项目要求的统一 DSN）
- [ ] 端口/host 与本机环境一致

## 迁移

- [ ] `alembic upgrade head` 成功
- [ ] 若报 “模型未注册/关系解析失败”：检查 `backend/app/domain/__init__.py` 是否导入了新模型

## seed

- [ ] `python -m scripts.seed_data` 成功
- [ ] 登录后 `GET /api/v1/menus/routes` 非空
- [ ] `admin` 角色拥有系统配置/关键页面权限

## 常见故障定位

- [ ] “老租户看不到新菜单”：缺 Alembic 数据迁移补齐
- [ ] “新租户看不到新菜单”：seed（或租户创建钩子）未更新

