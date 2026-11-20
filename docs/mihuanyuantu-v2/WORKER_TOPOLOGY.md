# realphotos 进程拓扑（AD-001 · REMAIN-GAP R5 · W3-B）

三入口（**不等于** S7 生产部署）：

| 角色 | 命令 | 认领 / 职责 |
| --- | --- | --- |
| process | `python -m scripts.run_realphotos_process_worker` | `heartbeat` / `noop` / `process_image` |
| notify | `python -m scripts.run_realphotos_notify_worker` | outbox → inbox（不经 execution_jobs） |
| cleanup | `python -m scripts.run_realphotos_cleanup_worker` | `inbox_cleanup` / `output_cleanup` |

兼容入口：`python -m scripts.run_worker --worker realphotos_heartbeat` 现与 **process** 同白名单（不再认领 cleanup）。

## W3-B 受控并发

- 认领：PostgreSQL `claim_one` + `FOR UPDATE SKIP LOCKED`，多槽不双消费；SQLite 条件更新仅适合单测。
- 租约：`PROCESS_JOB_LEASE_SECONDS=1800`，覆盖单张 1.5–3 分钟墙钟，避免并发槽误回收 running 行。
- 开关：环境变量 `REALPHOTOS_PROCESS_CONCURRENCY`（钳位 1–4，**默认 1**）。
- CLI：`--concurrency N`（与 env 二选一，CLI 优先于启动参数默认值来源）。
- 回滚：设回 `1` 并 `systemctl restart realphotos-process`。
- 积分：仍按张冻结/结算/释放；并发只提高吞吐，不合并账本。

## systemd 示例（开发机 / 非生产）

见 `docs/mihuanyuantu-v2/deploy-examples/realphotos-*.service`。复制到 `/etc/systemd/system/` 前须改 `User`/`WorkingDirectory`/`EnvironmentFile`；**禁止**当作已授权 S7。

## 端测标记

`R5_WORKER_TOPOLOGY_PASS`：process 不认领 cleanup job；cleanup 不认领 process_image；notify 独立 `--once` 可跑。
`PROD_GAP_4PACK_W3B_PASS`：并发开关可钳位；lease≥处理墙钟；queueSummary 含 `processConcurrency`。
