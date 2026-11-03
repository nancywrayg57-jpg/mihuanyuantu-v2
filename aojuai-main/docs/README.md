# nextjs-base docs

`docs/` 是仓库唯一文档根目录。

## Routing

- `DOCUMENTATION_ROUTING.md`：文档顶层设计和路径归属规则。

## Public

- `public/open-edition-base-hardening.md`：公开版稳定基线、合入准则、发布检查。
- `public/assistant-foundation-boundary.md`：AI 助手底座边界。

`public/` 可以描述租户配置、个人/租户/系统设置、RBAC、数据权限、AI 助手 foundation、语音配置、Message Channel 和 Nginx 可信代理边界。

## Deploy

- `deploy/README.md`：部署文档入口。
- `deploy/NEXTJS_BASE_MINIMAL_DEPLOY_SOP.md`：独立部署最小基线。
- `deploy/BT_PROJECT_RESTART_SOP.md`：宝塔 / Nginx 前后端重启总入口。
- `deploy/*.conf`：Nginx 参考配置和 BT extension 片段。

`deploy/` 统一承载前端、后端、Nginx、BT 相关部署规范，避免根目录和 `frontend/` 同时维护重复 SOP。

## Dev

- `dev/README.md`：维护者文档入口。
- `dev/checklists/`：开发和发布检查表。
- `dev/flows/`：开发流程。
- `dev/guide_docs/`：代码级指南。
- `dev/issues/`：可复现问题和部署踩坑。
- `dev/reference/`：核心参考、助手/消息通道边界和跨分支回流审计。
- `dev/skills/`：AI/工程协作执行剧本。
- `dev/templates/`：需求、API、DB、测试、发布模板。

`dev/` 可以记录工程经验，但不能携带垂直业务方案、客户真实路径、分支治理流水账或回收站归档。
