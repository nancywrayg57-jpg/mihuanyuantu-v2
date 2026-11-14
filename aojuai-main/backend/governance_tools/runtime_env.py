"""GOV-10: keep direct process-environment access inside Settings."""

from __future__ import annotations

import ast
from pathlib import Path

from .common import ScanResult, Violation, require_discovered, validate_allowlist

ENV_ACCESS_ALLOWLIST = {
    "app/core/ai_client_factory.py": (
        "Backflow-ready kernel factory (kept free of Settings import); single AOJU_AI_REASONING_EFFORT knob."
    ),
    "app/domain/assistant/openai_client.py": (
        "Standalone gateway client (zero app-internal imports by design); its two AOJU_OPENAI_COMPAT knobs stay env-read."
    ),
    "app/core/config.py": (
        "Settings is the repository's single process-environment boundary; runtime code must read Settings."
    ),
    "scripts/five_layer_legacy_align_e2e.py": (
        "Operator ALIGN e2e: must clear Cursor sandbox HTTP(S)_PROXY before load_dotenv so Meta Fake-IP TUN egress works; not a runtime Settings path."
    ),
    "scripts/det_score_ablation_e2e.py": (
        "Operator DET-SCORE ablation e2e: same proxy-clear + ALIGN_* env knobs as ALIGN e2e; not a runtime Settings path."
    ),
    "scripts/det_score_protocol_c_e2e.py": (
        "Operator DET-SCORE protocol C wrapper: clears proxy and ALIGN overrides before invoking ALIGN e2e; not a runtime Settings path."
    ),
    "scripts/det_score_r4_measure_e2e.py": (
        "Operator DET-SCORE R4 measurement e2e: proxy-clear + measurement-only optical/noise env overrides; not a runtime Settings path."
    ),
    "scripts/det_score_nonlegacy_pilot_e2e.py": (
        "Operator DET-SCORE NONLEGACY OPEN_PILOT e2e: proxy-clear + Bayer/PG measurement flags; not a runtime Settings path."
    ),
    "scripts/det_score_default_opt_e2e.py": (
        "Operator FIVE-LAYER-DEFAULT-OPT e2e: proxy-clear + single-variable measurement overrides; not a runtime Settings path."
    ),
}


class _EnvironmentAccessVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.os_aliases: set[str] = set()
        self.getenv_aliases: set[str] = set()
        self.environ_aliases: set[str] = set()
        self.hits: list[tuple[int, str]] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name == "os":
                self.os_aliases.add(alias.asname or "os")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module == "os":
            for alias in node.names:
                local_name = alias.asname or alias.name
                if alias.name == "getenv":
                    self.getenv_aliases.add(local_name)
                elif alias.name == "environ":
                    self.environ_aliases.add(local_name)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if isinstance(node.value, ast.Name) and node.value.id in self.os_aliases and node.attr in {"environ", "getenv"}:
            self.hits.append((node.lineno, f"{node.value.id}.{node.attr}"))
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in self.getenv_aliases or node.id in self.environ_aliases:
            self.hits.append((node.lineno, node.id))


def discover_python_targets(backend_root: Path) -> tuple[Path, ...]:
    targets = {
        path
        for root in (backend_root / "app", backend_root / "scripts")
        if root.is_dir()
        for path in root.rglob("*.py")
        if path.is_file()
    }
    return tuple(sorted(targets))


def scan_runtime_env_access(
    backend_root: Path,
    *,
    allowlist: dict[str, str] | None = None,
) -> ScanResult:
    backend_root = backend_root.resolve()
    allowed = ENV_ACCESS_ALLOWLIST if allowlist is None else allowlist
    validate_allowlist("GOV-10", allowed)
    targets = discover_python_targets(backend_root)
    discovered = tuple(path.relative_to(backend_root).as_posix() for path in targets)
    require_discovered("GOV-10", discovered, "Python files under app/ and scripts/")

    violations: list[Violation] = []
    for path, relative in zip(targets, discovered, strict=True):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError) as exc:
            violations.append(Violation("GOV-10", relative, 0, f"cannot parse Python source: {exc}"))
            continue
        visitor = _EnvironmentAccessVisitor()
        visitor.visit(tree)
        if relative in allowed:
            continue
        seen: set[tuple[int, str]] = set()
        for line, expression in visitor.hits:
            if (line, expression) in seen:
                continue
            seen.add((line, expression))
            violations.append(
                Violation(
                    "GOV-10",
                    relative,
                    line,
                    f"direct process-environment access via {expression}; use app.core.config.settings",
                )
            )
    return ScanResult("GOV-10", discovered, tuple(violations))
