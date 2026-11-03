# checklists（开发自检与质量门禁）

> checklists 的目的不是“写完就好看”，而是把线上风险在上线前就拦住。

## 必读

- `DEV_CHECKLIST.md`：开发检查清单（权限、DataScope、菜单/权限三写、路由顺序等）
- `CORE_DEVELOPMENT_GUIDE.md`：核心开发指南（规则速记）

## 维护规则

- 新出现的“可重复踩坑”，优先沉淀为 checklist 项
- checklist 应链接到：
  - `guide_docs/*`（落地写法）
  - `docs/dev/skills/*`（执行剧本）
- `BRANCH_INHERITANCE_CHECKLIST.md`：分支继承/回流检查单（变更分级 → 安全同步 → 最小验证；回流自 nextjs-plugins）
