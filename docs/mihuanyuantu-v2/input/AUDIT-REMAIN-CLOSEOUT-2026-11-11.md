# 蜜獾原图 v2 · 任务工单

| 字段 | 内容 |
| --- | --- |
| 工单编号 | AUDIT-REMAIN-CLOSEOUT-2026-11-11 |
| 创建日期 | 2026-11-11 |
| 修订 | 2026-11-11：侧聊审计整理；**A 中 FR-028 + ND-012 正式导入本单跳过**；纳入 B 残余与 C |
| 范围 | 侧聊「文档↔源码未对齐」清单中的：**模块 A**（除 FR-028/ND-012）、**模块 B 残余**、**模块 C** |
| 前置 | `main` 已含 REMAIN-GAP W1+W2（#48）；W3/W4（#49 或等价分支）须合入或本分支基于其 tip。开干前：`git fetch origin && git checkout main && git pull`，再切 `cursor/audit-remain-closeout-9973` |
| 不做 | **FR-028 正式 URL 导入 / ND-012 正式供应商**（本单跳过，另单）；真 S7 / 生产收费；OSS 真桶上云；ZIP；Key 轮询；改 `PASS_SCORE`；重做 FR-025；自评自合；清空业务库 |
| 依据 | PRD 2.10：FR-002 / FR-031；架构 1.7：AD-005 §6.2 残余 / AD-011 / front-matter；侧聊审计 2026-11-11；`AGENTS.md` §7.3 CI |
| 管理员裁决（本工单） | ① A 中 **FR-028 + ND-012 暂时跳过**；② 按波次推进，每波先端测；③ **推送前本地对齐 CI**；④ 改配置读取须同改测试；⑤ S7 仍 BLOCKED |
| 验证环境 | 开发机（`hbs@192.168.19.128`）FE `3000` / API `38000` + PostgreSQL + worker；证据建议 `/tmp/audit-remain-closeout-e2e.log` |
| 分支约定 | `cursor/audit-remain-closeout-9973`（Collaborator）；合入仅非作者 Owner squash |

---

## 0. 开干前硬约束

1. 权威顺序：PRD → 架构 → 本工单 → `DEV_INSTRUCTIONS.md`；冲突停问。
2. 密钥只读同级 `生产物料/`；禁止入库。
3. 每开发项须有：**缺口说明 / 如何修复 / 预期结果 / 端测标记**；文档项可无运行时端测，但须 diff 可审。
4. 不得在未授权时启动 S7 真部署或改 `production_billing=true`。
5. 改动落在 `aojuai-main` 与 `docs/`；不扩未点名系统。
6. **推送前本地对齐 CI 门禁（必做）**  
   - 对照 `.github/workflows/ci.yml` 与 `AGENTS.md` §7.3：至少在本地跑通本 PR 会触发的检查，再 `git push`。  
   - 后端改动：`cd aojuai-main/backend && ruff check`（改动范围）+ `DB_DRIVER=sqlite pytest`（相关用例，勿只跑端测脚本）。  
   - 前端改动：`cd aojuai-main/frontend && pnpm typecheck` + `pnpm test`（相关包）。  
   - 文档/流程改动：确认门控文件仍在。  
   - 未本地对齐就推送，**极易**在 Required **`CI gate`** 红灯返工。
7. **改配置读取方式时，测试必须一起改**  
   - 凡把 `os.environ` / 散落 getenv 收口到 `settings`、改 Settings 字段名、改 feature flag 读取路径：同步改所有依赖旧读法的单测与 fixture（含 `monkeypatch`、`env` 夹具）。  
   - 历史教训：只改生产代码、测试仍直读环境变量 → 本地/CI 表现不一致，**CI 易失败**。  
   - 自检：全局搜旧键名与旧读取点；PR 中「配置改动」与「测试改动」同提交或同 PR，禁止拆成「先合代码、后补测试」。

---

## 1. 与上单关系 / 本单纳入范围

| 来源 | 项 | 本单动作 |
| --- | --- | --- |
| 模块 A | FR-002 冻结后禁止新资源获取 | **纳入** |
| 模块 A | FR-028 + ND-012 正式导入 | **跳过**（见 §3 OUT-ND012） |
| 模块 A | FR-031 资源库下载扩展名与同名后缀 | **纳入** |
| 模块 A | NFR-008 / AD-001 进程拓扑 | **不重复**（W3/R5 已交；本单仅回归不抢错队列） |
| 模块 B 残余 | AD-011 Alembic 真源未齐 | **纳入** |
| 模块 B 残余 | AD-005 lease/心跳 + `copy_latch_*` 遗留列 | **纳入** |
| 模块 C | 架构 front-matter / §14 仍写 NOT_IMPLEMENTED 的残留句 | **纳入**（R8 头字段已改，正文残留须扫清） |

已由 REMAIN-GAP 闭合、本单不重开：R1 旁路、R2 分页、R3 outbox/guard 表初迁、R4 路径 A 主码、R5 三分进程、R6 SDK 生成物、R7 OSS stub、R8 头字段 `s0_s6_coded_partial`。

---

## 2. 波次总览

| 波次 | ID | 类型 | 缺口 | 优先级 | 建议端测标记 |
| --- | --- | --- | --- | --- | --- |
| W1 | A1 | 开发 | FR-002 冻结账号禁止上传/导入 | P0 | `A1_FROZEN_NO_ACQUIRE_PASS` |
| W1 | A2 | 开发 | FR-031 资源库下载扩展名 + 同名后缀 | P1 | `A2_LIBRARY_DOWNLOAD_PASS` |
| W2 | B1 | 开发 | AD-011 Alembic 补齐 S3/S5/S6 等差集、收敛 create_all/ensure_* | P0 | `B1_ALEMBIC_HEAD_PASS` |
| W2 | B2 | 开发 | AD-005 残余：lease/心跳或书面降级；退役 `copy_latch_*` 业务读写 | P1 | `B2_COPY_GUARD_RESIDUAL_PASS` |
| W3 | C1 | 文档 | 架构正文残留「NOT_IMPLEMENTED / 未实现」与 front-matter 一致 | P2 | `C1_ARCH_DOC_CONSISTENCY_PASS` |
| — | G0 | 闸门 | S7 / ND-011；FR-028 正式导入 | 阻塞/跳过 | `R9_S7_BLOCKED=true`；`OUT_ND012_SKIPPED=true` |

总闸：

```text
AUDIT_REMAIN_W1_PASS / W2 / W3
R9_S7_BLOCKED=true
production_billing=false
OUT_ND012_SKIPPED=true
```

---

## 3. 明确排除 / 延期（写入证据）

| ID | 项 | 裁决 |
| --- | --- | --- |
| OUT-ND012 | FR-028 正式 URL/JSON 外呼 + ND-012 正式供应商 | **本单跳过**；证据强制 `OUT_ND012_SKIPPED=true`；staging 现状保持，不冒充正式 |
| OUT-S7 | 真 S7 / 生产收费 | 未授权禁止；`R9_S7_BLOCKED=true` |
| OUT-OSS-LIVE | OSS 真桶 | 仅已有 stub；禁止接真桶 |
| OUT-ZIP | ZIP 交付 | 继续拒绝 |
| OUT-POLL | Key 轮询 | 第一版关闭 |
| OUT-PHYS | PASS_SCORE / 五层抬分 | 另单 |

---

## 4. 任务明细

### A1 · FR-002 冻结账号禁止新资源获取

| 字段 | 内容 |
| --- | --- |
| 缺口说明 | 冻结后处理/生图已拦；**本地上传、批量上传、URL/JSON 导入**仍可入库，违反「不能提交新的资源获取」 |
| 如何修复 | 1）`upload` / `upload_batch` / `import_resources`（及对应 API）调用与处理提交相同的冻结检查（如 `assert_can_create_task` 或等价 `ACCOUNT_FROZEN`）。2）前端资源库在 `preReviewFrozen` 时禁用上传/导入入口并提示。3）单测：冻结后上传/导入 403；解冻后恢复；查看/下载仍允许。 |
| 预期结果 | 冻结账号无法新入库；可登录并下载保留期内结果；端测 `A1_FROZEN_NO_ACQUIRE_PASS` |
| 依赖 | 无 |

---

### A2 · FR-031 资源库下载扩展名与同名后缀

| 字段 | 内容 |
| --- | --- |
| 缺口说明 | 资源库前端下载固定拼 `.jpg`；批量下载无同名冲突后缀（任务页已有 `usedNames` 可参考） |
| 如何修复 | 1）按 `contentType` / 源类型映射扩展名（JPEG→`.jpg`，PNG→`.png` 等）。2）同批/勾选下载维护已用文件名集合，冲突追加 `_2`/`_3` 或等价后缀。3）单测或浏览器冒烟覆盖 PNG 与重名。 |
| 预期结果 | PNG 不再被强制改名为 `.jpg`；同批重名可区分保存；`A2_LIBRARY_DOWNLOAD_PASS` |
| 依赖 | 无；勿破坏网关鉴权下载 |

---

### B1 · AD-011 Alembic 真源收口

| 字段 | 内容 |
| --- | --- |
| 缺口说明 | 仅有 `realphotos_0001–0003`；S3/S5/S6 等表仍靠 `create_all` / `ensure_*_schema.py`；`OWNED_TABLES` 过窄；与「迁移唯一真源、禁止启动期建表」不完全一致 |
| 如何修复 | 1）盘点 ORM 表 vs Alembic 差集，新增 `realphotos_0004+`（或等价）覆盖缺表/缺列。2）扩大 `migrations/env.py` `OWNED_TABLES`（或改为前缀策略）。3）端测：空库（或干净 PG）`capability`/realphotos upgrade head → 应用可启动 → 关键冒烟。4）逐步让 e2e **优先 migrate**，`ensure_*` 降为兼容兜底并标注废弃计划；禁止新增「仅脚本 ALTER」作为唯一路径。5）若触及 Settings/环境变量读法，测试同改。 |
| 预期结果 | `alembic upgrade head`（realphotos 链）后具备本单纳入的表结构；`B1_ALEMBIC_HEAD_PASS` |
| 依赖 | 宜在清 `copy_latch` 列（B2）前或同 PR，避免二次迁移 |

---

### B2 · AD-005 残余（lease / 遗留列）

| 字段 | 内容 |
| --- | --- |
| 缺口说明 | 主路径已是 `guard_epoch` + `ACCOUNT_SPEND_BUSY`；但 `lease_until` 恒 `None`（无心跳）；`merchant.copy_latch_*` 列仍在，脚本仍偶清镜像 |
| 如何修复 | **二选一须在 PR 写明（禁止静默）**：① **对齐架构**：acquire/心跳更新 `lease_until`；恢复器废止过期 epoch（最小可用实现即可）。② **书面降级**：架构 §6.2 注明首版不启用 lease TTL，仅 batch 终态释放。同时：业务与端测脚本停止读写 `copy_latch_*`；新增迁移废弃/置空遗留列（或文档标明仅历史兼容、禁止新写）。 |
| 预期结果 | 合同与代码对 lease 策略一致；无双轨业务读写；忙时仍为 `ACCOUNT_SPEND_BUSY`；`B2_COPY_GUARD_RESIDUAL_PASS` |
| 依赖 | B1 迁移窗口；lease 策略若选降级需在 PR 描述引用本条 |

---

### C1 · 架构文档正文一致性

| 字段 | 内容 |
| --- | --- |
| 缺口说明 | front-matter 已是 `s0_s6_coded_partial`，但正文仍可能残留「实现…NOT_IMPLEMENTED」等句（如 §14 表），易误读为完全未实现 |
| 如何修复 | 全文检索 `NOT_IMPLEMENTED` / 「未实现」与生产就绪相关表述；改为与 front-matter 一致：S0–S6 部分已编码；S7/生产收费仍 BLOCKED。 |
| 预期结果 | 新人不会误读「完全未实现」；`C1_ARCH_DOC_CONSISTENCY_PASS`（文档 diff + 检索无冲突句即可） |
| 依赖 | 无 |

---

## 5. 端测与证据

证据文件建议：`/tmp/audit-remain-closeout-e2e.log`（可按波次分段追加）。

最低：

1. **A1**：账号 `pre_review_frozen=true` → 上传/batch/导入拒（`ACCOUNT_FROZEN`）；处理提交仍拒；下载/列表仍通；解冻后上传通。  
2. **A2**：PNG（或非 JPEG）资源下载扩展名正确；两文件同名基名时第二份带后缀。  
3. **B1**：migrate 到 head 后关键表/列存在；应用可启动；冒烟认领或读资产成功。  
4. **B2**：二次复制仍 `ACCOUNT_SPEND_BUSY`；业务路径无 `COPY_LATCH_ACTIVE`；若启用 lease 则过期/心跳有断言，若降级则日志/文档有 `LEASE_TTL_DEFERRED` 类标记。  
5. **C1**：架构文件检索无与 front-matter 冲突的「完全未实现」断言。  
6. **闸门**：打印 `R9_S7_BLOCKED=true`、`production_billing=false`、`OUT_ND012_SKIPPED=true`。

每波通过后才可合入该波 PR（或统一 PR，但证据须分段齐全）。

---

## 6. 交付与合入

1. 分支：`cursor/audit-remain-closeout-9973`（或按波次 `-w1-9973` 等）。  
2. PR 标题示例：`fix(realphotos): audit remain closeout FR-002/031 + alembic/guard residual`。  
3. **推送检查清单（Collaborator 推分支前）**  
   - [ ] 本地已跑本 PR 路径对应的 CI 等价命令（ruff / pytest·sqlite / pnpm typecheck+test 等）  
   - [ ] 若改了 Settings / 环境变量读取：相关测试与 monkeypatch **已同改**并通过  
   - [ ] 无密钥入库；`CI gate` 预期可绿（存量基线问题须在 PR 说明）  
   - [ ] 证据含 `OUT_ND012_SKIPPED=true`（本单未做正式导入）  
4. 合入：仅非作者 Owner squash；Collaborator 不合并、不打 Tag、不部署。  
5. 完成后回写 `progress.yaml` / `wiki.md` / `checkpoint.md` / `handoff.md`；**不**自动开 S7；**不**宣称 ND-012 正式闭合。

---

## 7. 完成定义（DoD）

- [ ] A1 / A2 / B1 / B2 / C1 按裁决完成或书面降级（B2 lease 策略须有记录）  
- [ ] 每波推送前完成本地 CI 对齐；配置读取变更均有测试同改  
- [ ] 端测证据含 `production_billing=false`、`R9_S7_BLOCKED=true`、`OUT_ND012_SKIPPED=true`  
- [ ] 未宣称生产收费 / S7 完成 / ND-012 正式导入完成  
- [ ] 未改 `PASS_SCORE`；未接 OSS 真桶；未做 ZIP  

---

## 8. 建议端测脚本落点

| 项 | 建议 |
| --- | --- |
| 脚本 | `aojuai-main/backend/scripts/audit_remain_closeout_e2e.py` |
| 日志 | `/tmp/audit-remain-closeout-e2e.log` |
| 单测 | `tests/capabilities/realphotos/test_audit_remain_closeout.py`（至少 A1 冻结上传；B2 忙码回归） |
