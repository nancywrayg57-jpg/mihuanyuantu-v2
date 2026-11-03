---

> 开关来源：`frontend/src/lib/demo.ts` 的 `isDemoMode()`，读 `NEXT_PUBLIC_DEMO_MODE`（`1`/`true` 生效）；
> 提示文案读 `NEXT_PUBLIC_DEMO_MODE_MESSAGE`，缺省走 i18n。
> 旧文档写的 `frontend/src/utils/http/index.ts` 是 Vue 时代路径，已不存在。
name: aojuai-demo-mode
description: Enforce and extend AOJUAI demo mode (read-only). Use when new features must remain viewable but non-modifiable, especially when list endpoints use POST and need allowlisting.
---

# AOJUAI 演示模式（只读）扩展指南

演示模式用于：**只能看，不能改**。本仓库默认关闭，需要时用环境变量开启。

## 当前实现位置

- 开关：环境变量 `NEXT_PUBLIC_DEMO_MODE`（`1`/`true` 生效）与 `NEXT_PUBLIC_DEMO_MODE_MESSAGE`，读取处见 `frontend/src/lib/demo.ts`
  （旧文档写的 `platform-config.json` 是 Vue 时代产物，本仓没有这个文件）
- 拦截点：`frontend/src/lib/api.ts`（`apiFetch` 内按 `isDemoMode()` 拦截非允许写操作，命中时抛 `ApiError(..., code: "DEMO_MODE_READONLY")`）

## 何时需要改 DemoMode 逻辑

只在这种情况才需要修改：
- 你新增了“列表/查询”接口，但它用的是 **POST**（例如 `POST /api/v1/projects`）
- 演示模式下该列表仍需要可浏览

## 允许列表的原则（务必克制）

- ✅ 只允许“读”语义的 POST（分页查询）
- ❌ 永远不要把 create/update/delete 等写接口加入 allowlist

## 操作步骤

1. 找到拦截 allowlist：`frontend/src/lib/api.ts` 的 `allowPostExact`
2. 将新的列表查询路径加入（只加不带参数的 path）
3. 在演示模式下验证：
   - 列表可打开、可翻页
   - 新增/编辑/删除会被阻断并提示 `DemoModeMessage`

## 参考

- allowlist 规则：`docs/dev/skills/aojuai-demo-mode/references/ALLOWLIST_RULES.md`

## 本地开发提示

需要联调写接口时，建议本地临时将 `DemoMode` 设为 `false`（不要提交到生产配置）。
