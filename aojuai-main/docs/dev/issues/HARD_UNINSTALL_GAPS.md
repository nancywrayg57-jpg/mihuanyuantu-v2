# 硬卸载：当前到底做到了哪一层

> 回流说明（2026-08-27，来源 nextjs-plugins <commit> / <commit> / <commit> / <commit>）：文中的模块名与
> "N/15" 计数都是 nextjs-plugins 分支的实测；base 已回流的是**判定语义**——`module_code_is_present()` 三态
> （缺一部分抛 `ModuleInstallationBroken`）、前缀映射保留已卸载模块以 fail-closed、GOV-23 API 契约比对工具。
> GOV-22 真删目录探针（`hard_uninstall_probe.py`）与 plugins 的 15 模块清单强绑定，未回流；base 用
> `tests/test_hard_uninstall.py` 的 speech 删除端到端用例覆盖同一判据。

模块清单把硬卸载定义为"删掉 `code_paths` 里的目录"。这份文档记录**实测**结论，
不记录设想。测量工具 `backend/governance_tools/hard_uninstall_probe.py` 在基座里不存在，
它只在 nextjs-plugins 分支上（整树拷贝后真 `rm -rf`，判据是子进程退出码）。

## 分层现状（2026-08-20 实测）

| 层 | 起点 | 现在 | 卡在哪 |
| --- | --- | --- | --- |
| `app.domain`（模型 + 适配器） | 1/15 | **15/15** | — |
| `app.main`（含路由装配） | 2/15 | **11/15** | 见下 |
| `startup`（再加 `register_tasks()`） | — | **11/15** | 同上 |

## "单独删不掉"不等于缺陷

应用层那 4 个（aippt / harness / notes / assistant）单独删会让**依赖方**起不来。
但 ppt_master 本来就建立在 aippt 之上——依赖是允许的，说不清的依赖才是问题。
正确的口径是**连同 GOV-21 声明的依赖方一起删**，实测：

| 目标 | 一起卸载的模块 | 结果 |
| --- | --- | --- |
| aippt | agents, aippt, harness, ppt_master, training | ✅ |
| harness | agents, harness, training | ✅ |
| notes | agents, aippt, harness, notes, ppt_master, training | ✅ |
| assistant | 连全部 12 个依赖方一起删 | ❌ |

守卫见 `test_module_uninstalls_cleanly_together_with_its_dependents`，
依赖图实时取自 GOV-21 的扫描器，不另抄一份。

### assistant 是例外，且是定性的

即便把 12 个依赖方全删掉也起不来：`automation/assistant_adapter.py`、
`assistant_bridge.py`、`tenant_profile.py` 这些**常在**代码在模块级 import 它。
这与模块目录里 `always_installed=True` 一致——assistant 是内核设施，不是可选能力。
它留在清单里是为了 `table_prefixes`（autogenerate 的排除口径）。
要让它真正可卸载，得先拆掉那 8 处常在引用，属于独立的一件事。

> `startup` 这一层是补测出来的，教训值得单记：卸载 `project_management` 后
> `import app.main` **成功**，却在 `register_tasks()` 时 ModuleNotFoundError——
> 内核在 `register_tasks()` 里静态 import 了业务任务模块。
> **import 成功不等于启动得起来**，只测 import 的探针对这类"晚一步才炸"的问题
> 一律是绿的。现在业务定时任务由各模块自己注册：内核只留扩展点
> `backend/app/core/composition.py` 的 `register_scheduler_jobs()`，
> 下游分支在自己的组合层 `app/plugins/app_wiring.py` 里实现
> `register_plugin_scheduler_jobs()`；纯基座没有 `app.plugins` 包，钩子静默跳过。

两层卡住的是同一批：`notes`、`harness`、`training`、`assistant`、`aippt`，
与 GOV-21 记录的依赖对一一对应。

`app.main` 层原来只有 2/15（public_site 与 speech，它们早就走按需挂载），
唯一原因是 `app/api/v1/__init__.py` 顶部按名字静态 import 各业务 endpoint。
改用 `register_module_router()` 之后与域层持平。

守卫 `backend/tests/governance/test_gov_22_hard_uninstall.py` 在基座里不存在，它在 nextjs-plugins 分支：
域层跑真删探针（约 14 秒），路由层用静态守卫（应用层真删要 42 秒，太贵）。
完整两层实测（同样只在那条分支）：`.venv/bin/python -m governance_tools.hard_uninstall_probe`。
基座这边对应的是 `backend/tests/test_hard_uninstall.py`——只覆盖开关链路（目录项、
`is_module_installed`、门禁、autogenerate 排除），不做真删，局限写在该文件头部。

### `register_module_router` 的判据

它只看**代码在不在**（`module_code_is_present`），不看部署级安装状态。
旁边的 `register_builtin_capability_router` 用的才是后者。

区别不是理论上的：本机当前 `crm` 与 `project_management` 的
`is_module_installed()` 就是 False，而它们的路由今天挂着。换成部署级判据，
路由表会当场少掉一批、403 变 404——那是产品行为变更，
不该作为"修硬卸载"的副作用被顺手带进来。要统一成 404 得单独立项。

> 注意 `backend/tests/test_hard_uninstall.py` 证明的是**开关链路读得对**，
> 不是"物理删掉还起得来"——它把 `BACKEND_ROOT` 指向不存在的路径，源码一行没少。
> 改前真删一遍只有 1 个模块起得来，而那条测试一直是绿的。别用它冒充 GOV-22。

## 未修：父模块卸载后，子域失去门禁（fail-open）

三个业务域是别的模块的子域，却**不在父模块的 `code_paths` 里**：

| 子域 | 父模块 | 归属证据 |
| --- | --- | --- |
| `documents` | `knowledge_base` | `api_prefixes` 含 `/api/v1/documents` |
| `ai_config` | `assistant` | `api_prefixes` 含 `/api/v1/ai-config` |
| `ai_practice` | `training` | 路由 `/ai-practice`、API `/api/v1/ai-practice`、权限 `ai_practice` 三者齐备 |

父模块被硬卸载后，它会从 `MODULE_CATALOG` 里消失（`feature_switches.py`
只收录 `module_code_is_present` 为真的项），**它携带的前缀映射也一起消失**。
子域的代码却还在磁盘上。实测：

```
全量安装：/api/v1/documents/x -> knowledge_base
卸载之后：/api/v1/documents/x -> None
```

解析不到模块的请求会被当成公共/内核 API 放行 —— 能力还在，门禁没了。

### 为什么没有顺手修

看着只是往 `code_paths` 里加两行，实际不是：这三个子域都有**跨模块消费方**。

- `documents` 被 `agents`、`harness`、`knowledge_bases` 引用
- `ai_config` 被 `okr` 引用
- `ai_practice` 被 `training` 引用，其 `ai_model_configs` / `ai_function_models`
  两张表还被 `exam_prep` 用着

直接并进父模块，等于把"潜在 fail-open"换成"卸载父模块即崩"——
并且 `table_prefixes` 必须同步扩，否则卸载后第一次 autogenerate 会生成
DROP TABLE 把数据删掉。所以它得排在 GOV-21 那批跨模块依赖之后做。

眼下这个洞被"API 装配层直接崩溃"挡着（`app.main` 层 0/15），
**一旦修好路由装配，它就会立刻显现**。修路由装配时必须同时处理这一项。

## 部署残缺 ≠ 硬卸载（三态）

`code_paths` 的判据原来是 `all(exists)`：70 条路径里缺 1 条，和干干净净删掉整个模块，
返回值一模一样。后果是**静默的**——该模块的路由不再挂载、worker 不再启动、
菜单里也没有，而进程正常运行、日志里一个字都没有。现象是"这个功能昨天还在，今天没了"。

现在分三态：

| 状态 | 判定 | 行为 |
| --- | --- | --- |
| `code_paths` 全部存在 | 装着 | 正常 |
| 全部不存在 | 已硬卸载 | 不挂载、不启动 worker（运维的明确动作） |
| **只缺一部分** | 部署残缺 | 抛 `ModuleInstallationBroken`，**启动即失败**，报文里列出缺哪些文件 |

残缺在现实里很容易发生：选择性 rsync、按目录裁剪打包、合并冲突后漏提交、
`.gitignore` 误伤。实测本机 `<worktree-root>/nextjs-plugins`（停在
`<commit>`）就缺 `app/domain/course_studio` 与对应 endpoint，却留着
`marketing_training.py`——正是这种状态。把新代码热补丁到这类目录上，
旧行为是整个 training 静默消失，新行为是启动即报错并指名缺失文件。

配套的三层闭合：

- **CI**：GOV-18 检查每条 `code_paths` 在仓库里真实存在（拦住笔误，
  否则一个写错的路径会让该模块**永远**被判成残缺）。
- **运行时**：残缺抛错，完整缺失照常按卸载处理。
- **守卫**：GOV-22 里两条测试分别钉住"残缺要抛"和"全删仍算卸载"，均做过变异验证。

## 升级到本批改动时的破坏性变更（仓库外脚本）

仓库内与部署脚本都已核对无引用，但**仓库外**的 cron、数据修复脚本、Notebook
如果用了下面这些旧入口会直接失败，且**没有保留兼容别名**——
保留别名等于把刚拆掉的硬依赖again接回去：

- `from app.api.deps import TrainingScopeCtx, get_training_scope`
  → `from app.domain.training.api_deps import ...`
- `from app.domain import AgentApp` 等顶层模型导入（`__all__` 从 165 条收敛到 40 条，
  119 个模型属性不再从 `app.domain` 命名空间导出）
  → 从各自的 `app.domain.<模块>.models` 导入
- `import app.domain.all_models` → 该文件已删除（详见下节）

## 部署形态限制

`module_code_is_present()` 判的是真实文件系统路径。zipimport / zipapp、
部分 PyInstaller/PEX 布局会把所有模块误判成未安装（全线判空，不是少认一个）。
本项目不支持这些形态；要支持得改成基于 `find_spec` 的判据。

## `all_models.py` 的来历（已删除）

它曾是 ORM 模型注册的**唯一显式入口**：当时 `app/domain/__init__.py` 刻意保持轻量
（"any import under `app.domain.*` pull in database/config/logging dependencies"），
注册收在一个函数里由启动和迁移显式调用：

```python
def import_all_models() -> None:
    from app.domain import all_models   # 副作用注册
```

**2026-01-23 的 `<commit>` 把设计反了过来**：删掉 `import_all_models()`，
改由 `app/domain/__init__.py` 静态 import。`all_models.py` 从那天起零调用方——
却**又被继续编辑了 5 次**，一直到 2026-05-21（crm / marketing-training / ppt-master
都往里加过模型）。有人以为往它里面加模型就等于注册了。

删除时核实过：它 import 的 20 个模块、74 个符号所注册的表，
全部已在现行的 204 张里，**新增零张**；而且它从来只覆盖 36 个域里的 18 个，
`aippt` / `notes` / `okr` / `assistant` 从未进过它。

它本身就是"往不生效的地方加东西、没有任何报错"的典型样本。

## API 契约比对：别直接 diff openapi.json

FastAPI 的 schema 名称**跨进程不稳定**：同一份代码连跑三次，
`SessionCreate` / `ChatRequest` / `MessageResponse` / `TaskStatus` 这些短名有冲突的模型，
谁拿到短名、谁被降级成 `app__domain__okr__coaching__schemas__ChatRequest`，每次可能不同
（固定 `PYTHONHASHSEED` 也压不住）。`operationId` 同理。

实测代价：本批改动后直接 diff openapi.json，报出 11 条路径"内容不同"，
看着像改坏了契约；逐条展开 `$ref` 才确认 894 条路径结构完全一致。

用 `governance_tools/api_contract.py` 比，它把名字这一层抹掉：

```bash
# 两个 checkout 各跑一次，注意用相同的 .env 与 AOJ_ENABLED_MODULES
.venv/bin/python -m governance_tools.api_contract > /tmp/before.json
.venv/bin/python -m governance_tools.api_contract > /tmp/after.json
.venv/bin/python -m governance_tools.api_contract --diff /tmp/before.json /tmp/after.json
```

`.env` 被 gitignore，旧 checkout 少了它会因 `DEBUG` 默认值不同而凭空多出
4 条 docs 路由差异——这个坑也踩过。

守卫见 `tests/governance/test_gov_23_api_contract.py`。
