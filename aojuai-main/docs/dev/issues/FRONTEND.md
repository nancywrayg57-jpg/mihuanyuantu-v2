# Frontend Pitfalls

本文件记录 `nextjs-base` 前端构建、路由、权限预加载和页面对接问题。只记录 Next.js App Router + shadcn/ui 当前形态。

## 普通用户打开页面先触发 403

### 症状

- 普通用户能看到页面入口，但进入页面后先打若干 `403`。
- 某些页面会被误判为登录失效并跳回 `/login`。
- 常见于页面首屏无条件加载用户、团队、配置、provider options。

### 根因

前端把受保护 options/config 接口当作免费元数据加载，但后端接口已有 `PermissionChecker(...)`。

### 解决方案

- 前端先用 `hasAnyPermission(session, [...])` 对齐后端权限。
- 无权限时不发请求，清空候选项并禁用相关控件。
- 不要靠 `catch 403` 兜底体验。

参考：`docs/dev/guide_docs/FRONTEND_PERMISSION_OPTION_LOADING.md`。

## 菜单可见但点击后 404

### 症状

- 侧边栏有入口。
- 点击后 Next.js 返回 404。

### 根因

菜单来自后端 `GET /api/v1/menus/routes`，当前前端不做后端 component 到 React 组件的动态映射。`menus.path` 必须与 `frontend/src/app/(app)/**/page.tsx` 对齐。

### 排查

```bash
rg -n '"path"|menus/routes' backend frontend/src
find frontend/src/app -path '*page.tsx' | sort
```

确认：

- 后端 seed / migration 写入的 path 正确。
- 前端存在对应页面文件。
- 当前用户角色确实有该菜单权限。

## `.gitignore` 误伤路由目录

### 症状

新增页面后 `git status` 看不到文件。

### 根因

过宽 ignore 规则可能忽略任意层级同名目录，例如 `logs`。

### 解决方案

- ignore 根目录产物时使用 `/logs` 这类根路径规则。
- 新增页面后用 `git status --short --untracked-files=all` 核对。

## CMS 页面 i18n 欠账（2026-08-09 记，同日已清）

`(app)/cms/` 六个页面（pages / posts / settings / languages / messages / navigation）
从落地起就没走 i18n，约 **155 处硬编码中文**，切到 en-US / es-ES 时仍显示中文。

**已清账**：新增 `frontend/src/lib/i18n/locales/cms.ts`（约 110 个键 × 三语，
通用动词复用核心 `common.*`），六个页面全部改走 `t()`，
GOV-16 的豁免条目**整表删空**，检查仍然 PASS。

清账时顺带抓到两个东西，都比 i18n 本身更值得记：

1. **三处删除确认用的是裸 `confirm(...)`，不是 `window.confirm(...)`**——
   GOV-16 第一版正则只匹配 `window.` 前缀，所以这三处一直没被拦下来，
   而文档里还写着"原生弹窗那条对它们仍然生效"。**检查写窄了比没写更危险**，
   因为它给出的是虚假的安全感。正则已收紧到同时匹配裸调用，
   并排除 `onConfirm(` / `obj.confirm(` / `function confirm(` 这三类误报，
   四种情况都做过变异验证。三处已改为 `AlertDialog`。
2. **`toLocaleString('zh-CN')` 写死在留言列表里**——时间格式不跟随界面语言。
   已改成 `useLocale().locale`。这类"隐式中文"正则抓不到，
   只能靠人读；新页面写日期时间时留意。

> 豁免不是"以后都可以这么写"。新页面一律按
> `guide_docs/FRONTEND_PAGE_SCAFFOLD_GUIDE.md` §5/§6 写，GOV-16 会拦。
