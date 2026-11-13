# LIBRARY-ASSET-PURGE · Constraint Ledger

记录时间：2026-11-13（开干基线 `main` = `6a471ac` = #50 squash）  
分支：`cursor/library-asset-purge-9973`

## 硬性要求

| ID | 原文依据 | 执行 |
| --- | --- | --- |
| PRD-93 | PRD §9.3：资源库原图「删除覆盖对象副本」 | `DELETE /assets/{id}` 软删后立刻 `storage.delete(object_key)` |
| ARCH-ORPHAN | 架构：图片删除、孤儿对象扫描与对账 | `cleanup_library_orphans` + cleanup worker kind + admin API |
| SCOPE-LIB | 仅 `upload/` + `generation/` 资源库前缀 | 不扫/不删 `output/`；不动 `__seed__` |
| OUT-TTL | 处理结果仍走 7 天 `output_cleanup` | 本单不改 TTL 语义 |
| NO-LEDGER | 清理不得删账本/检测摘要/任务行 | 只删对象副本 |
| NO-ALEMBIC | 本单不加 `purged_at` | 审计靠 `deleted_at` + `object_key` |
| NO-OSS | OSS 仅 stub | 不接真桶 |
| NO-S7 | 未授权 | 不部署、不打 Tag |
| SELF-MERGE | AGENTS §7 | Collaborator 仅推送开 PR，不自合 |
| CI-LOCAL | 推送前端测对齐 CI | secret_scan + ruff + pytest(sqlite) |

## 已识别边界

| ID | 说明 | 处置 |
| --- | --- | --- |
| SOFT-THEN-PURGE | 主动删除仍写 `deleted_at`（列表/网关过滤） | 同步物理删文件；文件已不在视为幂等成功 |
| ORPHAN-A | 已软删行盘上仍有文件（历史缺口） | cleanup 路径 A 删文件 |
| ORPHAN-B | 盘上 `upload`/`generation` 无任何 asset.object_key 引用 | cleanup 路径 B 删文件 |
| KEEP-LIVE | `deleted_at IS NULL` 的资源 | 永不因孤儿扫描删除 |

## 非目标

- 不混入预设/五层 WIP；不改前端删除按钮文案（仍走同一 DELETE）。
- 不清空客户未删资源。

## 证据闸门

```text
LIBRARY_ASSET_PURGE_E2E_PASS
```

## 执行记录（2026-11-13）

1. 分支 `cursor/library-asset-purge-9973` 基于 `origin/main`=`6a471ac`（#50）。
2. `soft_delete_asset` 写 `deleted_at` 后 `storage.delete(object_key)`。
3. `cleanup_library_orphans`：软删残留 + `upload`/`generation` 真孤儿；跳过 `output/` 与 seed。
4. `JOB_KIND_LIBRARY_ORPHAN_CLEANUP` 入 cleanup worker / `enqueue_cleanup`；`POST /assets/cleanup-orphans`。
5. 本地：secret_scan 通过；realphotos pytest 81 passed；e2e 日志 `/tmp/library-asset-purge-e2e.log`。
