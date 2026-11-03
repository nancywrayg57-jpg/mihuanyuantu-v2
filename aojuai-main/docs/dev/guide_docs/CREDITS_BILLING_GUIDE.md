# 积分计费接入指南（统一积分策略，2026-08-27）

> 方案与验收、报价表在 nextjs-plugins 的 方案与报价表文档（业务分支）；
> 稳定坑：`docs/dev/issues/CREDITS_BILLING_PITFALLS.md`。本文只讲"新模块怎么接、旧模块怎么改"。

## 1. 三层结构

| 层 | 位置 | 职责 |
|---|---|---|
| 计量 | `credits/usage.py` | 每次真实的模型/图片/工具/语音调用在**拿到 usage 的那一行**上报一条 `UsageEvent`；`collect_usage()` 收集一次业务动作内的全部事件 |
| 计价 | `credits/pricing.py` + `price_service.py` | 平台 pricebook（`default_price_items.json`，随代码发布）∪ 租户覆盖（`credit_price_items`）；纯函数 `price_usage()` |
| 结算 | `credits/settlement.py` + `credits/billing.py` | 即时结算 / 硬预算预留；`charge_usage_with_pricing_mode()` 按租户 `pricingMode` 分流 |

租户模式 `tenant.config.credits.pricingMode`：`legacy`（缺省，旧算法不变）/ `shadow`（照旧扣费，流水附统一口径结果）/ `unified`（只按费率）。

## 2. 新模块接入（对话类：一次请求一次扣费）

```python
from app.domain.credits.usage import collects_usage
from app.domain.credits.billing import ensure_user_credit_precheck, charge_usage_with_pricing_mode

class MyService:
    @collects_usage("mymodule:reply")          # 1) 入口包一个根收集器
    async def reply(self, *, tenant_id, user_id, ...):
        account_id = await ensure_user_credit_precheck(credit_service=svc, tenant_id=tenant_id, user_id=user_id, minimum=Decimal("0.01"))
        text, usage = await client.chat_with_usage(messages)   # 2) 共享 OpenAIClient 会自动上报事件
        legacy_points = calc_points_from_tokens(...)           # 3) 旧算法金额（legacy/shadow 用）
        await charge_usage_with_pricing_mode(               # 4) 按模式结算；失败不扣
            credit_service=svc, tenant_id=tenant_id, user_id=payer_user_id,
            legacy_points=legacy_points, reference_type="mymodule_reply",
            reference_id=message_id, idempotency_key=f"mymodule_reply:{message_id}",
        )
```

规则：
- **付费人由调用方解析**（分享场景扣创建者还是访问者），结算层不判断。
- **幂等键必须稳定**（业务 id），重试不会双扣；unified 下同键重放返回原流水。
- 直连供应商（不走 `OpenAIClient`）的客户端，在解析 usage 处调用 `record_llm_usage(model=…, usage=<原始 usage dict>, api_type=…, source="<client>")`——**传原始 usage**，缓存/思考字段由归一层细分，不要压成两个数。
- 图片/工具/语音用 `record_unit_usage(kind="image"|"tool_call"|"tts"|"asr", quantity=成功输出件数, model=…, unit_key="operation/size/quality")`。
- 没有任何事件的固定费动作（如出题策略）在 unified 下自动按 `legacy_points` 扣并标 `basis=flat_fallback`。

## 3. 任务类接入（长任务：预留 → 完成 / 失败）

```python
from app.domain.credits.settlement import SettlementContext, reserve, complete, refund_all
ctx = SettlementContext(tenant_id, payer_user_id, reference_type="mytask", idempotency_base=f"mytask:{task_id}", ...)
tx = await reserve(svc, ctx, amount=cap, mode=mode, price_version=version)      # 入队：按上限预扣（:reserve）
... # worker 内 @collects_usage 根收集器里跑任务
await complete(svc, ctx, reserve_tx=tx, mode=mode, price_items=items, price_version=version)  # 成功：只退差额（:complete）
await refund_all(svc, ctx, reserve_tx=tx, reason="failed")                      # 失败/取消：全退（:refund）
```

规则：
- 硬预算**只退不追**：实际超过预留最多收预留额并记 `unbilledOverrun`，因此 unified 下预留额必须按统一价**估足**（图片：模型/尺寸/质量 单价×张数；文本：估算 token×模型价），shadow 下保持旧金额只记录预估。
- `complete` 与 `refund_all` 互斥：已完成不再退已消费部分，已退不再结算。
- worker 进程要有自己的根收集器（`@collects_usage` 或 `collect_usage(root=True)`）；detached 后台任务不要继承请求的收集器。
- 长任务要有僵尸回收（超时判死 + 退预留），参考 aippt `_reap_stale_batch_item_jobs`、ppt_master 判死 reaper。

## 4. 费率与运营

- 平台默认价改 `default_price_items.json`（内容 SHA 即 priceVersion）；租户覆盖走「积分管理 → 计费模式与费率」。
- 匹配：精确模型名 > glob > `*`；命中 `*` 流水标 `fallbackRate`，用它发现新模型没定价。
- 灰度：先 `shadow` 跑一周，看同页签"灰度对账"（覆盖率 / 估算率 / 空模型 / 兜底率 / 差额），再逐租户切 `unified`。

### 4.1 分时费率（rate_schedule）

同一费率项可以按时段乘一个倍率（DeepSeek 谷时/高峰就是这么配的）。时段表存在
`credit_price_items.extra.rateSchedule`，**不加列**；平台默认价在
`default_price_items.json` 里用同名字段 `rate_schedule` 写。

```json
{
  "timezone": "tenant",
  "defaultBand": "off_peak",
  "bands": [
    {"key": "peak", "multiplier": "2", "weekdays": [1,2,3,4,5],
     "windows": [["01:00","04:00"], ["06:00","10:00"]], "priority": 0}
  ]
}
```

- `timezone`：`"tenant"` = 按租户时区（`core/tenant_time.get_tenant_timezone`）；
  也可以写固定 IANA 时区（供应商按自己时区公布谷时价时用 `"UTC"` 之类）。
- `weekdays` 用 ISO 1–7，缺省全周；`windows` 跨零点合法（`["23:00","02:00"]`），
  跨零点部分按**前一天**的 weekday 判定；单个窗口不允许覆盖满 24 小时。
- 多个 band 同时命中取 `priority` 高者，再取倍率大者；都不命中记 `defaultBand`，倍率 1。
- **按事件时间定档，不按结算时间**：`UsageEvent.occurred_at` 是上报那一刻，
  跨时段的长任务每条事件各自定档。
- 预扣要用 `PricingContext(conservative=True)`（`resolve_rate_context(..., conservative=True)`）：
  按最高倍率预留，完成后按真实时段结算并退差额，band 记作 `reserve_max:<key>`。
- 流水明细同时落打折后的 `rate*` 与原价 `baseRate*`，外加
  `rateMultiplier` / `rateBand` / `rateTimezone` / `ratedAt`，对账能还原是哪一档。

### 4.2 硬上限扣费

`charge_usage_with_pricing_mode(..., maximum_amount=X)` 与
`settle_immediate(..., maximum_amount=X)`：实际算出来超过 X 时**只收 X**，不追扣，
差额记 `extra.billing.unbilledOverrun`，结果对象上是
`CreditChargeResult.actual_amount` / `unbilled_overrun`。给"一条分享链接总预算"
这类下游场景用；基座本身不带这种业务，只提供原语。

## 5. 必须遵守的硬规则

1. **行锁读新值**：`with_for_update()` 必须配 `populate_existing=True`（并发扣费丢失更新，见 PITFALLS §1）。
2. **一段用量只归一笔流水**：事件结算后带 `settled_tx_id`；嵌套收集器只打标签不重复计价。
3. **不压扁 usage**：上报点传原始 usage；`input` 含缓存部分、`output` 含思考部分。
4. **不在收集阶段复制事件**（会破坏父子共享身份）。
5. **真实测试批量任务时不要改后端文件**（dev `--reload` 会杀任务）；生产用非 reload 进程。
6. pyflakes 未定义名扫描——运行到才炸的 NameError 必须静态守住（plugins 侧 `tests/test_ppt_master_insert_slide_imports.py`）。
