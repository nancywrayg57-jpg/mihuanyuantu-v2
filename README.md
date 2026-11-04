# 蜜獾原图 v2

本仓库汇总项目需求、架构、生产资源准备材料和指定 aojuai 底座源码。开发实施以当前需求及架构文档为依据，原始输入材料保留用于追溯。

## 文档入口

完整目录见 [docs/README.md](docs/README.md)。被替代材料在 [docs/archive/](docs/archive/README.md)。

- [现行 PRD v2.0（2.8）](docs/蜜獾原图-v2-PRD-v2.0.md)
- [AidevOps 第一刀工作区](docs/mihuanyuantu-v2/progress.yaml)
- [Agent 开发指令](docs/mihuanyuantu-v2/DEV_INSTRUCTIONS.md)
- [grill-me 逻辑架构裁决](docs/architecture_decisions/蜜獾原图-v2-grill-me逻辑架构裁决-2026-11-04.md)
- [Gemini Vision 检测与自动重做](docs/蜜獾原图-v2-Gemini-Vision检测与自动重做方案-v1.0.md)
- [决策清单](docs/蜜獾原图-v2-待决策清单-v1.0.md)
- [项目架构（1.4）](docs/蜜獾原图-v2-项目架构-v1.0.md)
- [生产物料清单](docs/蜜獾原图-v2-生产物料清单-v1.0.md)
- [HTML 原型](prototype/README.md)
- [架构设计裁决与交接](docs/architecture_decisions/蜜獾原图-v2-架构设计裁决与交接-2026-10-23.md)

文件名中的版本号可能与正文内部版本不同，请以文件元数据及正文为准。

## 目录

```text
.
├── aojuai-main/                 # 指定底座源码，作为本仓库的普通子目录
│   ├── backend/                 # FastAPI / SQLAlchemy
│   ├── frontend/                # Next.js / React
│   ├── docs/                    # 底座文档
│   └── LICENSE                  # 底座原许可证，保留原文
├── aidevops/                    # AidevOps 快速开发部署包（技能与脚本）
├── skills/                      # 第三方技能快照（含 grill-me）
├── docs/                        # 本项目需求、架构和共享资源清单
│   ├── architecture_decisions/  # 现行裁决
│   └── archive/                 # 被替代的 PRD、原型交接与增量 ADR
├── prototype/                   # 离线 HTML 交互原型
├── 输入材料/                    # 原始资料、旧版复用材料及原始压缩包
├── 测试用/                      # 本地检测样图语料，Git 忽略
├── output/                      # 生成的原型校验与浏览器走查产物，Git 忽略
└── 生产物料/                    # 仅本地保存的生产账号、密钥及资源配置，Git 忽略
```

本次整理保留现有目录与源码，未将底座改成子模块。前后端命令请在各自目录执行，参见 [底座说明](aojuai-main/README.md)、[后端说明](aojuai-main/backend/README.md) 和 [前端说明](aojuai-main/frontend/README.md)。本地仓库初始化不代表项目已经实现、通过运行验收或部署。

## 版本控制约定

- 追踪源码、`pnpm-lock.yaml`、`uv.lock`、增量迁移、需求与决策文档、原始输入资料和已脱敏的环境模板。
- 忽略 `生产物料/`、`测试用/`、`output/`、实际 `.env` 配置、私钥、依赖目录、构建与测试产物、日志、本地数据库和备份。原型同步脚本在 `prototype/sync-inline.js`。
- 环境模板采用 `.env.example`、`.env.sample`、`.env.template` 或 `.env.<用途>.template` 等命名，只填写占位值。
- 原始资料压缩包需要保留，不使用全局 `*.zip` 忽略规则；新增压缩包须检查内部是否含本地配置或凭据。
- `.gitattributes` 统一代码文本行尾为 LF，Windows `.bat` / `.cmd` 使用 CRLF；`docs/`、`输入材料/` 及二进制保持现有字节内容，避免已有审计指纹失效。
- 保留底座许可证与原始署名；项目自有内容的授权范围另行确定。

## 本地 Git

仓库根目录为 `D:\workspace\蜜獾原图v2`，本地分支使用 `main`。`origin` 指向 [mihuanyuantu-v2](https://github.com/nancywrayg57-jpg/mihuanyuantu-v2.git)。

提交前可在项目根目录检查：

```powershell
git status --short
git diff --cached --stat
git diff --cached --check -- .gitignore .gitattributes README.md
git check-ignore -v -- "生产物料/蜜獾原图v2-生产物料.md" "aojuai-main/backend/.env"
```

忽略规则不会阻止显式的 `git add -f`；生产配置应继续仅保存在本地或专用凭据管理系统中。

首次入库保留底座及原始资料的既有空白格式，全量 `git diff --cached --check` 可能报告历史空白告警；本次只对新增仓库文件执行通过性检查，详细结果见本地仓库整理记录。
