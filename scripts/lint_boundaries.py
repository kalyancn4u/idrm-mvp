"""
Enforce the import boundaries between app/, dashboard/ and shared/.

The rules (CLAUDE.md rule 1, ADR-0005, ADR-0009):

    app/        may not import  dashboard
    dashboard/  may not import  app
    shared/     may not import  app, dashboard, fastapi, starlette, flask, flask_*

Why: the API and the console are peers that share one database. If one
imports the other, they can no longer be deployed, tested or changed on their
own. `shared/` is used by both, so it must not depend on either app or on
either web framework (FastAPI is built on Starlette; Flask extensions are
named flask_*).

How: each .py file is PARSED (Python's `ast` module), not searched as text.
So an import written over several lines, inside a function, or as
`import app.core as c` is found, while the same words in a comment or a
string are not.

Not caught (on purpose, to keep this simple): `importlib.import_module("app")`
and other dynamic imports. Relative imports (`from .x import y`) stay inside
their own package and cannot cross a boundary.

Run:
    python scripts/lint_boundaries.py            # check the repository
    python scripts/lint_boundaries.py ROOT       # check another tree (tests)

Exits 0 if there are no violations, 1 otherwise, 2 if a file cannot be parsed.
Standard library only, so it runs before any dependency is installed.

Invoked by:
    - `make lint`
    - the CI workflow `.github/workflows/ci.yml`
"""

from __future__ import annotations

import ast
import pathlib
import sys

DEFAULT_ROOT = pathlib.Path(__file__).resolve().parent.parent

# package directory -> top-level module names it must not import
RULES: dict[str, tuple[str, ...]] = {
    "app": ("dashboard",),
    "dashboard": ("app",),
    "shared": ("app", "dashboard", "fastapi", "starlette", "flask"),
}

# A forbidden name also forbids names that start with it plus "_", so that
# "flask" covers flask_login and flask_wtf. (No other rule name has
# legitimate packages with that prefix.)
PREFIX_FAMILIES = ("flask",)

SKIP_DIRS = {"__pycache__", ".venv", "venv", "node_modules"}

Violation = tuple[pathlib.Path, int, str, str]   # path, line, imported name, package


def _top_level(module: str) -> str:
    return module.split(".", 1)[0]


def _is_forbidden(module: str, forbidden: tuple[str, ...]) -> bool:
    top = _top_level(module)
    if top in forbidden:
        return True
    return any(top.startswith(f + "_") for f in PREFIX_FAMILIES if f in forbidden)


def imported_modules(tree: ast.AST) -> list[tuple[int, str]]:
    """Every absolute module name imported anywhere in the file, with its line."""
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.append((node.lineno, node.module))
    return found


def find_violations(root: pathlib.Path) -> tuple[list[Violation], list[str]]:
    violations: list[Violation] = []
    errors: list[str] = []
    for package, forbidden in RULES.items():
        base = root / package
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            if SKIP_DIRS.intersection(path.parts):
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except (SyntaxError, UnicodeDecodeError) as exc:
                errors.append(f"{path.relative_to(root)}: cannot parse ({exc})")
                continue
            for lineno, module in imported_modules(tree):
                if _is_forbidden(module, forbidden):
                    violations.append((path.relative_to(root), lineno, module, package))
    return violations, errors


def main(argv: list[str]) -> int:
    root = pathlib.Path(argv[1]).resolve() if len(argv) > 1 else DEFAULT_ROOT
    violations, errors = find_violations(root)

    for err in errors:
        print(f"! {err}")
    if errors:
        return 2

    if not violations:
        print("OK  import boundaries: app -/-> dashboard, dashboard -/-> app, "
              "shared -/-> app, dashboard, fastapi, starlette, flask")
        return 0

    print("FAIL  import boundary violations:")
    print()
    for path, lineno, module, package in violations:
        print(f"  {path}:{lineno}  {package}/ imports '{module}'")
    print()
    print("app/ and dashboard/ are peers: neither may import the other.")
    print("shared/ is used by both: it may not import either app, or FastAPI/Flask.")
    print("Move the code both need into shared/, without the framework parts.")
    print("Reasoning: docs/adr/0009-shared-code.md and CLAUDE.md rule 1.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
