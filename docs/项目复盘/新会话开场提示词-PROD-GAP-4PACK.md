# 新会话开场提示词 · PROD-GAP-4PACK

> **状态（2026-11-20）**：工单已交付并部署。W1/W2/W3-A/W4 + 授权后的 W3-B（并发=2）+ 导入页客户化（#98）均已合入；生产 HEAD `f5bc1f8`。  
> 下文「提示词正文」保留作历史开场模板，**勿再当作未完成工单启动**。残余未授权项见 `03_后续优化与演进建议.md`（R7 / R6）。

> 工单全文：`docs/mihuanyuantu-v2/input/REALPHOTOS-PROD-GAP-4PACK-work-order-2026-11-20.md`  
> 收口/部署证据：`docs/mihuanyuantu-v2/input/REALPHOTOS-PROD-GAP-4PACK-*`

---

## 提示词正文（历史模板 · 勿重复开工）

```text
你是本仓库编码 Agent。请先阅读并遵守：
1) aidevops/SKILL.md（AidevOps 已激活）
2) AGENTS.md（含 CI/CD 双账号与合入纪律）
3) handoff.md → anchor.md → checkpoint.md
4) docs/mihuanyuantu-v2/DEV_INSTRUCTIONS.md + progress.yaml（下一步以 progress 为准）
5) 工单：docs/mihuanyuantu-v2/input/REALPHOTOS-PROD-GAP-4PACK-work-order-2026-11-20.md
6) 背景摘要：docs/项目复盘/03_后续优化与演进建议.md（仅四项可处理缺口，勿扩 scope）

【任务】
基于**已部署**蜜獾原图 v2（公网 https://exif-demo.honeybadgersoft.com），按工单落地四项产品更新（可拆 PR）：

- W2 JSON 导入：补齐 name 必填提示与 failed[] 可读回显（优先，无额外物料）
- W4 管理端：最终检测/处理默认策略只读摘要 + 回退说明（无额外物料）
- W3-A 大批次：队列/预计等待说明或诚实空态（无额外物料）；W3-B 多 worker 并发**仅当管理员本会话明确授权**再做
- W1 URL 导入正式启用：须管理员提供正式 Base URL + 样例对象；无物料则只做代码/文案预备，**不得**宣称生产已正式可用

【硬约束】
- 功能分支：cursor/prod-gap-4pack-9973（或按项拆分 *-9973）；合入 main 仅 PR squash；禁止直接推 main；禁自评自合
- production_billing 保持 false；不改 PASS_SCORE；不默认晋升算法试点；不做 ZIP/OSS 必选/独立 GPS/客户自建上游 Key
- 密钥与真实 .env 禁止入库；生产凭据只读仓库同级 生产物料/
- 每个可交付切片：实现 → 单测/手测证据 → 推分支开/更新 PR；生产部署须管理员确认
- 中文沟通；代码/路径/API/环境标识保持英文

【开工顺序】
1. 用 git/gh 核对当前 origin/main HEAD，对照工单，列出四项「代码改动点 / 配置点 / 阻塞物料」
2. 若 W1 物料未齐：先实现 W2 → W4 → W3-A，并在进度里标明 W1 阻塞项
3. 每完成一项：更新 progress.yaml / checkpoint 摘要（若本轮约定维护），并留下 docs/mihuanyuantu-v2/input/ 下简短证据文件
4. 不要擅自开始 W3-B 或 R7 换代理、R6 改口令（除非管理员另行授权）

【验收口令】
完成切片后在回复中明确：改了什么、证据路径、PR 链接、未做项与原因。
```

---

## 交付对照（已完成）

| 包 | 结果 |
| --- | --- |
| W1 | PASS · 导入正式启用 |
| W2 | PASS · name 提示 + 失败明细；#98 客户文案 |
| W3-A | PASS · 排队预计文案 |
| W3-B | PASS · 受控并发=2（管理员授权后） |
| W4 | PASS · 策略摘要 |
| 未做 | R7 / R6（未授权） |
