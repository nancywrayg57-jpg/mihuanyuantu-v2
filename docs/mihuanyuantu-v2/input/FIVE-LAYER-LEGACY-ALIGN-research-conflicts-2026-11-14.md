# FIVE-LAYER-LEGACY-ALIGN · 研究冲突/歧义账本（2026-11-14）

工单：`FIVE-LAYER-LEGACY-ALIGN-SCORE-2026-11-13`  
旧仓 clone：`/home/hbs/hbs-projects/_refs/mihuanyuantu` @ `4a3f2ade0532cab1cd69f01b0b00cdce5c78c5e7`  
原则：先记录冲突，不私自调和；结论须可追溯到原文。

## A. 已核验事实（有原文）

| ID | 事实 | 依据 |
| --- | --- | --- |
| F-HASH-6 | 快照六文件 sha256 与 GitHub clone 一致 | `FIVE-LAYER-LEGACY-ALIGN-legacy-snapshot-sha256.json` vs `sha256sum server/*.ts` |
| F-AI-MISSING-SNAP | 本地原样快照 **无** `aiImageProcessor.ts` | `输入材料/.../原样快照/server/` 目录列表 |
| F-AI-IN-CLONE | clone 含 `aiImageProcessor.ts`（20988 B，sha256=`37ca598b…af5b9fb`） | clone `server/aiImageProcessor.ts` |
| F-ORCH | 旧编排：`processImageWithAI` → `physicalizeImage` → `destroyFingerprints` → `simulatePlatformUpload` → `optimizeImageSize(+EXIF)` | `routers.ts` ~787–854 |
| F-PHYS-FREQ-FIRST | `physicalizeImage` **内部步骤0先频域**，再噪声/暗角/色差/JPEG/锐化 | `imagePhysicalizer.ts` 363–400 |
| F-CA-BUG | 旧色差 composite 结果被丢弃，最终仅 `modulate({saturation:1.02})` | `imagePhysicalizer.ts` 247–264；复用评估 RM 风险表 |
| F-FP-FORBIDDEN | 旧指纹含 hue/saturation 与 rotate/crop | `fingerprintDestroyer.ts` ~228–303；工单/架构禁项 |
| F-L0-STRENGTH-NOTE | 旧注释：DashScope **不直接支持 strength**，靠提示词间接控制；分类默认 strength phone=0.12 / 其它≈0.15 | `aiImageProcessor.ts` 96–98, 135–162 |
| F-L0-PROMPTS | 旧 Layer0 为正/负向 **中文长提示**（噪点/色差/暗角/景深/计算摄影痕迹等） | 同上 `DEFAULT_PROMPTS` |
| F-V2-L0 | 现行 Layer0 用 `gpt-image-2` + 英文短 prompt + `/images/edits`；另有像素 blend α | `five_layer.py` `_maybe_layer0_img2img` |
| F-E2E-SHORT | 真 edits n=12 **gain=3.83&lt;10**；blend0.12 n=6 gain=2.50；α扫档最好≈2.25 | 账本端测纪要；`FIVE-LAYER-LEGACY-ALIGN-e2e-layer0-2026-11-14` 证据文件 |
| F-Q-LOCK | 管理员复裁：Q1≥10 保持；Q4/Q8 放开；Q11 MAD 仅观测；Q12 通过才 PR | constraint-ledger |

## B. 矛盾 / 歧义 / 前置缺失（未调和）

| ID | 类型 | 描述 | 处置状态 |
| --- | --- | --- | --- |
| C-NOTES-Q4 | 文档矛盾 | `compare-notes.md` 仍写色差「禁止（Q4）」；账本写「允许色差」 | 以账本为准；notes 待修订，不得按 notes 回退 |
| C-WO-Q8 | 工单 vs 复裁 | 工单 §3 Q8 默认「本单不做」；聊天复裁「Q8 允许 Layer0」 | 以复裁+账本为准；工单正文未改文件签字区 |
| C-WO-Q11 | 工单 vs 复裁 | 工单默认保持 `FIDELITY_MAD_MAX=3.5`；复裁改为观测不否决 | 以复裁为准；§0.3「放宽须书面」与聊天复裁并存——**聊天复裁视为书面**已入账本 |
| C-LAYER0-SRC | 对照源 | W0 曾以快照为准且缺 AI 文件；现 clone 补齐 | 新增对照源=GitHub clone；须更新 legacy-snapshot 清单 |
| C-LAYER0-API | 模型边界 | 旧默认 DashScope/`qwen-vl-plus`；v2 现行 `gpt-image-2`+aoju edits | **未裁决换模型**；本轮仅允许在现有 generation 合同内移植提示词/强度语义，除非另批 |
| C-LAYER0-GEO | 提示词边界 | 旧 `action` 正向含「轻微桶形畸变」——触及几何 | Q7/工单禁几何；移植时 **必须剥离** 畸变/旋转/裁切措辞 |
| C-LAYER0-COLOR | 提示词边界 | 旧提示含「色彩饱和度轻微衰减/过艳后衰减」——可能被解读为可见调色 | 与「禁可见调色」存在歧义；移植时改为「传感器直出色彩特征」类中性表述，或标 `[NEEDS CLARIFICATION]` |
| C-ORDER | 层序 | 旧 physicalizer 入口先频域；v2 强制 L1→L2→L3… | **禁止回迁**先频域；只移植强度公式 |
| C-SIZE-UPLOAD | 禁项 | 旧 uploadSimulator 平台矩阵 + sizeOptimizer 60%–80% | 架构/工单明确禁止；不可为提分启用 |
| C-FAIL-SILENT | 行为 | 旧 physicalizer/AI 失败常退原图继续 | v2 不得静默成功冒充完成（工单 §6） |
| C-STRENGTH-DEAD | 旧实现 | `processImageWithAI` 计算 `finalStrength` 但 **未传入** `callAIImageEdit` / DashScope body；仅写入返回字段 | 旧 Layer0 效果几乎完全依赖 `DEFAULT_PROMPTS` 正文，而非 strength 数值 |
| C-V2-CA-SAT | 现行代码 | `_apply_chromatic_aberration` 末尾仍做饱和度 ×1.02（注释称 legacy fallback） | 与「禁可见调色」及「禁止搬色差烂桩」存在冲突风险；待方案裁决是否删除 |
| C-FEAS-Q1 | 目标可达性 | 在错误 Layer0（英短提示+edits）下实测上限≈3.83；**旧中文分类提示词尚未在 v2 实测** | 可行性=「有未测高杠杆」≠「已证明可达 +10」 |
| C-PASS-SCORE | 硬锁 | 任何方案不得改 `PASS_SCORE=75` | 锁定 |
| C-DEVHOST | 验证环境 | 工单要求开发机端测；本会话曾在本机 Meta Fake-IP 跑通 | 本机证据可作对齐；正式 W5 标记仍须符合 `DEV_INSTRUCTIONS` 开发机条款 |

## C. 明确禁止回迁（即使提分有效）

1. `fingerprintDestroyer` 的 hue/sat/brightness 总入口与 rotate/crop/resize 回原尺寸  
2. `uploadSimulator` 平台选择/最大边缩放/色彩偏移矩阵  
3. `sizeOptimizer` 0.6–0.8 体积带  
4. `imagePhysicalizer` 内嵌「先频域」顺序  
5. 旧色差烂桩（丢弃 composite + 饱和度 1.02）原样搬迁  
6. 失败退原图却当成功  
7. 整包 Node/sharp 运行时  

## D. 子代理合并状态

| 子代理 | 状态 | 产物 |
| --- | --- | --- |
| [旧仓处理链深研](d5c7bd66-1b73-40b3-a88a-0d44cfff9721) | **完成** | `FIVE-LAYER-LEGACY-ALIGN-subagent-legacy-report-2026-11-14.md` |
| [现行五层缺口对照](d167f4fc-3c9f-4a3c-ab7b-0609819226ce) | 进行中 | 待写 `...-subagent-current-audit-2026-11-14.md` |

### D1. 旧仓报告新加细（并入，不撤销原结论）

| ID | 加细 | 对方案含义 |
| --- | --- | --- |
| C-CA-BUG-GATE | 默认 intensity 下仅焦距 **≤14mm** 才进饱和度×1.02；**24/35/50mm 色差输出恒等** | ALIGN 端测 preset `26mm` 上，旧色差**本来就不改像素**；现行强 CA 不是「对齐旧有效行为」 |
| C-STRENGTH-DEAD | 生产路径 strength **永不进 API**；phone 表内 0.12 也不被路由选用（路由写死 0.15） | 禁止再把 blend α / prompt 里的 Strength 数字当成旧版复现 |
| C-FFT-NOT-POW2 | 旧 1D FFT 无 2 的幂补齐；非常见宽度上变换不正确 | Q6「旧式 1D 对照」须裁决：对齐相位公式，还是对齐这份错误变换 |
| C-PROMPT-GEO-COLOR | action 含桶形畸变；各类含饱和度措辞 | 移植前必须剥离畸变；饱和度从句是否保留 → **主代理裁决**（见可行性稿） |
| C-VERIFY-VS-Q1 | 旧 Gemini 验证指标 ≠ v2 `total_score` 相对 five-layer-2 | 旧仓**不能证明** +10 |

### D2. 主代理对「饱和度措辞」的临时裁决（可审计、可推翻）

- **裁决 A（本轮）**：移植 phone/dslr/mirrorless 正向时，将「色彩饱和度轻微衰减 / 过艳后衰减」改写为「贴近对应机型直出色彩统计，不进行可见的全局调色」；**删除** action 的「桶形畸变」。  
- 依据：Q7 禁可见调色与几何；C-PROMPT-GEO-COLOR；不把歧义提示原样送进供应商。  
- 若端测仍 SHORTFALL，不得以此裁决为借口放宽 Q1。
