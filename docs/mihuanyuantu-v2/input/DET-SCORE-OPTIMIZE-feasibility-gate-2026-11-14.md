# DET-SCORE-OPTIMIZE · 可行性门禁（主代理交叉裁定）

日期：2026-11-14  
交叉来源：
- [消融/门禁草案](4bc69865-36ae-444b-b8a2-3fdbf7a33d5f) → `DET-SCORE-OPTIMIZE-subagent-ablation-plan-2026-11-14.md`
- 既有旧仓冲突账本 `FIVE-LAYER-LEGACY-ALIGN-research-conflicts-2026-11-14.md`（`C-CA-BUG-GATE` / `C-STRENGTH-DEAD`）
- 主代理库表 + Layer0 async 复现（DET 账本 F-*）
- 旧仓杠杆子代理 [Grok 重派](94c69ea2-6860-4407-84be-9f86077d0296) → `DET-SCORE-OPTIMIZE-subagent-legacy-levers-2026-11-14.md`（门禁后补交叉，见下「后补核对」）

## 裁定

| 项 | 裁定 | 依据 |
| --- | --- | --- |
| 编码门禁 | **OPEN_PARTIAL** | 消融稿 §5；仅缺陷修复 + 旧有效像素对齐 |
| Q1 可达 | **UNPROVEN** | C1 gain=1.00；英短最好 3.83；OPEN≠已证明 +10 |
| PASS_SCORE | **75 不改** | H-PASS / Q10 |
| A Layer0 async | **允许** | worker running loop 上 `asyncio.run` 静默失败；修法见消融 §1.1（禁止同 loop 死等） |
| D Layer0 默认 | **允许**（与 A 同 diff） | `ALIGN_LAYER0_IMG2IMG` 默认 `auto`→`0`；扫档显式 `=1` |
| B 色差近零 | **允许** | 推翻 ALIGN 门禁句「保留现行通道错位」；对齐 `C-CA-BUG-GATE` 红线内残差（各焦距有效 shift=0）；**禁止** `saturation×1.02`；**禁止**中间档提分扫档；保留焦距表 |
| C 降光学/噪声/频域 | **关闭** | 未证 P-V3-OVERDRIVE；不进本 diff |
| E 生产切 v2 | **关闭** | `C-PIPE-V2-HEMOSTASIS`；`PIPELINE_VERSION` 保持 `s2-five-layer-3` |
| F 换模型/改分/指纹 | **禁止** | H-PASS / H-FP |

## 白名单（编码子代理仅此范围）

1. `five_layer.py`：`_maybe_layer0_img2img`（及若选向上传递时的 `run_five_layer` async）；`_CA_INTENSITY` / `_apply_chromatic_aberration` 仅使默认 shift&lt;1 早退；**不改**光学/噪声/频域常量、提示词、`PIPELINE_VERSION`、焦距表。  
2. `config.py`：`ALIGN_LAYER0_IMG2IMG` 默认 → `"0"`。  
3. 若选「向上 await」：`s1_processing._five_layer_jpeg` 仅加 await；相关测试/脚本仅补 `asyncio.run`/`await`。若选「它线程 asyncio.run」则**不改**调用处。  
4. `test_s2_five_layer.py`：running-loop Layer0；flag=0 不改像素；8mm/26mm CA 恒等；保留 `PASS_SCORE`/`PIPELINE_VERSION` 断言。

## 主代理对冲突的书面裁决

| ID | 裁决 |
| --- | --- |
| C-PRIOR-GATE-CA | **推翻**「不改 shift / 保留通道错位」——该句属 C1 提示词轮；本轮证据为 v3 短焦可见 CA 伤分且旧有效近零 |
| C-Q4-VS-CA-GATE | Q4 读为「允许保留 CA 函数与焦距表」；**默认有效像素恒等**（红线内旧残差）。若管理员书面要求保留可见错位，再关 B |
| C-Q1-STILL-OPEN | 本 OPEN 不承诺 Q1；端测 SHORTFALL 则停止加码，回管理员改裁 |

## 退出条件

- 单测绿（白名单测试）→ 本地真 Gemini 消融 R1/R2（协议 W）至少留证 → 再视情况 R3  
- 合同集协议 C：`gain≥10` 且真 Gemini → 才可 `ALIGN_W5_E2E_PASS` / 谈 Q12  
- 否则 SHORTFALL：**停止加码**；不得改 PASS_SCORE；不得自评自合开 S7  

## 编码授权

管理员本轮指令：「确认可行后再由子代理执行更新」。本文件即为确认。  
授权子代理：**仅白名单**；**暂不推送**（沿用管理员「暂不推送」直至主代理另裁）；同步更新 `handoff.md` / `checkpoint.md` / `progress.yaml`。

## 后补核对（legacy-levers 完成后）

来源：[旧仓提分杠杆](94c69ea2-6860-4407-84be-9f86077d0296) · Q1 结论 **UNPROVEN**（与本门禁一致）。

| 杠杆 ID | 与 OPEN_PARTIAL 关系 |
| --- | --- |
| `L-CA-NEARZERO` | **已在白名单 B** |
| `L-ASYNC-AWAIT`（含禁 `L-SILENT-OK`） | **已在白名单 A**；失败须打日志 |
| `L-OPTICAL-BACKOFF` | 报告标允许，但属消融 R4 / 候选项 C → **本轮仍关闭**（不扩白名单） |
| `L-NOISE-RANK` | 同上 → **本轮关闭** |
| `L-REF-NATIVE` | 条件未测 → **本轮关闭**；仅当 R1–R2 后 reason 仍指文字/结构且主代理另开测量 |
| 禁止表（指纹/平台/体积/先频域/烂桩/换模型/改分） | **维持禁止** |

**不因后补报告扩大本轮 diff。** 白名单实施完成并消融留证后，若仍 SHORTFALL，再按报告消融序 2→5 另开测量门禁。
