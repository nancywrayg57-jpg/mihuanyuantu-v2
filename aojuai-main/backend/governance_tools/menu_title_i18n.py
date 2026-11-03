"""GOV-19: 声明出来的菜单标题必须有对应的 `menu.<标题>` 翻译键。

这条是从**下游分支反复踩的坑**回流的，不是凭空加的规则。物流/clocart 两条分支
都出过同一个故障，提交信息写得很直白：

    fix(i18n): menu key must match DB title verbatim — 'Shopify 接入' has a space

原因在 `frontend/src/lib/i18n/registry.ts`：

    export function translateMenuTitle(title, locale) {
      if (!title || locale === 'zh-CN') return title
      const hit = MESSAGES[locale]?.[`menu.${title}`]
      return hit || title          // ← 查不到就**静默**返回中文
    }

菜单标题来自数据库，翻译键是 `menu.` + 标题原文。漏一个键、或者标题里多一个空格，
界面切到 en/es 就是中文，**没有任何报错**。这类"静默降级"靠人工点页面才发现，
所以必须做成门禁。

检查两件事：
1. 后端声明里的每个菜单标题，在每个非 zh-CN 语言包里都要有 `menu.<标题>`
2. 标题两端不许有空白——它看不见，却会让键永远对不上
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from .common import ScanResult, Violation, require_discovered, validate_allowlist

MENU_TITLE_I18N_ALLOWLIST: dict[str, str] = {}

# 菜单声明所在的后端文件：系统菜单、CMS、以及各能力包自己的 access.py
_DECLARATION_GLOBS = (
    "app/core/system_menus.py",
    "app/domain/*/access.py",
    "app/capabilities/*/access.py",
)

# 需要覆盖的目标语言（zh-CN 直接返回标题原文，不需要键）
_TARGET_LOCALES = ("en-US", "es-ES")

_MENU_KEY_RE = re.compile(r"""['"]menu\.([^'"]+)['"]\s*:""")


def _declaration_files(backend_root: Path) -> tuple[Path, ...]:
    found: list[Path] = []
    for pattern in _DECLARATION_GLOBS:
        found.extend(sorted(backend_root.glob(pattern)))
    return tuple(found)


def discover_declared_menu_titles(backend_root: Path) -> tuple[tuple[str, str, int], ...]:
    """返回 (相对路径, 标题, 行号)。用 AST 找 `MenuNodeSpec(title=...)`。"""
    titles: list[tuple[str, str, int]] = []
    for path in _declaration_files(backend_root):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        relative = path.relative_to(backend_root).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
            if name != "MenuNodeSpec":
                continue
            for keyword in node.keywords:
                if keyword.arg == "title" and isinstance(keyword.value, ast.Constant):
                    value = keyword.value.value
                    if isinstance(value, str):
                        titles.append((relative, value, node.lineno))
    return tuple(titles)


def _locale_menu_keys(repo_root: Path, locale: str) -> set[str]:
    path = repo_root / "frontend" / "src" / "lib" / "i18n" / "locales" / f"{locale}.ts"
    if not path.is_file():
        return set()
    return set(_MENU_KEY_RE.findall(path.read_text(encoding="utf-8")))


def scan_menu_title_i18n(
    repo_root: Path,
    *,
    allowlist: dict[str, str] | None = None,
) -> ScanResult:
    allowed = MENU_TITLE_I18N_ALLOWLIST if allowlist is None else allowlist
    validate_allowlist("GOV-19", allowed)

    backend_root = repo_root / "backend"
    declared = discover_declared_menu_titles(backend_root)
    require_discovered(
        "GOV-19",
        tuple(f"{source}:{title}" for source, title, _ in declared),
        "declared menu titles",
    )

    keys_by_locale = {locale: _locale_menu_keys(repo_root, locale) for locale in _TARGET_LOCALES}

    violations: list[Violation] = []
    for source, title, lineno in declared:
        if title != title.strip():
            violations.append(
                Violation(
                    "GOV-19",
                    source,
                    lineno,
                    f"菜单标题两端有空白：{title!r}。翻译键是 'menu.'+标题原文，"
                    "多一个空格就永远查不到，界面静默显示中文",
                )
            )
        if title in allowed:
            continue
        for locale in _TARGET_LOCALES:
            if title not in keys_by_locale[locale]:
                violations.append(
                    Violation(
                        "GOV-19",
                        source,
                        lineno,
                        f"菜单标题 {title!r} 在 {locale} 里没有 'menu.{title}' 键；"
                        "translateMenuTitle 查不到会静默回落成中文",
                    )
                )

    return ScanResult(
        rule="GOV-19",
        discovered=tuple(f"{source}:{title}" for source, title, _ in declared),
        violations=tuple(violations),
    )
