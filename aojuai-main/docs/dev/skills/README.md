# skills（执行剧本/工具/脚本说明）

> skills 用来把 AOJUAI 当前 Next.js 主线的高频任务“产品化”为可复用剧本：输入→步骤→输出→验收。
>
> 这些 skill 的写法参考 `antvis/Infographic/.skills`：每个 skill 目录包含 `SKILL.md`（带 front matter），可选 `references/`、`scripts/`、`templates/`。

当前约定：

- 现行主线默认使用面向 `nextjs-base` 公开底座的 Skill
- 下游扩展可以复用这些 Skill，但不得把业务语义写回底座文档

## 入口

- 总入口：`docs/dev/skills/skills.md`
- 推荐搭配：
  - 开发链路：`docs/dev/flows/NEW_MODULE.md`
  - Skills 地图：`docs/dev/flows/SKILLS_MAP.md`

## 维护原则

- skill 不拥有“系统事实”，只承载“可执行套路”
- 规则类内容应沉淀到：
  - `docs/public/open-edition-base-hardening.md`（公开版稳定基线）
  - `docs/dev/guide_docs/*`（代码级落地）
  - `docs/dev/checklists/DEV_CHECKLIST.md`（上线前可验收）
