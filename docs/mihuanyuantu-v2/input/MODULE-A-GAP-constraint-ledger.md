# MODULE-A-GAP-2026-11-10 · 约束台账（开干前）

依据：工单原文、PRD 2.10、ND-012/033、架构 1.7、AGENTS.md。本文件只记录核对结果，不发明新需求。

## 已识别冲突 / 歧义 / 前置条件

| ID | 类型 | 原文依据 | 处理 |
| --- | --- | --- | --- |
| C1 | 冲突表象 | PRD FR-028/FR-003/ND-012：缺正式供应商证据时不得真实外呼；工单管理员裁决①：临时图床允许联调 | **不私自调和为「正式已齐」**。采用工单路径：`formalSupplier=false` + `stagingAllowed=true` + 环境旗标；`gap_note` 明示不得宣称 ND-012 正式闭合。正式 ND-012 仍 PENDING。 |
| C2 | 命名 | 架构写 `rp_provider_usage`；仓库物理表一律 `cap_realphotos_*` | 物理表名 `cap_realphotos_provider_usage`；语义对齐架构字段。证据日志写明映射。 |
| C3 | 迁移链 | 工单写「Alembic 业务链」；现有 realphotos 表均靠 ORM + `create_all`（无独立 alembic 版本） | **[DECLARED DEVIATION]** 跟随既有 realphotos 惯例：新增 ORM 模型，端测/`create_all` 建表；不伪造不存在的 alembic 业务链。 |
| A1 | 策略歧义 | 工单 A1.4：逐条失败 vs 整单；推荐逐条；PRD FR-003 不合格逐张拒绝合格继续 | **选定策略 `per_item_continue`**，写入证据日志。101 条仍整单拒（PRD）。 |
| A2 | 单价前置 | 工单：配置表或物料登记；仓库尚无单价物料段 | 环境变量 `REALPHOTOS_UNIT_COSTS_JSON`（本机可读、不入库密钥）。缺单价 → `cost_status=unavailable`，汇总 `cost=null`，禁止假 0。 |
| P1 | 前置 | 导入 API 现状未注入 `CurrentUser`/`TenantCtx`，无法入库归属 | 本工单补齐租户/账号入参；无授权旗标仍 `SERVICE_NOT_CONFIGURED`。 |

## 硬性禁止（工单 / AGENTS）

- 不做 S7；`production_billing=false`
- 不改 `PASS_SCORE`；不清空业务库；不自评自合 PR
- 不做 OSS 真切换、外部 geocoder、AC-009 种子实现
- 禁止 SSRF（仅 allowlist 主机 + `/images/` 路径）
- 禁止用客户积分倒推上游成本
- 禁止把临时图床写成正式供应商已验收

## 跳过项证据标记（实现于总端测）

- `AC009_SKIPPED=true reason=gpt-image-2_no_seed`
- `FR012_PRE_REVIEW_WIRED=true code_change=false`
- `OSS_IMPL_OUT_OF_SCOPE=true`
- `GEOCODER_OUT_OF_SCOPE=true`
