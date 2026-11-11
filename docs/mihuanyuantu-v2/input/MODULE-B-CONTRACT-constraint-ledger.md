# MODULE-B-CONTRACT-2026-11-10 · 约束台账

依据：工单原文、PRD FR-033/010/011、架构 1.7、物料清单、AGENTS.md。

## 开干前核对

| ID | 类型 | 原文 | 处理 |
| --- | --- | --- | --- |
| C1 | 门闸 | B2 未取得「支持尺寸控制」书面/接口证据前不得标 B2 完成 | 先 B2-G；物料密钥文件**无**尺寸合同条款 → `B2_G_supplier_doc_checked=false`，须向管理员索取；同时做探测 |
| C2 | 禁止 | 适配器不得静默改写客户请求尺寸再宣称已按尺寸交付 | 保持 `sizeRemappedByAdapter=false`；UI 已展示请求/实际 |
| C3 | 排除 | OUT-SCORE / OUT-ND011 / OUT-AC009 / OUT-ND012-FORMAL | 仅写证据，不实现 |
| C4 | 上线 | `production_billing=false`；`s7_started=false` | 不得因本单改放行 |

## B2 判定规则（工单原文，不放宽）

- `SUPPORTS_SIZE_CONTROL=true`：合同写明支持 **且** 探测 actual==requested（或批准映射表内一一对应）
- `false`：合同写明不支持，**或** 探测请求≠实图且无批准映射表
- `inconclusive`：缺合同且探测不稳定 → 停问，不得进 B2-X

## 物料检索结果（本机，2026-11-11）

- 文件：`生产物料/蜜獾原图v2-生产物料.md` 存在（仅密钥段落 + 服务器备注）
- **未发现** size / width×height 枚举、忽略/报错/回落策略的书面合同句
- 故：`B2_G_supplier_doc_checked=false`；已在本工单执行中向管理员索取（见进度/PR）；探测仍按工单执行
