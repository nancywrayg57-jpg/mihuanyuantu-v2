# Assistant Published Route Workflow

## Goal

为业务模块提供一套可控的 AI 助手接入流程：

1. 自动扫描 FastAPI 路由，生成候选草案
2. 人工确认后写入 publish manifest
3. 将 manifest 编译为 assistant tool schema
4. 仅让已发布工具进入 runtime `toolCatalog`

默认拒绝。存在于后端的 API 不等于自动暴露给助手。

## Pipeline

`APIRoute / Pydantic request model / permission dependency`

-> `scan_api_route_drafts(...)`

-> `AssistantPublishedRouteManifest`

-> `compile_published_route_tool(...)`

-> `lint_published_route_manifest(...)`

-> `toolCatalog`

## Why

直接 runtime 扫全量 OpenAPI 会带来几个问题：

- 内部接口会被误暴露
- delete / public / auth / internal 路由难以统一治理
- 模型看到的契约会过大
- 不同模块会重新回到“边做边补 prompt hack”的状态

因此必须采用 publish-based，而不是 crawl-based。

## Module Integration Steps

1. 先用 `scan_api_route_drafts(...)` 扫描模块相关路由，得到候选清单。
2. 只选择真正需要给助手使用的路由写入模块自己的 `route_manifest.py`。
3. 对 tool 的 `label / summary / resource / field_overrides / requiredWhen / followUpHint` 做业务级修正。
4. 运行 manifest lint，确保字段描述、示例、权限依赖可用于助手理解。
5. 再决定是否把这批 published tools 合入模块运行时目录。

## Recommended File Layout

建议每个业务模块按照统一结构接入：

- `<module>/assistant/adapter.py`
- `<module>/assistant/catalog.py`
- `<module>/assistant/route_manifest.py`

其中：

- `adapter.py` 负责页面上下文、预设、能力源和动作执行
- `catalog.py` 负责当前模块真正向助手暴露的工具目录
- `route_manifest.py` 负责从候选 API 中人工挑选后的 published routes

这三层分开后，才能做到：

- 底层负责发现和编译
- 模块负责业务边界和上线节奏
- runtime 只消费合规发布后的工具

## Field Contract Rules

要让自动编译出来的 assistant tool 可用，后端 schema 需要满足最低要求：

- 每个对助手有价值的字段都应有 `description`
- 用户可直接填写的字段尽量补 `examples`
- 复杂筛选字段要明确搜索维度，而不是只写“关键词”
- 枚举字段要写清语义，必要时在 manifest 里补 `enumOptions`
- 条件必填字段要通过 `requiredWhen` 在 manifest 中显式声明
- 高影响但非阻塞字段，优先通过 `importance / downstreamEffects / followUpHint` 表达

## When To Use Manifest Override

以下情况不要依赖原始 schema，应该在 manifest 中覆盖：

- path 参数需要改成 camelCase 的 assistant 字段名
- 原始字段说明太技术化，不适合直接给助手理解
- 同一个接口只想暴露其中部分字段
- 需要补充 `requiredWhen`
- 需要把某个非阻塞字段标记为高影响字段
- 需要追加 runtime binding，而不是直接映射到 API

## Recommended Next Step

后续每新增一个模块，先做两件事：

1. 补全 schema 的 `description/examples`
2. 先产出 route drafts，再人工选择 publish

这样可以减少 prompt 手写和接口手工维护，同时保持治理边界。

## Minimal Module Flow

对于新模块，推荐按这个顺序落地：

1. 接入 `ModuleAdapterBase`
2. 完成只读上下文和预设
3. 扫描 API 产出 route drafts
4. 建立模块 `route_manifest.py`
5. 编译并 lint published tools
6. 再把 published tools 合入模块 `toolCatalog`
7. 最后才开放 mutation 类工具

这样 `base` 才真正承担“发现能力 + 合规发布路径”的职责，而不是继续依赖人工零散维护。
