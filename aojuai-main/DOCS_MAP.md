# nextjs-base 文档地图

本文件是公开版根目录的路径指引。根目录只保留入口、部署、清单和必要说明；历史阶段记录、分支治理流水账、业务研究资料不属于公开发行版。

## 公开入口

- `README.md`：项目定位、底座范围、本地启动、生产代理边界。
- `docs/README.md`：统一文档索引。
- `docs/DOCUMENTATION_ROUTING.md`：文档顶层设计和路径归属规则。
- `docs/public/open-edition-base-hardening.md`：公开版稳定基线、合入准则、发布检查。
- `docs/public/assistant-foundation-boundary.md`：AI 助手底座边界。
- `docs/deploy/README.md`：部署文档入口。
- `docs/deploy/NEXTJS_BASE_MINIMAL_DEPLOY_SOP.md`：最小独立部署 SOP。
- `docs/deploy/BT_PROJECT_RESTART_SOP.md`：宝塔 / Nginx 前后端重启 SOP。
- `NON_CODE_MANIFEST.md`：非代码文件清单和公开版携带规则。

## 维护者文档

- `docs/dev/README.md`：维护者文档入口。
- `docs/dev/checklists/`：开发和发布检查表。
- `docs/dev/flows/`：开发流程、菜单权限双写、新模块流程。
- `docs/dev/guide_docs/`：API、事务、权限、菜单、日志、调度器等代码级指南。
- `docs/dev/issues/`：可复现问题和部署/开发踩坑。
- `docs/dev/reference/`：认证安全、数据库迁移、前端基线、助手接入、消息通道边界。
- `docs/dev/skills/`：AI/工程协作执行剧本。
- `docs/dev/templates/`：需求、API、DB、测试、发布模板。

## 子系统说明

- `backend/README.md`：FastAPI 后端开发和运行说明。
- `backend/API_ROUTES.md`：后端 API 路由索引。
- `backend/app/domain/assistant/README.md`：助手底座代码层说明。
- `frontend/README.md`：Next.js 前端开发、构建和代理说明。
- `frontend/public/README.md`：前端公开资源说明。

## 文档边界

- `docs/public/` 面向公开发行版读者，只写底座能力和公开部署边界。
- `docs/deploy/` 面向部署和运维，统一承载前后端、BT、Nginx、缓存、代理配置。
- `docs/dev/` 面向维护者，可记录工程经验、检查表和回流审计，但不能携带垂直业务方案或真实客户部署细节。
- `frontend/` 只保留前端本地开发、构建和前端边界说明，不承载全局部署 SOP。
- 根目录不放阶段性 `S1/S2/S3`、分支治理、业务路线图、客户事故原文或回收站资料。
