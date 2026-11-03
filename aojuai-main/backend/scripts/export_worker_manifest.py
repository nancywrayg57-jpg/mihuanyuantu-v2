#!/usr/bin/env python3
"""导出 worker 清单，给运维侧（autubuild/manage.sh）读。

为什么要有这个文件：`manage.sh` 里三个 worker 的名字是写死的，
新模块的 worker 运维侧看不见——不会 start、不会 stop、status 里也没有。
2026-08-09 停 nextjs-plugins 时就吃了亏：`manage.sh stop` 只杀了绑端口的 uvicorn，
三个 worker（510 MB）继续在后台空转。

改成：基座扫描声明生成清单，manage.sh 读清单。加 worker 不再需要改运维脚本。

**清单只含元数据，不 import 任何业务代码**——所以在没装依赖的机器上也能生成。

用法：
    python -m scripts.export_worker_manifest            # 生成
    python -m scripts.export_worker_manifest --check    # 校验是否漂移（门禁用）
    python -m scripts.export_worker_manifest --installed-only   # 只列当前部署该起的
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.worker_registry import (  # noqa: E402
    WorkerDefinition,
    discover_workers,
    installed_workers,
    resolve_concurrency,
)

OUTPUT = BACKEND_DIR / "deploy" / "workers.json"


def _entry(definition: WorkerDefinition, *, with_concurrency: bool) -> dict[str, object]:
    entry: dict[str, object] = {
        "code": definition.code,
        "label": definition.label,
        "module": definition.module_code,
        "runModule": f"scripts.run_worker",
        "args": ["--worker", definition.code],
        "defaultConcurrency": definition.default_concurrency,
        "maxConcurrency": definition.max_concurrency,
        "concurrencySetting": definition.settings_concurrency_key,
        "pollInterval": definition.poll_interval,
        "description": definition.description,
    }
    if with_concurrency:
        entry["concurrency"] = resolve_concurrency(definition)
    return entry


def build_manifest(*, installed_only: bool) -> dict[str, object]:
    definitions = installed_workers() if installed_only else discover_workers()
    return {
        "version": 1,
        "installedOnly": installed_only,
        "workers": [_entry(item, with_concurrency=installed_only) for item in definitions],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="only verify the generated file is current")
    parser.add_argument(
        "--installed-only",
        action="store_true",
        help="list only workers whose module is installed in this deployment (for manage.sh)",
    )
    parser.add_argument("--stdout", action="store_true", help="print the manifest instead of writing it")
    options = parser.parse_args()

    manifest = build_manifest(installed_only=options.installed_only)
    content = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    if options.stdout:
        print(content, end="")
        return 0

    if options.check:
        if not OUTPUT.exists():
            print(f"missing {OUTPUT.relative_to(BACKEND_DIR)}; run scripts/export_worker_manifest.py", file=sys.stderr)
            return 1
        if OUTPUT.read_text(encoding="utf-8") != content:
            print(f"{OUTPUT.relative_to(BACKEND_DIR)} is stale; run scripts/export_worker_manifest.py", file=sys.stderr)
            return 1
        print(f"worker manifest up to date ({len(manifest['workers'])} workers)")
        return 0

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(content, encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(BACKEND_DIR)} ({len(manifest['workers'])} workers)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
