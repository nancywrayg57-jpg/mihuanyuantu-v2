"""GOV-17: 语言包索引必须与目录一致，且没人绕过它手改中央文件。

模块加语言包不应该要求改内核文件——业务分支每加一个模块就回来改一次
`i18n/index.tsx`，多分支并行时必然冲突，也直接违背能力包"不改中央文件"的承诺。

所以索引改为构建期生成。这条检查守两件事：
1. `locales/index.generated.ts` 与目录里的实际语言包一致（漏生成会导致文案静默丢失）
2. `i18n/index.tsx` 里没有手写的 `import './locales/<module>'`（绕过索引就白改了）
"""

from __future__ import annotations

import re
from pathlib import Path

from .common import ScanResult, Violation, require_discovered, validate_allowlist

_MANUAL_IMPORT = re.compile(r"""import\s+['"]\./locales/(?!index\.generated)([\w.-]+)['"]""")

LOCALE_INDEX_ALLOWLIST: dict[str, str] = {}


def _locales_dir(repo_root: Path) -> Path:
    return repo_root / "frontend" / "src" / "lib" / "i18n" / "locales"


def discover_locale_packs(repo_root: Path) -> tuple[Path, ...]:
    directory = _locales_dir(repo_root)
    if not directory.is_dir():
        return ()
    core = {"zh-CN.ts", "en-US.ts", "es-ES.ts", "index.generated.ts"}
    return tuple(sorted(path for path in directory.glob("*.ts") if path.name not in core))


def scan_locale_index(
    repo_root: Path,
    *,
    allowlist: dict[str, str] | None = None,
) -> ScanResult:
    allowed = LOCALE_INDEX_ALLOWLIST if allowlist is None else allowlist
    validate_allowlist("GOV-17", allowed)

    discovered = discover_locale_packs(repo_root)
    require_discovered("GOV-17", discovered, "module locale packs under i18n/locales")

    violations: list[Violation] = []
    index_path = _locales_dir(repo_root) / "index.generated.ts"
    index_relative = index_path.relative_to(repo_root).as_posix()

    if not index_path.exists():
        violations.append(
            Violation("GOV-17", index_relative, 0, "generated locale index is missing; run scripts/export_locale_index.py")
        )
    else:
        indexed = set(re.findall(r"""import\s+['"]\./([\w.-]+)['"]""", index_path.read_text(encoding="utf-8")))
        actual = {path.stem for path in discovered}
        for missing in sorted(actual - indexed):
            violations.append(
                Violation(
                    "GOV-17",
                    index_relative,
                    0,
                    f"locale pack '{missing}' exists but is not indexed; run scripts/export_locale_index.py",
                )
            )
        for stale in sorted(indexed - actual):
            violations.append(
                Violation("GOV-17", index_relative, 0, f"indexed locale pack '{stale}' no longer exists")
            )

    entry = repo_root / "frontend" / "src" / "lib" / "i18n" / "index.tsx"
    if entry.exists():
        relative = entry.relative_to(repo_root).as_posix()
        for lineno, line in enumerate(entry.read_text(encoding="utf-8").splitlines(), start=1):
            match = _MANUAL_IMPORT.search(line)
            if match:
                violations.append(
                    Violation(
                        "GOV-17",
                        relative,
                        lineno,
                        f"manual locale import '{match.group(1)}' bypasses the generated index; "
                        "drop the module file into locales/ and regenerate instead",
                    )
                )

    return ScanResult(rule="GOV-17", discovered=discovered, violations=tuple(violations))
