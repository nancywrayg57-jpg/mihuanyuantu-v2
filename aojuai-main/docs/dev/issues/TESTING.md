# 测试问题

> 本文件累计"测试写了却没起作用"类问题。

## 1. 规则是全仓的，测试却只扫一个模块

**已经发生三次**（记录在 下游电商分支 分支的开发规范里）：

| 规矩 | 定规矩时加了测试 | 后来在哪又犯了 |
|---|---|---|
| 配置走 Settings 不读 `os.environ` | media 模块 | `transform` 的导出目录 |
| 收费金额只由服务端定 | publish | monitors 原封不动，前端还是可编辑输入框 |
| 迁移不许把 `updated_at` 建成 NOT NULL | pricing | plans 又建了一次 |

共同点：**测试的作用域比规矩的作用域小**。规矩是全仓的，测试只盯一个模块，
或者只盯错误的产物（查 ORM 模型挡不住迁移文件里写错，查 service 层挡不住接口层收金额）。

**做法**：
- 扫描目标**动态发现**（遍历目录 / SQLAlchemy registry / Alembic graph / FastAPI routes），
  **禁止维护模块名白名单** —— 白名单一定会漏掉下一个模块。
- 断言"发现集合非空"，排除项必须是带原因的显式 allowlist。
- 加一条**元测试**：临时放一个探针文件，确认扫描器真的发现了它。

## 2. 测试写完全绿，但一个 bug 也抓不到

本仓已出现两次（正则跨不过括号；重写时误删了测试函数本身）。
本轮又出现一次：一条"init_db 不许在已迁移库上 create_all"的测试只扫源码文本，
把 `if 条件` 改成 `if False` 之后它**依然是绿的** —— 因为 SQL 字符串里还有那个关键词。

**硬规则**：**每写完一个检查，注入一次真实违规，确认它变红，再还原。**
在提交信息或报告里写明注入了什么、哪个测试红了。做不到这一点的测试等于没写。

## 3. 纯逻辑单测全绿，一保存就 500

`TenantBaseModel` 不含 `created_by`/`updated_by`，service 传了就炸，
而公式测试根本不走 ORM。

**做法**：新建业务表时必须有一条"模型字段 ⊇ service 写入字段 ⊇ API 请求体字段"的契约测试，
并补迁移契约测试。纯逻辑测试再多也覆盖不到落库路径，而落库失败是用户第一眼就撞上的。

## 4. mock 通过 ≠ live 通过

文案加工的两个 bug（变量取空留下悬空分隔符、正则字符类里未转义的连字符被当成范围）
都是纯逻辑层的，单测全绿，只有真跑一遍才看得见 —— 而它们会直接把半截标题写进用户的店铺。

**做法**：功能上线后必须拿真实数据跑一遍完整链路。

## 5. 测试污染共享中间件

测试不得连接部署配置里的真实 Redis；进程内的模块级 TTL 缓存要在 fixture 里统一清理，
不要让每个测试文件自己记得清。

## 6. 全量跑与单独跑结果不一致

典型症状：某个测试文件在全量收集顺序下 setup 报
`AttributeError: module 'app.core' has no attribute 'xxx'`，单独跑却全过 ——
原因是它用字符串路径 monkeypatch 子模块，依赖别的测试先 import 过。
修法是在该测试文件顶部显式 import 那个子模块，而不是把它记成"既有失败基线"。

## 7. 实例（回流自 nextjs-plugins）

### 7.1 单测经由 remember_json 写真实共享 Redis，TTL 内重跑必失败（缓存投毒）

### 症状
- 带 `remember_json` 缓存的端点测试（如 `tests/test_tenant_profile_feature_switches.py`）单独跑失败：
  mock 的 `TenantService.get_by_id` 未被调用（`requested_tenant_ids == []`），但响应 200 且数据"正确"。
- 隔几分钟再跑又通过；换个顺序跑另一批又失败——典型时间/顺序相关假失败。

### 触发条件
- 测试进程能连上开发机真实 Redis（本仓库 runtime_cache 无 mock，redis 可达时直接写入）。
- 上一次运行（≤ TTL，`tenant_feature_switches:*` 为 180s）已把假租户（42/84 等）的 mock 数据写进 Redis；
  本次 `remember_json` 命中缓存，loader（含被 mock 的 service 调用）整个被跳过。

### 根因
- `app/infrastructure/cache/runtime_cache.py` 是"Redis 优先 + 进程内兜底"，测试没有隔离层；
  `remember_json` 的写入跨进程存活，测试互相投毒且污染共享开发 Redis。

### 修复/预防
- 已修：相关测试开头调用 `invalidate_tenant_runtime_cache(<假租户id>)` 先清缓存（2026-07-17）。
- 规范：凡测试打到带 runtime_cache 的端点，必须先失效对应 key（或 monkeypatch `remember_json` 直通）；
  测试用的假租户 id 也会把假数据留在真实 Redis，选 id 时避开真实租户。
- 同类排查入口：`redis-cli -n 0 --scan --pattern '*tenant_feature_switches*'`（本机 redis 无密码，
  `.env` 里的 REDIS_PASSWORD 与实际服务不一致，不能作为判断依据）。


### 7.2 存量 seed 单测的 mock 清单滞后于 seed 主流程（新增 _ensure_* 未 mock 即假失败）

> 案例来自 **nextjs-plugins 下游分支**：`scripts/seed_product_modules.py` 与
> `tests/test_seed_module_guards.py` 都是那条分支独有的，基座里没有这两个文件。
> 记在这里是因为踩的是**写法**上的坑（全量 mock + 白名单断言），基座的 seed 单测
> （`scripts/seed_data.py` 一线）同样适用。

### 症状
- `tests/test_seed_module_guards.py` 报 `unexpected direct upsert path: /harness` 或
  `'object' object has no attribute 'execute'`。

### 触发条件
- 下游分支的 `scripts/seed_product_modules.py` 主流程新增了 `_ensure_<module>_module` 或
  `_sync_tenant_feature_switches` 等 db 调用，而 guard 测试的 monkeypatch 清单没同步。

### 根因
- 这类测试用"全量 mock + 白名单断言"的写法，seed 主流程每加一步都要同步测试；
  未同步时真实函数拿到 `object()` 假 db 直接崩，或走到未预期的 `_upsert_menu`。

### 修复/预防
- 已修：补齐 `_ensure_ppt_master_module` / `_ensure_project_management_module` /
  `_ensure_crm_module` / `_sync_tenant_feature_switches` 的 mock 与期望集合（2026-07-17）。
- 规范：给 `seed_product_modules` 主流程加新步骤时，同一提交内更新该测试的 mock 清单。


### 7.3 服务模块级 TTL 缓存把上一个测试的 tmp 工作区泄漏给后续测试

### 症状
- `tests/test_harness_executor_service.py` 整文件跑时若干测试失败（文档 versionNo 远大于预期、
  会话查不到），单跑每个测试都通过。

### 触发条件
- `executor_service._WORKSPACE_PATH_CACHE`（模块级 dict，30s TTL，键为 tenant/user）在同进程
  内跨测试存活；多个测试用相同 (tenant_id=7, user_id=9) 但各自的 tmp_path 工作区。

### 根因
- 第一个测试解析的工作区路径被缓存，30 秒内后续测试直接命中，读写到前一个测试的 sqlite。

### 修复/预防
- 已修：该测试文件加 autouse fixture 逐测试 `_WORKSPACE_PATH_CACHE.clear()`（2026-07-17）。
- 规范：给 service 加模块级缓存时，同一提交里检查相关测试是否共享 (tenant,user) 键并补清理
  fixture；测试间尽量使用不同 tenant/user id。
**做法**：
- 扫描目标**动态发现**（遍历目录 / SQLAlchemy registry / Alembic graph / FastAPI routes），
  **禁止维护模块名白名单** —— 白名单一定会漏掉下一个模块。
- 断言"发现集合非空"，排除项必须是带原因的显式 allowlist。
- 加一条**元测试**：临时放一个探针文件，确认扫描器真的发现了它。
