#!/usr/bin/env python3
"""生成前端语言包索引：模块加语言包不需要再改中央文件。

原来 `frontend/src/lib/i18n/index.tsx` 里要手工写一行
`import './locales/<module>'`——这对能力包"不改中央文件"的承诺是个破口：
业务分支每加一个模块就得回来改一次内核文件，多分支并行时必然冲突。

改为扫描目录生成 `locales/index.generated.ts`，`index.tsx` 只 import 它一次。
与 `export_module_catalog.py` 是同一个套路（构建期生成、有漂移守卫），
不依赖 webpack 的 require.context，turbopack 下同样成立。

用法：
    python -m scripts.export_locale_index          # 生成
    python -m scripts.export_locale_index --check  # 只校验是否漂移（CI/门禁用）
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_DIR = BACKEND_DIR.parent
LOCALES_DIR = REPOSITORY_DIR / "frontend" / "src" / "lib" / "i18n" / "locales"
OUTPUT = LOCALES_DIR / "index.generated.ts"

# 核心语言包由 registry.ts 直接 import（它们导出常量，不自注册），不进这个索引。
CORE_LOCALE_FILES = {"zh-CN.ts", "en-US.ts", "es-ES.ts"}


def discover_module_locales() -> list[str]:
    if not LOCALES_DIR.is_dir():
        return []
    names = [
        path.stem
        for path in sorted(LOCALES_DIR.glob("*.ts"))
        if path.name not in CORE_LOCALE_FILES and path.name != OUTPUT.name
    ]
    return names


def render(names: list[str]) -> str:
    header = (
        "// 本文件由 `python -m scripts.export_locale_index` 生成，请勿手改。\n"
        "// 模块语言包放进 locales/ 目录即自动注册；无需改任何中央文件。\n"
        "// 漂移由 GOV-17 守卫（governance_tools/locale_index.py）。\n"
    )
    if not names:
        return header + "\nexport {}\n"
    imports = "\n".join(f"import './{name}'" for name in names)
    listed = "\n".join(f"  '{name}'," for name in names)
    return f"{header}\n{imports}\n\nexport const REGISTERED_LOCALE_MODULES = [\n{listed}\n] as const\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="only verify the generated file is current")
    options = parser.parse_args()

    names = discover_module_locales()
    content = render(names)

    if options.check:
        if not OUTPUT.exists():
            print(f"missing {OUTPUT.relative_to(REPOSITORY_DIR)}; run scripts/export_locale_index.py", file=sys.stderr)
            return 1
        if OUTPUT.read_text(encoding="utf-8") != content:
            print(
                f"{OUTPUT.relative_to(REPOSITORY_DIR)} is stale; run scripts/export_locale_index.py",
                file=sys.stderr,
            )
            return 1
        print(f"locale index up to date ({len(names)} module packs)")
        return 0

    OUTPUT.write_text(content, encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(REPOSITORY_DIR)} ({len(names)} module packs: {', '.join(names) or 'none'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
