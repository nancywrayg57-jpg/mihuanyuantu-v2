# flows（开发链路）

> flows 负责回答：做一个新功能模块时“从哪些方面考虑、按什么顺序做、用哪些 skills、如何验收”。

## 入口

- `NEW_MODULE.md`：新功能模块端到端
- `SKILLS_MAP.md`：每个阶段该用哪个 skill
- `DYNAMIC_MODULE_LOADING.md`：模块动态加载（不装就不加载）——新模块与存量模块改造
- `MENUS_PERMS_DUALWRITE.md`：最容易漏的双写闭环（seed + Alembic 数据迁移）
- `DEVELOPMENT_WORKFLOW.md`：完整闭环流程（稳定版）
- `SQLITE_LIGHTWEIGHT_DEPLOY.md`：轻量档部署（SQLite 单机、无 Redis）——`scripts/lite.sh init|run|upgrade|backup|doctor`，与标准档的分工
