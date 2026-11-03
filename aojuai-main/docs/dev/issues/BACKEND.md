# 后端问题（Backend）

> 本文件用于累计后端运行时、SQLAlchemy 异步、事务、性能等问题。

## 强关联规范

- `guide_docs/SERVICE_LAYER_GUIDE.md`
- `guide_docs/DATABASE_TRANSACTION_GUIDE.md`
- `docs/dev/skills/aojuai-sqlalchemy-async/SKILL.md`

## 写入模板

见 `issues/README.md`。


## flush/commit 之后读 ORM 属性会炸（2026-07 下游分支沉淀）

### 症状
异步 service 里 `await db.flush()` 之后直接读 `obj.updated_at` / 其他 server-managed 列，
在 asyncio 下抛 `MissingGreenlet`，接口 500。**同一个根因在 下游分支撞了两次**
（分享链接更新、插话新增），都是"flush 之后马上拿对象去构造响应视图"。

### 根因
`flush`/`commit` 会让被写入对象的属性过期；下次读取需要一次隐式 SQL，
而在 async 上下文里隐式 IO 没有 greenlet 可用，直接抛错。
`server_default` / `onupdate` 的列尤其容易中招，因为值只有数据库知道。

### 做法
- flush/commit 之后要读的对象，先 `await db.refresh(obj)`，或者重新查询。
- 更省事的办法：**在 flush 之前**把需要的值快照进普通变量，构造响应时用快照。
- 判定规则可以静态化：同一个 async 函数里，flush/commit 之后、refresh/重查之前，
  不许读 mapped attribute。

## 内核不许认识业务

**已做成门禁 GOV-14**（`backend/governance_tools/kernel_purity.py`，随
`backend/scripts/check_governance.py` 一起跑）：扫 `app/core/**` 与 `app/infrastructure/**`
的 import，只允许「认证与租户根」那一组域，其余能力域与具体能力包一律报错。

2026-08 复盘时它一上线就抓到四处**层次倒置**（都是历史遗留，不是新引入）：
`core/notification.py` 与 `core/operation_log.py` 其实是各自域的门面、
操作日志中间件同理、`core/scheduler.py` 直接 import 飞书长连接客户端做关停。
处置：门面搬回自己的域；需要内核回调的改成模块**自己注册钩子**
（`core/scheduler.register_shutdown_hook`）。

还抓到一个归属错误：装配机制 `capability_registry/runtime` 一开始放在
`app/capabilities/` 下，导致内核不得不 import 它。机制属于内核，
`app/capabilities/` 只放能力包。

以下写法在下游分支都真实出现过，回流基座时一律改成注册式：

| 反面写法 | 正确做法 |
|---|---|
| `scheduler.py` 里 `from app.domain.<业务> import runner` 注册定时任务 | 提供任务注册钩子，模块自己注册 |
| 通知事件枚举里写死 `SUPPORT_TICKET_CREATED` / `QUOTA_EXHAUSTED` 之类 | 基座只认 opaque topic，事件描述符由模块注册 |
| 配置脱敏函数里硬编码某业务的密钥字段名 | 由模块声明自己的敏感字段 |
| 内核 `Team` 模型上加某业务的配额列 | 配额属于那个业务的表 |
| 安全响应头里写死某业务的分享路径 | 由模块声明自己的 relaxed-embed 路径 |

判据：**把这个内核文件拷进一个只有内核的空基座，能不能编译通过。**

## 可扩展配置用注册表，不要硬编码枚举/key（2026-06 物流分支沉淀）

### 症状 / 偏离
物流分支：数据模型本是平台中立的（承运商 = config 字符串，`LogisticsChannelAccount.platform` = 字符串字段，注释写明"across Shopify, Amazon, eBay … and future platforms"），但**应用层把它锁死成单一供应商**：
- 承运商：`normalize_carrier_adapter()` 是 2 值枚举（`local_preset`/`zda_usps`），加第三家要改枚举 + 调用方
- 渠道：设置视图硬编码 `config.channels.shopify` 这个 key，加 Amazon 要重写整条链路

结果与"当前供应商/渠道只是其一、后续可增"的需求相悖——是"其一"但**不可增**。提交记录看不出，只有对照需求审计才暴露。

### 根因
"模型开放、应用层收口"的常见割裂：底层 schema 用了开放字符串/JSONB，但中间的归一函数/视图构建用了写死的 `if x in {a,b}` 或固定 key 字面量，把开放退化成封闭。

### 修复模式（通用）
把"网关判定"从枚举改成**注册表查找**：
```python
_CATALOG: dict[str, dict] = {}
def register_x(code, *, name, builtin=True): _CATALOG[code] = {...}
def list_registered_x(): return [...]            # 供 UI 列表渲染
def normalize_x(value):                          # 归一 → 注册表校验 → 兜底
    code = fold_aliases(value)
    return code if code in _CATALOG else DEFAULT
register_x("local_preset", ...); register_x("zda_usps", ...)   # 内置
# 未来 FedEx/Amazon：builtin=False 占位，注册即出现在"可选列表"，接通 API 后置 True
```
- 加新供应商 = 一行 `register_x()`，不改枚举/调用方/视图。
- 设置视图输出 `xCatalog` 列表，前端渲染成"可增减列表"（已接入=可配置，占位=即将支持禁用态）。

### 预防
- 审查"模型开放但行为受限"时，定位中间层的 `if x in {固定集合}` 和硬编码 key 字面量——这些是把开放退化成封闭的点。
- 凡"当前是其一、未来要增"的能力（承运商/渠道/支付/通知通道等），从一开始就用注册表，不要先写枚举等以后重构。
- 参考实现在 **logistics 分支**（基座没有这些文件）：`app/domain/logistics/carrier_adapters.py` 的 register_carrier、`config_service.py` 的 register_channel。
  基座里的同类写法见 `backend/app/core/capability_registry.py`（能力包自注册）与 `backend/app/domain/speech/` 的 provider 注册表。
