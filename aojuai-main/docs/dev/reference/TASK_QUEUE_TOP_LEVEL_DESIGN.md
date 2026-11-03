# 任务队列：顶层设计

> 回流说明（2026-08-27）：`app/core/task_queue.py`（QueuePolicy / 认领 / 租约 / `scheduler_job_lock`）与 `WorkerDefinition.queue` 声明已回流 base；base 内置 worker 尚无 DB 队列表，L0 的并发测试依赖 plugins 的 message_relay 表，未随代码回流。SQLite 档 `scheduler_job_lock` 直接放行（单进程）。

> 状态：**L0 已实现，message_relay 已接入**（2026-08-21）。实现见
> `backend/app/core/task_queue.py`，真实 PostgreSQL 并发用例见
> `backend/tests/test_task_queue_concurrency.py`——它依赖 message_relay 队列表，基座里不存在，
> 只在 nextjs-plugins 分支上跑。course_studio 及之后的迁移未动。
>
> 写这份文档是因为要动 `message_relay` 队列的四个已知
> 缺陷之前，发现同样的缺陷在另外七套队列里各有一份。
>
> 前置阅读：[WORKER_AND_AGENT_LOOP.md](./WORKER_AND_AGENT_LOOP.md)——那份定了
> L1（轮询运行时）/ L2（声明与发现）/ L3（宏循环）。本文补的是它下面缺的一层。

## 1. 上一份设计留了个口子，现在这个口子长大了

`WORKER_AND_AGENT_LOOP.md` §6 有一句明确的承诺：

> `WorkerDefinition` 与 `TaskSource` 都不假设任务表结构，harness 那套
> `FOR UPDATE SKIP LOCKED` 的认领语句可以原样包进 `claim()`

当时这是对的：只有一套实现，抽象无从抽起，"过早抽象比重复更贵"。

现在仓库里有 **8 套 DB 队列 + 1 套内存队列**，每套都自己回答了同一组问题：
任务卡住多久算死、认领标记写哪、死了以后重跑还是判死、一个用户能不能霸占所有槽位。
**答案互不相同，而且没有一处地方声明过这些答案是什么。**

## 2. 事实清单

### 2.1 DB 队列（`FOR UPDATE SKIP LOCKED` 认领）

| 队列 | 表 | 重试次数 | 认领标记写在哪 | 僵尸窗口 | 回收后 | 公平性 |
|---|---|---|---|---|---|---|
| `message_relay_dispatch` | `message_relay_deliveries` | `attempts`，上限 3 | 专用列 `claimed_at`，投递中续租 | 300s | **重跑** | 按属主排他（子查询） |
| `course_studio_run` | `course_studio_runs` | 无 | 专用列 `lease_owner`（唯一一处真正的租约持有者） | 900s（下限 120） | 重跑 | 无 |
| `harness_worker` | `harness_tasks` | 无 | `progress_json.claimedBy` | 21600s | 重跑 | 同 session 排他（扫 20 行） |
| `agent_worker`（insight / aippt） | 无专用任务表，状态寄生在 `agent_app_usages.extra` JSONB | 无 | `extra.*.claimed_by` | 21600s | 重跑 | 无 |
| `ppt_master_worker` | `ppt_master_tasks` | 无 | `result.claimedBy/claimedAt`（JSONB） | 1800s | **判死 + 退积分**（见 §3.1） | 同项目排他（扫 20 行 + 锁父 project 行） |
| automation（调度器内联，锁的是 `automation_jobs` 行，**非本表队列**） | `automation_runs` | job 上有 `failure_count` + 退避；run 上无 | 不写 | run 无回收；job 行锁跨执行事务，崩溃回滚后 due job 会重跑 | — | 无 |
| aippt 图片批量（进程内 asyncio） | `aippt_generation_jobs` | 无 | `response_json.claimedAt` | **只在进程重启时** | 重排队 | 租户轮询 |
| 项目管理提醒（调度器内联，**无认领、非 SKIP LOCKED**） | 扫 `..._reminders`，`..._reminder_deliveries` 是发后去重/审计 | 无 | **完全不加锁** | — | — | 无 |

四个不同的僵尸窗口（300 / 900 / 1800 / 21600 秒），三种写认领标记的地方
（专用列 / JSONB 里 / 根本不写），两种相反的回收策略。

### 2.2 调度器任务（APScheduler，7 个 job）

全部 `max_instances=1, coalesce=True`，**无 jobstore，进程内**。
`max_instances=1` 只约束同一个进程；多开一个 API 进程就是多一份定时器。
全仓只有 `poll_message_gateways` 用 `pg_try_advisory_lock(480281904)` 做了跨进程互斥
（`app/tasks/message_gateway_task.py:70-98`），**其余 6 个 job 都假设单进程**。

## 3. 分歧不是风格，是语义

### 3.1 同一个语义写了两遍，其中一遍挂在读路径上

**勘误（codex 复核，2026-08-21）**：本节初版声称 ppt_master 的两个处理器语义相反
（认领路径重跑、收割路径判死），**这是错的**。细读 `service.py:944-966`：
认领路径把 stale `running` 行选出来是为了**判死并退积分**（`_mark_ppt_master_task_timeout_failed`
+ `refund_app_share_task_credits`），与 `expire_stalled_ppt_master_tasks` 做的是同一件事。
ppt_master 自始至终是一致的 at-most-once。初版靠"SELECT 里包含 stale running"就推断
"认领后会重跑"，没有读认领之后的分支——从 SQL 形状猜语义，猜错了。

真正的问题仍然存在，但比初版说的轻：

- **同一个"判死"写了两处**（worker 认领路径 + 读路径的收割函数），改僵尸窗口、
  改退费逻辑要同时记得两处，漂移的温床。
- **其中一处挂在读路径上**（项目详情 `service.py:8639`、任务列表 `:13099`）：
  判死+退费是写操作，由"用户刷新页面"触发写操作本身就是错位；
  两处并发收割同一行时靠 SKIP LOCKED 和退费幂等兜底，正确性是"碰巧"的。

### 3.2 "重跑还是判死"本来就该由业务声明

`message_relay` 重跑是对的：投递有幂等键，重复入队不会重复发。
`ppt_master` 判死也可能是对的：生成一次要烧钱，盲目重跑等于重复扣费。

**两个都对。错的是这件事现在是隐式的**——没有任何地方写着"这个队列是 at-least-once
还是 at-most-once"，它藏在某个 `or_(...)` 条件和函数分支里；同一语义还可能被
复制多份、其中一份挂在读路径上（§3.1）。

注意 at-least-once 的准确含义是**接受外部重复的残余风险**：数据库票据拦得住
旧 worker 写库，撤不回已发出的消息。"外发成功后、结果落库前"崩溃的窗口只能靠
下游幂等键或接收端去重消掉，声明里不该把它说成"崩了重跑是安全的"。

### 3.3 没有心跳，僵尸窗口只能靠猜

除 `message_relay` 会在投递过程中续租 `claimed_at` 外，其余队列**执行期间不写任何东西**，
僵尸判定靠 `coalesce(updated_at, started_at, created_at)` 的年龄。
所以窗口只能往大了设（harness / agent 设到 6 小时）——设小了会把还活着的长任务抢走。
代价是进程真的崩了，任务要卡 6 小时。**有心跳才敢把窗口调小**，这是同一件事的两面。

## 4. 缺的顶层概念

不是"缺一个队列库"。缺的是**每个队列必须显式声明自己的交付语义**，以及一个统一的地方
落这几个字段。归纳出来只有五个问题，每个队列都必须回答：

1. **交付语义**：`at_least_once`（可重跑）还是 `at_most_once`（崩了就判死）
2. **重试上限与退避**：重跑几次、间隔多久
3. **租约**：僵尸窗口多长、执行期间是否续租
4. **公平性**：按什么键排他（属主 / session / 项目 / 无）
5. **准入**：入队时的深度上限（目前只有 `message_relay` 有，因为只有它对外开放入站口）

## 5. 三个方案

### 方案 A：所有队列合并到一张 `tasks` 表

**不推荐。** 各队列的业务字段差异极大（`message_relay` 要存标题正文和逐渠道结果，
`ppt_master` 要关联项目并锁父行，`agent_worker` 的状态干脆寄生在 `agent_app_usages.extra` 里）。
合表要么退化成一个 JSONB 大袋子，要么要写 8 个数据迁移。而且单表会变成写热点。

### 方案 B：共享**列约定 + 认领原语**，各模块保留自己的表（推荐，已按此实施）

三样东西，都是纯加法：

1. **`QueueTaskMixin`**（落在 `app/infrastructure/database/base.py`，和其余 mixin 一处）
   提供 `status` / `attempts` / `claimed_at` / `claimed_by` / `next_attempt_at` 五列。
2. **`claim_one()`**（新文件，`app/core/task_queue.py`）
   一条泛型认领语句：`FOR UPDATE SKIP LOCKED` + 僵尸回收 + 可选公平键排他 + 写租约。
   §2.1 那八种写法坍缩成一次调用。
3. **`WorkerDefinition` 上新增声明字段**（见 §6），把 §4 的五个问题变成必填。

**收益**：新队列不再需要发明语义；旧队列一次搬一个，行为可以逐条对拍。
**代价**：仍然是 8 张表，运维看队列深度要查 8 个地方（可以用一个 UNION 视图收口）。

### 方案 C：只写规范文档，不给代码

**不推荐，但要说清为什么。** §3.1 那个竞态就是在"文档说清楚了"的前提下也会发生的——
它是两个函数各写各的结果，不是没人知道该怎么做。约定必须有一处可执行的实现来承载。

## 6. 声明长什么样

```python
WORKER = WorkerDefinition(
    code="message_relay_dispatch",
    ...
    queue=QueuePolicy(
        delivery="at_least_once",     # 崩了重跑。前提：业务侧幂等
        max_attempts=3,
        retry_backoff_seconds=(0, 30, 300),
        lease_seconds=300,            # 配合执行期续租，才敢设这么短
        renew_lease=True,
        fairness_key="user_id",       # 一个属主同时只占一个槽
    ),
)
```

对照 `ppt_master`：

```python
    queue=QueuePolicy(
        delivery="at_most_once",      # 生成要烧钱，不盲目重跑
        lease_seconds=1800,
        renew_lease=True,             # 昂贵长任务恰恰需要心跳防止被误收割
        fairness_key="project_id",
    ),
```

（判死动作由 `reap_expired()` 承载且只此一处、绝不挂读路径；
初版示例里的 `on_lease_expired` 字段并未实现，按需再加。）

关键点：**`delivery` 没有默认值，必须显式写。** 这正是现在缺的那句话。

## 7. 迁移路径

每一步都能独立停下，都不改变现有行为：

1. **加 L0 契约与实现**，不接任何现有队列。带一套跑在真实 PostgreSQL 上的并发用例
   （僵尸回收、公平性、重复认领），因为这类 bug 在 SQLite / mock 上测不出来。
2. **`message_relay` 先接**——它最新、最小、幂等最完整，出问题影响面最小。
   接完之后 #100 / #101 直接在 L0 里解决，八个队列一起受益。
3. **`course_studio` 第二个**——它已经有 `lease_owner`，语义最接近目标形态。
4. **`ppt_master` 第三个**：把复制两份的判死+退款状态机收成一处，并从读路径挪走（§3.1 勘误后的真问题）。
5. **`harness` / `agent_worker` 最后，或者不动。** 它们在生产上跑得好，
   `agent_worker` 的状态还寄生在 JSONB 里，搬迁要动数据。没有明确收益就先不动。
6. **调度器那 6 个 job**：把 `poll_message_gateways` 里那把 advisory lock 抽成公共装饰器，
   逐个套上。这一步与 L0 无关，可以并行做。

## 8. 顺带暴露的两个结构问题

### 8.1 domain 模块无法声明 worker，只能塞进内核

`discover_workers()` 只扫 `app/capabilities/*/worker.py`（经 `capability_registry`），
**不扫 `app/domain/*/worker.py`**。所以两个 domain 模块的 worker 只能硬写进
`app/core/worker_registry.py` 的 `_BUILTIN_WORKERS`，而那个元组自己的注释写着：

> 内核级 worker：不属于任何可选模块，任何部署都要有。目前为空——

注释和内容已经对不上了（里面躺着 `module_code="message_relay"` 和 `module_code="training"`
两条），这跟 GOV-14 内核纯度也是拧着的。

连带后果：`app/domain/message_relay/worker.py:19` 那份 `WORKER = WorkerDefinition(...)`
**永远不会被发现**，是死元数据。当时没删，只加了一句"两处要保持一致"的注释——
这是把漂移风险写进注释而不是消除它。

**建议**：发现机制扩到 `app/domain/<code>/worker.py`（模块名取自 `MODULE_REGISTRY`），
然后删掉 `_BUILTIN_WORKERS` 里的两条。死声明已在接入 L0 时删除
（`message_relay/worker.py` 现在只留一句指路注释）；发现机制的扩展仍未做。

### 8.2 三个遗留 worker 运维侧看不见

`deploy/workers.json` 里只有 3 个 worker，`harness_worker` / `agent_worker` /
`ppt_master_worker` 都不在其中——它们由 `manage.sh` / `worker_supervisor.sh` 旁路启动。
`WORKER_AND_AGENT_LOOP.md` §1 记的 2026-08-09 事故（停服务时三个 worker 继续空转
510 MB）就是这个结构造成的，那份文档 §6 把"给 harness 加适配层"列为可选的第二步，
至今没做。**这一步是纯加法且不改 harness 内部**，建议提前到 L0 之前做掉。

## 8.5 实现补记（2026-08-21）

按方案 B 落地时比设计稿多出三个事实，记在这里免得下次重新踩：

1. **公平键的子查询在 READ COMMITTED 下真的会失效**，不是理论风险。
   实测：worker A 认领属主 7 的第一条未提交时，worker B 的子查询看不见那行
   `delivering`，照样认领了 7 的第二条。`FOR UPDATE SKIP LOCKED` 挡不住
   （两行无锁冲突）。解法是认领前拿 `pg_advisory_xact_lock`（键=表名哈希），
   把"看快照 → 锁行 → 写状态"整段串行化；只在声明了公平键的队列上加。
2. **用 `asyncio.gather` 起两个认领测不出上面这个竞态**：协程各自等 IO，
   先发的往往已提交，窗口没打开——去掉锁后 gather 版本三连绿。
   要测就得把 A 的事务卡在未提交状态再让 B 认领（见
   `test_a_second_claim_cannot_slip_past_an_uncommitted_one`）。
3. **准入的三个 COUNT 同样要原子**。并发 N 个入队各自数出"还差一条"然后全插进去，
   上限被顶穿 N-1 条。同一把 advisory lock 思路，键用 `<表名>:admission`
   和认领锁分开——准入排队不该等在认领后面。

## 9. #100~#103 重新归位

上一轮 codex 复核开的四个待办，按本文重新判断：

| 编号 | 原描述 | 结论 |
|---|---|---|
| #100 | 中转三级准入原子化 | **本地修**。准入是 `message_relay` 独有的（唯一对外开放的入站口），但接口形状要按 §4-5 写，将来能上提。 |
| #101 | 公平认领在 SKIP LOCKED 下的完整性 | **等 L0**。同样的缺陷 harness 用扫 20 行、ppt_master 用扫 20 行、message_relay 用子查询，三份都不完整。在一处修才有意义。 |
| #102 | 续期提醒逐条提交 + 跨进程互斥 | **可以先做**，而且应该做成 §7 第 6 步的公共装饰器——6 个 job 是同一个洞。 |
| #103 | `channelMode=default` 补前端入口 | **与队列无关**，随时可做。 |

## 10. 明确不做的

- **不引入 Redis / Celery / arq。** 现在的量级用 PostgreSQL 的 `SKIP LOCKED` 完全够，
  多一个中间件就多一个部署依赖和一处故障域。真正需要它的信号是"队列深度持续高于消费能力"，
  那时数据会自己说话。
- **不做远端吞吐限速。** 理由见下游分支 `app/domain/message_relay/schemas.py` 的注释（该域基座里不存在）：
  下游的限额维度（按 IP 还是按用户）我们不知道，按猜的维度限速要么白白压低吞吐，
  要么根本没限对地方。先记录下游的拒绝，让真实限额可被发现。
- **不统一 §2.2 那 7 个调度器 job 的写法。** 它们是定时器不是队列，只缺跨进程互斥这一件事。

## 11. 相关

- [WORKER_AND_AGENT_LOOP.md](./WORKER_AND_AGENT_LOOP.md) —— L1 / L2 / L3，本文是它下面的 L0
- `backend/app/core/worker_registry.py` —— 声明与发现（§8.1 要改的地方）
- `backend/app/domain/message_relay/models.py`（下游分支，基座里不存在） —— 文件头有队列化的动机说明
- `backend/app/tasks/message_gateway_task.py:70` —— 全仓唯一一处 advisory lock，§7 第 6 步的样板
