"""GOV-15: 文档里引用的仓内路径必须真实存在。

这一轮文档复盘里，最费时间也最容易把人带沟里的，全是同一类问题：
文档指着一个**根本不存在**的文件/模块（`app/core/notification.py` 搬走了、
`app/domain/permissions/models.py` 从来没有过、`frontend/src/utils/http/index.ts`
是 Vue 时代的路径）。人照着找，找不到，再自己猜一个写法。

所以把它做成检查：扫 docs/ 里出现的仓内路径引用，逐个验证存在性。
只认"长得像仓内路径"的（以 backend/ frontend/ docs/ scripts/ app/ 开头），
不去碰外部 URL 和纯代码示例里的东西。
"""

from __future__ import annotations

import re
from pathlib import Path

from .common import ScanResult, Violation, require_discovered, validate_allowlist

# 反引号里、看起来像仓内路径的片段
_PATH_IN_BACKTICKS = re.compile(
    r"`((?:backend|frontend|docs|scripts|app)/[A-Za-z0-9_./<>*-]+\.(?:py|ts|tsx|md|json|mjs|conf|yaml|yml))`"
)

# 带原因的显式豁免。加条目前先问：这是"历史记录"，还是"现在照着做的指南"？
# 只有前者可以豁免——指南里的死链必须修。
DOC_REFERENCE_ALLOWLIST: dict[str, str] = {
    "docs/dev/reference/IMPORTANT_DEV_VIOLATIONS.md":
        "历史违规记录：记录的是当时在下游分支修的模块（如 agents），基座本就没有这些路径",
}

# 文档在明确指出"这个路径不存在/已废弃"时会引用它，属于正确用法。
_NEGATIVE_CONTEXT = (
    "不存在",
    "已不存在",
    "从未存在",
    "已作废",
    "Vue 时代",
    "旧路径",
    "旧脚手架",
    "别再去找",
    # 跨分支引用是合法的：经验从下游分支沉淀回基座时，
    # 参考实现本来就不在基座里——只要文档写明了"在某某分支"。
    "分支（基座没有",
    "分支**（基座没有",
    "在 **logistics 分支**",
    "下游分支",
    "改为",
    "搬到",
    "移到",
)


def discover_doc_files(repo_root: Path) -> tuple[Path, ...]:
    docs_root = repo_root / "docs"
    if not docs_root.is_dir():
        return ()
    return tuple(sorted(docs_root.rglob("*.md")))


def scan_doc_references(
    repo_root: Path,
    *,
    allowlist: dict[str, str] | None = None,
) -> ScanResult:
    allowed = DOC_REFERENCE_ALLOWLIST if allowlist is None else allowlist
    validate_allowlist("GOV-15", allowed)

    discovered = discover_doc_files(repo_root)
    require_discovered("GOV-15", discovered, "Markdown files under docs/")

    violations: list[Violation] = []
    for path in discovered:
        relative = path.relative_to(repo_root).as_posix()
        if relative in allowed:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            violations.append(Violation("GOV-15", relative, 0, f"cannot read: {exc}"))
            continue

        for lineno, line in enumerate(lines, start=1):
            # 文档正在说"它不存在"时，引用死路径是正确的
            if any(marker in line for marker in _NEGATIVE_CONTEXT):
                continue
            for match in _PATH_IN_BACKTICKS.finditer(line):
                target = match.group(1)
                # 通配/占位路径不检查
                if any(ch in target for ch in "<>*"):
                    continue
                # 允许三种写法：仓根相对、相对该文档所在目录（README 常用）、
                # 以及省略 backend/ 或 frontend/src/ 前缀的简写（文档里很常见，
                # 与其为措辞习惯改一堆文档，不如让检查认它——**只要目标真实存在**）。
                candidates = (
                    repo_root / target,
                    path.parent / target,
                    repo_root / "backend" / target,
                    repo_root / "frontend" / "src" / target,
                )
                if any(candidate.exists() for candidate in candidates):
                    continue
                violations.append(
                    Violation(
                        "GOV-15",
                        relative,
                        lineno,
                        f"referenced repository path does not exist: {target}",
                    )
                )

    return ScanResult(rule="GOV-15", discovered=discovered, violations=tuple(violations))
