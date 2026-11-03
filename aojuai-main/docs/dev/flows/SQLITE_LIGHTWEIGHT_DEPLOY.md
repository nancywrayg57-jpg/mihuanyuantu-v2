# 轻量档部署（SQLite 单机，无 Redis）

两种部署形态由 **一个开关** `DB_DRIVER` 决定，代码同一份、互不影响：

| | 轻量档 lite | 标准档 standard |
|---|---|---|
| 数据库 | SQLite 单文件（WAL） | PostgreSQL |
| Redis | 默认关闭（进程内本地缓存） | 必需（多进程共享缓存/锁） |
| 进程 | 单进程 uvicorn + 进程内调度器 | web / worker 分进程，多实例 |
| 适用 | 试点、演示、<50 人小团队、离线环境 | 生产、多租户、后台任务集群 |
| 不可用功能 | 登记在 `core/dialect_features.PG_ONLY_FEATURES`，前端自动隐藏（目前：积分灰度对账） | — |
| 模板 | `backend/.env.lite.template` | `backend/.env.production.template` |

## 一条命令

```bash
scripts/lite.sh init            # 生成 .env（如无）→ 建库（create_all + stamp）→ 能力包迁移链 → 菜单/权限对账 → seed
scripts/lite.sh run --port 8000 # 前台运行；生产用 systemd/supervisor 托管同一条命令
scripts/lite.sh doctor          # 形态 / 方言 / Redis / 事务模式 / 表数 / 各迁移链 head / 完整性 / 不可用功能
scripts/lite.sh backup          # sqlite 在线备份到 data/backups/（WAL 下不要直接 cp 文件）
scripts/lite.sh upgrade         # 备份 → 核心链 + 能力包链 upgrade → 对账；之后重启进程
```

前端与标准档完全一样（`pnpm build && pnpm start`），Nginx 代理边界也一样。

## 升级规则（最容易踩的一条）

- **新库** 用 ORM 建全表后直接 stamp 到 head（`init_db()`、`alembic upgrade head`、`capability db upgrade` 三个入口同一语义），PG 专有的历史迁移不重放。
- **存量库** 只能靠迁移升级，因此基线（2026-08-27）之后的 base 迁移必须双方言，`tests/test_sqlite_migration_portability.py` 是门禁；应用代码由 `tests/test_sqlite_app_portability.py` 守。
- 升级后进程必须重启（没有 `--reload` 的进程不会加载新代码）。

## 需要 Redis 的场景

多进程 / 多实例 / worker 分进程时把 `REDIS_ENABLED=true` 并配置 `REDIS_HOST`；单进程轻量档不要开（本地缓存即最终形态，避免"看起来连上了其实各说各话"）。

## 已知边界

- SQLite 单写者：`SQLITE_BEGIN_MODE=immediate`（缺省）下事务串行化，长事务会让其他请求排队；请求处理期间不要再开第二个写会话（见 `issues/SQLITE_LIGHTWEIGHT_DEPLOY_PITFALLS.md` §7）。
- `:memory:` 只供单进程测试。
- 详细坑与修法：`docs/dev/issues/SQLITE_LIGHTWEIGHT_DEPLOY_PITFALLS.md`。
