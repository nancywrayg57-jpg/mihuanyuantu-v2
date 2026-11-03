# 前端 i18n 与大规模文案外置的坑（2026-06 实战沉淀）

> 来源：三分支（nextjs-base / nextjs-plugins / 下游业务分支）全前端文案 i18n 化（共 ~16,000 键，含 codex 代理批量执行）暴露的、**之前没有注意到**的问题。
> 规则正本见 `docs/dev/guide_docs/FRONTEND_I18N_GUIDE.md`，本文只记踩坑与预防。

---

## 1. `translateActive` 在服务端组件模块顶层调用 → 预渲染崩溃（最严重）

### 症状
`pnpm build` 在 `Generating static pages` 阶段报：
```
Error: Attempted to call translateActive() from the server but translateActive is on the client.
Error occurred prerendering page "/login" (/register, not-found, ...)
```
`pnpm exec tsc --noEmit` **完全通过**——类型检查发现不了，只有 build 的预渲染阶段才暴露。线上演示站随之宕机。

### 根因
- 翻译函数最初定义在 `lib/i18n/index.tsx`（带 `'use client'`）。
- 模块级常量/数组（如 `theme-presets.ts` 的 `label: translateActive(...)`、`useSiteBranding.ts` 的 `DEFAULT_SITE_TITLE = translateActive(...)`）在**模块加载时**就执行翻译；这些模块被服务端组件 import 后，Next 在服务端求值，但函数体属于 client chunk → 抛错。

### 解决方案
- 把 `translateActive` / `getActiveLocale` / `setActiveLocale` / `activeLocale` 实现迁到**纯模块** `lib/i18n/registry.ts`（无 `'use client'`，服务端可安全 import）。
- `LocaleProvider` 通过 `setActiveLocale(locale)` 同步当前语言。
- 非组件 `.ts/.tsx` 一律从 `@/lib/i18n/registry` 直引 `translateActive`（绕开 client 边界）；`index.tsx` 再导出以保持兼容。

### 预防
- **tsc 通过 ≠ 可发布**：i18n/SSR 相关改动必须跑完整 `pnpm build`（含静态生成）才算验收。
- 模块顶层（const/数组/默认值）禁止调用任何 client-only 函数；要本地化的常量改成组件内 `useMemo`，或确保翻译函数是服务端安全的纯模块。

---

## 2. 后端菜单标题翻译：键必须与 DB 原文**逐字一致**（含空格）

### 症状
切到 en/es 后大部分菜单名翻译了，个别（如 `Shopify 接入`）仍是中文。

### 根因
菜单标题存在 DB（中文），靠 `menu.<中文原文>` 键做客户端映射。提取 DB 标题时用了 `tr -d ' '`，把标题内空格删了 → 注册的键 `menu.Shopify接入` 与真实标题 `menu.Shopify 接入`（带空格）不匹配 → 回退原文。

### 解决方案 / 预防
- 提取 DB 标题用 `psql -t -A`（不裁剪），逐字写进语言包。
- 自检：把 DB 全部菜单标题与已注册 `menu.*` 键做集合差，命中差集即漏译。
  ```bash
  psql -t -A -c "SELECT title FROM menus WHERE deleted_at IS NULL AND menu_type IN ('0','1');"
  # 与 grep -oP "'menu\.([^']+)':" 的结果比对
  ```

---

## 3. 分支合并后的"漏译"：基座翻译了基座版本，分支自有增量保留原文

### 症状
base 全量 i18n 合并进 logistics 后，audit 仍发现 4 处正文中文——都在 base/分支**共有文件**里（login、tenant-settings）。

### 根因
这些行是分支自有增量（Shopify 弹窗登录、租户设置里的物流模块卡片）。base 上的迁移只翻译了 base 版本；合并时 `--theirs`/冲突解决取了**分支侧**那几行原文，于是逃过了翻译。
**提交记录看不出这个问题**——base 显示"已全量 i18n"，分支显示"已合并"，但两者交集处有缝。

### 解决方案 / 预防
- 合并完成后**必须重跑非注释中文审计**，不能只信各自分支的"已完成"：
  ```bash
  for f in $(grep -rlP '[\x{4e00}-\x{9fff}]' src --include='*.tsx' | grep -v lib/i18n/locales); do
    grep -nP '[\x{4e00}-\x{9fff}]' "$f" | grep -vE '^\s*[0-9]+:\s*(//|\*|/\*)'   # 排除注释
  done
  ```
- 分支专属、且写进共有文件的文案（模块目录卡片的 label/description 等），要按基座既有的"键即值"模式登记进**分支语言包**，不要遗留在数据结构里。

---

## 4. 整文件重写会静默丢功能

### 症状
codex（或任何"整文件重排"式改写）在外置文案时重打了 `useSiteBranding.ts` / `tenant-theme-applier.tsx` / `register-client.tsx`，顺手丢掉了：租户 `defaultLocale` 管线、登录注册的 Shopify 参数转发、`registerHref`、个人设置的钱包 tab、`import './locales/logistics'`。

### 根因
LLM 重排整文件时以"当前可见结构"为准，会丢掉它认为"无关"的既有特性；这些丢失 **tsc 不报错**（只是行为缺失）。

### 解防
- 大改后对**关键既有特性**做定向回归（不是只看 tsc）：defaultLocale 往返、分享/登录链路、分支语言包是否仍 import。
- 优先约束代理"只外置字符串、不重排结构"；做不到时，改完用 `git diff` 逐文件核对非字符串行有无被动过。

---

## 5. 语言包结构与切换器

- 语言切换器项的 label 若改成 i18n 键（`LOCALE_LABELS: Record<Locale, MessageKey>`），渲染处要 `t(LOCALE_LABELS[item])`，否则显示裸键。
- 新增语言（如 es-ES）要四处同步：`SUPPORTED_LOCALES` + `LOCALE_LABELS` + 新核心包文件 + 后端 `validate_default_locale` 白名单。漏一处就出现"能选不生效"或 422。

---

## 6. 验收基线（i18n 任务的"完成"定义）

1. `pnpm exec tsc --noEmit` 零错误
2. `pnpm exec eslint src --quiet` 零错误（外置后常留未用的旧 import/解构，必须清）
3. **`pnpm build` 完整通过**（防 #1 的 SSR 崩溃）
4. 非注释中文审计为 0（防 #2/#3 漏译；语言包文件本身除外）
5. 切换三语后实测壳层菜单 + 至少一个深层页面（防"切了不变"）
6. 关键既有功能定向回归（防 #4）
