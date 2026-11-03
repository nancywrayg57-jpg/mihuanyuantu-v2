---
name: aojuai-development-workflow
description: Closed-loop feature delivery workflow for AOJUAI nextjs-base (requirements→DB/API→implementation→tests→deploy→log verification) with templates and scripts.
---

# AOJUAI 应用开发闭环（Workflow Skill）

用于：任何**新功能/新模块/外部平台接入**的开发前后，确保产出“可安装、可验证、可排错”的闭环交付物。

## 你需要先给出什么（最少输入）

- 需求概述（谁/场景/目标/非目标）
- 模块形态：Core 改造 or 下游扩展
- 主要实体（3-10 个）与关键字段
- 权限边界（管理员/租户管理员/普通用户/外部访客）
- 是否涉及外部平台与配置来源

## 强制闭环流程（按顺序）

1. 需求澄清（验收标准可测试）
2. 数据模型设计（tenant_id/索引/JSONB/server_default）
3. 权限/菜单设计（`resource:action` + `menu_type 0/1/2`）
4. 接口契约（请求/响应/分页/错误码）
5. 后端先行实现（对齐 `docs/dev/guide_docs/`）
6. 迁移与 seed（幂等，可重复执行）
7. 前端对接（动态路由 + 演示模式检查）
8. 验证（冒烟→关键链路→回归）
9. 上线后闭环：检查日志 + 记录问题 + 更新文档/Skills

规范总文档：`docs/dev/flows/DEVELOPMENT_WORKFLOW.md`

## 直接复用的模板（按需打开）

- 需求模板：`docs/dev/skills/aojuai-development-workflow/references/REQUIREMENTS_TEMPLATE.md`
- 数据模型模板：`docs/dev/skills/aojuai-development-workflow/references/DB_DESIGN_TEMPLATE.md`
- 接口契约模板：`docs/dev/skills/aojuai-development-workflow/references/API_CONTRACT_TEMPLATE.md`
- 测试 TaskList 模板：`docs/dev/skills/aojuai-development-workflow/references/TEST_TASKLIST_TEMPLATE.md`
- 发布/回滚模板：`docs/dev/skills/aojuai-development-workflow/references/RELEASE_RUNBOOK_TEMPLATE.md`

## 脚手架（可选）

一键生成该功能的文档骨架（dry-run 默认）：

```bash
python docs/dev/skills/aojuai-development-workflow/scripts/init_feature_bundle.py --slug feature_x
```
