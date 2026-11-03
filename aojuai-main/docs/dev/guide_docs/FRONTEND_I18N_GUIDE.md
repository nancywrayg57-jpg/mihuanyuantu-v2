# 前端多语言（i18n）指南（2026-06-12 确立）

> 适用于 nextjs-base 及全部下游分支。架构与语言包写法在 base 与分支间保持同构。
> 当前支持：`zh-CN`（基准）/ `en-US` / `es-ES`。

## 1. 架构

```
src/lib/i18n/
├── registry.ts          # 注册表：SUPPORTED_LOCALES、translate、translateMenuTitle、registerLocaleMessages
├── index.tsx            # LocaleProvider / useLocale / useT（含 tMenu）；静态导入各分支语言包
└── locales/
    ├── zh-CN.ts         # 核心包·基准语言（壳层文案；菜单标题 zh 无需登记）
    ├── en-US.ts         # 核心包·英文（含 menu.* 基础菜单译文）
    ├── es-ES.ts         # 核心包·西班牙文
    └── system.ts        # 模块语言包（基座里的参考实现）
```

**查找顺序**：当前语言 → `zh-CN` 兜底 → 键本身（保证永不渲染裸键）。

## 2. 三类文案的翻译方式

| 类型 | 写法 | 示例 |
|---|---|---|
| 组件内文案 | `const t = useT()` + 业务前缀键 | `t('logistics.ship.title')` |
| 非组件函数（格式化器/模块级 map） | `translateActive(key)`（读取当前语言，组件需有任一 useT 订阅以触发重渲） | statusText 状态映射 |
| **后端菜单标题**（DB 存中文） | `tMenu(title)`，语言包登记 `menu.<中文原文>` 键 | `'menu.发货列表': 'Shipments'` |

菜单标题方案说明：DB 不存多语言列，**以中文原文为键**做客户端映射——零迁移成本、未登记标题原样显示、新菜单不会出现裸键。壳层（app-layout）的分组/菜单/收起态飞出层已全部接 `tMenu`。

## 3. 模块语言包写法（照抄 `frontend/src/lib/i18n/locales/system.ts`）

1. 新建 `src/lib/i18n/locales/<module>.ts`：
   ```ts
   import { registerLocaleMessages } from '../registry'
   const zh = { '<module>.xxx.title': '中文', ... }          // 业务键：模块前缀
   const en = { '<module>.xxx.title': 'English', ...,
                'menu.中文菜单标题': 'English Menu', ... }    // 菜单键：menu.<原文>
   const es = { ... }
   registerLocaleMessages('zh-CN', zh)
   registerLocaleMessages('en-US', en)
   registerLocaleMessages('es-ES', es)
   ```
2. 在 `src/lib/i18n/index.tsx` 顶部追加一行静态导入：`import './locales/<module>'`
3. 组件接线：页面组件 `const t = useT()`；状态/标签映射走 `translateActive`
4. 后注册覆盖先注册：分支可覆写核心键（慎用，注明原因）

## 4. 硬规则

- **zh-CN 是唯一基准**：新增文案先写 zh，en/es 缺失自动回退 zh，禁止只写 en
- 业务键必须带模块前缀（`logistics.*`），禁止裸键/通用键塞业务文案
- 菜单键只用 `menu.<中文原文>`，原文必须与 DB/seed 中的 title 逐字一致（含空格）
- 新增语言：registry.ts 的 SUPPORTED_LOCALES + LOCALE_LABELS + 新核心包文件 + 后端 `tenant_profile.validate_default_locale` 白名单，四处同步
- 回迁规则：核心包与 registry 属于 base 设计核心，分支只新增 locales/<module>.ts，不改核心包结构

## 5. 验收

- 切换语言后：侧边栏菜单、顶栏、已接线页面标题/状态即时变化（无需刷新）
- `localStorage.removeItem('aoju.locale')` 后刷新：跟随租户默认语言（租户设置·品牌与语言）
- 三语下无裸键（`logistics.status.xxx` 字样出现即为漏登记）
