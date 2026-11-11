# realphotos 进程拓扑（AD-001 · REMAIN-GAP R5）

三入口（**不等于** S7 生产部署）：

| 角色 | 命令 | 认领 / 职责 |
| --- | --- | --- |
| process | `python -m scripts.run_realphotos_process_worker` | `heartbeat` / `noop` / `process_image` |
| notify | `python -m scripts.run_realphotos_notify_worker` | outbox → inbox（不经 execution_jobs） |
| cleanup | `python -m scripts.run_realphotos_cleanup_worker` | `inbox_cleanup` / `output_cleanup` |

兼容入口：`python -m scripts.run_worker --worker realphotos_heartbeat` 现与 **process** 同白名单（不再认领 cleanup）。

## systemd 示例（开发机 / 非生产）

见 `docs/mihuanyuantu-v2/deploy-examples/realphotos-*.service`。复制到 `/etc/systemd/system/` 前须改 `User`/`WorkingDirectory`/`EnvironmentFile`；**禁止**当作已授权 S7。

## 端测标记

`R5_WORKER_TOPOLOGY_PASS`：process 不认领 cleanup job；cleanup 不认领 process_image；notify 独立 `--once` 可跑。
