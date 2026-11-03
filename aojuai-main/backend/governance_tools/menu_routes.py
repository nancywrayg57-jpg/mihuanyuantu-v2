"""GOV-06: menu paths and Next App Router pages must agree."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .common import ScanResult, Violation, require_discovered, validate_allowlist

NON_PAGE_MENU_PATH_ALLOWLIST = {
    "/cms": "Directory menu; its selectable children are real /cms/* pages.",
    "/personal": "Directory menu; its selectable children are real /personal/* pages.",
    "/system": "Directory menu; its selectable children are real /system/* pages.",
    "/tenant": "Directory menu; its selectable children are real /tenant/* pages.",
}


HIDDEN_PAGE_ALLOWLIST = {
    "/": "Authenticated app-shell redirect, not a selectable menu page.",
    "/assistant": "Internal assistant workspace opened through assistant entry points.",
    "/assistant/[...slug]": "Internal assistant catch-all owned by the assistant workspace.",
    "/permission/button": "Internal permission editor route reached from administration flows.",
    "/permission/page": "Internal permission editor route reached from administration flows.",
    "/personal/profile-required": "Forced profile-completion flow, intentionally hidden from menus.",
    "/schedule": "Internal scheduler example page, intentionally hidden in the base product.",
    "/speech": "Optional speech module entry, mounted outside the base seed menu.",
    "/speech/[...slug]": "Optional speech module catch-all, mounted outside the base seed menu.",
    "/system/ai-settings": "Hidden tenant-settings extension page, not standalone navigation.",
    "/system/dict": "Internal dictionary administration page not enabled in the base menu.",
    "/system/speech/demo": "Legacy hidden speech demo retained only for compatible deep links.",
    "/tenant/package/index": "Internal tenant-package page reached from tenant administration.",
    "/welcome": "Post-login landing flow, intentionally hidden from menus.",
}


_MENU_WRITE_RE = re.compile(r"\b(?:insert\s+into|update)\s+menus\b", re.IGNORECASE)
_ROUTE_RE = re.compile(r"^/(?:[^\s?#]*)$")


@dataclass(frozen=True)
class PageRoute:
    pattern: str
    source: str


@dataclass(frozen=True)
class MenuPath:
    path: str
    source: str
    line: int


def _normalize_route(value: str) -> str | None:
    route = value.split("#", 1)[0].split("?", 1)[0].strip()
    if not _ROUTE_RE.fullmatch(route):
        return None
    if route != "/":
        route = route.rstrip("/")
    return route or "/"


def discover_next_pages(repo_root: Path) -> tuple[PageRoute, ...]:
    app_root = repo_root / "frontend" / "src" / "app" / "(app)"
    pages: list[PageRoute] = []
    for path in sorted(app_root.rglob("page.tsx")) if app_root.is_dir() else ():
        segments = [
            segment
            for segment in path.parent.relative_to(app_root).parts
            if not (segment.startswith("(") and segment.endswith(")"))
        ]
        pattern = "/" + "/".join(segments) if segments else "/"
        pages.append(PageRoute(pattern, path.relative_to(repo_root).as_posix()))
    return tuple(pages)


def _route_pattern_regex(pattern: str) -> re.Pattern[str]:
    if pattern == "/":
        return re.compile(r"^/$")
    expression = "^"
    for segment in pattern.strip("/").split("/"):
        if segment.startswith("[[...") and segment.endswith("]]"):
            expression += r"(?:/.+)?"
        elif segment.startswith("[...") and segment.endswith("]"):
            expression += r"/.+"
        elif segment.startswith("[") and segment.endswith("]"):
            expression += r"/[^/]+"
        else:
            expression += "/" + re.escape(segment)
    return re.compile(expression + "$")


def _contains_menu_write(tree: ast.AST) -> bool:
    if any(
        isinstance(node, ast.Constant) and isinstance(node.value, str) and _MENU_WRITE_RE.search(node.value)
        for node in ast.walk(tree)
    ):
        return True

    nodes = tuple(ast.walk(tree))
    menu_table_names: set[str] = set()
    for node in nodes:
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        call_name = node.value.func.attr if isinstance(node.value.func, ast.Attribute) else ""
        first_arg = node.value.args[0] if node.value.args else None
        if call_name == "table" and isinstance(first_arg, ast.Constant) and first_arg.value == "menus":
            menu_table_names.update(target.id for target in node.targets if isinstance(target, ast.Name))

    for node in nodes:
        if not isinstance(node, ast.Call):
            continue
        call_name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
        if "menu" in call_name.lower() and any(keyword.arg == "path" for keyword in node.keywords):
            return True
        if call_name not in {"insert", "bulk_insert"}:
            continue
        if any(
            isinstance(argument, ast.Name)
            and (argument.id == "Menu" or argument.id in menu_table_names)
            or isinstance(argument, ast.Constant)
            and argument.value == "menus"
            for argument in node.args
        ):
            return True
    return False


def discover_menu_source_files(backend_root: Path) -> tuple[Path, ...]:
    candidates = [
        *(backend_root / "scripts").rglob("*.py"),
        *(backend_root / "alembic" / "versions").glob("*.py"),
        # 声明式菜单规格（reconciler 的输入）住在 app/ 里，也必须被发现，
        # 否则把菜单从 seed 脚本搬进声明模块之后，这条门禁会静默漏掉整组菜单。
        *(backend_root / "app").rglob("*.py"),
    ]
    discovered: list[Path] = []
    for path in sorted(set(candidates)):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError):
            continue
        if _contains_menu_write(tree):
            discovered.append(path)
    return tuple(discovered)


def _literal_values(tree: ast.AST) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        value_node = node.value
        if value_node is None:
            continue
        try:
            value = ast.literal_eval(value_node)
        except (ValueError, TypeError):
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                values[target.id] = value
    return values


def _string_value(node: ast.AST, literals: dict[str, Any]) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name) and isinstance(literals.get(node.id), str):
        return literals[node.id]
    return None


def _matching_paren(text: str, start: int) -> int | None:
    depth = 0
    quote: str | None = None
    index = start
    while index < len(text):
        char = text[index]
        if quote:
            if char == quote and (index == 0 or text[index - 1] != "\\"):
                quote = None
        elif char in {"'", '"'}:
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return None


def _split_sql_csv(text: str) -> list[str]:
    fields: list[str] = []
    start = 0
    depth = 0
    quote: str | None = None
    index = 0
    while index < len(text):
        char = text[index]
        if quote:
            if char == quote:
                if index + 1 < len(text) and text[index + 1] == quote:
                    index += 1
                else:
                    quote = None
        elif char in {"'", '"'}:
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        elif char == "," and depth == 0:
            fields.append(text[start:index].strip())
            start = index + 1
        index += 1
    fields.append(text[start:].strip())
    return fields


def _select_body(text: str, start: int) -> str:
    depth = 0
    quote: str | None = None
    index = start
    while index < len(text):
        char = text[index]
        if quote:
            if char == quote:
                if index + 1 < len(text) and text[index + 1] == quote:
                    index += 1
                else:
                    quote = None
        elif char in {"'", '"'}:
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        elif depth == 0:
            tail = text[index:].lower()
            if any(re.match(rf"{word}\b", tail) for word in ("from", "where", "returning", "on")):
                return text[start:index]
        index += 1
    return text[start:]


def _sql_string_route(expression: str) -> str | None:
    match = re.fullmatch(r"\s*'((?:''|[^'])*)'(?:::[a-z0-9_]+)?\s*", expression, re.IGNORECASE)
    if not match:
        return None
    return _normalize_route(match.group(1).replace("''", "'"))


def _paths_from_sql(sql: str) -> set[str]:
    paths: set[str] = set()
    insert_re = re.compile(r"insert\s+into\s+menus\s*\((.*?)\)\s*(values|select)\b", re.IGNORECASE | re.DOTALL)
    for match in insert_re.finditer(sql):
        columns = [column.strip().strip('"').lower() for column in _split_sql_csv(match.group(1))]
        if "path" not in columns:
            continue
        path_index = columns.index("path")
        body_start = match.end()
        if match.group(2).lower() == "values":
            open_paren = sql.find("(", body_start)
            close_paren = _matching_paren(sql, open_paren) if open_paren >= 0 else None
            body = sql[open_paren + 1 : close_paren] if close_paren is not None else ""
        else:
            body = _select_body(sql, body_start)
        fields = _split_sql_csv(body)
        if path_index < len(fields):
            route = _sql_string_route(fields[path_index])
            if route:
                paths.add(route)

    update_re = re.compile(r"update\s+menus(?:\s+(?:as\s+)?[a-z_][a-z0-9_]*)?\s+set\s+", re.IGNORECASE)
    for match in update_re.finditer(sql):
        assignments = _select_body(sql, match.end())
        for field in _split_sql_csv(assignments):
            assignment = re.match(r"(?:[a-z_][a-z0-9_]*\.)?path\s*=\s*(.+)", field, re.IGNORECASE | re.DOTALL)
            if assignment:
                route = _sql_string_route(assignment.group(1))
                if route:
                    paths.add(route)
    return paths


def extract_menu_paths(path: Path, backend_root: Path) -> tuple[MenuPath, ...]:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    literals = _literal_values(tree)
    relative = path.relative_to(backend_root).as_posix()
    found: set[tuple[str, int]] = set()

    def add(value: str | None, line: int) -> None:
        route = _normalize_route(value) if value else None
        if route:
            found.add((route, line))

    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values, strict=True):
                if isinstance(key, ast.Constant) and key.value == "path":
                    add(_string_value(value, literals), value.lineno)
        elif isinstance(node, ast.Call):
            call_name = ""
            if isinstance(node.func, ast.Name):
                call_name = node.func.id.lower()
            elif isinstance(node.func, ast.Attribute):
                call_name = node.func.attr.lower()
            # 名字里含 menu 的调用视为菜单声明：既覆盖 seed 里的 Menu(...)/insert_menu(...)，
            # 也覆盖 reconciler 的 MenuNodeSpec(...)。但要排除**读取型**调用——
            # 例如 _find_menu_id(path=LEGACY_PATH) 是拿旧路径去查历史行，
            # 那个路径本就不该存在对应页面，算成声明就是误报。
            writes_menu = "menu" in call_name and not any(
                reader in call_name for reader in ("find", "get", "select", "lookup", "resolve", "exists")
            )
            if writes_menu:
                for keyword in node.keywords:
                    if keyword.arg == "path":
                        add(_string_value(keyword.value, literals), keyword.value.lineno)
        elif isinstance(node, ast.For) and isinstance(node.target, (ast.Tuple, ast.List)):
            names = [item.id if isinstance(item, ast.Name) else None for item in node.target.elts]
            if "path" not in names:
                continue
            path_index = names.index("path")
            rows = literals.get(node.iter.id) if isinstance(node.iter, ast.Name) else None
            if isinstance(rows, (list, tuple)):
                for row in rows:
                    if isinstance(row, (list, tuple)) and path_index < len(row) and isinstance(row[path_index], str):
                        add(row[path_index], node.lineno)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and _MENU_WRITE_RE.search(node.value):
            for route in _paths_from_sql(node.value):
                add(route, node.lineno)

    return tuple(MenuPath(route, relative, line) for route, line in sorted(found))


def scan_menu_routes(
    repo_root: Path,
    *,
    menu_allowlist: dict[str, str] | None = None,
    hidden_page_allowlist: dict[str, str] | None = None,
) -> ScanResult:
    repo_root = repo_root.resolve()
    backend_root = repo_root / "backend"
    allowed_menus = NON_PAGE_MENU_PATH_ALLOWLIST if menu_allowlist is None else menu_allowlist
    allowed_pages = HIDDEN_PAGE_ALLOWLIST if hidden_page_allowlist is None else hidden_page_allowlist
    validate_allowlist("GOV-06", allowed_menus)
    validate_allowlist("GOV-06", allowed_pages)

    pages = discover_next_pages(repo_root)
    require_discovered("GOV-06", tuple(page.source for page in pages), "Next page.tsx files under (app)")
    sources = discover_menu_source_files(backend_root)
    source_names = tuple(path.relative_to(repo_root).as_posix() for path in sources)
    require_discovered("GOV-06", source_names, "seed/migration files that write menus")
    menu_paths = tuple(item for source in sources for item in extract_menu_paths(source, backend_root))
    require_discovered("GOV-06", tuple(item.path for item in menu_paths), "menu paths")

    patterns = {page.pattern: _route_pattern_regex(page.pattern) for page in pages}
    violations: list[Violation] = []
    for menu in menu_paths:
        if menu.path in allowed_menus:
            continue
        if not any(regex.fullmatch(menu.path) for regex in patterns.values()):
            violations.append(
                Violation(
                    "GOV-06", f"backend/{menu.source}", menu.line, f"menu path {menu.path!r} resolves to no (app) page"
                )
            )

    concrete_menu_paths = {item.path for item in menu_paths}
    for page in pages:
        if page.pattern in allowed_pages:
            continue
        regex = patterns[page.pattern]
        if not any(regex.fullmatch(menu_path) for menu_path in concrete_menu_paths):
            violations.append(
                Violation(
                    "GOV-06",
                    page.source,
                    1,
                    f"page route {page.pattern!r} is neither a menu nor an explicit hidden/internal page",
                )
            )

    discovered = tuple(sorted({*(page.source for page in pages), *source_names}))
    return ScanResult("GOV-06", discovered, tuple(violations))
