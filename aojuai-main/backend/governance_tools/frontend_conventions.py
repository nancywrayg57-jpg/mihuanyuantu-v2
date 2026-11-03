"""GOV-16: 前端页面必须遵守基座的交互与文案约定。

两条都是线上看出来的，且都出在"新模块要照抄的模板"上——不做成检查，
下一个模块照抄的就是错的写法：

1. **禁止浏览器原生弹窗**（`window.prompt` / `window.confirm` / `window.alert`）。
   原生弹窗一次只能填一个字段、样式不受控，按钮文字跟随**系统语言**、改不了，
   多语言直接失效。统一用 `@/components/ui/dialog`。
2. **页面里不许硬编码中文**。文案走模块语言包 + `t()`，
   否则切到 en/es 还是中文。

只扫 `(app)` 下的页面与组件；`(site)` 公开站与 `(auth)` 暂不纳入
（它们有自己的 SSR/元数据链路，另行处理）。
"""

from __future__ import annotations

import re
from pathlib import Path

from .common import ScanResult, Violation, require_discovered, validate_allowlist

# `window.confirm(...)` 和裸 `confirm(...)` 都要抓——CMS 三个页面就是用裸调用
# 混过第一版检查的。前面不能紧跟 `.`（排除 `foo.confirm()` 这类自有方法）
# 或标识符字符（排除 `onConfirm(`），也排除 `function confirm(` 这类声明。
_NATIVE_DIALOG = re.compile(
    r"(?<![.\w])(?:window\.)?(prompt|confirm|alert)\s*\("
)
_DIALOG_DECLARATION = re.compile(r"\b(function|const|let|var|async)\s+(prompt|confirm|alert)\b")

# JSX 文本或字符串字面量里的中文
_CJK = re.compile(r"[一-鿿]")

# 注释行不算违规：注释里写中文是好事
_COMMENT = re.compile(r"^\s*(//|/\*|\*)")

# 带原因的显式豁免。**只用于有记录的存量欠账**，不是"以后都可以这么写"。
# 每加一条都要在 docs/dev/issues/FRONTEND.md 里有对应条目，说明什么时候清。
#
# 2026-08-09：CMS 六个页面的 i18n 欠账已清（约 155 处），豁免全部撤掉。
# 清账时顺带发现：那三处删除确认用的是**裸 `confirm(...)`**，
# 第一版正则只匹配 `window.confirm`，所以一直没被抓到——正则已收紧。
FRONTEND_CONVENTION_ALLOWLIST: dict[str, str] = {}


def discover_app_pages(repo_root: Path) -> tuple[Path, ...]:
    app_root = repo_root / "frontend" / "src" / "app" / "(app)"
    if not app_root.is_dir():
        return ()
    return tuple(sorted(app_root.rglob("*.tsx")))


def scan_frontend_conventions(
    repo_root: Path,
    *,
    allowlist: dict[str, str] | None = None,
) -> ScanResult:
    allowed = FRONTEND_CONVENTION_ALLOWLIST if allowlist is None else allowlist
    validate_allowlist("GOV-16", allowed)

    discovered = discover_app_pages(repo_root)
    require_discovered("GOV-16", discovered, "TSX files under frontend/src/app/(app)")

    violations: list[Violation] = []
    for path in discovered:
        relative = path.relative_to(repo_root).as_posix()
        # 豁免只作用于「硬编码中文」这一条；原生弹窗对任何文件都不豁免。
        cjk_exempt = relative in allowed
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            violations.append(Violation("GOV-16", relative, 0, f"cannot read: {exc}"))
            continue

        for lineno, line in enumerate(lines, start=1):
            if _NATIVE_DIALOG.search(line) and not _DIALOG_DECLARATION.search(line):
                violations.append(
                    Violation(
                        "GOV-16",
                        relative,
                        lineno,
                        "native browser dialog is forbidden; use @/components/ui/dialog "
                        "(its buttons follow the OS language and break i18n)",
                    )
                )
            if cjk_exempt or _COMMENT.match(line):
                continue
            if _CJK.search(line):
                violations.append(
                    Violation(
                        "GOV-16",
                        relative,
                        lineno,
                        "hardcoded Chinese in a page; move it to the module locale pack and use t()",
                    )
                )

    return ScanResult(rule="GOV-16", discovered=discovered, violations=tuple(violations))
