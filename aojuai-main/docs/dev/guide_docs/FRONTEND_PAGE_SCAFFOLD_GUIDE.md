# 前端页面脚手架标准（2026-06-12 确立）

> 背景：95+ 页面普查发现头部/筛选/统计区无标准，移动端（375px）核心内容被推出首屏。
> 本标准与共享组件同步落地于 nextjs-plugins 与 nextjs-base 两分支。
> 参考实现（基座里现存、按本标准写的页面）：`system/menu`、`system/invitations`、`cms/pages`、`sample-items`。
> （旧版本这里列的 notes/wework/harness/ppt-master 都是下游分支的模块，基座没有。）

## 0. 一条硬指标

**移动端 375×667 首屏必须看到核心内容**（表格首行 / 列表首项 / 主操作区）。
头部 + 筛选 + 状态条的总高度 ≤ 约 200px。新页面验收时必须缩到 375px 检查。

## 1. 页头（必须用 PageHeader，不要包 Card）

```tsx
<div className="grid gap-3">
  <div className="space-y-1.5">
    <PageHeader title="模块 · 页面名" description="一句话说明" actions={<Button size="sm">主操作</Button>} />
    {/* 可选：状态徽标单行横滚 */}
    <div className="flex items-center gap-2 overflow-x-auto pb-0.5">
      <Badge className="shrink-0">...</Badge>
    </div>
  </div>
  ...
```

规则：
- **页头不包 Card**——Card 的 padding 是纯浪费；页面容器本身已有 `p-3 md:p-4`
- `PageHeader` 已内建自适应：移动端标题 16px、description 单行截断（title 属性保留全文）、桌面完整展示——**不要自己写 text-2xl 大标题**
- 统计徽标 / 快捷入口：**单行 `overflow-x-auto` 横滚**，每项 `shrink-0`；禁止竖向堆叠多行
- 长解释段落：`hidden md:block`（移动端不显示说明性长文）
- notice/error：合并为一行 `flex flex-wrap text-xs`，不要一条一行
- 动作按钮统一 `size="sm"`，超过 4 个时收进 DropdownMenu

## 2. 筛选区（CollapsibleFilters + FilterGrid）

```tsx
<Card>
  <CardContent className="pt-4">
    <CollapsibleFilters title="筛选">
      <FilterGrid>
        <div className="grid gap-1"><Label className="text-xs">字段</Label><Select .../></div>
        <Input className="col-span-2 md:col-span-1" ... />  {/* 长控件跨两列 */}
      </FilterGrid>
    </CollapsibleFilters>
  </CardContent>
</Card>
```

规则：
- **移动端筛选永远默认折叠**（CollapsibleFilters 已强制；`defaultExpanded` 只是语义保留）
- 用 `FilterGrid`（移动端 2 列起步）替代 `md:grid-cols-N`——后者在移动端塌成 1 列全宽，每个控件占一整行
- 不要在外层 Card 再写一个 "筛选" CardTitle（CollapsibleFilters 自带，会双标题）
- Label 用 `text-xs` + `gap-1`

## 3. 内容区

- 内容 Card 是页面的主体；**禁止固定高度造成空白**（`h-[calc(100vh-x)]` 的网格会把空行分给卡片）
- 表格外层 `overflow-auto` + Table 加 `whitespace-nowrap`（防止窄屏单字竖排）
- Tabs 顶层布局：TabsList 已内建 `max-w-full overflow-x-auto`，移动端可横滑，不再溢出

## 4. 布局区分（页面类型）

| 类型 | 头部形态 | 示例 |
|---|---|---|
| 列表页 | PageHeader + 筛选 Card + 列表 Card | `cms/pages`、`sample-items` |
| 设置页 | PageHeader + Badge 标识 + 分节 Card（每节 CardTitle 14px） | `system/tenant-settings` |
| 工作台/编辑器 | 自定义全屏布局（豁免本标准，但移动端仍须可用） | 基座暂无，见下游分支 |

视觉区分用 Badge（页头身份标识）与模块 accent 色，不靠放大标题和堆说明文字。

## 5. 交互弹窗：一律用 Dialog，禁止浏览器原生弹窗

**禁止** `window.prompt` / `window.confirm` / `window.alert`。
新建、编辑、删除确认全部用 `@/components/ui/dialog`。

理由不是"好看"，是这几条硬伤：

| | 原生弹窗 | Dialog |
|---|---|---|
| 字段数 | **只能一个**，三个字段就得连弹三次 | 一个弹窗放整张表单 |
| 校验 | 没有，只能提交后报错 | 即时校验、条件禁用提交按钮 |
| 多语言 | 按钮文字是浏览器自带的，**跟随系统语言、改不了** | 完全受控，走 `t()` |
| 主题 | 不受控，暗色模式下突兀 | 跟随主题令牌 |
| 移动端 | 各浏览器表现不一 | 与其它页面一致 |

标准写法（参考 `frontend/src/app/(app)/sample-items/page.tsx`）：

```tsx
<Dialog open={createOpen} onOpenChange={setCreateOpen}>
  <DialogContent>
    <DialogHeader>
      <DialogTitle>{t('yourModule.dialog.createTitle')}</DialogTitle>
    </DialogHeader>
    <div className="space-y-3">
      <div>
        <Label>{t('yourModule.column.name')}</Label>
        <Input value={form.name} onChange={(e) => setForm((s) => ({ ...s, name: e.target.value }))} />
      </div>
    </div>
    <DialogFooter>
      <Button variant="outline" onClick={() => setCreateOpen(false)} disabled={submitting}>
        {t('yourModule.action.cancel')}
      </Button>
      <Button onClick={() => void submit()} disabled={submitting || !form.name.trim()}>
        {t('yourModule.action.confirm')}
      </Button>
    </DialogFooter>
  </DialogContent>
</Dialog>
```

删除确认同样走 Dialog（`DialogDescription` 里写清后果，如"软删除，可由管理员恢复"），
危险操作的确认按钮用 `variant="destructive"`。

## 6. 文案一律走 i18n，不写死中文

页面里不许出现硬编码中文。文案放模块自己的语言包
`frontend/src/lib/i18n/locales/<module>.ts`，在文件末尾 `registerLocaleMessages` 注册，
并在 `frontend/src/lib/i18n/index.tsx` 里 import 一次。

- 键前缀用模块 code 的 camelCase（`sampleItems.` / `orderItems.`），避免撞键
- 三份语言：`zh-CN`（基准，必须写全）、`en-US`、`es-ES`
- 缺翻译时回退链是 `当前语言 → zh-CN → 键本身`，所以英文/西班牙文可以逐步补
- **后端下发给前端展示的文案也要发 key**：`ModuleCatalogItem` 有 `label_key` /
  `description_key` 字段；前端 `resolveMaybeI18n` 只翻译 `system.` / `common.` /
  `auth.` 开头的值，写死中文会导致切语言不生效（线上就这么发现的）。
  注意 `label` 本身仍保留中文显示名——助手会把它拼进给用户看的自然语言。

`python -m scripts.new_module` 生成的模块开箱就带语言包与 `useT()`，照着改即可。

## 7. 颜色令牌

- 禁止硬编码 `text-slate-950` / `bg-white` / `border-slate-200`（破坏暗色模式与租户主题色）
- 一律用语义令牌：`text-foreground` / `text-muted-foreground` / `bg-muted` / `border-border` / `text-primary`

## 8. 存量页面对齐策略

这套标准是逐步铺开的，不搞一次性大重构。

迁移时机：动到该页面的任何需求都必须顺手对齐本标准（同 db.commit 治理策略）。

## 9. 说明文字的层级（2026-06-12 增补：HintTip 模式）

小字说明（`text-xs text-muted-foreground` 的解释性段落）阅读性差、占空间。分级处理：

1. **用户必须读才能操作的**：保留为正文 `text-sm`，不算"说明"
2. **解释概念/规则的**（如"Skill 是工作方法…由 Loop 判断如何使用"）：
   改为标题旁 `<HintTip content="..." />`（`components/page/hint-tip.tsx`）——桌面 hover 浮层、移动端点按，零依赖（基于 Popover）
   ```tsx
   <CardTitle className="flex items-center gap-1.5 text-base">
     可用 Skill
     <HintTip content="Skill 是 AI 使用的工作方法和质量标准，不是固定阶段。" />
   </CardTitle>
   ```
3. **列表项的动态描述**（item.description）：保留 `line-clamp-2 text-xs`

CardDescription 一句话超过 ~20 字且属于第 2 类时，一律改 HintTip。
（这条原本引用的 harness/apps、harness/settings 是下游分支页面，基座没有；基座里可参照 `system/tenant-settings` 的分节说明写法。）

## 10. 最小字号规范（2026-06-12 增补）

- **绝对下限 12px（text-xs）**：禁止 `text-[9px]/[10px]/[11px]`（已全库清零，PC 和手机都看不清）
- 字号阶梯：12 辅助信息 / 13-14 正文与菜单项 / 14-16 标题；侧栏菜单项 14px（text-sm）
- 新代码 review 时 grep `text-\[1?[01]px\]` 应为零命中

## 11. 质感基线（保持简洁的"去素"手段）

- 顶栏：`sticky top-0 bg-background/80 backdrop-blur`（毛玻璃 + 滚动常驻）
- 主按钮：`shadow-sm shadow-primary/20` + hover 提升（主题色投影随租户主色变化）
- 页头身份锚点：`PageHeader icon={<Icon className="h-4 w-4"/>}` 渲染主题色 chip——每页一个彩色锚点，胜过放大标题
- 已有：三层材质面（侧栏 muted/30、内容 background、卡片 border+shadow）、active 主色指示条、模块色徽标
- 原则：色彩只出现在"身份、状态、动作"三类元素上；面保持中性
