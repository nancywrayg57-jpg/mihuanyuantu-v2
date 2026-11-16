# 蜜獾原图 v2 · 任务工单

| 字段 | 内容 |
| --- | --- |
| 工单编号 | `REALPHOTOS-UI-POLISH-2026-11-15` |
| 创建日期 | 2026-11-15 |
| 提出人 | 管理员（侧会话规划） |
| 执行角色 | 主代理拆单与审计；Collaborator 子会话实现；Owner 审合（**不得自评自合**） |
| 建议分支 | `cursor/realphotos-ui-polish-9973` |
| 建议 worktree | `/home/hbs/hbs-projects/mihuanyuantu-v2/.worktrees/realphotos-ui-polish`（或现有干净 worktree） |
| 基线 | 开干前 `git fetch` 取当时 `origin/main` tip；禁止在脏主树或 DOF 实验分支上改样式 |
| 不做 | S7；生产收费；改 PRD 信息架构/菜单；改 `PASS_SCORE` 默认；营销落地页式重设计；为每字段堆卡片；发明新业务能力；自评自合；密钥入库 |
| 证据总日志 | `/tmp/realphotos-ui-polish-e2e.log`（须含 `T1_E2E_PASS`…`T4_E2E_PASS` 与汇总 `REALPHOTOS_UI_POLISH_E2E_PASS`） |
| 红线 | 样式**延续 aojuai 底座**（HSL token / 现有主题变量）；IA 对齐 `prototype/`；列表优先表格；中文运营工具密度 |

---

## 0. 背景与目标

### 0.1 现状

- 前端功能页已接近原型交互，但视觉偏「线框 + 轻抛光」：裸 `border px-2 py-1` 输入、按钮 class 复制粘贴、表格无统一表头/悬停/状态色。
- `realphotos-surface.css` 仅覆盖圆角与 hover，组件体系统一性不足。
- **任务详情**弹窗内「基本 / 积分 / 失败 / EXIF·GPS / 检测报告」等模块仅靠小标题分隔，同屏报告模块之间区分弱，正式感不足。

### 0.2 目标（管理员确认）

1. 视觉升级为**成熟的中文 B2B 运营后台**，而不是营销站或另一套设计语言。
2. **样式延续 aojuai 底座风格**（颜色、圆角、边框、字体阶梯、focus ring 均基于现有 CSS 变量；在 `.realphotos-shell` 内收紧与扩展，不另起紫渐变/大阴影主题）。
3. 布局与信息架构继续对齐 `prototype/`：**不改菜单顺序与主流程**；表格优先、弹窗承载详情/处理。
4. **任务详情页的具体任务表单/详情面板必须同步改样式**；**同一份报告内不同模块内容须相互区分**（分区边框/底色/标题条，一眼可分块阅读）。

### 0.3 成功标准（目视 + 合同）

- 登录后主路径页（工作台、图片资源、批量原图、任务详情）观感一致，不再像离线 HTML 原型草稿。
- 任务详情「详情」弹窗：各报告模块有清晰分区；检测报告与账务/失败/GPS 不混成一长段纯文本。
- 无信息架构漂移；无无意义多卡片瀑布；深色模式/营销 hero 不引入。

---

## 1. 约束账本（摘要）

| ID | 类型 | 内容 |
| --- | --- | --- |
| C1 | 硬约束 | **延续 aojuai 底座风格**；禁止另起独立视觉品牌体系 |
| C2 | 硬约束 | IA / 角色菜单 / 主流程对齐 `prototype/` 与现行 PRD；冲突听 PRD |
| C3 | 硬约束 | 运营工具密度：列表表格优先；不为每个字段堆卡片 |
| C4 | 硬约束 | 任务详情弹窗内报告模块**必须相互区分**（至少：基本、积分、失败、EXIF/GPS、检测报告） |
| C5 | 硬约束 | 不改业务 API 合同、不改状态机、不改积分规则、不改默认 `PASS_SCORE` |
| C6 | 建议 | 先抽共享组件再换肤；禁止各页继续复制超长 Tailwind 按钮串 |
| C7 | 禁止 | 自评自合；S7；密钥入库；清空业务数据 |

完整约束可在实现时写入 `docs/mihuanyuantu-v2/input/REALPHOTOS-UI-POLISH-constraint-ledger.md`。

---

## 2. 任务拆分

### T1 · 设计令牌与共享组件（底座延续）

| 项 | 内容 |
| --- | --- |
| 范围 | `realphotos-surface.css`；新建或扩展 `components/realphotos/`（如 `RpButton` / `RpCard` / `RpTable` / `RpField` / `RpDialog` / `RpPageHeader` / `RpSection`） |
| 做法 | 1）只使用 aojuai 的 `--background/--foreground/--muted/--accent/--border/--ring/--card` 等变量。<br>2）定义主按钮 / 次按钮 / 危险按钮、表头行、状态 pill、表单控件高度与 focus。<br>3）提供 `RpSection`（标题条 + 分区容器）供报告模块复用。<br>4）删除或收敛页面内重复的 `rp-btn … hover:-translate-y-px …` 长 class。 |
| 验收 | 组件在 Story/单页样例或 tasks 页可复用；CSS 无新引入的非底座主色体系 |
| 端测标记 | `T1_E2E_PASS` |

### T2 · 主路径页面骨架统一

| 项 | 内容 |
| --- | --- |
| 范围（优先） | 工作台、图片资源、批量原图、任务详情列表、登录相关 realphotos 壳 |
| 随后 | 积分、预设、提示词、工单、用户管理、系统管理（同一组件横向替换，可不阻塞 T3） |
| 做法 | 每页固定：**页头（标题 + 短说明 + 主操作）→ 筛选条 → 主表 → 分页/空态/加载/错误**。<br>统一空态文案区、筛选控件样式、分页按钮。 |
| 验收 | 上述优先页目视一致；截图或 DOM 合同证明使用共享组件 class |
| 端测标记 | `T2_E2E_PASS` |

### T3 · 任务详情：列表 + **详情表单/报告分区**（本单重点）

| 项 | 内容 |
| --- | --- |
| 范围 | `aojuai-main/frontend/src/app/(app)/realphotos/tasks/page.tsx`（处理详情弹窗 + 生图详情弹窗） |
| 做法 | 1）列表区应用 T1 表格/按钮/筛选样式。<br>2）**详情弹窗（具体任务表单/报告）全面换肤**：宽度可读（可略大于现 `max-w-lg`，以不破坏窄屏为准）、分区滚动保留。<br>3）**同一份报告模块相互区分**，至少独立区块：<br> · 基本（状态 / 预设 / 时间 / 复制来源）<br> · 积分（处置 / 计费模式）<br> · 失败（原因 / 模式 / 详情）<br> · EXIF / GPS（有数据才显示）<br> · 检测报告（五维分数、通过判定、说明）<br>4）区分手段：`RpSection` 标题条 + 浅底/边框分隔，或左边强调条；模块标题字重/字号高于正文；禁止再「纯 `<p>` 长文无框」。<br>5）生图详情弹窗同步分区（预览 / 逐张状态 / 计费），保持 PRD：生图无复制/重处理时间线。 |
| 验收 | 打开任一已完成处理任务详情：5 类模块（有数据者）视觉可分；未改字段语义与按钮权限 |
| 端测标记 | `T3_E2E_PASS`（建议附前后截图路径） |

### T4 · 状态反馈与回归门禁

| 项 | 内容 |
| --- | --- |
| 范围 | 主路径提交/失败 toast 或对话框（已有 `toastTask` / Sonner 则复用）；关键页冒烟 |
| 做法 | 提交生图/处理、详情内关键操作成功失败有统一反馈；`pnpm typecheck`（或现有前端 CI 等价）+ 秘密扫描；不引入 eslint 升必过除非 Owner 批准 |
| 验收 | 日志含汇总标记；无样式回归导致主按钮不可点/弹窗无法关闭 |
| 端测标记 | `T4_E2E_PASS` + 汇总 `REALPHOTOS_UI_POLISH_E2E_PASS` |

---

## 3. 明确不做 / 延后

| 项 | 说明 |
| --- | --- |
| 菜单重排、新一级导航 | 延后；本单只做视觉与组件 |
| 任务详情实时轮询 | 另单（侧会话已评估可行）；本单不绑定 |
| URL 导入 API 化 / 通用导入 API | 另单；与样式无关 |
| 全站换字体到展示型营销字体 | 禁止；跟随 aojuai |
| 暗色主题专项 | 非目标 |
| 后端接口变更 | 除非纯展示字段已有；本单默认纯前端 |

---

## 4. 建议实施顺序

1. T1 组件与 CSS（阻断后续）
2. T3 任务详情报告分区（管理员点名重点，可与 T2 并行但须用 T1 组件）
3. T2 主路径页铺开
4. T4 反馈与回归 → 开 PR（Collaborator）→ Owner squash

---

## 5. 协作纪律

1. 仅在指定 worktree / 分支改代码；不碰主树未点名脏工作区。
2. 合入目标 `main`，仅 PR + squash；作者不得自合。
3. 证据写入 `/tmp/realphotos-ui-polish-e2e.log` 与 `docs/mihuanyuantu-v2/input/REALPHOTOS-UI-POLISH-e2e-*.txt`。
4. 进度回写 `docs/mihuanyuantu-v2/progress.yaml`（`current_loop` / `next_action`）。
5. 桌面本稿为管理员可读规划件；入库副本由执行会话写入 `docs/mihuanyuantu-v2/input/` 时保持编号一致。

---

## 6. 验收清单（管理员目视）

- [ ] 整体仍是 aojuai 风格，无「另一品牌官网」感
- [ ] 工作台 / 资源 / 批量 / 任务详情列表明显比改前正式、一致
- [ ] 任务详情弹窗内：**基本 / 积分 / 失败 / GPS / 检测报告**模块边界清晰
- [ ] 主按钮与次按钮可区分；表格状态可读
- [ ] 窄屏（约 390 宽）无横向撑破；弹窗可关闭
- [ ] 无 S7、无密钥、无业务规则暗改

---

## 7. 参考路径

| 用途 | 路径 |
| --- | --- |
| 现样式壳 | `aojuai-main/frontend/src/components/realphotos/realphotos-surface.css` |
| 任务详情 | `aojuai-main/frontend/src/app/(app)/realphotos/tasks/page.tsx` |
| IA 原型 | `prototype/` |
| 既往样式口径 | `docs/mihuanyuantu-v2/input/OPS-SUPPLIER-KEY-UX-2026-11-13.md` §T5 |
| UI 规则 | 仓库根 `AGENTS.md` §4 |

---

**桌面文件路径：** `/home/hbs/Desktop/蜜獾原图-v2-UI正式化样式工单-2026-11-15.md`
