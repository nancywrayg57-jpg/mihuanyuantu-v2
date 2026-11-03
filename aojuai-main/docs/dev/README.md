# docs/dev

`docs/dev` 是 `nextjs-base` 公开版维护者文档中心，用于记录底座开发流程、检查表、代码级指南、问题库和跨分支通用经验回流。正式部署 SOP 统一在 `docs/deploy/`。

公开读者优先看根目录 `DOCS_MAP.md`、`docs/README.md` 和 `docs/public/`。`docs/dev` 面向维护者，不应写入垂直业务方案、客户真实路径或分支治理流水账。

## 建议阅读顺序

1. `docs/public/open-edition-base-hardening.md`
2. `docs/dev/reference/AUTH_SECURITY_BASELINE.md`
3. `docs/deploy/README.md`
4. `docs/dev/issues/DEPLOYMENT_PROXY_PITFALLS.md`
5. `docs/dev/checklists/CORE_DEVELOPMENT_GUIDE.md`
6. `docs/dev/flows/NEW_MODULE.md`
7. `docs/dev/checklists/DEV_CHECKLIST.md`
9. `docs/dev/guide_docs/`

## 文档体系章程（2026-06-12，与 nextjs-plugins devdocs 同构）

每份文档必须能归入且仅归入一类；生命周期随类型确定：

| 类型 | 目录 | 生命周期 |
|---|---|---|
| 事实（系统"是什么"） | `reference/` | 持续修订，永远代表现状 |
| 规则（"必须怎么写"） | `guide_docs/` | 持续修订，**唯一规则源** |
| 门禁 | `checklists/` | 持续修订 |
| 流程 / 剧本 / 模板 | `flows/` `skills/` `templates/` | 持续修订 |
| 经验 | `issues/` | 追加式 |
| 方案/复盘（带日期） | `plans/`（按需创建，命名 `<主题>_YYYYMMDD`，带状态头，落地后冻结） | 冻结 |
| AI 规范 | `ai/` | 持续修订 |

硬规则：
1. **单一规则源**：规则正文只活在一个 guide 里，其他文档引用不复制
2. **索引完整**：目录 README 必须列出全部文档，新增文档同 PR 更新索引
3. **回流接收**：上游分支（nextjs-plugins 等）的通用规则**剥离业务案例后**回流到本目录同名文件；本目录不接收业务分支流水账（与公开版定位一致）
4. 部署 SOP 统一在 `docs/deploy/`，本目录不存副本

## 目录职责

- `flows/`：端到端开发链路。
- `checklists/`：开发与发布检查表。
- `guide_docs/`：API、事务、权限、菜单、日志、调度器等代码级指南。
- `issues/`：公开底座问题与踩坑沉淀，包含部署代理事故；正式 SOP 放在 `docs/deploy/`。
- `reference/`：认证、安全、迁移、前端基线、跨分支回流审计等核心参考。
- `skills/`：面向 AI/工程协作的执行剧本。
- `templates/`：需求、DB、API、测试、发布模板。
- `ai/`：AI 辅助开发输出规范。

公开版不携带业务分支治理记录、垂直业务研究资料、客户真实部署路径或上游源码快照。
- 归档目录 `archive/`：历史审计/合并记录，仅供追溯（见 `archive/README.md`）。
- 轻量档部署（SQLite 单机）：[flows/SQLITE_LIGHTWEIGHT_DEPLOY.md](flows/SQLITE_LIGHTWEIGHT_DEPLOY.md)；坑清单 [issues/SQLITE_LIGHTWEIGHT_DEPLOY_PITFALLS.md](issues/SQLITE_LIGHTWEIGHT_DEPLOY_PITFALLS.md)
