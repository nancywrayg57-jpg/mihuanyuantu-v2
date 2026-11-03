# 积分计费的稳定坑（2026-08-26 统一积分策略验收时抓到）

## 1. 并发扣费丢失更新：行锁拿到了，但读的是会话里的旧对象

**症状**：aippt 批量生成 3 页并发预扣，三笔流水 `balance_before` 都是 931.88、`balance_after` 都是 923.88——余额只减了一笔（平台少收）。

**根因**：`CreditService._get_account_for_update` 用 `select(...).with_for_update()` 拿行锁，但同一会话此前已经
加载过该账户对象（`get_user_account` / `init_user_account`），SQLAlchemy 从身份映射返回旧实例、**不刷新属性**，
于是每个并发者都在锁前快照上做加减。

**修法**：锁查询加 `.execution_options(populate_existing=True)`（已修，`credits/service.py`）。
回归：`tests/test_credits_concurrent_consume.py`（各会话先加载账户再并发 consume；无修复时余额纹丝不动）。

**规则**：所有"先锁再算"的余额/配额/计数更新，`with_for_update()` 必须配 `populate_existing=True`，或者在锁后 `refresh()`。

## 2. `--reload` 开发后端会杀掉进行中的 aippt 批量任务，且没有回收

**症状**：unified 批次 3 页图片预扣后任务永远 `running`，预留不退。

**根因**：aippt 批量项是 API 进程内的 `asyncio.create_task`；`scripts/dev_services.sh backend-restart` 起的是
`--reload` 服务，改任何后端文件都会重载 worker、进行中的任务直接消失。ppt_master 有"判死 + 退积分"的
reaper（见 TASK_QUEUE_TOP_LEVEL_DESIGN §3.1），aippt 没有。

**规则**：真实测试跑批量任务期间不要改后端文件；生产用非 reload 进程。待办：给 aippt 批量项加超时判死 + 退预留（P2-4）。

## 3. 预留额要按新口径估足

硬预算只退不追（codex 评审结论）。预留若仍用旧 `credits_per_image=1`，而统一价是 8 分/张，就只能收 1 分并记
`unbilledOverrun=7`。现在 `_unified_reserve_amount` 在 shadow/unified 下按 `模型/尺寸/质量` 或提示词估算 token
取 max(旧金额, 统一预估)。事件的 `unit_key` 也必须与预留时一致（图片客户端 chat 兼容模式 payload 没有
size/quality，要回退到运行时配置），否则预留 8、实际按 `gpt-image-2` 兜底计 4。

## 4. 嵌套结算双计

planner 在子收集器先扣费，事件冒泡到根后被 chat 那笔再计一次。事件带 `settled_tx_id`，任何 consume /
settle / complete 成功后把当前收集器（含冒泡上来的）标为已结算，根动作只对未结算事件计价。收集器**不要在
收集阶段复制/聚合事件**（会破坏父子共享身份），只在输出时压缩。
