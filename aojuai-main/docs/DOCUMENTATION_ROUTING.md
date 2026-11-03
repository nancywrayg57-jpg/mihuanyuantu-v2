# Documentation Routing

本文定义 `nextjs-base` 公开发行版的文档顶层设计和路径路由。新增或移动文档时，优先按本文判断归属。

## 顶层入口

- `README.md`：项目定位、底座范围、本地启动和生产代理红线。
- `DOCS_MAP.md`：根目录文档地图，只放路径导航和边界说明。
- `docs/README.md`：文档中心入口。
- `NON_CODE_MANIFEST.md`：公开发行版携带哪些非代码文件。

根目录不放长 SOP、阶段复盘、分支治理流水账、业务 PRD 或客户事故原文。

## 文档路由

| 路由 | 用途 | 不应该放入 |
| --- | --- | --- |
| `docs/public/` | 面向公开读者的底座能力、边界和发布基线 | 维护者事故细节、业务分支方案 |
| `docs/deploy/` | 生产部署、BT/Nginx、重启、缓存、代理配置和可复制配置片段 | 前端组件开发指南、业务运行手册 |
| `docs/dev/checklists/` | 开发和发布检查表 | 具体事故复盘全文 |
| `docs/dev/flows/` | 可重复执行的开发流程 | 单点问题排查 |
| `docs/dev/guide_docs/` | 代码级落地手册 | 部署命令和服务器路径 |
| `docs/dev/issues/` | 可复现问题、踩坑、根因和预防 | 正式部署 SOP 全文 |
| `docs/dev/reference/` | 架构基线、能力边界、跨分支回流审计 | 垂直业务路线图 |
| `docs/dev/skills/` | AI/工程协作执行剧本和脚本说明 | 普通说明性文档 |
| `docs/dev/templates/` | 可复制模板 | 已完成项目记录 |
| `backend/README.md` | 后端本地开发、运行和目录说明 | 全局部署 SOP |
| `frontend/README.md` | 前端本地开发、构建和前端边界 | 后端/Nginx 全局部署 SOP |

## 部署文档路由

所有跨前端、后端、Nginx、BT 的部署文档统一归属 `docs/deploy/`：

- `docs/deploy/README.md`：部署文档入口和路径选择。
- `docs/deploy/NEXTJS_BASE_MINIMAL_DEPLOY_SOP.md`：独立部署最小基线。
- `docs/deploy/BT_PROJECT_RESTART_SOP.md`：BT 前后端重启总入口。
- `docs/deploy/BT_FRONTEND_DEPLOY_SOP.md`：BT 前端构建、重启、随机端口和 502 排查。
- `docs/deploy/BT_BACKEND_DEPLOY_SOP.md`：BT 后端迁移、seed、重启和新路由 404 排查。
- `docs/deploy/BT_NGINX_CACHE_SOP.md`：Next 静态资源、public 资源和 HTML 壳缓存策略。
- `docs/deploy/nginx.bt.reference.conf`：完整 Nginx 参考配置。
- `docs/deploy/nginx.bt.backend-routes.extension.conf`：BT extension 后端直连片段。

`docs/dev/issues/DEPLOYMENT_PROXY_PITFALLS.md` 只保留问题库视角：症状、根因、预防和跳转到 `docs/deploy/` 的正式 SOP。

## 公开版边界

- 可以写底座能力：租户配置、个人/租户/系统设置、RBAC、数据权限、AI 助手 foundation、语音配置、Message Channel、Nginx 可信代理边界。
- 可以写通用工程经验：deploy、proxy、rewrite、缓存、迁移、seed、权限、测试。
- 不能写垂直业务方案、客户真实域名、真实服务器路径、真实运行时任务名、业务 prompt、业务 action executor 或分支阶段流水账。
