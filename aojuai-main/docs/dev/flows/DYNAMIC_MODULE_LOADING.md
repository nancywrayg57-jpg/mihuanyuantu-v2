# 模块动态加载：开发流程（nextjs-base）

> 面向两类人：
> 1. 在基座上**新开模块**的人 —— 走 §2，默认就是动态的，不用读全篇
> 2. 把**已有分支的存量模块**（比如 nextjs-plugins 里那一堆）改造成动态加载的人 —— 走 §3
>
> 概念定义（三种「未安装」分别意味着什么）在
> `docs/dev/reference/BASE_ARCHITECTURE.md` §5.1，那是唯一权威表，本文不重复。

## 0) 先选层：能力包 还是 内置能力

| 问题 | 选择 |
|---|---|
| 内核（auth/users/roles/menus/teams/orgs/user_groups）之外的任何业务功能 | **能力包** `app/capabilities/<code>/` |
| 别的模块要 import 它才能工作（AI 基座、短信/邮件通道这类被依赖的底座） | 内置能力，并登记 manifest |
| 只是"我们这个部署一定会用" | 仍然是能力包。**"一定会用"不是理由**，装上就是了 |

默认答案是能力包。内置能力现在只剩 assistant / speech / public_site 三个，
且都在 `app/core/module_manifest.py` 里登记了物理边界——新增第四个之前先想清楚，
GOV-18 会要求你把边界写出来。

## 1) 动态加载靠什么成立

四件事缺一不可，缺哪件就在哪一层漏：

| 机制 | 在哪 | 漏了会怎样 |
|---|---|---|
| **自注册发现** | `app/core/capability_registry.py` pkgutil 扫描 | 要改中央文件才能加模块，多分支并行必冲突 |
| **条件挂载** | `register_capability_router()` / `register_builtin_capability_router()` | 未装的模块照样 import、照样注册路由 |
| **物理边界声明** | `app/core/module_manifest.py`（仅内置能力） | 删了代码目录，开关项还在、进程起不来 |
| **独立迁移链** | 能力包 `migrations/` + 独立 `version_table` | 卸载后表跟着核心链一起被管，摘不掉 |

关键点：**条件挂载必须做成"未装就不 import"**，而不是"import 了再判断要不要挂"。
后者省不下任何东西——Python 模块的开销全在 import 那一刻。

## 2) 新模块：默认就是动态的

```bash
cd backend
python -m scripts.new_module my_module --layer pack \
    --route /my-module --entity MyThing --permissions my_module
```

生成物自带自注册声明、独立迁移链、独立 version_table、语言包和前端页面，
**不需要改任何中央文件**。之后照 `flows/NEW_MODULE.md` 往下走。

装卸：

```bash
python -m scripts.capability list              # 看目录与安装状态
python -m scripts.capability db upgrade        # 核心链 + 每条已装能力链一起升
python -m scripts.capability sync              # 幂等对账已装能力的菜单权限等数据
python -m scripts.capability heads             # 每条链恰好一个 head
```

部署级启用靠 `AOJ_ENABLED_MODULES=my_module`（不列 = 不装）。
卸载清表 `python -m scripts.capability db purge my_module`——**破坏性操作，先备份**，
且只对已经从 `AOJ_ENABLED_MODULES` 里摘掉的模块生效。

## 3) 存量模块改造成动态加载（plugins 分支按这个顺序）

一个模块一个 PR，**不要批量改**——每一步都有独立的验证手段，混在一起出问题很难定位。

### 3.1 摸清边界

```bash
# 这个模块的代码都在哪
git grep -l "<module_keyword>" -- backend/app | sort
# 谁 import 它（这些是改造的阻力，也是真正的耦合）
git grep -n "from app.domain.<module>" -- backend/app | grep -v "app/domain/<module>"
```

被内核 import 就是设计问题，先解耦再谈动态加载。参考 GOV-14（内核纯度）的允许清单。

### 3.2 端点改条件挂载

把 `app/api/v1/__init__.py` 顶层的 `from ...endpoints import <module>` 删掉，改成：

```python
register_builtin_capability_router("<code>", "app.api.v1.endpoints.<module>", "/<prefix>", ["Tag"])
```

它只在 `is_module_installed()` 为真时才 `importlib.import_module`。

验证（**必须在子进程里**，同进程内模块已经在 `sys.modules` 里了，验不出来）：

```bash
AOJ_ENABLED_MODULES=none python -c "
import sys, app.api.v1 as v1
print(len([m for m in sys.modules if '<module>' in m]), len(v1.api_router.routes))"
```

前一个数必须是 0，后一个数必须仍然大于 0（内核路由不能被一起干掉）。

### 3.3 登记物理边界（内置能力才需要）

在 `app/core/module_manifest.py` 加一条 `BuiltinModuleManifest`：
`code_paths` / `model_modules` / `table_prefixes` 三项都不能空，GOV-18 会检查。

`table_prefixes` 要写全。漏一个前缀，硬卸载之后那些表就会出现在 autogenerate 的
DROP 列表里。核对：

```bash
git grep -h "__tablename__" backend/app/domain/<module>/ | sort -u
```

### 3.4 把模型 import 从中央文件里摘出来

`app/domain/__init__.py` 和 `alembic/env.py` 里写死的模型 import 是硬卸载的最后一道坎——
删掉模块目录之后，任何 `import app.domain` 都会 `ModuleNotFoundError`，整个应用起不来。
两个文件都改成走 `import_present_model_modules()`。

**判定用的是"代码在不在"，不是 `AOJ_ENABLED_MODULES`。** 这一条容易想反：
如果模型注册跟着环境变量走，同一份 checkout 在不同机器上 autogenerate 会给出不同结果，
开发机上跑一次就能生成一堆 DROP TABLE。部署级开关只决定路由挂不挂载。

### 3.5 迁移与 seed

- 结构迁移：能力包用自己的链（`down_revision=None` + 独立 `version_table`）；
  内置能力留在核心链，硬卸载后**表按设计留着**——内置能力的目标只有"不冗余加载代码"，
  零残留不是目标（见 `reference/BASE_ARCHITECTURE.md` §5.1.1）。
- 菜单权限**三写**（seed / 数据迁移 / 租户创建）共用 `app/domain/menus/reconciler.py`，
  按安装状态过滤。细节见 `flows/MENUS_PERMS_DUALWRITE.md`。

### 3.6 前端

- 路由守卫**不需要你做任何事**：`ModuleRouteGuard` 挂在 `(app)/layout.tsx` 上，
  按构建期生成的声明目录解析路径。只要模块在 catalog 里声明了 `route_prefixes`，
  未安装/未启用时手敲 URL 就进不去。判定逻辑在 `frontend/src/lib/module-routing.ts`
  （纯函数，`frontend/tests/module-routing.test.mjs` 覆盖）。
- 语言包扔进 `frontend/src/lib/i18n/locales/<module>.ts` 并在文件末尾
  `registerLocaleMessages`，然后 `python -m scripts.export_locale_index`。
  **不要手改 `i18n/index.tsx`**，GOV-17 会拦。
- 页面文案一律走 `t()`，弹窗一律用 `@/components/ui/dialog`（GOV-16）。
- 模块开关项由后端 catalog 驱动，前端不要再写第二份硬编码列表。

## 4) 验收（每一条都要有命令证据）

```bash
cd backend
pytest -q                                  # 含 tests/test_hard_uninstall.py
python scripts/check_governance.py         # 10 条门禁，GOV-17/18 与本文直接相关
python -m scripts.export_locale_index --check
python -m scripts.export_module_catalog --check
cd ../frontend
pnpm test                                   # 含 module-routing（路由守卫）
pnpm check                                  # typecheck + next build
```

外加两条只能人工确认的：

- [ ] `AOJ_ENABLED_MODULES=none` 时，这个模块的业务模块加载数为 0
- [ ] 删掉 `code_paths` 里的目录后，`pytest tests/test_hard_uninstall.py -q` 仍然全绿，
      且应用能启动（该测试用 monkeypatch 模拟删除，不会真动仓库）

## 5) 已知陷阱

**循环导入。** `app/domain/__init__.py` 要问"模块代码在不在"，如果它去 import
`feature_switches`，链路会变成 domain → feature_switches → capability_registry →
`app.capabilities.<x>` ——下游能力包的 `__init__.py` 只要 import 一次模型就绕回
`app.domain`，形成半初始化循环。所以 `module_manifest.py` 是只依赖标准库的叶子模块。
**能力包的 `__init__.py` 里只放 `CapabilityDefinition` 声明，不要 import 模型。**

**autogenerate 误删。** 硬卸载后残留表不在元数据里，autogenerate 会提议 DROP。
`alembic/env.py` 的 `include_object` 把残留表和能力包的 `cap_*` 表排除在比对之外。
新增模块时如果自己写了 env，别忘了这一段。

**always_installed 不等于不可卸载。** 它只保证"装着的时候常驻"；
代码被删掉时该模块照样整条消失。assistant 就是这个语义。

**404 而不是 403。** 未安装的模块路径根本不存在，不要为了"友好提示"退回 403——
那等于告诉外部"这里有功能只是关了"。

## 6) 相关文档

- `reference/BASE_ARCHITECTURE.md` §5 —— 装配契约与三种「未安装」的权威定义
- `flows/NEW_MODULE.md` —— 新模块完整开发链路与机器验收清单
- `flows/MENUS_PERMS_DUALWRITE.md` —— 菜单权限三写
- `reference/BASE_CHANGELOG_2026_08.md` —— 改造前后的量化对比
