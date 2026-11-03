# Worker 与智能体循环：顶层设计

> 面向两类读者：要在基座上写后台任务的人（看 §3、§4）；
> 要判断 harness 往哪走的人（看 §5、§6）。

## 1. 问题从哪来

nextjs-plugins 上已经跑出三个 worker：`harness_worker`、`agent_worker`、`ppt_master_worker`。
读一遍就会发现两件事：

**第一，骨架 90% 是同一份代码。** 三个文件的差异只有"认领哪种任务"：

```
- claimed = await claim_pending_harness_run()
+ claimed = await claim_pending_agent_run()
```

轮询、并发槽、优雅退出、失败隔离、日志字段——全部重复了三遍。

**第二，运维侧是写死的。** `autubuild/scripts/manage.sh` 里三个 worker 的名字硬编码：

```bash
start_backend_worker "$branch" "harness_worker" "app.tasks.harness_worker" "AOJU_HARNESS_WORKER_CONCURRENCY"
```

后果 2026-08-09 真的发生了：停 nextjs-plugins 时 `manage.sh stop` 只杀掉绑端口的 uvicorn，
**三个 worker（510 MB）继续在后台空转**，因为它们是旁路起的、pid 文件对不上。
更麻烦的是新模块的 worker 运维侧根本看不见——不会 start、不会 stop、status 里也没有。

但这两条都还只是**工程重复**。真正贵的是第三条：

**第三，"worker 在做什么"没有定义。** 每个业务模块都要自己回答同一组问题——
一次运行分几步？什么时候算做完？什么时候该停下别烧钱？中间状态存哪？事后怎么复盘？
各写各的结果就是：看起来都在跑智能体，但没有一个能复盘，也没有一个有预算上限。

## 2. 三层设计

| 层 | 文件 | 职责 | 业务能改吗 |
|---|---|---|---|
| L1 运行时 | `app/core/worker_runtime.py` | 轮询、并发槽、优雅退出、失败隔离 | 不能，只实现 `TaskSource` |
| L2 声明与发现 | `app/core/worker_registry.py` | 谁声明了 worker、当前部署该起哪些 | 只写声明 |
| L3 宏循环 | `app/core/agent_loop.py` | 一次运行怎么迭代、何时停、怎么留痕 | 填阶段处理器 |

L1/L2 解决工程重复，**L3 才是这份设计的核心**。

## 3. L1/L2：写一个 worker 需要做什么

在能力包里建 `app/capabilities/<code>/worker.py`：

```python
WORKER = WorkerDefinition(
    code="sample_items_review",
    label="样例条目复核",
    module_code="sample_items",          # 模块没装 → 这个 worker 不会被启动
    task_source_factory="app.capabilities.sample_items.worker:build_task_source",
    default_concurrency=1,
    max_concurrency=4,
)

class SampleItemTaskSource:
    async def claim(self) -> dict | None: ...    # 认领一个待办
    async def run(self, claimed: dict) -> None: ...  # 干活
    def describe(self, claimed: dict) -> dict: ...   # 日志字段
```

完整可运行的样例见 `backend/app/capabilities/sample_items/worker.py`。

**不需要改任何中央文件，也不需要改 manage.sh。** 运维侧读构建期生成的清单：

```bash
python -m scripts.export_worker_manifest     # 生成 backend/deploy/workers.json
python -m scripts.run_worker --list          # 看有哪些、装没装、并发多少
python -m scripts.run_worker --worker sample_items_review --once
```

三条刻意的设计选择：

- **`task_source_factory` 是字符串而不是函数对象。** 发现阶段只读元数据、不 import 业务代码；
  模块没装时那份代码根本不会被加载。这与模块动态加载的原则一致
  （见 `BASE_ARCHITECTURE.md` §5.1）。
- **模块没装就拒绝启动**，`scripts/run_worker.py` 返回非零。否则会出现
  "路由没挂载、菜单没有，却有个进程在轮询它的表"这种荒唐状态。
- **默认并发是 1，不是参考实现的 10。** plugins 里默认 10 没暴露问题是因为 manage.sh 总会
  显式传值；作为基座默认值，"声明写漏一个字段就悄悄起 10 条连接"是个陷阱。

## 4. L3：宏循环——worker 到底在做什么

一次运行 = 若干轮迭代，每轮按选定的**循环模型**依次走它的阶段。

### 两种内置模型

| | PDCA | OODA |
|---|---|---|
| 阶段 | Plan → Do → Check → Act | Observe → Orient → Decide → Act |
| 适合 | **收敛型**：目标明确，每轮质量应变好 | **响应型**：环境在变，要快速重新判断 |
| 收敛在哪决定 | **Check** | **Act**（态势稳定） |
| 典型 | 内容生成后自检重写、方案迭代、复盘 | 告警处置、对话式排障、实时运营 |

两者共享同一个引擎，差别只在阶段序列与语义——是**策略**，不是两套代码。
第三种循环用 `register_loop_model()` 注册，不改内核文件。

### 预算是必填的，不是可选的

```python
LoopContext(budget=LoopBudget(max_iterations=3, max_seconds=60, max_cost=100))
```

三个维度任一耗尽即停。另有一道**绝对轮数上限**（`ABSOLUTE_ITERATION_CEILING`）兜底，
即使预算判定被改坏也停得下来——这条是变异测试逼出来的：把预算检查去掉之后，
测试不是变红而是**挂死**，说明当时全靠预算这一道防线。
挂死的测试比失败的测试难查，失控的循环在生产上是真金白银。

### 轨迹

每个阶段记一条：第几轮、哪个阶段、备注、花费、耗时、是否收敛/中止。
**没有轨迹的智能体循环出了问题只能靠猜**——这是这一层存在的一半理由。

## 5. 与 pi 的对照：我们的 harness 混了两层

pi（github.com/earendil-works/pi）把智能体拆成两层，很值得对照：

| pi | 职责 | 我们的对应物 |
|---|---|---|
| `packages/agent/src/agent-loop.ts` | **微循环**：一个 turn 内 LLM ⇄ tool 往返，直到模型不再调工具 | 散在各处，没有统一实现 |
| `packages/agent/src/harness/` | **编排层**：session 持久化、上下文压缩、steering/follow-up 队列、suspend/resume、telemetry | 混在业务 harness 里 |

pi 的 `agent-loop.ts` 提供的能力很具体：`runLoop()` 内外两层循环、
工具并行/串行执行、`beforeToolCall`/`afterToolCall`/`shouldStopAfterTurn` 等钩子、
完整事件流（`agent_start`/`turn_start`/`tool_execution_*`）。
它的 `harness/agent-harness.ts` 才管 `CompactionSettings`（`reserveTokens`/`keepRecentTokens`）、
三个队列（`steer()`/`followUp()`/`nextRun()`）、`resume()` 与 `SuspendedOperation`。

**关键差别：pi 明确分开了"循环"和"编排"，我们的 harness 把"循环 + 编排 + 业务场景"揉成了一坨。**

我们的 harness（在 nextjs-plugins）是 22,907 行 / 38 个文件，里面同时有：

- 编排：`session_store`、`task_control_service`、`subagent_runtime`、`dag_scheduler`
- 业务：`scene_registry` 与七八个具体 scene、`search_providers/`、`billing`、`course_outline_scene`…

这解释了一个你已经观察到的现象：**ppt-master 跑得好，AI 助手却一直没能往前做。**
因为 ppt-master 的 scene 定义完整，而要新增一个能力，就得进那 22.9k 行里去加 scene——
门槛太高。这不是人的问题，是分层没切开的直接症状。

## 6. 对 harness 的建议：不搬、不重写、按需下沉

**结论先说：harness 保持不动，基座只收契约，新能力直接建在基座上。**

理由：

1. **harness 不该整体进基座。** 里面 scenes / search providers / billing 都是业务，
   搬进来直接违反"基座轻量"这条已经定死的原则。
2. **也不该重写。** ppt-master 在生产上跑得好，重写是拿确定的收益去换不确定的风险。
3. **但新能力不该再进 harness。** AI 助手、以及后续业务模块，直接用基座的 L1+L3：
   声明一个 worker，选一个循环模型，填四个阶段处理器。不必理解那 22.9k 行。

分三步走，每步都可独立停下、都不破坏现有能力：

**第一步（本次已完成）**：基座给出 L1/L2/L3 契约与最小实现，样例可运行。
harness 一行没动。

**第二步（下一轮，可选）**：给 harness 加一个**适配层**——把
`claim_pending_harness_run` / `run_claimed_harness_run` 包成 `TaskSource`，
`harness_worker.py` 换成 `WorkerDefinition` 声明。行为完全不变，
收益是 harness 的 worker 也进入统一的启停与观测。**这一步是纯加法，不改 harness 内部。**

**第三步（更后面，需要单独评估）**：把 harness 里真正通用的编排能力下沉到基座——
参照 pi 的 harness 层，候选是上下文压缩、steering 队列、suspend/resume。
这三件事每个业务模块都会遇到，但**现在还看不出通用形态**，
等基座上跑出第二、第三个 agent 类模块再抽，才抽得准。**过早抽象比重复更贵。**

### 兼容性承诺

- 基座新增的都是**新文件**，没有修改任何既有模块
- `manage.sh` 的改动是**纯加法**：写死的三个 worker 原样保留，
  只是额外读清单；没有清单的分支（含生产 clocart）执行路径与改动前**逐字节相同**
- `WorkerDefinition` 与 `TaskSource` 都不假设任务表结构，harness 那套
  `FOR UPDATE SKIP LOCKED` 的认领语句可以原样包进 `claim()`

## 7. 还没做的（明确列出）

- **微循环没有统一实现。** 基座只收了宏循环。微循环（LLM ⇄ tool）强依赖模型 SDK 与工具协议，
  各分支差异大，现在抽会抽错。等第二个模块落地再看。
- **队列层（L0）没有统一。** L1 只统一了轮询骨架，"任务存哪、怎么认领、崩了算重跑还是判死"
  仍然每个模块各写一套。写这份文档时只有一套实现，抽不出来；到 2026-08 已经有八套且语义互相矛盾。
  盘点与设计见 [TASK_QUEUE_TOP_LEVEL_DESIGN.md](./TASK_QUEUE_TOP_LEVEL_DESIGN.md)（待决策）。
- **没有持久化的循环状态。** `LoopContext.state` 目前只在内存里，进程崩了这一轮就没了。
  要做 suspend/resume 得先有存储契约——属于上面的"第三步"。
- **pi 的 steering（运行中注入消息）没有对应物。** 这是个好能力，但需要先有微循环。

## 8. 相关

- `backend/app/core/agent_loop.py` —— 宏循环内核，文件头有完整的设计说明
- `backend/app/core/worker_registry.py` —— 声明与发现
- `backend/app/capabilities/sample_items/worker.py` —— 可照抄的最小样例
- `docs/dev/flows/NEW_MODULE.md` —— 新模块完整开发链路
- `docs/dev/reference/BASE_ARCHITECTURE.md` §5 —— 模块装配契约（worker 遵循同一套安装语义）
